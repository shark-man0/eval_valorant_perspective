"""Small source-bound coordinate reviews, never population accuracy or ownership.

Manual annotations stay private. Predictions cannot be substituted for labels;
frame/geometry/prediction anchors bind each imported response to one observation.
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any, cast

import cv2
import numpy as np


def observation_fingerprint(record: dict[str, Any]) -> str:
    # Review metadata is an attachment to the frozen prediction, not a new one.
    data = {k: v for k, v in record.items() if k != "position_review"}
    return hashlib.sha256(json.dumps(data, sort_keys=True, allow_nan=False).encode()).hexdigest()


def fixed_review_indices(count: int) -> list[int]:
    """First, middle and last ordinals, independent of model acceptance."""
    if isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= 5000:
        raise ValueError("Bounded observation count required")
    return sorted({0, (count-1)//2, count-1})


def _points(value: Any, shape: tuple[int, ...]) -> np.ndarray:
    try:
        array = np.array(value, dtype=float)
    except (ValueError, TypeError) as exc:
        raise ValueError("Finite coordinate annotations required") from exc
    if array.shape != shape or not np.isfinite(array).all():
        raise ValueError("Finite coordinate annotations required")
    return array


def compare_position_review(
    record: dict[str, Any], review: dict[str, Any], *, frame_sha256: str,
    reference_sha256: str, roi_size_px: tuple[int, int],
    reference_bbox: tuple[int, int, int, int],
) -> dict[str, Any]:
    """Compare a frozen candidate to reviewed centers and a three-corner affine.

    Source/reference annotation tolerance remains explicit. Extrapolation is
    flagged. Residuals from these few points are never exported as an accuracy
    radius for other observations, or as calibrated boundary uncertainty.
    """
    if (record.get("qualification") != "development_only"
            or record.get("ownership", {}).get("identity") != "UNKNOWN"
            or record.get("formal_self_position_fact") is not None
            or review.get("status") != "human_confirmed"
            or review.get("label_origin") != "source_image_review"
            or review.get("not_used_for_fitting") is not True):
        raise ValueError("Scoped human review and frozen development prediction required")
    for key in ("source_id", "acquisition_id", "frame_index", "time_sec", "map_id",
                "geometry_version"):
        if key not in record or review.get(key) != record[key]:
            raise ValueError("Review observation identity mismatch")
    if (review.get("frame_sha256") != frame_sha256
            or review.get("reference_sha256") != reference_sha256
            or review.get("prediction_sha256") != observation_fingerprint(record)):
        raise ValueError("Review frame, reference or frozen prediction hash mismatch")
    if review.get("role") not in {"SELF", "NONSELF", "SPECTATOR", "DEATH", "UNKNOWN"}:
        raise ValueError("Explicit reviewed role required")
    tolerances = [review.get(k) for k in ("source_tolerance_px", "reference_tolerance_px")]
    if any(isinstance(v, bool) or not isinstance(v, (int, float))
           or not math.isfinite(v) or v < 0 for v in tolerances):
        raise ValueError("Finite non-negative annotation tolerances required")
    source_tolerance = float(cast(int | float, tolerances[0]))
    size = _points(roi_size_px, (2,))
    bbox = _points(reference_bbox, (4,))
    span = bbox[2:]-bbox[:2]
    if min(size) <= 0 or min(span) <= 0:
        raise ValueError("Positive image geometry required")
    source = _points(review.get("landmark_roi_px"), (3, 2))
    target = _points(review.get("landmark_reference_px"), (3, 2))
    center = _points(review.get("center_roi_px"), (2,))
    if (np.any(source < 0) or np.any(source >= size) or np.any(center < 0)
            or np.any(center >= size)):
        raise ValueError("Source annotations must lie in actual ROI")
    homogeneous = np.r_[source.T, np.ones((1, 3))]
    if abs(float(np.linalg.det(homogeneous))) < 1e-6:
        raise ValueError("Non-collinear reviewed landmarks required")
    weights = np.linalg.solve(homogeneous, np.r_[center, 1])
    affine = cv2.getAffineTransform(source.astype(np.float32), target.astype(np.float32))
    expected = affine @ np.r_[center, 1]
    appearance = record.get("appearance", {})
    measured = (None if appearance.get("x_roi_norm") is None else
                _points([appearance["x_roi_norm"], appearance["y_roi_norm"]], (2,))*size)
    point = record.get("map_position_norm")
    map_point = None if point is None else _points(point, (2,))*span+bbox[:2]
    difference = None if measured is None else float(np.linalg.norm(measured-center))
    return {
        "qualification": "development_only", "ownership": "UNKNOWN",
        "human_reviewed_role": review["role"], "sample_scope": "this_observation_only",
        "prediction_sha256": review["prediction_sha256"], "frame_sha256": frame_sha256,
        "review_sha256": hashlib.sha256(json.dumps(
            review, sort_keys=True, allow_nan=False).encode()).hexdigest(),
        "roi_center_difference_px": difference,
        "roi_difference_annotation_interval_px": None if difference is None else
            [max(0, difference-source_tolerance), difference+source_tolerance],
        "map_affine_reference_difference_px": None if map_point is None else
            float(np.linalg.norm(map_point-expected)),
        "affine_extrapolation": bool(np.any(weights < -1e-9)),
        "annotation_tolerances_px": tolerances,
        "transferable_error_radius_reference_px": None,
        "absolute_world_position_accuracy": "unmeasured",
        "population_accuracy": "unmeasured", "formal_self_position_fact": None,
    }
