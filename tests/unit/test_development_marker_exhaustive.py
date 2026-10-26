import copy
import hashlib

import cv2
import numpy as np
import pytest

from tests.unit.test_development_marker_quality import case
from valorant_ai_coach.maps.calibration import CalibrationResult
from valorant_ai_coach.visual.development_marker_attribution import freeze_native_sample
from valorant_ai_coach.visual.development_marker_exhaustive import (
    DevelopmentExhaustiveMarkerProposals,
    ExhaustiveMarkerDetector,
    _FrameCorrelations,
    _runtime_contract,
    _score_rows,
    observation_alternatives,
)
from valorant_ai_coach.visual.development_marker_quality import QualityMarkerDetector


def brute(image, ref, mask, x, y):
    a = image[y:y+len(ref), x:x+len(ref)][mask > 0].astype(np.float64)
    b = ref[mask > 0].astype(np.float64)
    a -= a.mean(axis=0)
    b -= b.mean(axis=0)
    den = np.sqrt((a*a).sum()*(b*b).sum())
    return float((a*b).sum()/den) if den else -1


@pytest.mark.parametrize('width', [9, 17, 65])
@pytest.mark.parametrize('signal', ['random', 'constant', 'low_variance', 'saturated'])
def test_every_window_matches_independent_centered_ncc(width, signal):
    rng = np.random.default_rng(372)
    image = rng.integers(0, 256, (width+5, width+6, 3), np.uint8)
    ref = rng.integers(0, 256, (width, width, 3), np.uint8)
    if signal == 'constant':
        image[:] = 87
    elif signal == 'low_variance':
        image[:] = 127
        image[3, 3] = 128
    elif signal == 'saturated':
        image[:] = 255
        image[3, 3] = 0
    mask = np.zeros((width, width), np.uint8)
    cv2.circle(mask, (width//2, width//2), round(width*.35), 1, -1)
    result = _score_rows(image, [ref], mask)[0]
    for y, x in np.ndindex(result.shape):
        assert result[y, x] == pytest.approx(brute(image, ref, mask, x, y), abs=1e-7)
    assert _runtime_contract()


def test_batch_planes_do_not_alias_integer_input_or_other_score_planes():
    rng = np.random.default_rng(37)
    image = rng.integers(0, 256, (70, 75, 3), np.uint8)
    refs = [rng.integers(0, 256, (17, 17, 3), np.uint8) for _ in range(12)]
    mask = np.ones((17, 17), np.uint8)
    results = _score_rows(image, refs, mask)
    for i, result in enumerate(results):
        assert result[12, 14] == pytest.approx(brute(image, refs[i], mask, 14, 12), abs=1e-7)
    results[0][:] = -1
    assert not np.all(results[1] == -1)


@pytest.mark.parametrize('condition', ['runtime', 'arithmetic'])
def test_unproven_conditions_use_original_full_search(tmp_path, monkeypatch, condition):
    crop, pool, _, _ = case(tmp_path)
    engine = ExhaustiveMarkerDetector()
    if condition == 'runtime':
        engine.correlations.valid = False
    else:
        def fail(*args):
            raise ValueError('unsupported arithmetic')
        monkeypatch.setattr('valorant_ai_coach.visual.development_marker_exhaustive._score_rows',
                            fail)
    original = QualityMarkerDetector()
    # Disable its approximate screen too, obtaining the original complete NCC.
    monkeypatch.setattr(original.screen, 'possible', lambda *args: True)
    expected = original.detect(crop, pool)
    actual = engine.detect(crop, pool)
    assert actual['candidates'] == expected['candidates']
    assert actual['ncc_observations'] == expected['ncc_observations']
    assert engine.execution_evidence['full_opencv_fallback_calls'] > 0
    assert engine.correlations.maps == engine.correlations.moments == {}
    assert engine.correlations.image is None


def test_noncontiguous_mask_falls_back_without_skipping_search():
    cache = _FrameCorrelations()
    image = np.zeros((70, 70, 3), np.uint8)
    ref = np.zeros((17, 17, 3), np.uint8)
    mask = np.ones((17, 17), np.uint8)
    mask[8, 8] = 0
    k = cache.key(ref, mask)
    cache.plan[k] = [(k, (ref, mask))]
    sentinel = np.ones((54, 54), np.float32)
    assert cache.get(image, ref, mask, lambda *args: sentinel) is sentinel
    assert cache.fallbacks == 1


def test_scale_library_and_circle_observations_are_not_forced_into_physical_markers():
    def point(x, kind='ncc_appearance', scale=1):
        return {'kind': kind, 'center_roi_px': [x, 30], 'size_roi_px': [17, 17],
                'scale': scale, 'library_index': 0}
    result = {'ncc_observations': [point(30), point(32, scale=.875), point(35)],
              'candidates': [point(30), point(35)],
              'circle_search': {'observations': [
                  {'center_roi_px': [33, 30], 'radius_px': 8, 'support': {'passed': True}}]},
              'alt_search': {'observations': []}}
    before = copy.deepcopy(result)
    got = observation_alternatives(result)
    assert result == before
    assert len(got['observations']) == 4
    assert all(x['relation'] == 'UNKNOWN' for x in got['links'])
    assert got['physical_marker_count'] is None
    assert any(len(x['canonical_indices']) == 2 for x in got['links'])
    # A death/normal display is not semantically resolved by geometry.
    assert all('role' not in x for x in got['observations'])


@pytest.mark.parametrize('change', ['reference', 'pixels', 'invalid_input'])
def test_caches_clear_and_no_stale_evidence_after_failure(tmp_path, monkeypatch, change):
    crop, pool, paths, _ = case(tmp_path)
    engine = ExhaustiveMarkerDetector()
    engine.detect(crop, pool)
    if change == 'invalid_input':
        pool = {}
    else:
        original = engine._refine

        def fail(*args):
            if change == 'reference':
                paths[0].write_bytes(b'corrupt')
            else:
                crop[0, 0] = 255
            return original(*args)
        monkeypatch.setattr(engine, '_refine', fail)
    with pytest.raises(ValueError):
        engine.detect(crop, pool)
    assert engine.correlations.maps == engine.correlations.moments == {}
    assert engine.correlations.image is None
    assert engine.execution_evidence == {}
    assert engine._fingerprint is None


@pytest.mark.parametrize('eligible', [False, True])
def test_raw_geometry_never_becomes_qualified_player_or_zone(tmp_path, monkeypatch, eligible):
    crop, pool, _, _ = case(tmp_path)
    sample = freeze_native_sample({
        'source_id': 'source', 'source_sha256': 'a'*64, 'acquisition_id': 'epoch',
        'native_epoch': 'epoch', 'native_pts_tick': 100, 'native_time_base': '1/1000',
        'acquired_frame_sha256': 'b'*64,
        'native_pixel_sha256': hashlib.sha256(crop.tobytes()).hexdigest(),
    }, frame_size_px=(120, 100))
    engine = DevelopmentExhaustiveMarkerProposals('bind')
    engine.floor[:] = 255
    monkeypatch.setattr(engine.calibrator, 'analyze', lambda *a, **k: CalibrationResult(
        'ok', 1., (0., 0., 1., 1.), 'synthetic', (),
        (1., 0., 0., 0., 1., 0.), (120, 100), (0., 0., 120., 100.)))
    result = engine.observe(crop, sample=sample, minimap_roi=[0., 0., 1., 1.],
                            appearance_pool=pool, calibration_profile={},
                            context_eligible=eligible)
    assert any(p['geometry_only_map_position_norm'] for p in result['proposals'])
    assert all(p['ownership'] == 'UNKNOWN' and p['map_position_norm'] is None
               and p['zone_resolution'] is None and p['version_compatibility'] == 'UNKNOWN'
               for p in result['proposals'])
    assert result['formal_self_position_fact'] is result['selected_self_position'] is None
    assert result['development_events'] == result['track_segments'] == []
    alternatives = result['detector_evidence']['observation_alternatives']
    assert alternatives['physical_equivalence'] == 'UNKNOWN'
