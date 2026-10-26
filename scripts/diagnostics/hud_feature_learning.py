"""Optional, local-only small feature models. Importing this module loads no weights.

Install pinned optional dependencies in an isolated research environment. Normal
application builds and contract CI need no torch, weights, or private imagery.
"""
from __future__ import annotations

import math
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from numpy.typing import NDArray

from scripts.diagnostics.hud_feature_contract import (
    file_hash,
    validate_split,
    verify_patch,
    verify_weights,
)


def _torch() -> Any:
    import importlib
    return importlib.import_module("torch")


def tiny_encoder() -> Any:
    nn = _torch().nn
    # Retain a spatial grid: global average pooling alone loses glyph layout.
    return nn.Sequential(
        nn.Conv2d(3, 16, 3, padding=1), nn.GELU(), nn.AvgPool2d(2),
        nn.Conv2d(16, 32, 3, padding=1), nn.GELU(), nn.AvgPool2d(2),
        nn.Conv2d(32, 48, 3, padding=1), nn.GELU(), nn.AvgPool2d(2),
        nn.AdaptiveAvgPool2d((2, 4)), nn.Flatten(), nn.Linear(384, 96))


def image_tensor(images: Sequence[NDArray[np.uint8]], *,
                 height: int = 64, width: int = 96) -> Any:
    """Letterbox complete ROIs. No glyph-removing crop, flip or spatial warp."""
    prepared = []
    for image in images:
        if (image.dtype != np.uint8 or image.ndim != 3 or image.shape[2] != 3
                or min(image.shape[:2]) < 2):
            raise ValueError("invalid_learning_image")
        h, w = image.shape[:2]
        scale = min(height/h, width/w)
        rw, rh = max(1, round(w*scale)), max(1, round(h*scale))
        resized = cv2.resize(image, (rw, rh), interpolation=cv2.INTER_AREA
                             if scale < 1 else cv2.INTER_LINEAR)
        canvas = np.zeros((height, width, 3), dtype=np.uint8)
        y, x = (height-rh)//2, (width-rw)//2
        canvas[y:y+rh, x:x+rw] = resized[:, :, ::-1]
        prepared.append(canvas.transpose(2, 0, 1))
    if not prepared:
        raise ValueError("empty_learning_images")
    return _torch().from_numpy(np.stack(prepared).astype(np.float32) / 255.)


def contrastive_fit(images: Sequence[NDArray[np.uint8]], *, seed: int,
                    steps: int, batch_size: int, max_seconds: float,
                    output: Path) -> dict[str, Any]:
    """Same-image photometric positives; adjacent frames are never positives.

    This learns an appearance representation, not semantic labels or a denoised
    evidence image. Repeated HUD states can be false negatives in this loss.
    """
    if (len(images) < 2 or type(steps) is not int or steps < 1
            or type(batch_size) is not int or batch_size < 2
            or not isinstance(max_seconds, (int, float)) or isinstance(max_seconds, bool)
            or not math.isfinite(max_seconds) or max_seconds <= 0
            or output.exists()):
        raise ValueError("invalid_learning_budget")
    torch = _torch()
    torch.manual_seed(seed)
    torch.set_num_threads(4)
    torch.use_deterministic_algorithms(True)
    inputs = image_tensor(images)
    model = tiny_encoder()
    projector = torch.nn.Sequential(torch.nn.GELU(), torch.nn.Linear(96, 64))
    optimizer = torch.optim.AdamW(list(model.parameters()) + list(projector.parameters()), lr=.001)
    generator = torch.Generator().manual_seed(seed)
    losses: list[float] = []
    started = time.perf_counter()
    for _ in range(steps):
        if time.perf_counter() - started >= max_seconds:
            break
        index = torch.randperm(len(inputs), generator=generator)[:batch_size]
        batch = inputs[index]
        views = []
        for _ in range(2):
            gain = .92 + .16*torch.rand((len(batch), 1, 1, 1), generator=generator)
            offset = (torch.rand((len(batch), 1, 1, 1), generator=generator)-.5)*.06
            noise = torch.randn(batch.shape, generator=generator)*.01
            views.append((batch*gain+offset+noise).clamp(0, 1))
        z = torch.nn.functional.normalize(projector(model(torch.cat(views))), dim=1)
        count = len(batch)
        logits = z @ z.T / .2
        logits.fill_diagonal_(-1e9)
        target = (torch.arange(2*count)+count) % (2*count)
        loss = torch.nn.functional.cross_entropy(logits, target)
        if not bool(torch.isfinite(loss)):
            raise ValueError("nonfinite_learning_loss")
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        losses.append(float(loss.detach()))
    if not losses:
        raise ValueError("no_learning_steps_completed")
    model.eval()
    # Only a state_dict, never a pickled custom model or a private input image.
    with output.open("xb") as stream:
        torch.save(model.state_dict(), stream)
    output.chmod(0o600)
    return {"kind": "same_image_contrastive_CNN_v1", "seed": seed,
            "steps_completed": len(losses), "loss_first": losses[0], "loss_last": losses[-1],
            "training_seconds": time.perf_counter()-started,
            "parameters": sum(p.numel() for p in model.parameters()),
            "weights_sha256": file_hash(output), "weights_bytes": output.stat().st_size,
            "semantic_labels_used": 0, "formal_events": []}


def fit_verified_dataset(records: Sequence[dict[str, Any]], *,
                         allowed_development: dict[str, str], profile_sha256: str,
                         source_ids: set[str], seed: int, steps: int, batch_size: int,
                         max_seconds: float, output: Path) -> dict[str, Any]:
    """Admission-aware fitting entry point; frozen/test rows never reach torch.

    The allowlist is a separate trusted registry receipt. It cannot be derived
    from the supplied patch records. Metadata is validated but is not a neural
    feature. Only original decoded local patch pixels enter the encoder.
    """
    dataset_hash = validate_split(records, allowed_development=allowed_development)
    selected = [r for r in records if r["frame"]["source_id"] in source_ids
                and r.get("spatial_training_sample") is True]
    if (not source_ids or not selected
            or {r["frame"]["source_id"] for r in selected} != source_ids
            or any(r["role"] != "SSL_TRAIN" or r.get("label_kind") != "UNLABELLED"
                   or r.get("label") is not None for r in selected)):
        raise ValueError("ssl_training_role_or_label_violation")
    unique: dict[str, dict[str, Any]] = {}
    for row in selected:
        unique.setdefault(row["patch_pixel_sha256"], row)
    images = [verify_patch(r, profile_sha256=profile_sha256) for r in unique.values()]
    fitted = contrastive_fit(images, seed=seed, steps=steps, batch_size=batch_size,
                            max_seconds=max_seconds, output=output)
    return {**fitted, "dataset_sha256": dataset_hash,
            "training_physical_matches": sorted({r["physical_match_id"] for r in selected}),
            "training_images": len(images), "raw_training_images": len(selected),
            "duplicate_patch_pixels_removed": len(selected)-len(images),
            "profile_sha256": profile_sha256}


def load_encoder(weights: Path, expected_hash: str, *,
                 maximum_bytes: int = 25*1024**2) -> Any:
    verify_weights(weights, expected_hash, max_bytes=maximum_bytes)
    torch = _torch()
    model = tiny_encoder()
    model.load_state_dict(torch.load(weights, map_location="cpu", weights_only=True), strict=True)
    model.eval()
    return model


def extract(model: Any, images: Sequence[NDArray[np.uint8]], *,
            generic_imagenet: bool = False, batch_size: int = 32
            ) -> NDArray[np.float32]:
    torch = _torch()
    if batch_size < 1 or not images:
        raise ValueError("invalid_feature_batch")
    torch.set_num_threads(4)
    values = []
    with torch.inference_mode():
        for start in range(0, len(images), batch_size):
            x = image_tensor(images[start:start+batch_size],
                             height=224 if generic_imagenet else 64,
                             width=224 if generic_imagenet else 96)
            if generic_imagenet:
                mean = torch.tensor([.485, .456, .406]).view(1, 3, 1, 1)
                std = torch.tensor([.229, .224, .225]).view(1, 3, 1, 1)
                x = (x-mean)/std
            z = model(x).flatten(1)
            z = torch.nn.functional.normalize(z, dim=1)
            values.append(z.cpu().numpy().astype(np.float32))
    return np.concatenate(values, axis=0)


def generic_encoder(weights: Path, expected_hash: str) -> Any:
    """Explicit local ImageNet baseline. No implicit network downloads."""
    import importlib
    verify_weights(weights, expected_hash, max_bytes=25*1024**2)
    torch = _torch()
    vision = importlib.import_module("torchvision.models")
    model = vision.mobilenet_v3_small(weights=None)
    model.load_state_dict(torch.load(weights, map_location="cpu", weights_only=True), strict=True)
    model.classifier = torch.nn.Identity()
    model.eval()
    return model
