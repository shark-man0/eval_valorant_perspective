import cv2
import numpy as np
import pytest

from valorant_ai_coach.visual.development_view import DevelopmentViewVeto


def test_stroke_match_suppresses_background_without_lowering_threshold(tmp_path):
    y, x = np.mgrid[:48, :48]
    reference = (20 + x * 2).astype(np.uint8)
    current = (30 + y * 3).astype(np.uint8)
    for image in (reference, current):
        cv2.circle(image, (24, 24), 12, 245, 2)
        cv2.line(image, (16, 30), (31, 15), 245, 2)
    path = tmp_path / 'glyph.png'
    cv2.imwrite(str(path), reference)
    frame = cv2.cvtColor(current, cv2.COLOR_GRAY2BGR)
    spec = {'mode': 'spectator_switch_v1', 'roi': [0, 0, 1, 1],
            'reference_frame_size_px': [64, 64], 'template_path': str(path)}
    # The authoring geometry is exact, and both images undergo the same resize.
    frame = cv2.resize(frame, (64, 64), interpolation=cv2.INTER_NEAREST)
    cv2.imwrite(str(path), cv2.resize(reference, (64, 64), interpolation=cv2.INTER_NEAREST))
    raw = DevelopmentViewVeto().inspect(frame, spec)
    shaped = DevelopmentViewVeto().inspect(frame, spec, feature_mode='positive_contrast_v1')
    assert raw['veto'] is False
    assert shaped['veto'] is True and shaped['similarity'] >= .90
    assert shaped['ownership'] == 'UNKNOWN'


def test_feature_switch_and_reference_change_do_not_mix_cached_pixels(tmp_path):
    rng = np.random.default_rng(31)
    image = rng.integers(0, 256, (64, 64, 3), np.uint8)
    path = tmp_path / 'pattern.png'
    cv2.imwrite(str(path), image)
    spec = {'mode': 'spectator_switch_v1', 'roi': [0, 0, 1, 1],
            'reference_frame_size_px': [64, 64], 'template_path': str(path)}
    engine = DevelopmentViewVeto()
    before = engine.inspect(image, spec)
    assert engine.inspect(image, spec, feature_mode='positive_contrast_v1')['veto'] is True
    assert engine.inspect(image, spec) == before
    cv2.imwrite(str(path), rng.integers(0, 256, (64, 64, 3), np.uint8))
    after = engine.inspect(image, spec, feature_mode='positive_contrast_v1')
    assert after['reference_sha256'] != before['reference_sha256']
    assert after == DevelopmentViewVeto().inspect(image, spec, feature_mode='positive_contrast_v1')
    path.unlink()
    missing = engine.inspect(image, spec, feature_mode='positive_contrast_v1')
    assert missing['status'] == 'unavailable'


@pytest.mark.parametrize('mode', ['unknown', None, [], {}])
def test_invalid_feature_mode_fails_closed(mode):
    result = DevelopmentViewVeto().inspect(np.zeros((64, 64, 3), np.uint8), {}, feature_mode=mode)
    assert result['status'] == 'unavailable' and result['veto'] is True
