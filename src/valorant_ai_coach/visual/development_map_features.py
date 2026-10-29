"""Native Map appearance features; no life, camera or Round state inference."""

from __future__ import annotations

from typing import Any

import cv2
import numpy as np

from .development_marker_features import Array, _digest, bound_patches
from .development_marker_topk import _native

OWNER_TRACK_FEATURE_FINGERPRINT = _digest(
    {
        "feature": "native_circle7_mean_centered_BGR_gaussian5_sigma1.2",
        "opencv": cv2.__version__,
        "numpy": np.__version__,
        "gap": 0.3,
        "reappearance_gap": 0.6,
        "cosine": 0.90,
        "distance": 12,
        "margin": 0.10,
    }
)


def owner_tracking_features(frame: Array, sample: dict[str, Any], pool: dict[str, Any]) -> Array:
    """Translation-tolerant native appearance, without adding/changing centers."""
    _native(frame, sample)
    n = pool["parent_count"]
    if type(n) is not int or not 0 <= n <= 128 or n > len(pool["candidates"]):
        raise ValueError("Bounded parent candidates required")
    if not n:
        return np.empty((0, 447), dtype=np.float64)
    patches, _ = bound_patches(
        frame, sample, [p["center_frame_px"] for p in pool["candidates"][:n]], radius=17
    )
    yy, xx = np.mgrid[-17:18, -17:18]
    mask = xx * xx + yy * yy <= 49
    features = np.array(
        [cv2.GaussianBlur(p, (5, 5), 1.2)[mask].astype(float).ravel() for p in patches]
    )
    features -= features.mean(axis=1, keepdims=True)
    return features
