"""Offline literal Timer formats, reusing existing readers and frozen assets.

No phase input, inferred values, template fitting or runtime installation.
"""

from __future__ import annotations

import math
import re

import cv2
import numpy as np

from scripts.diagnostics.result_title_region import title_region
from valorant_ai_coach.hud.readers import HudReader, ReaderResult
from valorant_ai_coach.hud.score_glyphs import StrictScoreGlyphReader
from valorant_ai_coach.hud.timer_glyphs import ImageU8, StrictTimerGlyphReader


class TimerDisplayReader:
    """Preserve strict colon reads; recognize only explicit four-digit dot lines.

    The single low separator must be between the second and third digits. A
    decimal display remains seconds.hundredths text, never rewritten as m:ss.
    Glyph confidence and competitor margin stay at .90/.04. Optional OCR is
    explicitly configured by the offline caller and must pass .90; there is no
    max-confidence selection between glyph/OCR methods. A parent
    ROI border outside the proposed glyph line is context, not missing text;
    fragments on the glyph baseline, including outside the line, reject it.
    """

    def __init__(
        self, reader: StrictTimerGlyphReader, *, decimal_reader: HudReader[str] | None = None
    ) -> None:
        if (
            not isinstance(reader, StrictTimerGlyphReader)
            or reader.comparison_preprocessing != "gaussian3x3_v1"
            or reader.THRESHOLD != 0.90
            or reader.CLASS_MARGIN != 0.04
        ):
            raise ValueError("unchanged strict Gaussian Timer reader required")
        self.reader = reader
        self.decimal_reader = decimal_reader
        self.digit_reader = StrictScoreGlyphReader(
            reader.templates,
            comparison_preprocessing=reader.comparison_preprocessing,
            foreground_preprocessing="white200_v1",
        )

    def read(self, image: ImageU8, roi: ImageU8) -> ReaderResult[str]:
        baseline = self.reader.read(image, roi)
        if baseline.value is not None:
            return baseline
        try:
            proposal = title_region(roi)
        except ValueError:
            return ReaderResult(None, 0.0, ("offline_timer_invalid_roi",))
        boxes = proposal["glyph_boxes"]
        if proposal["status"] != "PROPOSAL" or len(boxes) != 4:
            return ReaderResult(None, 0.0, (*baseline.sources, "offline_timer_format_unknown"))
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY) if roi.ndim == 3 else roi
        mask = np.asarray(gray >= 210, dtype=np.uint8) * 255
        count, _, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
        height = float(np.median([b[3] for b in boxes]))
        top = min(b[1] for b in boxes)
        bottom = max(b[1] + b[3] for b in boxes)
        others = [
            tuple(map(int, row[:4]))
            for row in stats[1:count]
            if list(map(int, row[:4])) not in boxes and top <= row[1] + row[3] / 2 <= bottom
        ]
        if len(others) != 1:
            return ReaderResult(None, 0.0, ("offline_timer_separator_ambiguous",))
        x, y, w, h = others[0]
        if not (
            0 < w <= 0.25 * height
            and 0 < h <= 0.25 * height
            and y >= bottom - 0.30 * height
            and y + h <= bottom + 0.05 * height
            and boxes[1][0] + boxes[1][2] < x < x + w < boxes[2][0]
        ):
            return ReaderResult(None, 0.0, ("offline_timer_decimal_topology_unknown",))
        if self.decimal_reader is not None:
            a, b, c, d = proposal["bounds"]
            value = self.decimal_reader.read(image, roi[b:d, a:c])
            if (
                not isinstance(value.value, str)
                or re.fullmatch(r"[0-9]{2}\.[0-9]{2}", value.value) is None
                or type(value.confidence) not in (int, float)
                or not math.isfinite(value.confidence)
                or not 0.90 <= value.confidence <= 1
            ):
                return ReaderResult(
                    None, 0.0, (*value.sources, "offline_timer_decimal_ocr_rejected")
                )
            return ReaderResult(
                value.value,
                value.confidence,
                (*value.sources, "offline_timer_seconds_hundredths_v1"),
            )
        values, scores = [], []
        pad = proposal["padding_px"]
        for x, y, w, h in boxes:
            glyph = np.asarray(gray[y - pad : y + h + pad, x - pad : x + w + pad], dtype=np.uint8)
            value = self.digit_reader.read(image, glyph)
            if value.value is None or len(value.value) != 1:
                return ReaderResult(None, 0.0, (*value.sources, "offline_timer_digit_unknown"))
            values.append(value.value)
            scores.append(value.confidence)
        return ReaderResult(
            "".join(values[:2]) + "." + "".join(values[2:]),
            min(scores),
            (
                "offline_timer_seconds_hundredths_v1",
                "strict_timer_digit_assets",
                "comparison_gaussian3x3_v1",
            ),
        )


class ProfileTimerDisplayReader:
    """Keep the configured Timer subregion when adding literal decimal support.

    Unwrapping a Profile's SubregionReader and reading its outer layout ROI is
    a different observation method. Successful configured reads are returned
    unchanged. Only a strictly validated decimal can recover a rejected read;
    an alternate colon or guessed punctuation cannot replace the Profile.
    """

    def __init__(self, baseline: HudReader[str], *,
                 decimal_reader: HudReader[str] | None = None) -> None:
        from valorant_ai_coach.hud.templates import SubregionReader
        strict = baseline.reader if isinstance(baseline, SubregionReader) else baseline
        if not isinstance(strict, StrictTimerGlyphReader):
            raise ValueError('configured strict Timer reader required')
        self.baseline = baseline
        self.literal = TimerDisplayReader(strict, decimal_reader=decimal_reader)

    def read(self, image: ImageU8, roi: ImageU8) -> ReaderResult[str]:
        observed = self.baseline.read(image, roi)
        if observed.value is not None:
            return observed
        alternative = self.literal.read(image, roi)
        if alternative.value is not None and '.' in alternative.value:
            return alternative
        return observed
