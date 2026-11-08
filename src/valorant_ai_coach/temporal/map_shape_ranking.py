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
