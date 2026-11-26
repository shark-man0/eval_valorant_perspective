"""Propose observed portrait centers in a bounded current minimap neighborhood."""

from __future__ import annotations

import math
from fractions import Fraction

import cv2
import numpy as np

from valorant_ai_coach.temporal.evidence import native_time
from valorant_ai_coach.temporal.map_direct_recorder import _rim_evidence


def matching_centers(roi, patches, center, scale):
    """Return separated response peaks present in both current patch comparisons."""
    if patches[0] is None or patches[1] is None or patches[0].shape != patches[1].shape:
        return []
    radius = patches[0].shape[0] // 2
    axis = np.arange(-radius, radius + 1)
    mask = (np.hypot(axis[:, None], axis[None, :]) <= radius).astype(np.uint8) * 255
    margin = max(14, math.ceil(14 * scale)) + 2 * radius
    cx, cy = center
    height, width = roi.shape[:2]
    x0, y0 = max(0, cx - margin), max(0, cy - margin)
    x1, y1 = min(width, cx + margin + 1), min(height, cy + margin + 1)
    if min(x1 - x0, y1 - y0) < 2 * radius + 1:
        return []
    image = roi[y0:y1, x0:x1]
    scores = np.stack(
        [
            cv2.matchTemplate(image, template, cv2.TM_CCOEFF_NORMED, mask=mask)
            for template in patches
        ]
    )
    minimum = scores.min(axis=0)
    minimum[~np.isfinite(minimum)] = -1
    candidates = []
    # Keep distinct centers so the ordinary ambiguity guard can see rivals.
    suppression = max(2, round(4 * scale))
    for _ in range(6):
        y, x = map(int, np.unravel_index(minimum.argmax(), minimum.shape))
        if minimum[y, x] < 0.83:
            break
        candidates.append(((x0 + x + radius, y0 + y + radius), scores[:, y, x].tolist()))
        minimum[
            max(0, y - suppression) : y + suppression + 1,
            max(0, x - suppression) : x + suppression + 1,
        ] = -1
    return candidates


def bracket_excess(left, point, right):
    return math.dist(left, point) + math.dist(point, right) - math.dist(left, right)


def measured_atlas_neighborhood(image, alignment, bracket, sample, patches, public_scores, target):
    """Use anchor geometry to place the search, then require current rim and Agent pixels."""
    left_point, right_point = bracket
    start, stop = (native_time(point["sample"]) for point in bracket)
    now = native_time(sample)
    if not (start < now < stop and stop - start <= Fraction(4)):
        return []
    left, top, right, bottom = alignment["roi_pixel_bounds"]
    matrix = np.asarray(
        alignment["map_name_candidates"][0]["reference_to_roi_homography_candidate"],
        dtype=float,
    )
    if (
        matrix.shape != (3, 3)
        or not np.isfinite(matrix).all()
        or (abs(float(np.linalg.det(matrix))) < 1e-9)
    ):
        return []
    a, b = (np.asarray(point["map_reference_px"], dtype=float) for point in bracket)
    # The prediction locates the search window. Reported coordinates always come
    # from pixels actually measured on this frame and its exact atlas transform.
    predicted = a + float((now - start) / (stop - start)) * (b - a)
    cx, cy = map(round, matrix[:2] @ [*predicted, 1.0])
    roi = image[top:bottom, left:right]
    scale = image.shape[1] / 1920
    peaks = matching_centers(roi, patches, (cx, cy), scale)
    if not peaks:
        return []
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    extent = math.ceil(11 * scale)
    result = []
    for (x, y), similarities in peaks:
        if not (extent <= x < right - left - extent and extent <= y < bottom - top - extent):
            continue
        warm, pairs, rivals = _rim_evidence(hsv, x, y, scale)
        if warm < 10 or pairs < 3 or rivals > 2:
            continue
        coordinate = np.linalg.solve(matrix, [x, y, 1.0])[:2]
        if (
            bracket_excess(
                left_point["map_reference_px"], coordinate, right_point["map_reference_px"]
            )
            > 8
        ):
            continue
        center = (x + left, y + top)
        official = public_scores(image, center)
        if official is None:
            continue
        score = float(official[target])
        gap = score - float(np.delete(official, target).max())
        if score < 0.73 or gap < 0.055:
            continue
        result.append(
            (
                center,
                {
                    "proposal": "atlas_neighborhood",
                    "strong_current_portrait": True,
                    "warm_sectors": warm,
                    "opposite_pairs": pairs,
                    "rival_sectors": rivals,
                    "external_target_score": score,
                    "external_agent_margin": gap,
                    "anchor_similarities": similarities,
                },
            )
        )
    return result
