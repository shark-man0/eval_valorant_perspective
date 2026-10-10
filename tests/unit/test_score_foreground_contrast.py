"""Synthetic controls for the diagnostic wrapper, not real qualification."""
import numpy as np
import pytest

from scripts.diagnostics.score_foreground_contrast import LocalContrastScoreReader
from tests.unit.test_timer_glyphs import _templates
from valorant_ai_coach.hud.score_glyphs import StrictScoreGlyphReader


def reader():
    return LocalContrastScoreReader(StrictScoreGlyphReader(
        _templates(), comparison_preprocessing='gaussian3x3_v1',
        foreground_preprocessing='white200_v1',
    ))


@pytest.mark.parametrize('roi', [np.zeros((40, 40), np.uint8),
                               np.full((40, 40), 230, np.uint8),
                               np.full((40, 40), .5, np.float32),
                               np.zeros((40, 40, 4), np.uint8)])
def test_absent_or_invalid_input_never_fills_score(roi):
    before = roi.copy()
    result = reader().read(roi, roi)
    assert result.value is None and result.confidence == 0
    assert np.array_equal(roi, before)


def test_wrapper_preserves_all_competitors_and_existing_acceptance_policy():
    wrapped = reader().reader
    assert set(wrapped.templates) == set('0123456789')
    assert wrapped.THRESHOLD == .90 and wrapped.CLASS_MARGIN == .04
    with pytest.raises(ValueError, match='frozen'):
        LocalContrastScoreReader(StrictScoreGlyphReader(_templates()))
