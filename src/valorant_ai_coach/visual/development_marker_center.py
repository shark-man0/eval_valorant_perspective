"""Opt-in center/annulus features and small train-only development readouts.

Position support, appearance semantics and recorder ownership are independent.
Offset supervision describes an uncertain annotation-relative pretext, never a
true center or a background label. No default detector imports this module.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import asdict
from typing import Any

import cv2
import numpy as np

from .development_learning_dataset import (
    FrameLabel,
    FrameRecord,
    Use,
    validate_dataset,
    validate_use,
)
from .development_marker_features import CLASSES, Array, _digest, _patches

CENTER_FEATURE_FINGERPRINT = _digest(
    {
        "method": "native_center_annulus_v1",
        "shape": [25, 25],
        "opencv": cv2.__version__,
        "numpy": np.__version__,
        "radii": [5, 6, 7, 8, 9, 10, 11],
        "angles": 32,
        "regions": [4, 8, 12],
        "pretext_uncertainty_px": 2,
    }
)


def _ring(gx: Array, gy: Array, ox: float, oy: float, radius: float) -> float:
    angles = np.arange(32, dtype=np.float32) * np.float32(2 * np.pi / 32)
    dx, dy = np.cos(angles), np.sin(angles)
    xx = (12 + ox + radius * dx).reshape(1, -1).astype(np.float32)
    yy = (12 + oy + radius * dy).reshape(1, -1).astype(np.float32)
    ax = cv2.remap(gx, xx, yy, cv2.INTER_LINEAR)[0]
    ay = cv2.remap(gy, xx, yy, cv2.INTER_LINEAR)[0]
    radial = np.abs(ax * dx + ay * dy)
    magnitude = np.hypot(ax, ay)
    # Coverage across opposing arcs, not just one straight map edge.
    sectors = radial.reshape(8, 4).mean(axis=1)
    alignment = float(radial.sum() / (magnitude.sum() + 1e-6))
    coverage = float(np.quantile(sectors, 0.25) / (sectors.mean() + 1e-6))
    return alignment * coverage * min(1.0, float(magnitude.mean()) / 0.2)


def center_features(patches: list[Array]) -> Array:
    """Native 25px center, rim and background measurements, no fitted inputs."""
    _patches(patches)
    if any(p.shape != (25, 25, 3) for p in patches):
        raise ValueError("Complete native 25px patches required")
    yy, xx = np.mgrid[-12:13, -12:13]
    radius = np.hypot(xx, yy)
    masks = [radius <= 4, (radius > 4) & (radius <= 8), (radius > 8) & (radius <= 12)]
    diagonal = (np.abs(np.abs(xx) - np.abs(yy)) <= 1) & (radius >= 3) & (radius <= 9)
    axes = ((np.abs(xx) <= 1) | (np.abs(yy) <= 1)) & (radius >= 3) & (radius <= 9)
    results = []
    for patch in patches:
        pixels = patch.astype(np.float32) / 255
        gray = cv2.cvtColor(pixels, cv2.COLOR_BGR2GRAY)
        gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
        ring = [_ring(gx, gy, 0, 0, r) for r in range(5, 12)]
        center = max(ring[:5])
        alternatives = [
            max(_ring(gx, gy, x, y, r) for r in (5, 7, 9))
            for x, y in [(-2, 0), (2, 0), (0, -2), (0, 2)]
        ]
        hsv = cv2.cvtColor(patch, cv2.COLOR_BGR2HSV)
        chroma = ((hsv[:, :, 1] >= 80) & (hsv[:, :, 2] >= 50)).astype(np.float32)
        cross = float(chroma[diagonal].mean() - chroma[axes].mean())
        means = [pixels[m].mean(axis=0) for m in masks]
        stats = []
        for mask in masks:
            stats.extend(pixels[mask].mean(axis=0).tolist())
            stats.extend(pixels[mask].std(axis=0).tolist())
            stats.extend([float(np.hypot(gx, gy)[mask].mean()), float(chroma[mask].mean())])
        contrast = [
            float(np.linalg.norm(a - b))
            for a, b in [(means[0], means[1]), (means[0], means[2]), (means[1], means[2])]
        ]
        results.append(
            [max(ring), cross, center - max(alternatives), *ring, *alternatives, *stats, *contrast]
        )
    return np.asarray(results, dtype=np.float64)


def center_rule(features: Array) -> Array:
    if (
        not isinstance(features, np.ndarray)
        or features.ndim != 2
        or features.shape[1] != 41
        or not np.isfinite(features).all()
    ):
        raise ValueError("Finite native center feature matrix required")
    return features[:, 0] + np.maximum(features[:, 1], 0) + 0.5 * features[:, 2]


class CenterReadout:
    """Bounded ridge readout; outputs are uncalibrated development scores."""

    def __init__(
        self,
        mean: Array,
        scale: Array,
        weights: Array,
        *,
        feature_fingerprint: str,
        mode: str,
        training_fingerprint: str,
    ) -> None:
        if (
            mode not in {"weak_center", "human_semantics"}
            or not isinstance(mean, np.ndarray)
            or mean.ndim != 1
            or not 1 <= len(mean) <= 512
            or scale.shape != mean.shape
            or weights.shape != (len(mean) + 1, 1 if mode == "weak_center" else 4)
            or not all(np.isfinite(a).all() for a in (mean, scale, weights))
            or (scale <= 0).any()
            or any(
                not isinstance(s, str) or len(s) != 64
                for s in (feature_fingerprint, training_fingerprint)
            )
        ):
            raise ValueError("Bounded fitted development readout required")
        self.mean, self.scale, self.weights = [
            a.astype(np.float64, copy=True) for a in (mean, scale, weights)
        ]
        for array in (self.mean, self.scale, self.weights):
            array.setflags(write=False)
        self.feature_fingerprint, self.mode = feature_fingerprint, mode
        self.training_fingerprint = training_fingerprint
        self.fingerprint = _digest(
            {
                "mean": self.mean.tolist(),
                "scale": self.scale.tolist(),
                "weights": self.weights.tolist(),
                "mode": mode,
                "feature_fingerprint": feature_fingerprint,
                "training_fingerprint": training_fingerprint,
            }
        )

    def scores(self, features: Array, *, feature_fingerprint: str) -> Array:
        if (
            feature_fingerprint != self.feature_fingerprint
            or not isinstance(features, np.ndarray)
            or features.ndim != 2
            or not 1 <= len(features) <= 512
            or features.shape[1] != len(self.mean)
            or not np.isfinite(features).all()
        ):
            raise ValueError("Matching finite current feature matrix required")
        scaled = np.clip((features - self.mean) / self.scale, -8, 8)
        return np.column_stack([scaled, np.ones(len(features))]) @ self.weights


def fit_center_readout(
    features: Array,
    frames: list[FrameRecord],
    labels: list[FrameLabel],
    *,
    feature_fingerprint: str,
    offsets_px: list[tuple[float, float]] | None = None,
) -> tuple[CenterReadout, dict[str, Any]]:
    """HUMAN TRAIN semantics or explicitly weak annotation-relative offsets.

    Frame/label bindings describe the original reviewed patch. Offset crops must
    be acquired by the caller from that same native frame; their hashes belong
    in its receipt. They never acquire the original human semantic label.
    """
    if (
        not isinstance(features, np.ndarray)
        or features.ndim != 2
        or not 2 <= len(features) <= 512
        or not 1 <= features.shape[1] <= 512
        or len(frames) != len(features)
        or len(labels) != len(features)
        or not np.isfinite(features).all()
    ):
        raise ValueError("Bounded paired TRAIN examples required")
    # Repeated weak-offset examples reference the same immutable human record;
    # they must not masquerade as multiple authored labels for that ROI.
    validate_dataset(frames, list(dict.fromkeys(labels)) if offsets_px is not None else labels)
    for frame, label in zip(frames, labels, strict=True):
        validate_use(frame, Use.SUPERVISED_TRAIN, label, dataset_frames=frames)
    mode = "human_semantics" if offsets_px is None else "weak_center"
    if offsets_px is None:
        if {label.label.value for label in labels} != set(CLASSES):
            raise ValueError("Human TRAIN support for every semantic class required")
        targets = np.asarray(
            [[float(label.label.value == name) for name in CLASSES] for label in labels]
        )
        counts = {name: sum(label.label.value == name for label in labels) for name in CLASSES}
        sample_weights = np.asarray([1 / counts[label.label.value] for label in labels])
    else:
        if (
            len(offsets_px) != len(features)
            or any(label.label.value not in {"PLAYER", "DEATH_MARKER"} for label in labels)
            or any(
                len(p) != 2
                or any(type(v) not in (int, float) or not math.isfinite(v) or abs(v) > 8 for v in p)
                for p in offsets_px
            )
        ):
            raise ValueError("Weak offsets from positive TRAIN references required")
        targets = np.asarray(
            [[math.exp(-(max(0.0, math.hypot(*p) - 2) ** 2) / 8)] for p in offsets_px]
        )
        sample_weights = np.ones(len(features))
    mean = features.mean(axis=0)
    scale = np.maximum(features.std(axis=0), 0.02)
    design = np.column_stack([np.clip((features - mean) / scale, -8, 8), np.ones(len(features))])
    weighted = design * sample_weights[:, None]
    penalty = np.eye(design.shape[1])
    penalty[-1, -1] = 1e-6
    weights = np.linalg.solve(design.T @ weighted + penalty, weighted.T @ targets)
    receipt = {
        "method": "center_ridge_v1",
        "mode": mode,
        "ridge": 1.0,
        "examples": len(features),
        "frames": [asdict(f) for f in frames],
        "unique_human_references": len(set(labels)),
        "human_reference_labels": [asdict(label) for label in labels],
        "offsets_px": offsets_px,
        "offset_origin": (
            "weak_uncertain_annotation_relative_pretext" if offsets_px is not None else None
        ),
        "true_center_GT": False,
        "shifted_is_background": False,
        "feature_fingerprint": feature_fingerprint,
        "features_sha256": hashlib.sha256(features.tobytes()).hexdigest(),
        "ownership": "UNKNOWN",
        "formal_outputs": 0,
    }
    model = CenterReadout(
        mean,
        scale,
        weights,
        feature_fingerprint=feature_fingerprint,
        mode=mode,
        training_fingerprint=_digest(receipt),
    )
    return model, receipt
