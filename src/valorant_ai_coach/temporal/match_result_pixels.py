"""Pixel corroboration for central and postmatch result layouts."""

from __future__ import annotations

from typing import Any

import cv2
import numpy as np
from numpy.typing import NDArray


def _components(mask: NDArray[np.bool_]) -> list[tuple[int, int, int, int, int]]:
    _, _, stats, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8))
    return [(int(x), int(y), int(w), int(h), int(area)) for x, y, w, h, area in stats[1:]]


def _score_shapes(
    mask: NDArray[np.bool_], left: int, right: int, top: int
) -> bool:
    if right <= left:
        return False
    start, end = max(0, top - 9), min(mask.shape[0], top + 38)
    return any(
        width >= 3 and 10 <= height <= 32 and area >= 22 and abs(y + start - top) <= 9
        for _, y, width, height, area in _components(mask[start:end, left:right])
    )


def postmatch_scoreboard(image: NDArray[np.uint8]) -> dict[str, Any] | None:
    """Recognize a large result title with flanking score glyphs and a rematch control.

    The client overlays players on the headline, so an exact OCR word may be
    unavailable. Aligned title glyphs, the two team score colors, and the
    independent rematch control support the layout and an outcome hypothesis.
    """
    if min(image.shape[:2]) < 120:
        return None
    scaled = cv2.resize(image, (480, 270), interpolation=cv2.INTER_AREA)
    hue, saturation, value = cv2.split(cv2.cvtColor(scaled, cv2.COLOR_BGR2HSV))
    teal = (hue >= 55) & (hue <= 105)
    red = (hue <= 13) | (hue >= 168)
    rematch = red & (saturation >= 135) & (value >= 165)
    buttons = _components(rematch[237:266, 155:320])
    if not any(35 <= w <= 94 and 6 <= h <= 23 and area >= .62 * w * h
               for _, _, w, h, area in buttons):
        return None
    score_masks = [color & (saturation >= 125) & (value >= 165) for color in (teal, red)]
    outcomes = []
    for outcome, color in (("VICTORY", teal), ("DEFEAT", red)):
        title = color & (saturation >= 45) & (value >= 145)
        title[:25] = False
        title[128:] = False
        title[:, :45] = False
        title[:, 435:] = False
        glyphs = [
            (x, y, w, h)
            for x, y, w, h, area in _components(title)
            if 10 <= w <= 65 and h >= 22 and area >= 120 and y < 57
        ]
        for top in sorted({g[1] for g in glyphs}):
            aligned = [g for g in glyphs if abs(g[1] - top) <= 4]
            if len(aligned) < 5:
                continue
            left = min(g[0] for g in aligned)
            right = max(g[0] + g[2] for g in aligned)
            if right - left < 190 or abs((left + right) / 2 - 240) > 38:
                continue
            scores = any(
                _score_shapes(score_masks[a], max(0, left - 55), left - 3, top)
                and _score_shapes(score_masks[b], right + 3, min(480, right + 55), top)
                for a, b in ((0, 1), (1, 0))
            )
            if scores:
                outcomes.append(outcome)
                break
    if len(outcomes) != 1:
        return None
    return {
        "visible": True, "outcome_candidate": outcomes[0],
        "layout": "POSTMATCH_SCOREBOARD",
        "basis": "aligned_result_title_palette_flanking_team_scores_and_rematch_control",
        "evidence": ["large_aligned_title", "paired_colored_score_glyphs", "rematch_control"],
        "unknown_possible": True, "qualified": False,
    }


def match_result_candidate(
    image: NDArray[np.uint8], central_words: list[dict[str, Any]]
) -> dict[str, Any]:
    """Combine native layout structure with the existing center OCR measurement."""
    scoreboard = postmatch_scoreboard(image)
    height, width = image.shape[:2]
    center = {
        word["text"].upper().strip(" .!|")
        for word in central_words
        if isinstance(word.get("text"), str)
        and type(word.get("confidence")) in (int, float)
        and .85 <= word["confidence"] <= 1
        and isinstance(word.get("native_roi_box"), list)
        and len(word["native_roi_box"]) == 4
        and all(type(v) in (int, float) for v in word["native_roi_box"])
        and word["native_roi_box"][2] >= .12 * width
        and word["native_roi_box"][3] >= .03 * height
    } & {"VICTORY", "DEFEAT"}
    if scoreboard and (not center or center == {scoreboard["outcome_candidate"]}):
        return scoreboard
    if not scoreboard and len(center) == 1:
        return {
            "visible": True, "outcome_candidate": next(iter(center)), "layout": "CENTRAL_OVERLAY",
            "basis": "large_central_result_word", "unknown_possible": True, "qualified": False,
        }
    return {
        "visible": False, "outcome_candidate": None, "layout": "UNKNOWN",
        "basis": "unresolved_match_result_layout", "unknown_possible": True, "qualified": False,
    }
