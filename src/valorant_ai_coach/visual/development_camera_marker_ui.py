"""Measure highlighted-marker rim geometry, not recorder ownership.

The same UI can occur on a spectated player. This selector only ranks existing
native windows and supplies a source-bound UI hypothesis. Independent camera /
recorder evidence is still required before an owner binding can be proposed.
"""

from __future__ import annotations

import math
from typing import Any

import cv2
import numpy as np

from .development_marker_features import Array, _digest, bound_patches
from .development_marker_topk import _native

UI_FINGERPRINT = _digest(
    {
        "method": "highlighted_marker_rim_geometry_v2",
        "opencv": cv2.__version__,
        "numpy": np.__version__,
        "radius": [8, 9, 10, 11, 12],
        "angles": 64,
        "pale": [210, 70],
        "warm_hue": [15, 40],
        "warm_saturation": [60, 230],
        "minimum_warm_arc": 0.15,
        "minimum_alignment": 0.55,
        "minimum_margin": 0.12,
        "role": "highlighted_marker_only_not_recorder",
    }
)


def _rim(patch: Array) -> dict[str, float]:
    gray = cv2.cvtColor(patch, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1)
    hsv = cv2.cvtColor(patch, cv2.COLOR_BGR2HSV)
    pale = (hsv[:, :, 2] >= 210) & (hsv[:, :, 1] <= 70)
    warm = (
        (hsv[:, :, 0] >= 15)
        & (hsv[:, :, 0] <= 40)
        & (hsv[:, :, 1] >= 60)
        & (hsv[:, :, 1] <= 230)
        & (hsv[:, :, 2] >= 150)
    )
    mask = (pale | warm).astype(np.float32)
    angle = np.arange(64, dtype=np.float32) * np.float32(2 * np.pi / 64)
    dx, dy = np.cos(angle), np.sin(angle)
    support, alignment, warm_support = [], [], []
    for radius in [8, 9, 10, 11, 12]:
        xx = (17 + radius * dx).reshape(1, -1).astype(np.float32)
        yy = (17 + radius * dy).reshape(1, -1).astype(np.float32)
        ax = cv2.remap(gx, xx, yy, cv2.INTER_LINEAR)[0]
        ay = cv2.remap(gy, xx, yy, cv2.INTER_LINEAR)[0]
        color = cv2.remap(mask, xx, yy, cv2.INTER_LINEAR)[0]
        warm_color = cv2.remap(warm.astype(np.float32), xx, yy, cv2.INTER_LINEAR)[0]
        magnitude = np.hypot(ax, ay)
        radial = np.abs(ax * dx + ay * dy) / np.maximum(magnitude, 1e-6)
        support.append(color * np.minimum(magnitude / 0.3, 1))
        warm_support.append(warm_color * np.minimum(magnitude / 0.3, 1))
        alignment.append(radial)
    best = np.argmax(support, axis=0)
    rim = np.max(support, axis=0)
    arc = float((rim >= 0.5).mean())
    aligned = np.array(alignment)[best, np.arange(64)]
    radial = float(np.average(aligned, weights=rim + 1e-6))
    sectors = rim.reshape(8, 8).mean(axis=1)
    distributed = float(np.quantile(sectors, 0.25))
    warm_arc = float((np.max(warm_support, axis=0) >= 0.5).mean())
    return {
        "arc_coverage": arc,
        "radial_alignment": radial,
        "warm_rim_arc": warm_arc,
        "distributed_rim_support": distributed,
        "score": 2 * warm_arc + 0.3 * radial + 0.2 * distributed,
    }


def inspect_camera_marker_ui(
    frame: Array,
    sample: dict[str, Any],
    pool: dict[str, Any],
) -> dict[str, Any]:
    frozen = _native(frame, sample)
    if (
        pool.get("sample") != frozen
        or pool.get("ownership") != "UNKNOWN"
        or pool.get("formal_outputs") != 0
        or pool.get("pool_sha256") != _digest({k: v for k, v in pool.items() if k != "pool_sha256"})
    ):
        raise ValueError("Current source-bound unqualified pool required")
    count = pool["parent_count"]
    if (
        type(count) is not int
        or not 0 <= count <= 128
        or not isinstance(pool.get("candidates"), list)
        or len(pool["candidates"]) < count
    ):
        raise ValueError("Bounded parent marker windows required")
    rows: list[dict[str, Any]] = []
    if count:
        patches, binding = bound_patches(
            frame, frozen, [p["center_frame_px"] for p in pool["candidates"][:count]], radius=17
        )
        for i, patch in enumerate(patches):
            rows.append(
                {
                    "candidate_index": i,
                    **_rim(patch),
                    "marker_observation_id": _digest(
                        {"sample": frozen["sample_sha256"], "pool": pool["pool_sha256"], "index": i}
                    ),
                }
            )
    else:
        binding = None
    order = sorted(range(len(rows)), key=lambda i: (-rows[i]["score"], i))
    selected = None
    margin = None
    if order:
        first = rows[order[0]]
        margin = first["score"] - rows[order[1]]["score"] if len(order) > 1 else math.inf
        if first["warm_rim_arc"] >= 0.15 and first["radial_alignment"] >= 0.55 and margin >= 0.12:
            selected = first["candidate_index"]
    return {
        "sample_sha256": frozen["sample_sha256"],
        "pool_sha256": pool["pool_sha256"],
        "feature_fingerprint": UI_FINGERPRINT,
        "native_window_binding": binding,
        "rows": rows,
        "ranked_indices": order,
        "selected_index": selected,
        "margin": margin if margin is not None and math.isfinite(margin) else None,
        "status": "highlighted_marker_candidate" if selected is not None else "UNKNOWN",
        "semantic_role": "current_camera_or_other_highlight_not_recorder_proof",
        "qualification": "development_only",
        "ownership": "UNKNOWN",
        "formal_outputs": 0,
    }
