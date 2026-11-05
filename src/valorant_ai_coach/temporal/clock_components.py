"""Independent clock glyph evidence, never an imputed numeric clock.

The opt-in component observer reuses the existing timer's segmentation grammar,
all ten competing classes, threshold and margin. The full reader is unchanged.
"""

from __future__ import annotations

from typing import Any

import cv2
import numpy as np

from valorant_ai_coach.hud.timer_glyphs import ImageU8, StrictTimerGlyphReader


def clock_components(roi: ImageU8, reader: StrictTimerGlyphReader) -> dict[str, Any]:
    result: dict[str, Any] = {
        "schema": "development_clock_components_v1",
        "minute": None,
        "minute_confidence": None,
        "components": [],
        "active_prefix_supported": False,
        "numeric_clock_imputed": False,
        "qualified": False,
        "threshold": reader.THRESHOLD,
        "class_margin": reader.CLASS_MARGIN,
    }

    def reject(reason: str) -> dict[str, Any]:
        return {**result, "reason": reason}

    if (
        not isinstance(roi, np.ndarray)
        or roi.dtype != np.uint8
        or roi.ndim not in (2, 3)
        or min(roi.shape[:2]) < 2
        or roi.ndim == 3
        and roi.shape[2] != 3
    ):
        return reject("invalid_ROI")
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY) if roi.ndim == 3 else roi
    if float(gray.std()) < 1:
        return reject("low_contrast")
    enlarged = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    _, mask = cv2.threshold(enlarged, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    if any(np.any(v) for v in (mask[0], mask[-1], mask[:, 0], mask[:, -1])):
        return reject("foreground_touches_border")
    count, _, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    boxes = [tuple(map(int, row[:4])) for row in stats[1:count] if row[4] > 0]
    if not boxes:
        return reject("no_components")
    height = max(b[3] for b in boxes)
    digits = sorted((b for b in boxes if b[3] >= 0.5 * height), key=lambda b: b[0])
    dots = sorted((b for b in boxes if b[3] < 0.5 * height), key=lambda b: b[1])
    if len(digits) not in (3, 4) or len(dots) != 2:
        return reject("digit_or_colon_count")
    a, b = dots
    digit_height = float(np.median([box[3] for box in digits]))
    ax, bx = a[0] + a[2] / 2, b[0] + b[2] / 2
    ay, by = a[1] + a[3] / 2, b[1] + b[3] / 2
    if abs(ax - bx) > max(2, 0.12 * digit_height) or not (
        0.12 * digit_height <= by - ay <= 0.65 * digit_height
    ):
        return reject("colon_geometry")
    separator = (ax + bx) / 2
    splits = [
        k
        for k in (1, 2)
        if 1 <= k <= len(digits) - 2
        and len(digits[k:]) == 2
        and digits[k - 1][0] + digits[k - 1][2] < separator < digits[k][0]
    ]
    if len(splits) != 1:
        return reject("ambiguous_minute_separator")
    minute_count = splits[0]
    records: list[dict[str, Any]] = []
    for i, (x, y, width, height) in enumerate(digits):
        glyph = reader._comparison_image(
            reader._normalize_known_white(
                np.asarray(mask[y : y + height, x : x + width], dtype=np.uint8)
            )
        )
        scores = {
            digit: max(
                float(cv2.matchTemplate(glyph, ref, cv2.TM_CCOEFF_NORMED)[0, 0]) for ref in refs
            )
            for digit, refs in reader.comparison_templates.items()
        }
        if not all(np.isfinite(v) for v in scores.values()):
            return reject("nonfinite_class_score")
        ranked = sorted(scores.items(), key=lambda pair: pair[1], reverse=True)
        accepted = (
            ranked[0][1] >= reader.THRESHOLD and ranked[0][1] - ranked[1][1] >= reader.CLASS_MARGIN
        )
        records.append(
            {
                "role": "minute" if i < minute_count else "second",
                "digit": ranked[0][0] if accepted else None,
                "best": list(ranked[0]),
                "runner": list(ranked[1]),
                "all_ten_class_scores": scores,
                "accepted": bool(accepted),
            }
        )
    result["components"] = records
    minutes, seconds = records[:minute_count], records[minute_count:]
    if all(r["accepted"] for r in minutes):
        value = int("".join(r["digit"] for r in minutes))
        if 0 <= value <= 9:
            result["minute"] = value
            result["minute_confidence"] = min(r["best"][1] for r in minutes)
            # Confident contradictory syntax must not authorize a partial clock.
            invalid_seconds = seconds[0]["accepted"] and int(seconds[0]["digit"]) >= 6
            result["active_prefix_supported"] = value >= 1 and not invalid_seconds
    result["reason"] = "independent_components_no_full_clock_imputation"
    return result
