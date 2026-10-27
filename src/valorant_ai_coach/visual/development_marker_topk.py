"""Opt-in broad current-frame hypotheses and non-destructive rank views.

Search does not authenticate a player, map build, camera or trajectory. Parent
coordinates/geometry survive verbatim. Close windows are alternatives, not a
claim that two observations are the same physical marker.
"""

from __future__ import annotations

import hashlib
import math
from copy import deepcopy
from typing import Any

import cv2
import numpy as np

from .development_marker_attribution import freeze_native_sample
from .development_marker_features import AppearanceCentroids, Array, _digest, bound_patches

POLICY = {
    "version": "broad_shape_topk_v1",
    "hough": [1, 3, 80, 10, 5, 11, 128],
    "components": [80, 50, 15, 500, 45, 64],
    "parent_limit": 128,
    "extra_limit": 192,
    "physical_merging": False,
}


def _native(frame: Array, sample: dict[str, Any]) -> dict[str, Any]:
    if (
        not isinstance(frame, np.ndarray)
        or frame.dtype != np.uint8
        or frame.ndim != 3
        or frame.shape[2] != 3
        or max(frame.shape[:2]) > 8192
    ):
        raise ValueError("Bounded native uint8 BGR frame required")
    frozen = freeze_native_sample(sample, frame_size_px=(frame.shape[1], frame.shape[0]))
    if (
        sample != frozen
        or hashlib.sha256(frame.tobytes()).hexdigest() != sample["native_pixel_sha256"]
    ):
        raise ValueError("Native source/pixel identity mismatch")
    return frozen


def _xy(value: Any, width: int, height: int) -> bool:
    return (
        isinstance(value, list)
        and len(value) == 2
        and all(
            type(v) in (int, float) and math.isfinite(v) and 0 <= v < side
            for v, side in zip(value, (width, height), strict=True)
        )
    )


def broad_shape_candidates(
    frame: Array,
    sample: dict[str, Any],
    *,
    roi_xywh: list[int],
    parent: list[dict[str, Any]],
    profile_fingerprint: str,
    map_id_candidate: str = "UNKNOWN",
) -> dict[str, Any]:
    """Append bounded loose circles and chromatic component alternatives.

    No annotation, semantic model, previous frame or geometry acceptance enters
    search. A caller must verify Source admission and split before reading media.
    Profile/build/geometry evidence remains separate from these pixel hypotheses.
    """
    frozen = _native(frame, sample)
    height, width = frame.shape[:2]
    if (
        not isinstance(roi_xywh, list)
        or len(roi_xywh) != 4
        or any(type(v) is not int for v in roi_xywh)
        or not isinstance(profile_fingerprint, str)
        or len(profile_fingerprint) != 64
        or any(c not in "0123456789abcdef" for c in profile_fingerprint)
        or not isinstance(map_id_candidate, str)
        or not map_id_candidate
        or not isinstance(parent, list)
        or len(parent) > 128
        or any(
            not isinstance(p, dict)
            or not _xy(p.get("center_frame_px"), width, height)
            or p.get("ownership") != "UNKNOWN"
            or p.get("map_position_norm") is not None
            or p.get("zone_resolution") is not None
            or p.get("formal_fact") is not None
            or p.get("formal_self_position_fact") is not None
            or p.get("formal_events") not in (None, [])
            for p in parent
        )
    ):
        raise ValueError("Bounded parent hypotheses, ROI and profile binding required")
    left, top, rw, rh = roi_xywh
    if (
        not 65 <= min(rw, rh) <= max(rw, rh) <= 1024
        or min(left, top) < 0
        or left + rw > width
        or top + rh > height
    ):
        raise ValueError("Bounded complete native minimap ROI required")
    crop = frame[top : top + rh, left : left + rw]
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    found = cv2.HoughCircles(
        gray, cv2.HOUGH_GRADIENT, 1, 3, param1=80, param2=10, minRadius=5, maxRadius=11
    )
    circles = [] if found is None else found[0].tolist()
    raw: list[dict[str, Any]] = []
    for x, y, radius in circles[:128]:
        raw.append(
            {
                "center_roi_px": [x, y],
                "method": "loose_hough",
                "raw_score": None,
                "evidence": {"radius_px": radius},
            }
        )
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    mask = ((hsv[:, :, 1] >= 80) & (hsv[:, :, 2] >= 50)).astype(np.uint8)
    count, labels, stats, centroids = cv2.connectedComponentsWithStats(mask, connectivity=8)
    eligible = [
        i
        for i in range(1, count)
        if 15 <= stats[i, 4] <= 500 and min(stats[i, 2:4]) >= 3 and max(stats[i, 2:4]) <= 45
    ]
    component_observations = []
    # Two alternatives per component reserve at most 64 additional windows.
    for index in eligible[:32]:
        x, y, w, h, area = map(int, stats[index])
        tile = (labels[y : y + h, x : x + w] == index).astype(np.uint8)
        distance = cv2.distanceTransform(np.pad(tile, 1), cv2.DIST_L2, 5)[1:-1, 1:-1]
        peaks = np.argwhere(
            (distance == cv2.dilate(distance, np.ones((5, 5), np.uint8))) & (distance >= 1.5)
        )
        alternatives = [[x + (w - 1) / 2, y + (h - 1) / 2]]
        if len(peaks):
            py, px = min(peaks.tolist(), key=lambda q: (-float(distance[q[0], q[1]]), q[0], q[1]))
            alternatives.append([float(x + px), float(y + py)])
        else:
            alternatives.append(centroids[index].tolist())
        for alternative, center in enumerate(alternatives):
            component_observations.append(
                {
                    "center_roi_px": center,
                    "method": "chromatic_component_alternative",
                    "raw_score": float(distance.max()),
                    "evidence": {
                        "component_index": index,
                        "alternative": alternative,
                        "component_bbox_roi_px": [x, y, w, h],
                        "area": area,
                        "physical_marker_count": None,
                        "color_is_not_semantic": True,
                    },
                }
            )
    raw.extend(component_observations)
    extras = [
        {
            **p,
            "center_frame_px": [p["center_roi_px"][0] + left, p["center_roi_px"][1] + top],
            "candidate_kind": "unassigned_marker_hypothesis",
            "class_candidate": "UNKNOWN",
            "ownership": "UNKNOWN",
            "qualification": "development_only",
            "geometry_only_map_position_norm": None,
            "geometry_reason": "not_evaluated",
            "map_position_norm": None,
            "zone_resolution": None,
            "unknown_reason": "appearance_only_no_identity_or_geometry",
        }
        for p in raw
    ]
    candidates = deepcopy(parent) + extras
    close_pairs = [
        [i, j]
        for i in range(len(candidates))
        for j in range(i)
        if math.dist(candidates[i]["center_frame_px"], candidates[j]["center_frame_px"]) <= 4
    ]
    payload = {
        "sample": frozen,
        "roi_xywh": roi_xywh.copy(),
        "profile_fingerprint": profile_fingerprint,
        "map_id_candidate": map_id_candidate,
        "map_build": "UNKNOWN",
        "policy_fingerprint": _digest(POLICY),
        "parent_sha256": _digest(parent),
        "parent_count": len(parent),
        "candidates": candidates,
        "near_window_pairs": close_pairs,
        "physical_association": "UNKNOWN",
        "hough_raw_count": len(circles),
        "eligible_components": len(eligible),
        "unprocessed_hough": max(0, len(circles) - 128),
        "unprocessed_components": max(0, len(eligible) - 32),
        "ownership": "UNKNOWN",
        "qualification": "development_only",
        "formal_outputs": 0,
    }
    payload["pool_sha256"] = _digest(payload)
    if _native(frame, sample) != frozen:
        raise ValueError("Native input changed during search")
    return payload


def rank_candidates(
    frame: Array,
    sample: dict[str, Any],
    pool: dict[str, Any],
    *,
    features: Array,
    feature_fingerprint: str,
    feature_binding_sha256: str,
    classifier: AppearanceCentroids,
    top_k: int = 5,
) -> dict[str, Any]:
    """Rank all windows by positive-vs-negative cosine support, retaining UNKNOWN.

    Top-K is a view of competing windows, not an output detector or deduplicated
    object count. Classification rejection never erases the underlying window.
    """
    frozen = _native(frame, sample)
    content = {k: v for k, v in pool.items() if k != "pool_sha256"}
    if (
        _digest(content) != pool.get("pool_sha256")
        or pool.get("sample") != frozen
        or pool.get("ownership") != "UNKNOWN"
        or pool.get("formal_outputs") != 0
        or type(top_k) is not int
        or not 1 <= top_k <= 10
        or classifier.feature_fingerprint != feature_fingerprint
    ):
        raise ValueError("Exact current pool/model binding required")
    candidates = pool["candidates"]
    if not 1 <= len(candidates) <= 320:
        raise ValueError("One to 320 bounded candidate windows required")
    centers = [p["center_frame_px"] for p in candidates]
    bindings = []
    for start in range(0, len(centers), 128):
        _, binding = bound_patches(frame, frozen, centers[start : start + 128])
        bindings.append(binding)
    if _digest(bindings) != feature_binding_sha256:
        raise ValueError("Features do not bind all current native windows")
    if (
        not isinstance(features, np.ndarray)
        or features.ndim != 2
        or len(features) != len(candidates)
        or not np.isfinite(features).all()
        or (np.linalg.norm(features, axis=1) <= 1e-12).any()
    ):
        raise ValueError("Paired finite nonzero current-window features required")
    predictions = []
    for start in range(0, len(features), 128):
        predictions.extend(
            classifier.classify(
                features[start : start + 128], feature_fingerprint=feature_fingerprint
            )
        )
    positive = [
        i for i, label in enumerate(classifier.labels) if label in {"PLAYER", "DEATH_MARKER"}
    ]
    negative = [i for i, label in enumerate(classifier.labels) if label in {"UI", "BACKGROUND"}]
    if not positive or not negative:
        raise ValueError("Both positive and negative human-trained prototypes required")
    unit = features / np.linalg.norm(features, axis=1, keepdims=True)
    similarity = unit @ classifier.centers.T
    scores = similarity[:, positive].max(axis=1) - similarity[:, negative].max(axis=1)
    order = sorted(range(len(candidates)), key=lambda i: (-float(scores[i]), i))
    return {
        "pool_sha256": pool["pool_sha256"],
        "feature_binding_sha256": feature_binding_sha256,
        "feature_fingerprint": feature_fingerprint,
        "classifier_fingerprint": classifier.fingerprint,
        "ranked_indices": order,
        "top_k_indices": order[:top_k],
        "scores": scores.tolist(),
        "score_kind": "uncalibrated_cosine_support_gap",
        "appearance_reviews": predictions,
        "UNKNOWN": sum(p["appearance_class_candidate"] == "UNKNOWN" for p in predictions),
        "ownership": "UNKNOWN",
        "qualification": "development_only",
        "formal_outputs": 0,
    }
