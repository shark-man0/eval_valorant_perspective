"""Shared pixel bounds for calibrated and measured normalized ROIs."""

from __future__ import annotations

import math
from typing import Any


def normalized_roi_bounds(
    roi: Any, width: int, height: int
) -> tuple[int, int, int, int] | None:
    if not isinstance(roi, (list, tuple)) or len(roi) != 4 or width <= 0 or height <= 0:
        return None
    try:
        x0, y0, x1, y1 = (float(value) for value in roi)
    except (TypeError, ValueError):
        return None
    if not all(math.isfinite(v) and 0 <= v <= 1 for v in (x0, y0, x1, y1)):
        return None
    if x1 <= x0 or y1 <= y0:
        return None
    bounds = round(x0 * width), round(y0 * height), round(x1 * width), round(y1 * height)
    if bounds[2] <= bounds[0] or bounds[3] <= bounds[1]:
        return None
    return bounds
