import hashlib

import cv2
import numpy as np
import pytest

from valorant_ai_coach.maps.calibration import CalibrationResult
from valorant_ai_coach.visual.development_marker_attribution import freeze_native_sample
from valorant_ai_coach.visual.development_marker_detection import BoundedMarkerDetector
from valorant_ai_coach.visual.development_marker_quality import (
    DevelopmentQualityMarkerProposals,
    QualityMarkerDetector,
    ScreenedMarkerDetector,
    _FrameScreen,
)


def case(tmp_path):
    cv2.setNumThreads(1)
    rng = np.random.default_rng(743)
    refs = [rng.integers(0, 256, (17, 17, 3), np.uint8) for _ in range(2)]
    paths = [tmp_path/'positive.png', tmp_path/'control.png']
    for path, ref in zip(paths, refs, strict=True):
        assert cv2.imwrite(str(path), ref)
    crop = rng.integers(15, 70, (100, 120, 3), np.uint8)
    crop[20:37, 30:47] = refs[0]
    crop[60:77, 80:97] = refs[1]
    pool = {'mode': 'appearance_pool_v1', 'libraries': [{
        'source_id': 'synthetic', 'role': 'appearance_contrast_only',
        'matcher': {'mode': 'portrait_v2', 'positive_templates': [str(paths[0])],
                    'negative_templates': [str(paths[1])]}}]}
    return crop, pool, paths, refs


@pytest.mark.parametrize('noise', [0, 15, 30, 45, 60, 90, 160])
def test_screen_preserves_exact_evidence_with_different_signal_strengths(tmp_path, noise):
    crop, pool, _, _ = case(tmp_path)
    rng = np.random.default_rng(81)
    jitter = rng.integers(-noise, noise+1, crop.shape, np.int16)
    crop = np.clip(crop.astype(np.int16)+jitter, 0, 255).astype(np.uint8)
    old = BoundedMarkerDetector().detect(crop, pool)
    engine = ScreenedMarkerDetector()
    assert engine.detect(crop, pool) == old
    assert engine.screen.energy == {} and engine.screen.key is None
    assert engine.execution_evidence['numerical_backend_qualified'] is False


def test_integer_moments_equal_direct_masked_sums():
    rng = np.random.default_rng(5)
    crop = rng.integers(0, 256, (40, 50, 3), np.uint8)
    mask = np.zeros((17, 17), np.uint8)
    cv2.circle(mask, (8, 8), 6, 1, -1)
    cache = _FrameScreen()
    total, energy, count = cache.moments(crop, mask)
    for x, y in [(0, 0), (14, 12), (33, 23)]:
        pixels = crop[y:y+17, x:x+17][mask > 0].astype(np.int64)
        sums = pixels.sum(axis=0)
        np.testing.assert_array_equal(total[y, x], sums)
        assert energy[y, x] == count*(pixels*pixels).sum()-(sums*sums).sum()


def test_moments_invalidate_on_current_pixel_change():
    cache = _FrameScreen()
    mask = np.ones((9, 9), np.uint8)
    crop = np.zeros((30, 30, 3), np.uint8)
    first = cache.moments(crop, mask)[0].copy()
    crop[5, 5] = 100
    second = cache.moments(crop, mask)[0]
    assert not np.array_equal(first, second)
    assert cache.stats['energy_builds'] == 2


def test_screen_failure_falls_back_to_the_exact_inspector(tmp_path, monkeypatch):
    crop, pool, _, _ = case(tmp_path)
    expected = BoundedMarkerDetector().detect(crop, pool)
    engine = ScreenedMarkerDetector()

    def fail(*args):
        raise ValueError('uncertain screen')

    monkeypatch.setattr(engine.screen, 'possible', fail)
    assert engine.detect(crop, pool) == expected
    assert engine.screen.energy == {}


def test_invalid_input_clears_execution_and_moment_cache(tmp_path):
    crop, pool, _, _ = case(tmp_path)
    engine = ScreenedMarkerDetector()
    engine.detect(crop, pool)
    with pytest.raises(ValueError):
        engine.detect(crop, {})
    assert engine.execution_evidence == {} and engine.screen.energy == {}


@pytest.mark.parametrize('eligible', [False, True])
def test_quality_wrapper_keeps_raw_geometry_separate_from_player_positions(
    tmp_path, monkeypatch, eligible,
):
    crop, pool, _, _ = case(tmp_path)
    sample = freeze_native_sample({
        'source_id': 'source', 'source_sha256': 'a'*64, 'acquisition_id': 'epoch',
        'native_epoch': 'epoch', 'native_pts_tick': 100, 'native_time_base': '1/1000',
        'acquired_frame_sha256': 'b'*64,
        'native_pixel_sha256': hashlib.sha256(crop.tobytes()).hexdigest(),
    }, frame_size_px=(120, 100))
    engine = DevelopmentQualityMarkerProposals('bind')
    engine.floor[:] = 255
    monkeypatch.setattr(engine.calibrator, 'analyze', lambda *a, **k: CalibrationResult(
        'ok', 1., (0., 0., 1., 1.), 'synthetic', (),
        (1., 0., 0., 0., 1., 0.), (120, 100), (0., 0., 120., 100.)))
    result = engine.observe(crop, sample=sample, minimap_roi=[0., 0., 1., 1.],
                            appearance_pool=pool, calibration_profile={},
                            context_eligible=eligible)
    assert result['context_eligible'] is eligible
    assert any(p['geometry_only_map_position_norm'] for p in result['proposals'])
    assert all(p['map_position_norm'] is None and p['zone_resolution'] is None
               and p['version_compatibility'] == 'UNKNOWN' and p['ownership'] == 'UNKNOWN'
               for p in result['proposals'])
    assert result['selected_self_position'] is result['formal_self_position_fact'] is None
    assert result['track_segments'] == result['development_events'] == []


def geometry_result(crop, centers, kinds):
    return {'candidates': [
        {'kind': kind, 'center_roi_px': p, 'size_roi_px': [17, 17],
         'x_roi_norm': p[0]/crop.shape[1], 'y_roi_norm': p[1]/crop.shape[0],
         'qualification': 'development_only', 'ownership': 'UNKNOWN'}
        for p, kind in zip(centers, kinds, strict=True)],
        'roi_pixel_sha256': hashlib.sha256(crop.tobytes()).hexdigest(),
        'reference_fingerprint': 'synthetic', 'search_truncated': False,
        'selected_self_position': None, 'formal_self_position_fact': None}


def setup_geometry(monkeypatch, engine, circles):
    # Isolate association geometry; the integration tests below exercise real
    # reference and pixel verification rather than this synthetic verifier.
    monkeypatch.setattr(engine, 'verify', lambda *a: None)
    monkeypatch.setattr(cv2, 'HoughCircles', lambda *a, **k: np.array([circles], np.float32))
    monkeypatch.setattr(engine, '_circle_support', lambda *a: {'passed': True})


def test_one_circle_cannot_coalesce_two_nearby_observations(monkeypatch):
    engine = QualityMarkerDetector()
    crop = np.zeros((120, 120, 3), np.uint8)
    setup_geometry(monkeypatch, engine, [[62, 60, 8]])
    result = engine._refine(crop, {'libraries': []}, geometry_result(
        crop, [[60, 60], [64, 60]], ['chromatic_rim_circle']*2))
    assert [p['center_roi_px'] for p in result['candidates']] == [[60, 60], [64, 60]]
    assert result['center_refinements'] == []
    assert result['alt_search']['suppressed_nearby'][0]['same_physical_marker'] == 'UNKNOWN'


def test_unique_circle_refinement_does_not_shift_ncc_anchors(monkeypatch):
    engine = QualityMarkerDetector()
    crop = np.zeros((120, 120, 3), np.uint8)
    setup_geometry(monkeypatch, engine, [[61, 60, 8], [21, 20, 8]])
    result = engine._refine(crop, {'libraries': []}, geometry_result(
        crop, [[60.5, 60.5], [20, 20]], ['chromatic_rim_circle', 'ncc_appearance']))
    assert [p['center_roi_px'] for p in result['candidates']] == [[61., 60.], [20, 20]]
    assert len(result['center_refinements']) == 1
    assert all(p['ownership'] == 'UNKNOWN' for p in result['candidates'])


def test_alt_stage_is_bounded_and_does_not_drop_original_hypotheses(monkeypatch):
    engine = QualityMarkerDetector()
    crop = np.zeros((120, 120, 3), np.uint8)
    setup_geometry(monkeypatch, engine, [[80, 80, 8]]*140)
    result = engine._refine(crop, {'libraries': []}, geometry_result(
        crop, [[20, 20]], ['chromatic_rim_circle']))
    assert result['alt_search']['checked_count'] == 128
    assert result['search_truncated']
    assert result['candidates'][0]['center_roi_px'] == [20, 20]


@pytest.mark.parametrize('change', ['reference', 'pixels'])
def test_late_reference_or_pixel_change_invalidates_quality_observation(
    tmp_path, monkeypatch, change,
):
    crop, pool, paths, _ = case(tmp_path)
    engine = QualityMarkerDetector()

    def changed(*args, **kwargs):
        if args[1] == cv2.HOUGH_GRADIENT_ALT:
            if change == 'reference':
                paths[0].write_bytes(b'corrupt')
            else:
                crop[0, 0] = 255
        return None

    monkeypatch.setattr(cv2, 'HoughCircles', changed)
    with pytest.raises(ValueError):
        engine.detect(crop, pool)
    assert engine.last_evidence['reason'] == 'quality_observation_failed'
    assert engine.execution_evidence == {} and engine.screen.energy == {}
