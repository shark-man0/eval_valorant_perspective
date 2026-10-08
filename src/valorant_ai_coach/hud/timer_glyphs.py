from __future__ import annotations

from collections.abc import Mapping, Sequence

import cv2
import numpy as np
from numpy.typing import NDArray

from .readers import ReaderResult

ImageU8 = NDArray[np.uint8]
DIGITS = frozenset("0123456789")


class StrictTimerGlyphReader:
    """Read numeric timer glyphs only; emits no player identity or current-frame state claim."""

    THRESHOLD = 0.90
    CLASS_MARGIN = 0.04
    TEMPLATE_SHAPE = (32, 24)

    def __init__(
        self, templates: Mapping[str, Sequence[ImageU8]], *,
        comparison_preprocessing: str = "binary_v1",
    ) -> None:
        if not isinstance(comparison_preprocessing, str) or comparison_preprocessing not in {
            "binary_v1", "gaussian3x3_v1"
        }:
            raise ValueError("unsupported strict timer comparison preprocessing")
        self.comparison_preprocessing = comparison_preprocessing
        if set(templates) != DIGITS:
            raise ValueError("strict timer templates must contain exactly digits 0 through 9")
        validated: dict[str, tuple[ImageU8, ...]] = {}
        for digit in sorted(DIGITS):
            refs = templates[digit]
            if not isinstance(refs, Sequence) or isinstance(refs, (str, bytes)) or not refs:
                raise ValueError(f"strict timer digit {digit} has no reference images")
            images: list[ImageU8] = []
            for reference in refs:
                image = np.asarray(reference)
                if image.dtype != np.uint8 or image.shape != self.TEMPLATE_SHAPE:
                    raise ValueError(f"strict timer digit {digit} reference must be uint8 32x24")
                if not np.isfinite(image).all() or not np.isin(image, (0, 255)).all():
                    raise ValueError(f"strict timer digit {digit} reference must be a binary mask")
                if not np.any(image) or np.all(image):
                    raise ValueError(f"strict timer digit {digit} reference is blank or flat")
                images.append(np.ascontiguousarray(image))
            validated[digit] = tuple(images)
        self.templates = validated
        self.comparison_templates = {
            digit: tuple(self._comparison_image(reference) for reference in refs)
            for digit, refs in validated.items()
        }

    def _comparison_image(self, image: ImageU8) -> ImageU8:
        if self.comparison_preprocessing == "gaussian3x3_v1":
            return np.asarray(cv2.GaussianBlur(image, (3, 3), 0), dtype=np.uint8)
        return image

    def read(self, image: ImageU8, roi: ImageU8) -> ReaderResult[str]:
        del image
        if not isinstance(roi, np.ndarray) or roi.size == 0 or roi.ndim not in (2, 3):
            return self._reject("strict_timer_invalid_or_empty_roi")
        if roi.dtype != np.uint8:
            return self._reject("strict_timer_invalid_roi_dtype_or_size")
        if roi.ndim == 3 and roi.shape[2] != 3:
            return self._reject("strict_timer_unsupported_channels")
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY) if roi.ndim == 3 else roi
        if min(gray.shape[:2]) < 2:
            return self._reject("strict_timer_invalid_roi_dtype_or_size")
        gray = np.ascontiguousarray(gray)
        if not np.isfinite(gray).all() or float(gray.std()) < 1.0:
            return self._reject("strict_timer_low_contrast_roi")
        enlarged = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
        _, mask = cv2.threshold(enlarged, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        if not np.any(mask):
            return self._reject("strict_timer_no_foreground")
        if np.any(mask[0, :]) or np.any(mask[-1, :]) or np.any(mask[:, 0]) or np.any(mask[:, -1]):
            return self._reject("strict_timer_foreground_touches_roi_border")

        count, _, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
        components = [
            (int(x), int(y), int(width), int(height))
            for x, y, width, height, area in stats[1:count]
            if area > 0
        ]
        if not components:
            return self._reject("strict_timer_no_components")
        max_height = max(component[3] for component in components)
        digits = sorted(
            (component for component in components if component[3] >= 0.5 * max_height),
            key=lambda component: component[0],
        )
        separators = sorted(
            (component for component in components if component[3] < 0.5 * max_height),
            key=lambda component: component[1],
        )
        if len(digits) not in (3, 4):
            return self._reject("strict_timer_expected_three_or_four_digits")
        if len(separators) != 2:
            return self._reject("strict_timer_expected_exactly_two_separator_dots")

        top_dot, bottom_dot = separators
        digit_height = float(np.median([component[3] for component in digits]))
        top_x = top_dot[0] + top_dot[2] / 2.0
        bottom_x = bottom_dot[0] + bottom_dot[2] / 2.0
        top_y = top_dot[1] + top_dot[3] / 2.0
        bottom_y = bottom_dot[1] + bottom_dot[3] / 2.0
        if abs(top_x - bottom_x) > max(2.0, 0.12 * digit_height):
            return self._reject("strict_timer_separator_dots_not_aligned")
        dot_spacing = bottom_y - top_y
        if not (0.12 * digit_height <= dot_spacing <= 0.65 * digit_height):
            return self._reject("strict_timer_separator_dot_spacing_invalid")
        separator_x = (top_x + bottom_x) / 2.0
        splits: list[tuple[list[tuple[int, int, int, int]], list[tuple[int, int, int, int]]]] = []
        for split_index in (1, 2):
            left, right = digits[:split_index], digits[split_index:]
            if (
                1 <= len(left) <= 2
                and len(right) == 2
                and left[-1][0] + left[-1][2] < separator_x < right[0][0]
            ):
                splits.append((left, right))
        if len(splits) != 1:
            return self._reject("strict_timer_separator_not_between_minutes_and_seconds")

        recognized: list[str] = []
        scores: list[float] = []
        for x, y, width, height in digits:
            glyph = self._normalize_known_white(
                np.asarray(mask[y : y + height, x : x + width], dtype=np.uint8)
            )
            glyph = self._comparison_image(glyph)
            class_scores: dict[str, float] = {}
            for digit, refs in self.comparison_templates.items():
                values = [
                    float(cv2.matchTemplate(glyph, reference, cv2.TM_CCOEFF_NORMED)[0, 0])
                    for reference in refs
                ]
                if not values or not all(np.isfinite(value) for value in values):
                    return self._reject("strict_timer_nonfinite_glyph_score")
                class_scores[digit] = max(values)
            ranked = sorted(class_scores.items(), key=lambda item: item[1], reverse=True)
            best_digit, best_score = ranked[0]
            runner_score = ranked[1][1]
            if not np.isfinite(best_score) or not np.isfinite(runner_score):
                return self._reject("strict_timer_nonfinite_glyph_score")
            if best_score < self.THRESHOLD:
                return self._reject("strict_timer_glyph_below_0_90")
            if best_score - runner_score < self.CLASS_MARGIN:
                return self._reject("strict_timer_glyph_competitor_gap_below_0_04")
            recognized.append(best_digit)
            scores.append(best_score)

        digits_text = "".join(recognized)
        minute_count = len(splits[0][0])
        if len(digits_text) != minute_count + 2:
            return self._reject("strict_timer_internal_digit_order_error")
        seconds = int(digits_text[-2:])
        if seconds >= 60:
            return self._reject("strict_timer_seconds_out_of_range")
        return ReaderResult(
            f"{digits_text[:-2]}:{digits_text[-2:]}",
            min(scores),
            ("strict_timer_glyphs",)
            if self.comparison_preprocessing == "binary_v1"
            else ("strict_timer_glyphs", "comparison_gaussian3x3_v1"),
        )

    @staticmethod
    def _reject(reason: str) -> ReaderResult[str]:
        return ReaderResult(None, 0.0, (reason,))

    @classmethod
    def _normalize_known_white(cls, image: ImageU8) -> ImageU8:
        points = cv2.findNonZero(image)
        if points is None:
            return np.zeros(cls.TEMPLATE_SHAPE, dtype=np.uint8)
        x, y, width, height = cv2.boundingRect(points)
        glyph = image[y : y + height, x : x + width]
        scale = min(18 / width, 26 / height)
        resized = cv2.resize(
            glyph,
            (max(1, round(width * scale)), max(1, round(height * scale))),
            interpolation=cv2.INTER_NEAREST,
        )
        output = np.zeros(cls.TEMPLATE_SHAPE, dtype=np.uint8)
        top = (output.shape[0] - resized.shape[0]) // 2
        left = (output.shape[1] - resized.shape[1]) // 2
        output[top : top + resized.shape[0], left : left + resized.shape[1]] = resized
        return output


class UnavailableStrictTimerGlyphReader:
    """Fail closed for an invalid opt-in timer profile instead of falling back to OCR."""

    def read(self, image: ImageU8, roi: ImageU8) -> ReaderResult[str]:
        del image, roi
        return ReaderResult(None, 0.0, ("strict_timer_configuration_invalid",))
