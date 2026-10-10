"""Training-only row background hypothesis; never installed by production.

Estimate bright scene support from the four outer columns on each side. Unlike
opening, this does not estimate background from the digit's interior strokes.
Keep original intensities only where both sides support foreground contrast.
No retry, class preference, expected label, timestamp or temporal filling.
"""
from __future__ import annotations

import cv2
import numpy as np

from valorant_ai_coach.hud.readers import ReaderResult
from valorant_ai_coach.hud.score_glyphs import StrictScoreGlyphReader
from valorant_ai_coach.hud.timer_glyphs import ImageU8


def separate_background(gray: ImageU8) -> ImageU8:
    """Fixed native-pixel support, not a promise that borders are background."""
    left = np.median(gray[:, :4], axis=1)
    right = np.median(gray[:, -4:], axis=1)
    background = np.maximum(left, right)[:, None]
    return np.where(gray.astype(np.float32) - background >= 12, gray, 0).astype(np.uint8)


class BorderBackgroundScoreReader:
    def __init__(self, reader: StrictScoreGlyphReader) -> None:
        if (reader.foreground_preprocessing != 'white200_v1'
                or reader.comparison_preprocessing != 'gaussian3x3_v1'):
            raise ValueError('frozen white200/Gaussian score reader required')
        self.reader = reader

    def read(self, image: ImageU8, roi: ImageU8) -> ReaderResult[str]:
        if (not isinstance(roi, np.ndarray) or roi.dtype != np.uint8 or not roi.size
                or roi.ndim not in (2, 3) or min(roi.shape[:2]) < 8
                or roi.ndim == 3 and roi.shape[2] != 3):
            return ReaderResult(None, 0.0, ('diagnostic_score_invalid_border_support',))
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY) if roi.ndim == 3 else roi
        return self.reader.read(image, separate_background(gray))
