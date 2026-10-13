import hashlib

import cv2
import numpy as np
import pytest

from tests.unit.test_result_structure_diagnostic import text_image
from valorant_ai_coach.hud.glyph_contrast import GlyphContrastGuard
from valorant_ai_coach.hud.semantic_text import SemanticTextReference


def semantic_reference(image, guard=None):
    # Synthetic transport/control fixture, never real source qualification.
    foreground = (image > 210).astype(np.uint8)*255
    mask = cv2.dilate(foreground, np.ones((3, 3), np.uint8))
    regions = np.zeros_like(mask)
    for group, part in enumerate(np.array_split(np.arange(image.shape[1]), 4), 1):
        regions[:, part] = np.where(mask[:, part] > 0, group, 0)
    training = [(hashlib.sha256(str(i).encode()).hexdigest(), image.copy()) for i in range(3)]
    return SemanticTextReference(image, mask, regions, training, .9, contrast_guard=guard)


def test_guard_retains_every_glyph_and_negative_space_without_reading_owned_values():
    image = text_image()
    guard = GlyphContrastGuard(image)
    measured = guard.measure(image)
    assert len(measured['glyphs']) == 7
    assert guard.score(image) == pytest.approx(1)
    assert all(g['foreground_population'] >= 32 and g['negative_space_population'] >= 32
               and g['polarity_positive'] for g in measured['glyphs'])
    for ref, fg, bg, masks in guard.parts:
        assert np.count_nonzero(fg & bg) == 0
        covered = np.zeros(ref.shape, bool)
        for mask in masks:
            selected = (mask > 0) & ~fg
            assert np.count_nonzero(selected) >= 32
            assert not np.any(covered & selected)
            covered |= selected
        assert np.array_equal(covered, bg)


def test_extra_stroke_confusable_and_blank_fail_guard():
    guard = GlyphContrastGuard(text_image())
    assert guard.score(text_image('TEAM AGE')) < .9
    assert guard.score(np.full_like(text_image(), 25)) == 0


def test_local_contrast_is_not_an_opaque_white_current_pixel_assumption():
    image = text_image()
    guard = GlyphContrastGuard(image)
    # Affine lighting changes preserve geometry and relative contrast.
    changed = (image.astype(np.float64)*.6+30).astype(np.uint8)
    assert changed.max() < 210
    assert guard.score(changed) >= .9


def test_optional_guard_preserves_default_and_conjoins_measure_score():
    image = text_image()
    plain = semantic_reference(image)
    guarded = semantic_reference(image, GlyphContrastGuard(image))
    assert plain.score(image) == pytest.approx(1)
    assert guarded.score(image) == pytest.approx(1)
    assert 'contrast_guard' not in plain.measure(image)
    for actual in [image, text_image('TEAM AGE'), np.full_like(image, 25)]:
        measured = guarded.measure(actual)
        assert measured['score'] == guarded.score(actual)
        assert measured['runtime_transition_authorized'] is False
        assert measured['absence_checked'] is False
        assert guarded.score(actual) <= plain.score(actual)
    assert guarded.measure(text_image('TEAM AGE'))['presence'] is None


@pytest.mark.parametrize('reference', [np.zeros((10, 10), np.uint8),
                                       np.zeros((0, 10), np.uint8),
                                       np.zeros((10, 10, 3), np.uint8),
                                       np.zeros((10, 10), np.float32)])
def test_invalid_reference_fails_closed(reference):
    with pytest.raises(ValueError, match='glyph contrast'):
        GlyphContrastGuard(reference)


@pytest.mark.parametrize('image', [np.zeros((3, 3), np.uint8),
                                  np.zeros((90, 360), np.float32),
                                  np.zeros((90, 360, 4), np.uint8)])
def test_invalid_current_image_is_unknown(image):
    assert GlyphContrastGuard(text_image()).score(image) == 0


def test_guard_reference_copied_and_semantic_shape_mismatch_rejected():
    image = text_image()
    guard = GlyphContrastGuard(image)
    image[:] = 0
    assert guard.score(text_image()) == pytest.approx(1)
    with pytest.raises(ValueError, match='guard shape'):
        semantic_reference(text_image(), GlyphContrastGuard(text_image()[:, :-1]))


def test_combined_training_support_cannot_ignore_guard_rejections():
    image = text_image('TEAM AGE')
    # The word reference itself matches, but guarded glyphs disagree.
    with pytest.raises(ValueError, match='training support'):
        semantic_reference(image, GlyphContrastGuard(text_image()))


def write_profile(tmp_path, *, guard_method='glyph_local_contrast_v1', role='round_end_template'):
    import json

    from valorant_ai_coach.hud.templates import HudTemplateProfile

    image = text_image()
    foreground = (image > 210).astype(np.uint8)*255
    mask = cv2.dilate(foreground, np.ones((3, 3), np.uint8))
    regions = np.zeros_like(mask)
    for group, part in enumerate(np.array_split(np.arange(image.shape[1]), 4), 1):
        regions[:, part] = np.where(mask[:, part] > 0, group, 0)
    for name, value in [('word', image), ('mask', mask), ('regions', regions), ('guard', image)]:
        assert cv2.imwrite(str(tmp_path / f'{name}.png'), value)
    spec = {
        'matcher': 'semantic_text_ncc_v1',
        'roi': 'round_end_banner' if role == 'round_end_template' else 'center_phase_banner',
        'roi_bounds': [0, 0, 1, 1], 'template': 'word.png', 'mask': 'mask.png',
        'support_regions': 'regions.png', 'threshold': .9,
        'training': [{'template': 'word.png',
                      'frame_sha256': hashlib.sha256(str(i).encode()).hexdigest()}
                     for i in range(3)],
        'contrast_guard': {'method': guard_method, 'template': 'guard.png'},
    }
    path = tmp_path / 'profile.json'
    path.write_text(json.dumps({'schema_version': '1.0', 'anchors': {}, 'signals': {role: spec}}))
    return HudTemplateProfile.load(path)


def test_profile_loads_opt_in_guard_and_hashes_its_asset(tmp_path):
    profile = write_profile(tmp_path)
    assert not profile.reader_diagnostics
    model = profile._semantic_text['round_end_template']
    assert model.contrast_guard is not None
    assert model.score(text_image('TEAM AGE')) < .9
    layout = tmp_path / 'layout.json'
    layout.write_text('{}')
    previous = profile.fingerprint(layout)
    path = tmp_path / 'guard.png'
    path.write_bytes(path.read_bytes()+b'changed')
    assert profile.fingerprint(layout) != previous


@pytest.mark.parametrize('role,method', [('round_end_template', 'untrusted_method'),
                                        ('buy_phase_template', 'glyph_local_contrast_v1')])
def test_invalid_guard_cannot_fall_back_to_unguarded_word(tmp_path, role, method):
    profile = write_profile(tmp_path, role=role, guard_method=method)
    assert role not in profile._semantic_text
    assert role not in profile._signal_templates
    assert any('contrast guard specification' in d for d in profile.reader_diagnostics)


def test_nonsemantic_matcher_cannot_ignore_requested_guard(tmp_path):
    import json

    from valorant_ai_coach.hud.templates import HudTemplateProfile

    write_profile(tmp_path)
    path = tmp_path / 'profile.json'
    raw = json.loads(path.read_text())
    raw['signals']['round_end_template']['matcher'] = 'plain_pixels'
    path.write_text(json.dumps(raw))
    profile = HudTemplateProfile.load(path)
    assert 'round_end_template' not in profile._signal_templates
    assert any('requires the semantic matcher' in d for d in profile.reader_diagnostics)
