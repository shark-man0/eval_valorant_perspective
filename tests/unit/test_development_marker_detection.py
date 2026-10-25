import copy
import hashlib

import cv2
import numpy as np
import pytest

from valorant_ai_coach.maps.calibration import CalibrationResult
from valorant_ai_coach.visual.development_marker_attribution import freeze_native_sample
from valorant_ai_coach.visual.development_marker_detection import (
    BoundedMarkerDetector,
    DevelopmentDetectedMarkerProposals,
)


def example(tmp_path, *, bandlimited=False):
    cv2.setNumThreads(1)
    rng = np.random.default_rng(97)
    p = rng.integers(0, 256, (17, 17, 3), np.uint8)
    n = rng.integers(0, 256, (17, 17, 3), np.uint8)
    if bandlimited:
        # Test coordinate recovery with retained image information. Arbitrary
        # high-frequency texture destroyed by downsampling cannot be restored.
        p = cv2.GaussianBlur(p, (3, 3), .7)
        n = cv2.GaussianBlur(n, (3, 3), .7)
    positive, negative = tmp_path/'p.png', tmp_path/'n.png'
    cv2.imwrite(str(positive), p)
    cv2.imwrite(str(negative), n)
    crop = np.zeros((140, 160, 3), np.uint8)
    crop[20:37, 30:47] = p
    crop[70:87, 90:107] = n
    spec = {'mode': 'appearance_pool_v1', 'libraries': [{
        'source_id': 'author', 'role': 'appearance_contrast_only',
        'matcher': {'mode': 'portrait_v2', 'positive_templates': [str(positive)],
                    'negative_templates': [str(negative)]}}]}
    return crop, spec, positive


def contains(candidates, xy, tolerance=.001):
    return any(np.linalg.norm(np.asarray(p['center_roi_px'])-xy) < tolerance for p in candidates)


def test_positive_and_control_appearances_are_equal_unassigned_anchors(tmp_path):
    crop, spec, _ = example(tmp_path)
    result = BoundedMarkerDetector().detect(crop, spec)
    assert contains(result['candidates'], [38, 28])
    assert contains(result['candidates'], [98, 78])
    assert result['native_groups'] == 2
    assert result['selected_self_position'] is result['formal_self_position_fact'] is None
    assert all(p['ownership'] == 'UNKNOWN' for p in result['candidates'])


@pytest.mark.parametrize('scale', [.75, 1.25])
def test_normalizing_a_supported_scale_can_restore_a_visible_marker(tmp_path, scale):
    crop, spec, _ = example(tmp_path, bandlimited=True)
    scaled = cv2.resize(crop, None, fx=scale, fy=scale,
                        interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR)
    result = BoundedMarkerDetector().detect(scaled, spec)
    expected = [(38+.5)*scale-.5, (28+.5)*scale-.5]
    assert contains(result['candidates'], expected, 2.)


def test_duplicate_libraries_do_not_multiply_output_markers(tmp_path):
    crop, spec, _ = example(tmp_path)
    single = BoundedMarkerDetector().detect(crop, spec)
    spec['libraries'].append(copy.deepcopy(spec['libraries'][0]))
    doubled = BoundedMarkerDetector().detect(crop, spec)
    assert [p['center_roi_px'] for p in single['candidates']] == [
        p['center_roi_px'] for p in doubled['candidates']]
    assert doubled['duplicates_removed'] >= single['duplicates_removed']


def test_reference_change_invalidates_saved_fingerprint(tmp_path):
    crop, spec, path = example(tmp_path)
    engine = BoundedMarkerDetector()
    result = engine.detect(crop, spec)
    path.write_bytes(b'broken')
    with pytest.raises(ValueError, match='Reference changed'):
        engine.verify(spec['libraries'], result['reference_fingerprint'])
    assert engine.last_evidence['reason'] == 'reference_changed'


def test_corrupt_bank_cannot_reuse_previous_candidates(tmp_path):
    crop, spec, _ = example(tmp_path)
    engine = BoundedMarkerDetector()
    engine.detect(crop, spec)
    with pytest.raises(ValueError):
        engine.detect(crop, {})
    assert engine.last_evidence['reason'] == 'invalid_input'
    assert 'candidates' not in engine.last_evidence


def test_scaled_roi_budget_is_explicit(tmp_path):
    _, spec, _ = example(tmp_path)
    result = BoundedMarkerDetector().detect(np.zeros((800, 1000, 3), np.uint8), spec)
    assert result['search_truncated']
    assert any(p.get('reason') == 'scaled_roi_bound' for p in result['scale_passes'])
    with pytest.raises(ValueError, match='Bounded'):
        BoundedMarkerDetector().detect(np.zeros((1200, 1200, 3), np.uint8), spec)


def test_circle_search_budget_is_not_silently_dropped(tmp_path, monkeypatch):
    crop, spec, _ = example(tmp_path)
    monkeypatch.setattr(cv2, 'HoughCircles', lambda *a, **k: np.array(
        [[[40., 40., 7.]]*140], np.float32))
    result = BoundedMarkerDetector().detect(crop, spec)
    assert result['circle_search']['checked_count'] == 128
    assert result['circle_search']['raw_count'] == 140
    assert result['search_truncated']


def test_blocked_context_never_promotes_proposal_geometry(tmp_path, monkeypatch):
    crop, spec, _ = example(tmp_path)
    sample = freeze_native_sample({
        'source_id': 'source', 'source_sha256': 'a'*64, 'acquisition_id': 'epoch',
        'native_epoch': 'epoch', 'native_pts_tick': 100, 'native_time_base': '1/1000',
        'acquired_frame_sha256': 'b'*64,
        'native_pixel_sha256': hashlib.sha256(crop.tobytes()).hexdigest(),
    }, frame_size_px=(160, 140))
    engine = DevelopmentDetectedMarkerProposals('bind')
    engine.floor[:] = 255
    monkeypatch.setattr(engine.calibrator, 'analyze', lambda *a, **k: CalibrationResult(
        'ok', 1., (0., 0., 1., 1.), 'synthetic', (),
        (1., 0., 0., 0., 1., 0.), (160, 140), (0., 0., 160., 140.)))
    result = engine.observe(crop, sample=sample, minimap_roi=[0., 0., 1., 1.],
                            appearance_pool=spec, calibration_profile={}, context_eligible=False)
    assert result['proposals'] and result['context_eligible'] is False
    assert any(p['geometry_only_map_position_norm'] for p in result['proposals'])
    assert all(p['map_position_norm'] is None and p['version_compatibility'] == 'UNKNOWN'
               for p in result['proposals'])
    assert result['selected_self_position'] is result['formal_self_position_fact'] is None
    assert result['track_segments'] == result['development_events'] == []


@pytest.mark.parametrize('rim_color', [(20, 230, 230), (230, 230, 20), (30, 40, 240)])
def test_unseen_textured_circle_is_a_candidate_without_an_identity(tmp_path, rim_color):
    crop, spec, _ = example(tmp_path)
    center = (58, 108)
    yy, xx = np.indices(crop.shape[:2])
    inside = np.hypot(xx-center[0], yy-center[1]) <= 6
    rng = np.random.default_rng(191)
    crop[inside] = rng.integers(20, 230, (int(inside.sum()), 3), np.uint8)
    cv2.circle(crop, center, 8, rim_color, 2)
    result = BoundedMarkerDetector().detect(crop, spec)
    proposals = [p for p in result['candidates'] if np.linalg.norm(
        np.asarray(p['center_roi_px'])-center) <= 2]
    assert proposals and any(p['kind'] == 'chromatic_rim_circle' for p in proposals)
    assert all(p['ownership'] == 'UNKNOWN' for p in proposals)


def test_colored_circle_without_inner_texture_is_not_a_shape_candidate(tmp_path):
    crop, spec, _ = example(tmp_path)
    cv2.circle(crop, (58, 108), 8, (20, 230, 230), 2)
    result = BoundedMarkerDetector().detect(crop, spec)
    assert not any(p['kind'] == 'chromatic_rim_circle' and np.linalg.norm(
        np.asarray(p['center_roi_px'])-[58, 108]) <= 2 for p in result['candidates'])


def test_missing_image_does_not_coast_previous_candidates(tmp_path):
    crop, spec, _ = example(tmp_path)
    engine = BoundedMarkerDetector()
    assert engine.detect(crop, spec)['candidates']
    result = engine.detect(np.zeros_like(crop), spec)
    assert result['candidates'] == []
    assert result['selected_self_position'] is None


def test_forged_recorder_fields_cannot_assign_candidates(tmp_path):
    crop, spec, _ = example(tmp_path)
    spec.update(ownership='SELF', recorder_agent='declared', view_state='live_first_person')
    result = BoundedMarkerDetector().detect(crop, spec)
    assert 'recorder_agent' not in result and 'view_state' not in result
    assert result['ownership'] == 'UNKNOWN'
    assert all(p['ownership'] == 'UNKNOWN' for p in result['candidates'])
    assert result['selected_self_position'] is None and result['development_events'] == []
