"""Opt-in score glyph reader; never supplies identity or lifecycle decisions."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import cast

import cv2
import numpy as np

from .readers import ReaderResult
from .timer_glyphs import ImageU8, StrictTimerGlyphReader


class StrictScoreGlyphReader(StrictTimerGlyphReader):
    """Reuse the ten-class template contract, with a separate score grammar.

    All ten digit classes remain competitors, even when training video scores
    cover fewer classes. No expected score, timer or round ID is an input.
    A successful read is current-frame text, not qualified round evidence.
    """

    def __init__(
        self, templates: Mapping[str, Sequence[ImageU8]], *,
        comparison_preprocessing: str = "binary_v1",
        foreground_preprocessing: str = "otsu_v1",
    ) -> None:
        if not isinstance(foreground_preprocessing, str) or foreground_preprocessing not in {
            "otsu_v1", "white200_v1", "white200_rowcontrast_v1",
        }:
            raise ValueError("unsupported strict score foreground preprocessing")
        if (foreground_preprocessing == "white200_rowcontrast_v1"
                and comparison_preprocessing != "gaussian3x3_v1"):
            raise ValueError("rowcontrast score preprocessing requires gaussian3x3_v1")
        super().__init__(templates, comparison_preprocessing=comparison_preprocessing)
        self.foreground_preprocessing = foreground_preprocessing

    def read(self, image: ImageU8, roi: ImageU8) -> ReaderResult[str]:
        del image
        if (
            not isinstance(roi, np.ndarray) or roi.dtype != np.uint8
            or roi.size == 0 or roi.ndim not in (2, 3)
            or (roi.ndim == 3 and roi.shape[2] != 3)
            or min(roi.shape[:2]) < 2
        ):
            return self._reject("strict_score_invalid_roi")
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY) if roi.ndim == 3 else roi
        if float(gray.std()) < 1:
            return self._reject("strict_score_low_contrast_roi")
        enlarged = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
        mask = self._foreground_mask(cast(ImageU8, enlarged))
        if np.any(mask[0]) or np.any(mask[-1]) or np.any(mask[:, 0]) or np.any(mask[:, -1]):
            return self._reject("strict_score_foreground_touches_roi_border")
        count, _, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
        components = sorted(
            [(int(x), int(y), int(w), int(h)) for x, y, w, h, area in stats[1:count]
             if area > 0],
            key=lambda component: component[0],
        )
        if len(components) not in (1, 2):
            return self._reject("strict_score_expected_one_or_two_digits")
        if len(components) == 2:
            (x1, y1, w1, h1), (x2, y2, _, h2) = components
            if (
                min(h1, h2) < .8 * max(h1, h2)
                or abs(y1 - y2) > .15 * max(h1, h2)
                or not 0 < x2 - (x1 + w1) <= max(h1, h2)
            ):
                return self._reject("strict_score_digit_layout_inconsistent")
        text, scores = [], []
        for x, y, width, height in components:
            glyph = self._comparison_image(self._normalize_known_white(
                np.asarray(mask[y:y + height, x:x + width], dtype=np.uint8),
            ))
            ranked = []
            for digit, references in self.comparison_templates.items():
                matches = [float(cv2.matchTemplate(
                    glyph, reference, cv2.TM_CCOEFF_NORMED,
                )[0, 0]) for reference in references]
                if not all(np.isfinite(value) for value in matches):
                    return self._reject("strict_score_nonfinite_glyph_score")
                ranked.append((max(matches), digit))
            ranked.sort(reverse=True)
            best, digit = ranked[0]
            if best < self.THRESHOLD:
                return self._reject("strict_score_glyph_below_0_90")
            if best - ranked[1][0] < self.CLASS_MARGIN:
                return self._reject("strict_score_glyph_competitor_gap_below_0_04")
            text.append(digit)
            scores.append(best)
        display = "".join(text)
        if len(display) == 2 and display.startswith("0"):
            return self._reject("strict_score_leading_zero")
        sources: tuple[str, ...] = ("strict_score_glyphs",)
        if self.comparison_preprocessing != "binary_v1":
            sources += ("comparison_gaussian3x3_v1",)
        if self.foreground_preprocessing != "otsu_v1":
            sources += (f"foreground_{self.foreground_preprocessing}",)
        return ReaderResult(display, min(scores), sources)

    def _foreground_mask(self, enlarged: ImageU8) -> ImageU8:
        """Single foreground stage; default production preprocessing is unchanged."""
        if self.foreground_preprocessing in {"white200_v1", "white200_rowcontrast_v1"}:
            _, mask = cv2.threshold(enlarged, 200, 255, cv2.THRESH_BINARY)
        else:
            _, mask = cv2.threshold(enlarged, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        if self.foreground_preprocessing == "white200_rowcontrast_v1":
            # Opt-in value-invariant background support in the already enlarged
            # domain. No resampling, retry or preferred digit class follows.
            left = np.median(enlarged[:, :8], axis=1)
            right = np.median(enlarged[:, -8:], axis=1)
            background = np.maximum(left, right)[:, None]
            mask = np.where(enlarged.astype(np.float32) - background >= 12, mask, 0)
        return np.asarray(mask, dtype=np.uint8)


class UnavailableStrictScoreGlyphReader:
    def read(self, image: ImageU8, roi: ImageU8) -> ReaderResult[str]:
        del image, roi
        return ReaderResult(None, 0.0, ("strict_score_configuration_invalid",))
