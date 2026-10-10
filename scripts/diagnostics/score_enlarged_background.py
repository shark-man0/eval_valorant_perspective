"""Frozen training-only foreground hypothesis, with no production registration.

Separate in the existing enlarged domain so suppressing dim scene pixels cannot
change cubic interpolation. The inherited classifier and grammar are unchanged.
Border support may be contaminated; training/holdout must establish suitability.
"""
from __future__ import annotations

import numpy as np

from valorant_ai_coach.hud.score_glyphs import StrictScoreGlyphReader
from valorant_ai_coach.hud.timer_glyphs import ImageU8


class EnlargedBackgroundScoreReader(StrictScoreGlyphReader):
    def _foreground_mask(self, enlarged: ImageU8) -> ImageU8:
        if (self.foreground_preprocessing != 'white200_v1'
                or self.comparison_preprocessing != 'gaussian3x3_v1'):
            raise ValueError('frozen white200/Gaussian score reader required')
        mask = super()._foreground_mask(enlarged)
        left = np.median(enlarged[:, :8], axis=1)
        right = np.median(enlarged[:, -8:], axis=1)
        background = np.maximum(left, right)[:, None]
        return np.where(enlarged.astype(np.float32) - background >= 12, mask, 0).astype(
            np.uint8,
        )
