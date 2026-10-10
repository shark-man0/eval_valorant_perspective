"""Synthetic segmentation controls; not independent real-image qualification."""
import numpy as np
import pytest

from scripts.diagnostics.score_border_background import (
    BorderBackgroundScoreReader,
    separate_background,
)
from tests.unit.test_timer_glyphs import _templates
from valorant_ai_coach.hud.score_glyphs import StrictScoreGlyphReader


def test_bright_row_removed_without_eroding_supported_strokes():
    gray = np.full((40, 44), 50, np.uint8)
    gray[30:] = 230
    gray[10:28, 20:23] = 255
    before = gray.copy()
    separated = separate_background(gray)
    assert np.array_equal(gray, before)
    assert np.all(separated[30:] == 0)
    assert np.all(separated[10:28, 20:23] == 255)
    assert np.count_nonzero(separated) == 18 * 3


@pytest.mark.parametrize('roi', [np.zeros((40, 44), np.uint8),
                               np.full((40, 44), 230, np.uint8),
                               np.zeros((4, 4), np.uint8),
                               np.zeros((40, 44, 4), np.uint8),
                               np.full((40, 44), .5, np.float32)])
def test_absent_or_invalid_support_never_fills_score(roi):
    reader = BorderBackgroundScoreReader(StrictScoreGlyphReader(
        _templates(), comparison_preprocessing='gaussian3x3_v1',
        foreground_preprocessing='white200_v1',
    ))
    assert reader.read(roi, roi).value is None
    assert set(reader.reader.templates) == set('0123456789')
    assert reader.reader.THRESHOLD == .90 and reader.reader.CLASS_MARGIN == .04
