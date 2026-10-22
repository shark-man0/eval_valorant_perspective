"""Offline title-line proposal inside the configured Result banner.

Uses original pixels and the existing white210 foreground hypothesis. Neither
the proposal nor an OCR word establishes a complete Result or a Round End.
No source-specific coordinates, word templates or expected labels enter here.
"""
from __future__ import annotations

import math
from typing import Any

import cv2
import numpy as np

from valorant_ai_coach.hud.timer_glyphs import ImageU8


def title_region(roi: ImageU8) -> dict[str, Any]:
    """Propose one consistent large-glyph line, rejecting clips/ambiguity.

    Constants are relative to the configured outer ROI or measured glyphs;
    they are frozen diagnostic hypotheses, not calibrated detection accuracy.
    A partial internal animation can still be UNKNOWN despite a valid box.
    """
    if (not isinstance(roi, np.ndarray) or roi.dtype != np.uint8
            or roi.ndim not in (2, 3) or roi.size == 0
            or (roi.ndim == 3 and roi.shape[2] != 3)):
        raise ValueError("nonempty uint8 gray/BGR banner ROI required")
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY) if roi.ndim == 3 else roi
    height, width = gray.shape
    result: dict[str, Any] = {
        "method": "relative_white210_title_line_v1", "status": "UNKNOWN",
        "reason": "large_glyph_line_unavailable", "bounds": None,
        "glyph_boxes": [], "semantic_completeness": "UNKNOWN",
        "formal_events": [], "production_qualified": False,
    }
    if min(height, width) < 8 or float(gray.std()) < 1:
        return result
    # Same foreground level as existing result-text diagnostics; no OCR retry.
    mask = np.asarray(gray >= 210, dtype=np.uint8) * 255
    count, _, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    boxes: list[tuple[int, int, int, int]] = []
    touching: list[tuple[int, int, int, int]] = []
    for x, y, w, h, area in stats[1:count]:
        box = (int(x), int(y), int(w), int(h))
        if not (.15 * height <= h <= .50 * height and .04 * h <= w <= 1.5 * h
                and area >= .08 * w * h):
            continue
        if x == 0 or y == 0 or x + w == width or y + h == height:
            touching.append(box)
        else:
            boxes.append(box)
    # Group by vertical centre and glyph height without consulting OCR text.
    groups: list[list[tuple[int, int, int, int]]] = []
    for box in sorted(boxes, key=lambda b: (b[1] + b[3] / 2, b[0])):
        x, y, w, h = box
        choices = [g for g in groups if all(
            abs(y + h / 2 - (b[1] + b[3] / 2)) <= .15 * max(h, b[3])
            and min(h, b[3]) >= .80 * max(h, b[3]) for b in g)]
        if len(choices) == 1:
            choices[0].append(box)
        else:
            groups.append([box])
    lines = [g for g in groups if 3 <= len(g) <= 16]
    if len(lines) != 1:
        result["reason"] = "ambiguous_title_lines" if lines else (
            "outer_ROI_clips_glyphs" if touching else "large_glyph_line_unavailable")
        return result
    line = lines[0]
    glyphs = sorted(line)
    median_height = float(np.median([b[3] for b in glyphs]))
    centre_y = float(np.median([b[1] + b[3] / 2 for b in glyphs]))
    if any(abs(y + h / 2 - centre_y) <= .35 * median_height
           for _, y, _, h in touching):
        result["reason"] = "outer_ROI_clips_glyphs"
        return result
    # Other substantial fragments on this baseline make completion ambiguous.
    if any(abs(b[1] + b[3] / 2 - centre_y) <= .35 * median_height
           for g in groups if g is not line for b in g):
        result["reason"] = "inconsistent_glyph_fragments"
        return result
    gaps = [b[0] - (a[0] + a[2]) for a, b in zip(glyphs, glyphs[1:], strict=False)]
    if any(gap < 0 or gap > 1.5 * median_height for gap in gaps):
        result["reason"] = "inconsistent_glyph_spacing"
        return result
    padding = max(1, math.ceil(.12 * median_height))
    left = min(b[0] for b in glyphs) - padding
    top = min(b[1] for b in glyphs) - padding
    right = max(b[0] + b[2] for b in glyphs) + padding
    bottom = max(b[1] + b[3] for b in glyphs) + padding
    if left < 0 or top < 0 or right > width or bottom > height:
        result["reason"] = "insufficient_outer_ROI_margin"
        return result
    return {**result, "status": "PROPOSAL", "reason": "consistent_large_glyph_line",
            "bounds": [left, top, right, bottom],
            "glyph_boxes": [list(b) for b in glyphs], "padding_px": padding}
