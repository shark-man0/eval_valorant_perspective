"""Segmentation and unchanged production mask controls; not real qualification."""
import cv2
import numpy as np
import pytest

from scripts.diagnostics.score_enlarged_background import EnlargedBackgroundScoreReader
from tests.unit.test_timer_glyphs import _templates
from valorant_ai_coach.hud.score_glyphs import StrictScoreGlyphReader


@pytest.mark.parametrize('preprocessing', ['white200_v1', 'otsu_v1'])
def test_default_mask_remains_exact_opencv_threshold(preprocessing):
    reader = StrictScoreGlyphReader(_templates(), foreground_preprocessing=preprocessing)
    image = np.random.default_rng(29).integers(0, 256, (90, 88), dtype=np.uint8)
    expected = cv2.threshold(image, 200 if preprocessing == 'white200_v1' else 0,
                             255, cv2.THRESH_BINARY if preprocessing == 'white200_v1'
                             else cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
    assert np.array_equal(reader._foreground_mask(image), expected)


def test_dim_background_does_not_change_interpolated_foreground():
    native = np.full((45, 44), 75, np.uint8)
    native[12:32, 20:23] = 255
    enlarged = cv2.resize(native, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    reader = EnlargedBackgroundScoreReader(_templates(),
                                          foreground_preprocessing='white200_v1',
                                          comparison_preprocessing='gaussian3x3_v1')
    assert np.array_equal(reader._foreground_mask(enlarged),
                          cv2.threshold(enlarged, 200, 255, cv2.THRESH_BINARY)[1])
    assert set(reader.templates) == set('0123456789')
    assert reader.THRESHOLD == .90 and reader.CLASS_MARGIN == .04


def test_uniform_bright_scene_never_becomes_a_digit():
    reader = EnlargedBackgroundScoreReader(_templates(),
                                          foreground_preprocessing='white200_v1',
                                          comparison_preprocessing='gaussian3x3_v1')
    roi = np.full((45, 44), 240, np.uint8)
    assert reader.read(roi, roi).value is None


def test_opt_in_production_mask_matches_frozen_diagnostic_and_records_provenance():
    production = StrictScoreGlyphReader(_templates(),
                                       foreground_preprocessing='white200_rowcontrast_v1',
                                       comparison_preprocessing='gaussian3x3_v1')
    diagnostic = EnlargedBackgroundScoreReader(_templates(),
                                              foreground_preprocessing='white200_v1',
                                              comparison_preprocessing='gaussian3x3_v1')
    image = np.random.default_rng(87).integers(0, 256, (90, 88), dtype=np.uint8)
    assert np.array_equal(production._foreground_mask(image), diagnostic._foreground_mask(image))
    from tests.unit.test_score_glyphs import render
    for digit in '0123456789':
        roi = render(digit)
        result = production.read(roi, roi)
        expected = diagnostic.read(roi, roi)
        assert (result.value, result.confidence) == (expected.value, expected.confidence)
        if result.value is not None:
            assert result.sources[-1] == 'foreground_white200_rowcontrast_v1'
        else:
            assert result.sources == expected.sources
    with pytest.raises(ValueError, match='requires gaussian'):
        StrictScoreGlyphReader(_templates(), foreground_preprocessing='white200_rowcontrast_v1')


@pytest.mark.parametrize('role', ['ally_score', 'enemy_score'])
def test_profile_routes_opt_in_mode_without_affecting_default(tmp_path, role):
    from tests.unit.test_timer_glyphs import _profile, _save_profile_assets
    profile = _profile(tmp_path, roi_name=role, kind='strict_score_glyphs',
                       templates=_save_profile_assets(tmp_path), subregion_norm=[0, 0, 1, 1],
                       foreground_preprocessing='white200_rowcontrast_v1',
                       comparison_preprocessing='gaussian3x3_v1')
    reader = profile.build_readers()[role]
    assert reader.reader.foreground_preprocessing == 'white200_rowcontrast_v1'
    assert not profile.reader_diagnostics
    assert StrictScoreGlyphReader(_templates()).foreground_preprocessing == 'otsu_v1'
