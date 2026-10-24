import hashlib

import cv2
import numpy as np
import pytest

from valorant_ai_coach.maps.calibration import CalibrationResult
from valorant_ai_coach.visual.development_marker_proposals import DevelopmentMarkerProposals


def case(tmp_path):
    rng = np.random.default_rng(53)
    positive = rng.integers(0, 256, (17, 17, 3), dtype=np.uint8)
    negative = rng.integers(0, 256, (17, 17, 3), dtype=np.uint8)
    p, n = tmp_path / 'p.png', tmp_path / 'n.png'
    assert cv2.imwrite(str(p), positive) and cv2.imwrite(str(n), negative)
    frame = np.zeros((140, 160, 3), np.uint8)
    frame[20:37, 30:47] = positive
    frame[70:87, 90:107] = negative
    sample = {
        'source_id': 'source', 'source_sha256': 'a' * 64,
        'acquisition_id': 'epoch', 'native_epoch': 'epoch',
        'native_pts_tick': 100, 'native_time_base': '1/1000',
        'acquired_frame_sha256': 'b' * 64,
        'native_pixel_sha256': hashlib.sha256(frame.tobytes()).hexdigest(),
    }
    options = {
        'sample': sample, 'minimap_roi': [0., 0., 1., 1.], 'calibration_profile': {},
        'context_eligible': False,
        'appearance_pool': {'mode': 'appearance_pool_v1', 'libraries': [{
            'source_id': 'author', 'role': 'appearance_contrast_only',
            'matcher': {'mode': 'portrait_v2', 'positive_templates': [str(p)],
                        'negative_templates': [str(n)]}}]},
    }
    return frame, options, p


def test_both_reference_roles_survive_without_selecting_self(tmp_path, monkeypatch):
    frame, options, _ = case(tmp_path)
    engine = DevelopmentMarkerProposals('bind')
    engine.floor[:] = 255
    calibration = CalibrationResult('ok', 1., (0., 0., 1., 1.), 'synthetic', (),
                                    (1., 0., 0., 0., 1., 0.), (160, 140), (0., 0., 160., 140.))
    calls = []
    monkeypatch.setattr(engine.calibrator, 'analyze', lambda *a, **k: (
        calls.append(True) or calibration))
    result = engine.observe(frame, **options)
    assert len(result['proposals']) == 2
    assert {p['appearance_evidence']['reference_category'] for p in result['proposals']} == {
        'self_reference_appearance', 'nonself_control_appearance'}
    assert result['context_eligible'] is False
    assert result['selected_self_position'] is result['formal_self_position_fact'] is None
    assert result['development_events'] == result['track_segments'] == []
    for p in result['proposals']:
        assert p['geometry_only_map_position_norm'] is not None
        assert p['ownership'] == 'UNKNOWN' and p['map_position_norm'] is None
    engine.observe(frame, **options)
    assert len(calls) == 2  # No previous-frame transform reused.


def test_bad_frame_binding_and_missing_control_fail_closed(tmp_path):
    frame, options, _ = case(tmp_path)
    engine = DevelopmentMarkerProposals('bind')
    wrong = frame.copy()
    wrong[0, 0] = 1
    with pytest.raises(ValueError, match='pixels'):
        engine.observe(wrong, **options)
    options['appearance_pool']['libraries'][0]['matcher']['negative_templates'] = []
    with pytest.raises(ValueError, match='Invalid appearance library'):
        engine.observe(frame, **options)


def test_changed_reference_cannot_reuse_prior_proposals(tmp_path):
    frame, options, path = case(tmp_path)
    engine = DevelopmentMarkerProposals('bind')
    engine.observe(frame, **options)
    path.write_bytes(b'bad reference')
    with pytest.raises(ValueError, match='Invalid appearance library'):
        engine.observe(frame, **options)


def test_calibration_failure_leaves_only_roi_proposals(tmp_path, monkeypatch):
    frame, options, _ = case(tmp_path)
    engine = DevelopmentMarkerProposals('bind')
    monkeypatch.setattr(engine.calibrator, 'analyze', lambda *a, **k: CalibrationResult(
        'calibration_required', 0., None, 'synthetic', ('wrong_geometry',)))
    result = engine.observe(frame, **options)
    assert len(result['proposals']) == 2
    assert all(p['geometry_only_map_position_norm'] is None for p in result['proposals'])


def test_unknown_map_is_not_assigned(tmp_path):
    with pytest.raises(ValueError):
        DevelopmentMarkerProposals('unknown')


def test_floor_rejects_geometry_without_erasing_observed_appearance(tmp_path, monkeypatch):
    frame, options, _ = case(tmp_path)
    engine = DevelopmentMarkerProposals('bind')
    engine.floor[:] = 0
    monkeypatch.setattr(engine.calibrator, 'analyze', lambda *a, **k: CalibrationResult(
        'ok', 1., (0., 0., 1., 1.), 'synthetic', (),
        (1., 0., 0., 0., 1., 0.), (160, 140), (0., 0., 160., 140.)))
    result = engine.observe(frame, **options)
    assert len(result['proposals']) == 2
    assert all(p['geometry_reason'] == 'outside_visible_floor' for p in result['proposals'])
    assert all(p['geometry_only_map_position_norm'] is None for p in result['proposals'])
