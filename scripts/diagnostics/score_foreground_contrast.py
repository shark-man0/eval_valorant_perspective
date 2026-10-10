"""Training-only score foreground hypothesis; not a production reader entrance.

Fixed local opening removes slowly varying bright background. Original retained
pixel intensities feed the existing strict score reader; no retry, expected value,
timestamp or class selection is available to this wrapper.
"""
from __future__ import annotations

import cv2
import numpy as np

from valorant_ai_coach.hud.readers import ReaderResult
from valorant_ai_coach.hud.score_glyphs import StrictScoreGlyphReader
from valorant_ai_coach.hud.timer_glyphs import ImageU8


class LocalContrastScoreReader:
    KERNEL_SIZE = 9
    MIN_LOCAL_CONTRAST = 12

    def __init__(self, reader: StrictScoreGlyphReader) -> None:
        if (reader.foreground_preprocessing != 'white200_v1'
                or reader.comparison_preprocessing != 'gaussian3x3_v1'):
            raise ValueError('frozen white200/Gaussian score reader required')
        self.reader = reader

    def read(self, image: ImageU8, roi: ImageU8) -> ReaderResult[str]:
        if (not isinstance(roi, np.ndarray) or roi.dtype != np.uint8 or not roi.size
                or roi.ndim not in (2, 3) or min(roi.shape[:2]) < 2
                or roi.ndim == 3 and roi.shape[2] != 3):
            return self.reader.read(image, roi)
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY) if roi.ndim == 3 else roi
        kernel = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE, (self.KERNEL_SIZE, self.KERNEL_SIZE),
        )
        background = cv2.morphologyEx(gray, cv2.MORPH_OPEN, kernel)
        contrast = cv2.subtract(gray, background)
        filtered = np.where(contrast >= self.MIN_LOCAL_CONTRAST, gray, 0).astype(np.uint8)
        return self.reader.read(image, filtered)
