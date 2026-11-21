"""Scoped boundary comparisons and annotation sensitivity, never accuracy bounds."""

from __future__ import annotations

from typing import Any

import cv2
import numpy as np
from shapely.geometry import Point, Polygon

from .development_position_review import compare_position_review


def compare_review_boundaries(
    record: dict[str, Any], review: dict[str, Any], *, frame_sha256: str,
    reference_sha256: str, roi_size_px: tuple[int, int],
    reference_bbox: tuple[int, int, int, int], zones: list[dict[str, Any]],
) -> dict[str, Any]:
    """Compare the prediction and independent affine against registered polygons.

    Single-coordinate +/- annotation tolerance perturbations are diagnostics,
    not a joint uncertainty bound, world GT or a new ZoneResolution. An absence
    of membership flips does not prove a robust interior. No labels fit a model.
    """
    result = compare_position_review(
        record, review, frame_sha256=frame_sha256, reference_sha256=reference_sha256,
        roi_size_px=roi_size_px, reference_bbox=reference_bbox)
    source = np.array(review['landmark_roi_px'], dtype=float)
    target = np.array(review['landmark_reference_px'], dtype=float)
    center = np.array(review['center_roi_px'], dtype=float)
    lo = np.array(reference_bbox[:2], dtype=float)
    span = np.array(reference_bbox[2:], dtype=float)-lo
    polygons = []
    for zone in zones:
        polygon = Polygon(np.array(zone['polygon_norm'])*span+lo)
        if not polygon.is_valid or polygon.is_empty or polygon.area <= 0:
            raise ValueError("Valid registered Zone polygon required")
        polygons.append((zone['zone_id'], polygon))

    def affine_point(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> np.ndarray:
        if min(abs(float(np.linalg.det(np.c_[p, np.ones(3)]))) for p in (a, b)) < 1e-6:
            raise ValueError("Annotation perturbation makes affine singular")
        return np.asarray(
            cv2.getAffineTransform(a.astype(np.float32), b.astype(np.float32)) @ np.r_[c, 1])

    def membership(p: np.ndarray) -> list[str]:
        return sorted(name for name, polygon in polygons if polygon.covers(Point(p)))

    expected = affine_point(source, target, center)
    varied = [expected]
    for index, original in enumerate([source, target, center]):
        tolerance = review['reference_tolerance_px' if index == 1 else 'source_tolerance_px']
        for coordinate in range(original.size):
            for sign in [-1, 1]:
                values = [source.copy(), target.copy(), center.copy()]
                values[index].flat[coordinate] += sign*tolerance
                varied.append(affine_point(*values))
    memberships = [membership(p) for p in varied]
    prediction = record.get('map_position_norm')
    actual = None if prediction is None else np.array(prediction)*span+lo
    return {**result, "reference_polygon_review": {
        "independent_affine_reference_point_px": expected.tolist(),
        "independent_membership": memberships[0],
        "prediction_membership": None if actual is None else membership(actual),
        "membership_agrees": None if actual is None else membership(actual) == memberships[0],
        "independent_signed_boundary_distance_px": {
            name: float(Point(expected).distance(polygon.boundary))
                  * (1 if polygon.covers(Point(expected)) else -1)
            for name, polygon in polygons},
        "single_coordinate_perturbation_cases": len(varied),
        "membership_changes_under_single_coordinate_perturbation": any(
            x != memberships[0] for x in memberships[1:]),
        "perturbation_max_reference_shift_px": max(
            float(np.linalg.norm(p-expected)) for p in varied),
        "joint_annotation_error_bound": None, "zone_boundary_accuracy": "unmeasured",
        "scope": "Registered polygon comparison at this point, not true/full Site geometry",
    }}
