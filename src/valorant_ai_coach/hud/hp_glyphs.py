"""Strict current-frame HP glyph reader; emits no identity or temporal claims."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

import cv2
import numpy as np
from numpy.typing import NDArray

from .readers import ReaderResult

ImageU8 = NDArray[np.uint8]
DIGITS = frozenset("0123456789")


class StrictHpGlyphReader:
    """Read only a configured HP numeral field using a complete numeric alphabet."""

    THRESHOLD = 0.90
    CLASS_MARGIN = 0.04
    TEMPLATE_SHAPE = (32, 24)

    def __init__(
        self,
        templates: Mapping[str, Sequence[ImageU8]],
        *,
        center_offset_norm: Sequence[float],
        gap_ratio_bounds: Sequence[float],
        tolerance_norm: float,
    ) -> None:
        if not isinstance(templates, Mapping) or set(templates) != DIGITS:
            raise ValueError("strict HP templates must contain exactly digits 0 through 9")
        self.templates = self._validate_templates(templates)
        self.center_offset_norm = self._bounds(
            center_offset_norm,
            name="center_offset_norm",
            minimum=-0.05,
            maximum=0.05,
        )
        self.gap_ratio_bounds = self._bounds(
            gap_ratio_bounds,
            name="gap_ratio_bounds",
            minimum=0.0,
            maximum=0.5,
        )
        if self.gap_ratio_bounds[0] >= self.gap_ratio_bounds[1]:
            raise ValueError("strict HP gap_ratio_bounds must be ordered")
        if self.center_offset_norm[0] >= self.center_offset_norm[1]:
            raise ValueError("strict HP center_offset_norm must be ordered")
        if not self.center_offset_norm[0] <= 0 <= self.center_offset_norm[1]:
            raise ValueError("strict HP center_offset_norm must include zero")
        if (
            isinstance(tolerance_norm, bool)
            or not isinstance(tolerance_norm, (int, float))
            or not math.isfinite(float(tolerance_norm))
            or not 0 < float(tolerance_norm) <= 0.02
        ):
            raise ValueError("strict HP tolerance_norm must be finite and in (0, 0.02]")
        self.tolerance_norm = float(tolerance_norm)

    @classmethod
    def _validate_templates(
        cls, templates: Mapping[str, Sequence[ImageU8]]
    ) -> dict[str, tuple[ImageU8, ...]]:
        validated: dict[str, tuple[ImageU8, ...]] = {}
        for digit in sorted(DIGITS):
            refs = templates[digit]
            if not isinstance(refs, Sequence) or isinstance(refs, (str, bytes)) or not refs:
                raise ValueError(f"strict HP digit {digit} has no reference images")
            images: list[ImageU8] = []
            for reference in refs:
                image = np.asarray(reference)
                if image.dtype != np.uint8 or image.shape != cls.TEMPLATE_SHAPE:
                    raise ValueError(f"strict HP digit {digit} reference must be uint8 32x24")
                if not np.isfinite(image).all() or not np.isin(image, (0, 255)).all():
                    raise ValueError(f"strict HP digit {digit} reference must be a binary mask")
                if not np.any(image) or np.all(image):
                    raise ValueError(f"strict HP digit {digit} reference is blank or flat")
                images.append(np.ascontiguousarray(image).copy())
            validated[digit] = tuple(images)
        return validated

    @staticmethod
    def _bounds(
        values: Sequence[float], *, name: str, minimum: float, maximum: float
    ) -> tuple[float, float]:
        if not isinstance(values, Sequence) or isinstance(values, (str, bytes)) or len(values) != 2:
            raise ValueError(f"strict HP {name} must contain two finite values")
        bounds: list[float] = []
        for value in values:
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(float(value))
                or not minimum <= float(value) <= maximum
            ):
                raise ValueError(f"strict HP {name} has an invalid bound")
            bounds.append(float(value))
        if bounds[0] >= bounds[1]:
            raise ValueError(f"strict HP {name} must be ordered")
        return bounds[0], bounds[1]

    def read(self, image: ImageU8, roi: ImageU8) -> ReaderResult[dict[str, int]]:
        """Return a numeric HP value only when the entire current field passes."""
        del image
        if not isinstance(roi, np.ndarray) or roi.size == 0 or roi.ndim not in (2, 3):
            return self._reject("strict_hp_invalid_or_empty_roi")
        if roi.dtype != np.uint8:
            return self._reject("strict_hp_invalid_roi_dtype")
        if roi.ndim == 3 and roi.shape[2] != 3:
            return self._reject("strict_hp_unsupported_channels")
        try:
            gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY) if roi.ndim == 3 else roi
        except cv2.error:
            return self._reject("strict_hp_unsupported_channels")
        if min(gray.shape[:2]) < 2:
            return self._reject("strict_hp_invalid_or_empty_roi")
        gray = np.ascontiguousarray(gray)
        if float(gray.std()) < 1.0:
            return self._reject("strict_hp_low_contrast_roi")
        enlarged = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
        _, mask = cv2.threshold(enlarged, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        if not np.any(mask):
            return self._reject("strict_hp_no_foreground")
        if np.any(mask[0, :]) or np.any(mask[-1, :]) or np.any(mask[:, 0]) or np.any(mask[:, -1]):
            return self._reject("strict_hp_foreground_touches_roi_border")

        count, _, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
        components = sorted(
            (
                (int(x), int(y), int(width), int(height))
                for x, y, width, height, area in stats[1:count]
                if area > 0
            ),
            key=lambda component: component[0],
        )
        # A single glyph has no independently checked field geometry or width.
        if len(components) not in (2, 3):
            return self._reject("strict_hp_expected_two_or_three_components")
        if any(height < mask.shape[0] * 0.5 for _, _, _, height in components):
            return self._reject("strict_hp_glyph_too_short_for_field")

        left = components[0][0]
        right = components[-1][0] + components[-1][2]
        center_offset_norm = ((left + right) / 2.0 - mask.shape[1] / 2.0) / mask.shape[1]
        if not self.center_offset_norm[0] <= center_offset_norm <= self.center_offset_norm[1]:
            return self._reject("strict_hp_center_outside_profile_bounds")

        gap_ratios: list[float] = []
        if len(components) > 1:
            median_height = float(np.median([component[3] for component in components]))
            if median_height <= 0:
                return self._reject("strict_hp_invalid_glyph_geometry")
            gap_ratios = [
                (components[index + 1][0] - (components[index][0] + components[index][2]))
                / median_height
                for index in range(len(components) - 1)
            ]
            tolerance = self.tolerance_norm * mask.shape[1] / median_height
            low = self.gap_ratio_bounds[0] - tolerance
            high = self.gap_ratio_bounds[1] + tolerance
            if any(not low <= ratio <= high for ratio in gap_ratios):
                return self._reject("strict_hp_gap_outside_profile_bounds")

        recognized: list[str] = []
        accepted_scores: list[float] = []
        for x, y, width, height in components:
            glyph = self._normalize_known_white(
                np.asarray(mask[y : y + height, x : x + width], dtype=np.uint8)
            )
            if not np.any(glyph):
                return self._reject("strict_hp_empty_glyph")
            class_scores: dict[str, float] = {}
            for digit, references in self.templates.items():
                scores = [
                    float(cv2.matchTemplate(glyph, reference, cv2.TM_CCOEFF_NORMED)[0, 0])
                    for reference in references
                ]
                if not scores or not all(math.isfinite(score) for score in scores):
                    return self._reject("strict_hp_nonfinite_glyph_score")
                class_scores[digit] = max(scores)
            ranked = sorted(class_scores.items(), key=lambda item: item[1], reverse=True)
            best_digit, best_score = ranked[0]
            runner_score = ranked[1][1]
            if not math.isfinite(best_score) or not math.isfinite(runner_score):
                return self._reject("strict_hp_nonfinite_glyph_score")
            if best_score < self.THRESHOLD:
                return self._reject("strict_hp_glyph_below_0_90")
            if best_score - runner_score < self.CLASS_MARGIN:
                return self._reject("strict_hp_glyph_competitor_gap_below_0_04")
            recognized.append(best_digit)
            accepted_scores.append(best_score)

        digits_text = "".join(recognized)
        if len(digits_text) > 1 and digits_text.startswith("0"):
            return self._reject("strict_hp_leading_zero")
        value = int(digits_text)
        if not 0 <= value <= 100:
            return self._reject("strict_hp_value_out_of_range")
        confidence = min(1.0, max(0.0, min(accepted_scores)))
        return ReaderResult({"hp": value}, confidence, ("strict_hp_glyphs",))

    @staticmethod
    def _normalize_known_white(image: ImageU8) -> ImageU8:
        points = cv2.findNonZero(image)
        if points is None:
            return np.zeros(StrictHpGlyphReader.TEMPLATE_SHAPE, dtype=np.uint8)
        x, y, width, height = cv2.boundingRect(points)
        glyph = image[y : y + height, x : x + width]
        scale = min(18 / width, 26 / height)
        resized = cv2.resize(
            glyph,
            (max(1, round(width * scale)), max(1, round(height * scale))),
            interpolation=cv2.INTER_NEAREST,
        )
        output = np.zeros(StrictHpGlyphReader.TEMPLATE_SHAPE, dtype=np.uint8)
        top = (output.shape[0] - resized.shape[0]) // 2
        left = (output.shape[1] - resized.shape[1]) // 2
        output[top : top + resized.shape[0], left : left + resized.shape[1]] = resized
        return output

    @staticmethod
    def _reject(reason: str) -> ReaderResult[dict[str, int]]:
        return ReaderResult(None, 0.0, (reason,))


class UnavailableStrictHpGlyphReader:
    """Fail closed for an invalid opt-in HP profile; does not invoke OCR."""

    def read(self, image: ImageU8, roi: ImageU8) -> ReaderResult[dict[str, int]]:
        del image, roi
        return ReaderResult(None, 0.0, ("strict_hp_configuration_invalid",))
