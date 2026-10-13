"""Diagnostic-only text-row crop proposal, not numeric/UI qualification.

Use unlabeled bright components inside an already configured ROI. No expected
digit, timestamp, world state or validation label can enter this proposal.
"""
from __future__ import annotations

import cv2
import numpy as np


def propose(gray: np.ndarray, *, timer: bool) -> tuple[int, int, int, int] | None:
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
        row = [box for box in glyphs if abs(box[3] - h) <= .25 * h
               and abs(box[1] + box[3] / 2 - y - h / 2) <= .20 * h]
        if len(row) not in ({3, 4} if timer else {1, 2}):
            continue
        left = min(box[0] for box in row)
        right = max(box[0] + box[2] for box in row)
        top = min(box[1] for box in row)
        bottom = max(box[1] + box[3] for box in row)
        # A colon must be observed as two small, vertically aligned components.
        # Its pixels are never synthesized from a three-/four-digit OCR string.
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
