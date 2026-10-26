"""Bounded local masked reconstruction, with no semantic or temporal labels.

This small network learns only from explicitly admitted SSL_TRAIN patches. It
is an experimental domain model trained from scratch, not DINO training or an
adaptation of the independently frozen ImageNet backbone. No model is downloaded.
"""

from __future__ import annotations

import hashlib
import importlib
import io
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from .development_learning_dataset import FrameRecord, Use, validate_dataset, validate_use
from .development_marker_features import Array, _digest, _patches


@dataclass(frozen=True)
class MaskedTrainingBudget:
    seed: int = 270027
    maximum_images: int = 3072
    epochs: int = 12
    steps: int = 600
    seconds: int = 600
    batch_size: int = 64

    def validate(self) -> None:
        if (any(type(v) is not int for v in asdict(self).values())
                or not 0 <= self.seed < 2**31 or not 16 <= self.maximum_images <= 4096
                or not 1 <= self.epochs <= 20 or not 1 <= self.steps <= 1000
                or not 1 <= self.seconds <= 1200 or not 1 <= self.batch_size <= 128):
            raise ValueError("Explicit bounded local training budget required")


def _network(torch: Any) -> tuple[Any, Any]:
    nn = torch.nn
    encoder = nn.Sequential(nn.Conv2d(3, 16, 3, 2, 1), nn.ReLU(),
                            nn.Conv2d(16, 32, 3, 2, 1), nn.ReLU(),
                            nn.Conv2d(32, 48, 3, 2, 1), nn.ReLU())
    decoder = nn.Sequential(nn.Upsample(scale_factor=2, mode="nearest"),
                            nn.Conv2d(48, 32, 3, 1, 1), nn.ReLU(),
                            nn.Upsample(scale_factor=2, mode="nearest"),
                            nn.Conv2d(32, 16, 3, 1, 1), nn.ReLU(),
                            nn.Upsample(scale_factor=2, mode="nearest"),
                            nn.Conv2d(16, 3, 3, 1, 1), nn.Sigmoid())
    return encoder, decoder


def _tensor(torch: Any, patches: list[Array]) -> Any:
    images = np.stack([cv2.resize(p[:, :, ::-1], (32, 32), interpolation=cv2.INTER_AREA)
                       for p in patches])
    return torch.from_numpy(images.copy()).permute(0, 3, 1, 2).float()/255


def train_masked_encoder(
    patches: list[Array], frames: list[FrameRecord], patch_hashes: list[str], *,
    budget: MaskedTrainingBudget, output: Path,
) -> dict[str, Any]:
    """Train once; labels, pseudo labels and camera/actor identities are absent.

    The caller binds each patch to its admitted native frame and actual ROI.
    Immutable patch hashes detect changes after that acquisition boundary. The
    split contract forbids validation/frozen frames even for this unlabeled loss.
    """
    budget.validate()
    if (not 16 <= len(patches) <= budget.maximum_images or len(frames) != len(patches)
            or len(patch_hashes) != len(patches) or output.exists()):
        raise ValueError("Bounded one-to-one patches/frames/hashes and new output required")
    for start in range(0, len(patches), 256):
        _patches(patches[start:start+256])
    validate_dataset(frames)
    for frame, patch, expected in zip(frames, patches, patch_hashes, strict=True):
        validate_use(frame, Use.SSL)
        if hashlib.sha256(patch.tobytes()).hexdigest() != expected:
            raise ValueError("Acquired training patch changed")
    torch = importlib.import_module("torch")
    if torch.get_num_threads() != 1:
        raise ValueError("Training requires explicit one-thread CPU control")
    started = time.perf_counter()
    # fork_rng preserves the caller's random stream; all tensors remain on CPU.
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(budget.seed)
        encoder, decoder = _network(torch)
        optimizer = torch.optim.Adam(
            list(encoder.parameters())+list(decoder.parameters()), lr=.001)
        clean = _tensor(torch, patches)
        losses, steps, completed_epochs = [], 0, 0
        stop = "epoch_budget"
        for _epoch in range(budget.epochs):
            order = torch.randperm(len(clean))
            epoch_losses = []
            for start in range(0, len(order), budget.batch_size):
                if steps >= budget.steps or time.perf_counter()-started >= budget.seconds:
                    stop = "step_budget" if steps >= budget.steps else "time_budget"
                    break
                target = clean[order[start:start+budget.batch_size]]
                mask = torch.rand((len(target), 1, 8, 8)) < .25
                mask = mask.repeat_interleave(4, 2).repeat_interleave(4, 3)
                corrupted = torch.where(mask, torch.full_like(target, .5), target)
                prediction = decoder(encoder(corrupted))
                # Optimize only masked native content, not predicted semantic classes.
                squared = (prediction-target).square()*mask
                loss = squared.sum()/(mask.sum().clamp_min(1)*3)
                if not torch.isfinite(loss):
                    raise ValueError("Nonfinite self-supervised loss")
                optimizer.zero_grad(set_to_none=True)
                loss.backward()
                optimizer.step()
                epoch_losses.append(float(loss.detach()))
                steps += 1
            if epoch_losses:
                losses.append(float(np.mean(epoch_losses)))
            if stop != "epoch_budget":
                break
            completed_epochs += 1
        if not steps:
            raise ValueError("Training budget expired before a completed update")
        encoder.eval()
        # Tensor-only state_dict; loading always uses weights_only=True.
        buffer = io.BytesIO()
        torch.save(encoder.state_dict(), buffer)
        content = buffer.getvalue()
    for patch, expected in zip(patches, patch_hashes, strict=True):
        if hashlib.sha256(patch.tobytes()).hexdigest() != expected:
            raise ValueError("Training patch changed during fit")
    with output.open("xb") as stream:
        stream.write(content)
    return {"method": "masked_patch_encoder32_v1", "images": len(patches),
            "physical_groups": len({f.leakage_group_id for f in frames}),
            "budget": asdict(budget), "completed_epochs": completed_epochs, "steps": steps,
            "stop_reason": stop, "epoch_masked_mse": losses,
            "training_sec": time.perf_counter()-started, "model_bytes": len(content),
            "model_sha256": hashlib.sha256(content).hexdigest(),
            "dataset_fingerprint": _digest([asdict(f) for f in frames]),
            "patch_fingerprint": _digest(patch_hashes), "torch": torch.__version__,
            "ownership": "UNKNOWN", "qualification": "development_only", "formal_events": [],
            "formal_outputs": 0}


class MaskedEncoderFeatures:
    """CPU inference using one explicit immutable local domain-model snapshot."""

    def __init__(self, path: Path, expected_sha256: str) -> None:
        self.path, self.expected_sha256 = path, expected_sha256
        content = self._bytes()
        self.torch = importlib.import_module("torch")
        self.encoder, _ = _network(self.torch)
        state = self.torch.load(io.BytesIO(content), map_location="cpu", weights_only=True)
        self.encoder.load_state_dict(state, strict=True)
        self.encoder.eval().requires_grad_(False)
        self.fingerprint = _digest({"method": "masked_patch_encoder32_v1",
                                    "model_sha256": expected_sha256,
                                    "torch": self.torch.__version__,
                                    "preprocessing": "BGR_RGB_area32_0to1_pool2x2"})
        self._bytes()

    def _bytes(self) -> bytes:
        if (not self.path.is_file() or self.path.stat().st_size > 1024**2
                or not isinstance(self.expected_sha256, str) or len(self.expected_sha256) != 64):
            raise ValueError("Explicit bounded encoder snapshot and SHA required")
        content = self.path.read_bytes()
        if hashlib.sha256(content).hexdigest() != self.expected_sha256:
            raise ValueError("Self-supervised encoder changed")
        return content

    def extract(self, patches: list[Array]) -> Array:
        _patches(patches)
        self._bytes()
        rows = []
        with self.torch.inference_mode():
            for start in range(0, len(patches), 64):
                features = self.encoder(_tensor(self.torch, patches[start:start+64]))
                pooled = self.torch.nn.functional.adaptive_avg_pool2d(features, 2)
                rows.append(pooled.flatten(1).numpy().copy())
        self._bytes()
        result = np.concatenate(rows).astype(np.float32)
        if not np.isfinite(result).all():
            raise ValueError("Nonfinite domain appearance features")
        return result
