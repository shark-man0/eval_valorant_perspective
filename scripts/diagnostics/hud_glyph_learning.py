"""Opt-in spatial Score feature experiments; no source decoder or event writer."""
from __future__ import annotations

import math
import re
import time
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from scripts.diagnostics.hud_feature_contract import file_hash, verify_weights
from scripts.diagnostics.hud_feature_learning import _torch, image_tensor
from scripts.temporal_gt.contract import canonical_hash


@dataclass(frozen=True)
class StructureConfig:
    height: int = 64
    width: int = 96
    pooling: str = "avg"
    grid: tuple[int, int] = (2, 4)
    shallow: bool = False

    def __post_init__(self) -> None:
        if (type(self.height) is not int or type(self.width) is not int
                or not 32 <= self.height <= 128 or not 48 <= self.width <= 192
                or self.pooling not in {"avg", "max", "none"}
                or self.grid not in {(2, 4), (4, 8), (8, 12)}
                or type(self.shallow) is not bool
                or (self.pooling == "none") != self.shallow):
            raise ValueError("unsupported_bounded_structure_config")

    @property
    def fingerprint(self) -> str:
        return canonical_hash(asdict(self))


def structure_encoder(config: StructureConfig) -> Any:
    nn = _torch().nn
    layers = []
    channels = (16, 24) if config.shallow else (16, 32, 48)
    previous = 3
    for channel in channels:
        layers += [nn.Conv2d(previous, channel, 3, padding=1), nn.GELU()]
        if config.pooling != "none":
            layers.append(nn.AvgPool2d(2) if config.pooling == "avg" else nn.MaxPool2d(2))
        previous = channel
    # Output pooling stays Avg across Avg/Max intermediate-pool ablations.
    layers += [nn.AdaptiveAvgPool2d(config.grid), nn.Flatten(),
               nn.Linear(previous*config.grid[0]*config.grid[1], 96)]
    return nn.Sequential(*layers)


def fit_structure_ssl(images: Sequence[NDArray[np.uint8]], config: StructureConfig, *,
                      seed: int, steps: int, batch_size: int, max_seconds: float,
                      output: Path) -> dict[str, Any]:
    if (len(images) < 2 or type(steps) is not int or steps < 1
            or type(batch_size) is not int or batch_size < 2
            or not isinstance(max_seconds, (int, float)) or isinstance(max_seconds, bool)
            or not math.isfinite(max_seconds) or max_seconds <= 0 or output.exists()):
        raise ValueError("invalid_structure_training_budget")
    torch = _torch()
    torch.set_num_threads(4)
    torch.manual_seed(seed)
    torch.use_deterministic_algorithms(True)
    model = structure_encoder(config)
    torch.manual_seed(seed+1)  # same projection initialisation across grid dimensions
    projector = torch.nn.Sequential(torch.nn.GELU(), torch.nn.Linear(96, 64))
    optimizer = torch.optim.AdamW(list(model.parameters())+list(projector.parameters()), lr=.001)
    inputs = image_tensor(images, height=config.height, width=config.width)
    sampler = torch.Generator().manual_seed(seed)
    losses = []
    start = time.perf_counter()
    for step in range(steps):
        if time.perf_counter()-start >= max_seconds:
            break
        batch = inputs[torch.randperm(len(inputs), generator=sampler)[:batch_size]]
        views = []
        for view in range(2):
            # Sampling and photometric factors do not drift when resolution changes.
            rng = torch.Generator().manual_seed(seed*10000+step*2+view)
            gain = .92+.16*torch.rand((len(batch), 1, 1, 1), generator=rng)
            offset = (torch.rand((len(batch), 1, 1, 1), generator=rng)-.5)*.06
            noise = torch.randn(batch.shape, generator=rng)*.01
            views.append((batch*gain+offset+noise).clamp(0, 1))
        z = torch.nn.functional.normalize(projector(model(torch.cat(views))), dim=1)
        count = len(batch)
        similarity = z@z.T/.2
        similarity.fill_diagonal_(-1e9)
        loss = torch.nn.functional.cross_entropy(similarity,
                                                (torch.arange(2*count)+count) % (2*count))
        if not bool(torch.isfinite(loss)):
            raise ValueError("nonfinite_structure_loss")
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        losses.append(float(loss.detach()))
    if not losses:
        raise ValueError("no_structure_training_steps")
    with output.open("xb") as stream:
        torch.save(model.state_dict(), stream)
    output.chmod(0o600)
    return {"kind": "same_image_structure_SSL", "config": asdict(config),
            "config_sha256": config.fingerprint, "weights_sha256": file_hash(output),
            "weights_bytes": output.stat().st_size,
            "parameters": sum(p.numel() for p in model.parameters()),
            "steps": len(losses), "seed": seed, "seconds": time.perf_counter()-start,
            "loss_first": losses[0], "loss_last": losses[-1], "Human_labels_used": 0}


def load_structure(weights: Path, expected_hash: str, config: StructureConfig, *,
                   expected_config_hash: str) -> Any:
    if config.fingerprint != expected_config_hash:
        raise ValueError("structure_config_mismatch")
    verify_weights(weights, expected_hash, max_bytes=25*1024**2)
    model = structure_encoder(config)
    state = _torch().load(weights, map_location="cpu", weights_only=True)
    model.load_state_dict(state, strict=True)
    model.eval()
    return model


def structure_features(model: Any, images: Sequence[NDArray[np.uint8]],
                       config: StructureConfig) -> NDArray[np.float32]:
    torch = _torch()
    torch.set_num_threads(4)
    if not images:
        raise ValueError("empty_structure_inputs")
    arrays = []
    with torch.inference_mode():
        for start in range(0, len(images), 32):
            x = image_tensor(images[start:start+32], height=config.height, width=config.width)
            arrays.append(torch.nn.functional.normalize(model(x), dim=1).cpu().numpy())
    return np.asarray(np.concatenate(arrays), dtype=np.float32)


def score_digits(text: str) -> tuple[int, ...]:
    if not isinstance(text, str) or re.fullmatch(r"(?:0|[1-9][0-9]?)", text) is None:
        raise ValueError("canonical_visible_score_required")
    return tuple(map(int, text))


def fit_slot_readout(features: NDArray[np.float32], scores: Sequence[str], *,
                     physical_groups: Sequence[str], forbidden_groups: set[str],
                     alpha: float = 1.) -> dict[str, Any]:
    """Human-supervised ridge heads, separate from image-only SSL fitting.

    Original Score strings supervise length and left-to-right digit slots; no
    connected-component proposal or reconstructed glyph becomes a Human label.
    All ten columns compete. Unsupported predicted classes withhold output.
    """
    if (features.ndim != 2 or len(features) != len(scores) or not len(scores)
            or len(physical_groups) != len(scores) or not np.isfinite(features).all()
            or not math.isfinite(alpha) or alpha <= 0
            or not all(isinstance(g, str) and g for g in physical_groups)
            or set(physical_groups) & forbidden_groups):
        raise ValueError("invalid_or_leaked_readout_fit")
    digits = [score_digits(s) for s in scores]
    mean, std = features.mean(axis=0), np.maximum(features.std(axis=0), .0001)
    x = np.column_stack(((features-mean)/std, np.ones(len(features))))

    def ridge(indices: list[int], labels: list[int], classes: int) -> dict[str, Any] | None:
        if not indices:
            return None
        a = x[indices]
        target = np.eye(classes)[labels]
        weights = a.T @ np.linalg.solve(a@a.T+alpha*np.eye(len(a)), target)
        return {"weights": weights.tolist(), "seen": sorted(set(labels))}

    return {"kind": "Human_supervised_score_slot_ridge", "mean": mean.tolist(),
            "std": std.tolist(), "alpha": alpha, "fit_groups": sorted(set(physical_groups)),
            "length": ridge(list(range(len(digits))), [len(d)-1 for d in digits], 2),
            "first": ridge(list(range(len(digits))), [d[0] for d in digits], 10),
            "second": ridge([i for i,d in enumerate(digits) if len(d) == 2],
                            [d[1] for d in digits if len(d) == 2], 10),
            "semantic_qualified": False}


def slot_candidates(readout: dict[str, Any], features: NDArray[np.float32]) -> list[str | None]:
    mean, std = np.asarray(readout["mean"]), np.asarray(readout["std"])
    if (features.ndim != 2 or features.shape[1:] != mean.shape
            or not np.isfinite(features).all() or std.shape != mean.shape or np.any(std <= 0)):
        raise ValueError("invalid_readout_features")
    x = np.column_stack(((features-mean)/std, np.ones(len(features))))

    def best(head: dict[str, Any] | None, row: NDArray[Any]) -> int | None:
        if head is None:
            return None
        value = int(np.argmax(row @ np.asarray(head["weights"])))
        return value if value in head["seen"] else None

    out = []
    for row in x:
        length, first = best(readout["length"], row), best(readout["first"], row)
        second = best(readout["second"], row) if length == 1 else None
        text = (str(first) if length == 0 and first is not None else
                f"{first}{second}" if length == 1 and first is not None and second is not None
                else None)
        out.append(text if text is not None
                   and re.fullmatch(r"(?:0|[1-9][0-9]?)", text) is not None else None)
    return out


def fit_supervised_structure(images: Sequence[NDArray[np.uint8]], scores: Sequence[str],
                             config: StructureConfig, *, physical_groups: Sequence[str],
                             forbidden_groups: set[str], label_kind: str, seed: int,
                             steps: int, max_seconds: float, output: Path) -> dict[str, Any]:
    """Small supervised CNN control, never described as image-only SSL."""
    if (label_kind not in {"HUMAN_CONFIRMED", "SYNTHETIC"} or len(images) != len(scores)
            or len(scores) != len(physical_groups) or not len(scores)
            or not all(isinstance(g, str) and g for g in physical_groups)
            or set(physical_groups) & forbidden_groups
            or type(steps) is not int or steps < 1
            or not isinstance(max_seconds, (int, float)) or isinstance(max_seconds, bool)
            or not math.isfinite(max_seconds) or max_seconds <= 0 or output.exists()):
        raise ValueError("invalid_or_leaked_supervised_fit")
    targets = [score_digits(s) for s in scores]
    torch = _torch()
    torch.set_num_threads(4)
    torch.manual_seed(seed)
    torch.use_deterministic_algorithms(True)
    model = torch.nn.Sequential(structure_encoder(config), torch.nn.GELU(), torch.nn.Linear(96, 22))
    inputs = image_tensor(images, height=config.height, width=config.width)
    lengths = torch.tensor([len(d)-1 for d in targets])
    first = torch.tensor([d[0] for d in targets])
    second = torch.tensor([d[1] if len(d) == 2 else 0 for d in targets])
    optimizer = torch.optim.AdamW(model.parameters(), lr=.001)
    sampler = torch.Generator().manual_seed(seed)
    start = time.perf_counter()
    losses = []
    for step in range(steps):
        if time.perf_counter()-start >= max_seconds:
            break
        indices = torch.randperm(len(inputs), generator=sampler)[:32]
        rng = torch.Generator().manual_seed(seed*10000+step)
        batch = inputs[indices]
        gain = .92+.16*torch.rand((len(batch), 1, 1, 1), generator=rng)
        offset = (torch.rand((len(batch), 1, 1, 1), generator=rng)-.5)*.06
        logits = model((batch*gain+offset).clamp(0, 1))
        loss = (torch.nn.functional.cross_entropy(logits[:, :2], lengths[indices])
                + torch.nn.functional.cross_entropy(logits[:, 2:12], first[indices]))
        mask = lengths[indices] == 1
        if bool(mask.any()):
            extra = torch.nn.functional.cross_entropy(logits[mask, 12:22], second[indices][mask])
            loss = loss+extra
        if not bool(torch.isfinite(loss)):
            raise ValueError("nonfinite_supervised_loss")
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        losses.append(float(loss.detach()))
    if not losses:
        raise ValueError("no_supervised_steps")
    with output.open("xb") as stream:
        torch.save(model.state_dict(), stream)
    output.chmod(0o600)
    return {"kind": "small_supervised_score_CNN", "config": asdict(config),
            "config_sha256": config.fingerprint, "label_kind": label_kind,
            "physical_fit_groups": sorted(set(physical_groups)),
            "seen_lengths": sorted({len(d)-1 for d in targets}),
            "seen_first": sorted({d[0] for d in targets}),
            "seen_second": sorted({d[1] for d in targets if len(d) == 2}),
            "weights_sha256": file_hash(output), "weights_bytes": output.stat().st_size,
            "parameters": sum(p.numel() for p in model.parameters()),
            "steps": len(losses), "seed": seed, "seconds": time.perf_counter()-start,
            "loss_first": losses[0], "loss_last": losses[-1]}


def supervised_candidates(weights: Path, receipt: dict[str, Any], config: StructureConfig,
                           images: Sequence[NDArray[np.uint8]]) -> list[str | None]:
    if receipt["config_sha256"] != config.fingerprint:
        raise ValueError("supervised_config_mismatch")
    verify_weights(weights, receipt["weights_sha256"], max_bytes=25*1024**2)
    torch = _torch()
    torch.set_num_threads(4)
    model = torch.nn.Sequential(structure_encoder(config), torch.nn.GELU(), torch.nn.Linear(96, 22))
    model.load_state_dict(torch.load(weights, map_location="cpu", weights_only=True), strict=True)
    model.eval()
    out = []
    with torch.inference_mode():
        for start in range(0, len(images), 32):
            logits = model(image_tensor(images[start:start+32],
                                        height=config.height, width=config.width))
            for row in logits:
                length = int(row[:2].argmax())
                first, second = int(row[2:12].argmax()), int(row[12:22].argmax())
                valid = (length in receipt["seen_lengths"] and first in receipt["seen_first"]
                         and (length == 0 or second in receipt["seen_second"]))
                text = str(first) if length == 0 else f"{first}{second}"
                out.append(text if valid and re.fullmatch(r"(?:0|[1-9][0-9]?)", text) else None)
    return out


def score_sequence_report(truth: Sequence[str | None], candidates: Sequence[str | None]
                          ) -> dict[str, Any]:
    """Conditional labelled-point metrics, not population precision or GT creation.

    Length mismatch has a separate confusion column: no guessed glyph alignment
    credits a surviving digit. Predictions on unlabelled inputs are not false
    positives. Pixel-level digit-box correctness is outside this transcription.
    """
    if len(truth) != len(candidates):
        raise ValueError("score_metric_lengths")
    matrix = np.zeros((10, 12), dtype=np.int64)
    unaligned_predictions = np.zeros(10, dtype=np.int64)
    support = np.zeros(10, dtype=np.int64)
    correct = wrong = unknown = drops = extra_digits = unlabelled_predictions = 0
    two_total = two_correct = 0
    for actual, proposed in zip(truth, candidates, strict=True):
        proposal = None if proposed is None else score_digits(proposed)
        if actual is None:
            unlabelled_predictions += proposed is not None
            continue
        target = score_digits(actual)
        two_total += len(target) == 2
        two_correct += len(target) == 2 and proposed == actual
        for digit in target:
            support[digit] += 1
        if proposal is None:
            unknown += 1
            for digit in target:
                matrix[digit, 10] += 1
        elif len(proposal) != len(target):
            wrong += 1
            drops += len(proposal) < len(target)
            extra_digits += len(proposal) > len(target)
            for digit in target:
                matrix[digit, 11] += 1
            for digit in proposal:
                unaligned_predictions[digit] += 1
        else:
            correct += proposed == actual
            wrong += proposed != actual
            for a, b in zip(target, proposal, strict=True):
                matrix[a, b] += 1
    digits = []
    for digit in range(10):
        tp = int(matrix[digit, digit])
        fp = int(matrix[:, digit].sum()-tp+unaligned_predictions[digit])
        recall = tp/int(support[digit]) if support[digit] else None
        digits.append({"digit": digit, "support": int(support[digit]), "correct": tp,
                       "FP": fp, "FN_including_unknown_and_length_error": int(support[digit])-tp,
                       "precision_on_labelled_points": tp/(tp+fp) if tp+fp else None,
                       "recall_on_labelled_points": recall})
    return {"labelled_scores": sum(t is not None for t in truth), "correct_complete": correct,
            "wrong_complete_candidate": wrong, "UNKNOWN": unknown, "digit_drop": drops,
            "one_to_two_digit_error": extra_digits, "two_digit_truth": two_total,
            "two_digit_correct": two_correct,
            "unlabelled_predictions_not_FP": unlabelled_predictions,
            "digits": digits, "confusion_columns": [str(i) for i in range(10)]
            + ["UNKNOWN", "LENGTH_ERROR"], "confusion": matrix.tolist(),
            "population_precision_recall": None}
