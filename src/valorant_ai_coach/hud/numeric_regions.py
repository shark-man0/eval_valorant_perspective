"""Opt-in numeric text isolation, independent of geometry and player identity.

Pixels alone propose a text region. A proposal does not prove UI identity or
qualify lifecycle events; existing calibration/qualification gates still apply.
"""
from __future__ import annotations

import math
import re
from typing import cast

import cv2
import numpy as np
from numpy.typing import NDArray

from .readers import HudReader, ReaderResult

ImageU8 = NDArray[np.uint8]
LOCATOR = "bright_components_v1"


def propose(gray: ImageU8, *, timer: bool) -> tuple[int, int, int, int] | None:
    """Fixed component-row proposal; never synthesize a missing colon."""
    if gray.ndim != 2 or gray.dtype != np.uint8 or min(gray.shape) < 16:
        raise ValueError("native grayscale numeric ROI required")
    height, width = gray.shape
    _, _, stats, _ = cv2.connectedComponentsWithStats(
        (gray >= 210).astype(np.uint8), connectivity=8)
    glyphs, dots = [], []
    for x, y, w, h, area in stats[1:]:
        row = (int(x), int(y), int(w), int(h))
        if (.20 * height <= h <= .65 * height and .10 <= w / h <= 1.25
                and area >= 8):
            glyphs.append(row)
        elif timer and 2 <= w <= .12 * height and 2 <= h <= .12 * height and area >= 4:
            dots.append(row)
    proposals = set()
    for _, y, _, h in glyphs:
        row_boxes = [box for box in glyphs if abs(box[3] - h) <= .25 * h
                     and abs(box[1] + box[3] / 2 - y - h / 2) <= .20 * h]
        if len(row_boxes) not in ({3, 4} if timer else {1, 2}):
            continue
        left = min(box[0] for box in row_boxes)
        right = max(box[0] + box[2] for box in row_boxes)
        top = min(box[1] for box in row_boxes)
        bottom = max(box[1] + box[3] for box in row_boxes)
        if timer:
            colon = [box for box in dots if left < box[0] < right
                     and top <= box[1] and box[1] + box[3] <= bottom]
            pairs = [(a, b) for a in colon for b in colon
                     if a[1] < b[1] and abs(a[0] - b[0]) <= 2
                     and .2 * h <= b[1] - a[1] <= .8 * h]
            if len(pairs) != 1:
                continue
        proposals.add((max(0, left - 4), max(0, top - 4),
                       min(width, right + 4), min(height, bottom + 4)))
    return next(iter(proposals)) if len(proposals) == 1 else None


class LocalizedNumericReader:
    def __init__(self, delegate: HudReader[str], *, timer: bool, minimum: float) -> None:
        if (type(timer) is not bool or type(minimum) not in (int, float)
                or not math.isfinite(minimum) or not .90 <= minimum <= 1):
            raise ValueError("explicit format and >=.90 configured confidence required")
        self.delegate, self.timer, self.minimum = delegate, timer, minimum

    def read(self, image: ImageU8, roi: ImageU8) -> ReaderResult[str]:
        gray = cast(ImageU8, cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)) if roi.ndim == 3 else roi
        bounds = propose(gray, timer=self.timer)
        if bounds is None:
            return ReaderResult(None, 0.0, ("numeric_region_unlocalized",))
        left, top, right, bottom = bounds
        result = self.delegate.read(image, gray[top:bottom, left:right])
        pattern = r"[0-9]{1,2}:[0-5][0-9]" if self.timer else r"[0-9]{1,2}"
        if (not isinstance(result, ReaderResult) or not isinstance(result.value, str)
                or re.fullmatch(pattern, result.value) is None
                or type(result.confidence) not in (int, float)
                or not math.isfinite(result.confidence)
                or not self.minimum <= result.confidence <= 1
                or not result.sources
                or any(not isinstance(s, str) or not s.strip() for s in result.sources)):
            return ReaderResult(None, 0.0, ("numeric_region_result_rejected",))
        # Spatial text isolation is not independent value evidence/crosschecking.
        return ReaderResult(result.value, result.confidence,
                            (*result.sources, LOCATOR), False)
