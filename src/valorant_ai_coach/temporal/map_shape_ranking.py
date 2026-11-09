"""Current-pixel white-arrow shape ranking experiment without owner authority."""

from __future__ import annotations

import math
from typing import Any

import cv2
import numpy as np
from numpy.typing import NDArray


def rank_white_arrow_shapes(
    image: NDArray[np.uint8], candidates: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Rank local shapes only; HUD camera/owner evidence must be joined separately.

    Three-corner, solid, low-saturation components are a weak arrow cue. Map text,
    spike UI and ally icons can share it. No acceptance threshold or state change
    is implied. Inputs contain no recording identity, time or previous state.
    """
    if image.dtype != np.uint8 or image.ndim != 3 or image.shape[2] != 3:
        raise ValueError("Native BGR image required")
    height, width = image.shape[:2]
    radius = max(6, round(12 * width / 1920))
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    white = ((hsv[:, :, 1] <= 70) & (hsv[:, :, 2] >= 170)).astype(np.uint8)
    rows = []
    for index, candidate in enumerate(candidates):
        point = candidate.get("center_frame_px")
        if (
            not isinstance(point, list)
            or len(point) != 2
            or any(type(v) not in (int, float) or not math.isfinite(v) for v in point)
        ):
            raise ValueError("Finite candidate centers required")
        x, y = map(float, point)
        if not 0 <= x < width or not 0 <= y < height:
            raise ValueError("Candidate outside native pixels")
        left, top = max(0, round(x) - radius), max(0, round(y) - radius)
        crop = white[
            top : min(height, round(y) + radius + 1), left : min(width, round(x) + radius + 1)
        ]
        contours, _ = cv2.findContours(crop, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        scores = []
        for contour in contours:
            area = cv2.contourArea(contour)
            hull_area = cv2.contourArea(cv2.convexHull(contour))
            if not 3 <= area <= (2 * radius) ** 2 / 2 or hull_area <= 0:
                continue
            perimeter = cv2.arcLength(contour, True)
            corners = len(cv2.approxPolyDP(contour, 0.06 * perimeter, True))
            moments = cv2.moments(contour)
            if not moments["m00"]:
                continue
            cx = left + moments["m10"] / moments["m00"]
            cy = top + moments["m01"] / moments["m00"]
            proximity = max(0.0, 1 - math.hypot(cx - x, cy - y) / radius)
            triangular = 1 / (1 + abs(corners - 3))
            scores.append(triangular * area / hull_area * proximity)
        rows.append(
            {
                "candidate_index": index,
                "score": max(scores, default=0.0),
                "method": "development_white_arrow_shape_v1",
                "ownership": "UNKNOWN",
                "qualified": False,
                "position_authority": False,
            }
        )
    return sorted(rows, key=lambda row: (-row["score"], row["candidate_index"]))


def rank_marker_context(
    image: NDArray[np.uint8], candidates: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Development-only marker ordering from shape and a nearby amber HUD accent.

    A small amber component beside a portrait can indicate a current-view marker.
    The same color can occur in the map or spike UI, so this is only a ranking
    cue. Camera, agent identity and ownership must be supplied and checked by
    another owner; this function never assigns them.
    """
    shape_rows = rank_white_arrow_shapes(image, candidates)
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    amber = (
        (hsv[:, :, 0] >= 17) & (hsv[:, :, 0] <= 39) & (hsv[:, :, 1] >= 100) & (hsv[:, :, 2] >= 130)
    ).astype(np.uint8)
    count, _, stats, centroids = cv2.connectedComponentsWithStats(amber, connectivity=8)
    # Large map fills and single compression pixels are poor marker accents.
    accents = [centroids[i] for i in range(1, count) if 2 <= int(stats[i, 4]) <= 60]
    scale = image.shape[1] / 1920
    reach = max(8.0, 18.0 * scale)
    rows = []
    for shape in shape_rows:
        index = shape["candidate_index"]
        x, y = candidates[index]["center_frame_px"]
        distance = min((math.hypot(x - a[0], y - a[1]) for a in accents), default=reach)
        accent_score = max(0.0, 1.0 - distance / reach)
        rows.append(
            {
                "candidate_index": index,
                "score": shape["score"] + accent_score,
                "shape_score": shape["score"],
                "accent_score": accent_score,
                "method": "development_marker_context_v1",
                "ownership": "UNKNOWN",
                "qualified": False,
                "position_authority": False,
            }
        )
    return sorted(rows, key=lambda row: (-row["score"], row["candidate_index"]))
