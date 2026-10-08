from __future__ import annotations

from copy import deepcopy

import cv2
import numpy as np
import pytest

from tests.unit.test_timer_glyphs import _profile, _save_profile_assets, _templates
from valorant_ai_coach.hud.score_glyphs import (
    StrictScoreGlyphReader,
    UnavailableStrictScoreGlyphReader,
)
from valorant_ai_coach.hud.templates import SubregionReader


def render(text):
    templates = _templates()
    field = np.zeros((48, 76), np.uint8)
    for index, digit in enumerate(text):
        ref = templates[digit][0]
        x, y, width, height = cv2.boundingRect(cv2.findNonZero(ref))
        glyph = ref[y:y + height, x:x + width]
        field[11:11 + height, 5 + index * 24:5 + index * 24 + width] = glyph
    return field


@pytest.mark.parametrize('text', ['0', '1', '2', '7', '9', '10', '12', '99'])
def test_score_source_display_and_minimum_confidence_preserved(text):
    image = render(text)
    reader = StrictScoreGlyphReader(_templates(), comparison_preprocessing='gaussian3x3_v1')
    result = reader.read(image, image)
    assert result.value == text
    assert result.confidence >= .90
    assert result.sources == ('strict_score_glyphs', 'comparison_gaussian3x3_v1')
    assert result.cross_checked is False
    assert reader.THRESHOLD == .90 and reader.CLASS_MARGIN == .04


@pytest.mark.parametrize('case', [
    'blank', 'dot', 'leading_zero', 'three_digits', 'clipped', 'inverted',
    'float', 'channels', 'layout',
])
def test_invalid_structure_is_unknown_without_ocr_or_value_completion(case):
    image = render('1')
    if case == 'blank':
        image[:] = 0
    elif case == 'dot':
        image[35:38, 60:63] = 255
    elif case == 'leading_zero':
        image = render('01')
    elif case == 'three_digits':
        image = render('123')
    elif case == 'clipped':
        image = image[:, 7:]
    elif case == 'inverted':
        image = 255 - image
    elif case == 'float':
        image = image.astype(np.float32)
    elif case == 'channels':
        image = np.zeros((48, 76, 4), np.uint8)
    else:
        image = render('12')
        image[:, 29:50] = np.roll(image[:, 29:50], 10, axis=0)
    result = StrictScoreGlyphReader(_templates()).read(image, image)
    assert result.value is None and result.confidence == 0
    assert result.sources[0].startswith('strict_score_')


def test_missing_class_and_ambiguous_competitors_cannot_be_removed():
    templates = _templates()
    del templates['9']
    with pytest.raises(ValueError, match='exactly digits'):
        StrictScoreGlyphReader(templates)
    templates = deepcopy(_templates())
    templates['9'] = templates['1']
    image = render('1')
    result = StrictScoreGlyphReader(templates).read(image, image)
    assert result.value is None
    assert result.sources == ('strict_score_glyph_competitor_gap_below_0_04',)


@pytest.mark.parametrize('roi', ['ally_score', 'enemy_score'])
def test_opt_in_profile_loads_score_assets_and_subregion(tmp_path, roi):
    templates = _save_profile_assets(tmp_path)
    profile = _profile(tmp_path, roi_name=roi, kind='strict_score_glyphs', templates=templates,
                       subregion_norm=[0, 0, 1, 1])
    reader = profile.build_readers()[roi]
    assert isinstance(reader, SubregionReader)
    image = render('2')
    assert reader.read(image, image).value == '2'
    assert not profile.reader_diagnostics


@pytest.mark.parametrize('spec', [
    {'glyph_threshold': .89}, {'glyph_margin': .03}, {'glyph_threshold': True},
    {'comparison_preprocessing': 'unsupported'}, {'templates': {}},
])
def test_invalid_explicit_score_profile_stays_present_and_fails_closed(tmp_path, spec):
    args = {'kind': 'strict_score_glyphs', 'templates': _save_profile_assets(tmp_path), **spec}
    profile = _profile(tmp_path, roi_name='enemy_score', **args)
    reader = profile.build_readers()['enemy_score']
    assert isinstance(reader, UnavailableStrictScoreGlyphReader)
    image = render('2')
    assert reader.read(image, image).value is None
    assert profile.reader_diagnostics


def test_score_reader_cannot_supply_hp_or_timer_role(tmp_path):
    profile = _profile(tmp_path, roi_name='player_hp_armor', kind='strict_score_glyphs',
                       templates=_save_profile_assets(tmp_path))
    assert isinstance(profile.build_readers()['player_hp_armor'], UnavailableStrictScoreGlyphReader)


@pytest.mark.parametrize('text', ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', '12', '99'])
def test_fixed_white_foreground_does_not_depend_on_numeric_class(text):
    source = render(text)
    image = np.tile(np.linspace(110, 175, source.shape[1], dtype=np.uint8), (48, 1))
    image[source > 0] = 255
    reader = StrictScoreGlyphReader(_templates(), comparison_preprocessing='gaussian3x3_v1',
                                    foreground_preprocessing='white200_v1')
    result = reader.read(image, image)
    assert result.value == text
    assert result.confidence >= .90
    assert result.sources[-1] == 'foreground_white200_v1'


@pytest.mark.parametrize('case', ['dim_text', 'bright_background', 'extra_dot', 'clipped'])
def test_white_foreground_does_not_retry_or_bypass_structural_rejection(case):
    image = render('1')
    if case == 'dim_text':
        image[image > 0] = 190
    elif case == 'bright_background':
        image[image == 0] = 225
    elif case == 'extra_dot':
        image[35:38, 60:63] = 255
    else:
        image = image[:, 7:]
    result = StrictScoreGlyphReader(_templates(), foreground_preprocessing='white200_v1').read(
        image, image,
    )
    assert result.value is None and result.confidence == 0


@pytest.mark.parametrize('invalid', [None, True, 199, 'white180_v1', [], {}])
def test_foreground_mode_cannot_be_arbitrarily_tuned(invalid):
    with pytest.raises(ValueError, match='foreground preprocessing'):
        StrictScoreGlyphReader(_templates(), foreground_preprocessing=invalid)


def test_profile_foreground_mode_is_explicit_and_invalid_mode_fails_closed(tmp_path):
    assets = _save_profile_assets(tmp_path)
    profile = _profile(tmp_path, roi_name='ally_score', kind='strict_score_glyphs',
                       templates=assets, foreground_preprocessing='white200_v1')
    reader = profile.build_readers()['ally_score']
    assert reader.foreground_preprocessing == 'white200_v1'
    bad = _profile(tmp_path, roi_name='ally_score', kind='strict_score_glyphs',
                   templates=assets, foreground_preprocessing='white180_v1')
    assert isinstance(bad.build_readers()['ally_score'], UnavailableStrictScoreGlyphReader)
