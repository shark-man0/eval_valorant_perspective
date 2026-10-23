import cv2
import numpy as np

from valorant_ai_coach.visual.development_view import DevelopmentViewVeto


def test_veto_only_at_authored_location_and_no_positive_authorization(tmp_path):
    rng = np.random.default_rng(73)
    template = rng.integers(0, 256, (15, 51, 3), np.uint8)
    path = tmp_path/'switch.png'
    cv2.imwrite(str(path), template)
    frame = np.zeros((160, 320, 3), np.uint8)
    frame[110:125, 20:71] = template
    spec = {'mode': 'spectator_switch_v1', 'template_path': str(path),
            'reference_frame_size_px': [320, 160], 'roi': [0, .6, .3, .9]}
    veto = DevelopmentViewVeto()
    result = veto.inspect(frame, spec)
    assert result['status'] == 'spectator_ui' and result['veto'] is True
    assert result['ownership'] == 'UNKNOWN'
    fingerprint = result['reference_sha256']
    frame[:] = 0
    frame[10:25, 20:71] = template
    absent = veto.inspect(frame, spec)
    assert absent['status'] == 'not_detected' and absent['veto'] is False
    assert 'view_eligible' not in absent and 'identity' not in absent
    cv2.imwrite(str(path), rng.integers(0, 256, template.shape, np.uint8))
    assert veto.inspect(frame, spec)['reference_sha256'] != fingerprint
    path.unlink()
    assert veto.inspect(frame, spec)['veto'] is True
    assert veto.inspect(frame, None)['status'] == 'disabled'


def test_bad_config_is_unavailable_and_fail_closed():
    frame = np.zeros((160, 320, 3), np.uint8)
    for spec in [{}, [], {'mode': 'spectator_switch_v1', 'roi': [0, 0, 1, 1],
                         'reference_frame_size_px': [99999, 99999]}]:
        result = DevelopmentViewVeto().inspect(frame, spec)
        assert result['veto'] is True and result['status'] == 'unavailable'


def test_subpixel_authoring_roi_fails_closed_instead_of_asserting():
    frame = np.zeros((160, 320, 3), np.uint8)
    spec = {'mode': 'spectator_switch_v1', 'reference_frame_size_px': [64, 64],
            'roi': [0, 0, .005, .005]}
    result = DevelopmentViewVeto().inspect(frame, spec)
    assert result['veto'] is True and result['status'] == 'unavailable'


def test_invalid_frames_fail_closed_when_veto_configured():
    spec = {'mode': 'spectator_switch_v1'}
    for frame in [np.zeros((0, 0, 3), np.uint8), np.zeros((160, 320), np.uint8),
                  np.zeros((160, 320, 4), np.uint8), np.zeros((160, 320, 3), np.float32)]:
        result = DevelopmentViewVeto().inspect(frame, spec)
        assert result['veto'] is True and result['status'] == 'unavailable'
