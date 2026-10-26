import hashlib

import cv2
import numpy as np
import pytest

from tests.unit.test_development_marker_quality import case
from valorant_ai_coach.maps.calibration import CalibrationResult
from valorant_ai_coach.visual.development_marker_attribution import freeze_native_sample
from valorant_ai_coach.visual.development_marker_cross import (
    CrossAppearanceProfile,
    CrossMarkerDetector,
    DevelopmentCrossMarkerProposals,
    _append_observations,
    _shape_options,
    cross_observations,
)
from valorant_ai_coach.visual.development_marker_exhaustive import ExhaustiveMarkerDetector

PROFILE = {'mode': 'unassigned_cross_shape_v1', 'hue_center': 120,
           'hue_tolerance': 12, 'saturation_min': 80, 'value_min': 50}


def paint(image, center, kind='cross'):
    x, y = center
    color = (255, 0, 0)
    if kind == 'cross':
        cv2.line(image, (x-5, y-5), (x+5, y+5), color, 2)
        cv2.line(image, (x+5, y-5), (x-5, y+5), color, 2)
    elif kind == 'plus':
        cv2.line(image, (x-6, y), (x+6, y), color, 2)
        cv2.line(image, (x, y-6), (x, y+6), color, 2)
    elif kind == 'ring':
        cv2.circle(image, center, 6, color, 2)
    elif kind == 'arrow':
        cv2.polylines(image, [np.array([[x-6, y-5], [x, y+5], [x+6, y-5]])],
                      False, color, 2)
    else:
        cv2.rectangle(image, (x-6, y-6), (x+6, y+6), color, -1)


@pytest.mark.parametrize('kind', ['cross', 'plus', 'ring', 'arrow', 'solid'])
def test_color_alone_does_not_authenticate_a_cross_or_player(kind):
    crop = np.zeros((100, 120, 3), np.uint8)
    paint(crop, (40, 40), kind)
    got = cross_observations(crop, CrossAppearanceProfile.parse(PROFILE))
    assert len(got['observations']) == (1 if kind == 'cross' else 0)
    assert got['ownership'] == got['semantic_marker_class'] == 'UNKNOWN'
    for p in got['observations']:
        assert np.linalg.norm(np.array(p['center_roi_px'])-[40, 40]) <= 1
        assert p['candidate_kind'] == 'unassigned_cross_appearance'
        assert p['physical_marker_count'] is None
        assert len(p['center_hypotheses']) == 25


def test_disconnected_cross_components_are_not_merged():
    crop = np.zeros((100, 120, 3), np.uint8)
    paint(crop, (40, 40))
    paint(crop, (55, 40))
    got = cross_observations(crop, CrossAppearanceProfile.parse(PROFILE))
    assert len(got['observations']) == 2
    assert len({p['component_index'] for p in got['observations']}) == 2
    assert all(p['ownership'] == 'UNKNOWN' for p in got['observations'])


@pytest.mark.parametrize('distance', [2, 3, 4, 5])
def test_near_ncc_and_cross_measurements_remain_separate_unknowns(distance):
    result = {'candidates': [{'kind': 'ncc_appearance', 'center_roi_px': [30, 30],
                              'size_roi_px': [17, 17]}], 'search_truncated': False}
    search = {'observations': [{'kind': 'chromatic_cross_shape',
                               'center_roi_px': [30+distance, 30], 'size_roi_px': [17, 17]}],
              'truncated': False}
    _append_observations(result, search)
    assert len(result['candidates']) == 2
    assert result['candidates'][0]['center_roi_px'] == [30, 30]
    assert result['cross_associations'][0]['relation'] == 'UNKNOWN'


def test_combined_output_budget_keeps_unemitted_observation_evidence():
    result = {'candidates': [{'center_roi_px': [10, 10], 'size_roi_px': [17, 17]}]*128,
              'search_truncated': False}
    search = {'observations': [{'center_roi_px': [80, 80], 'size_roi_px': [13, 13]}],
              'truncated': False}
    _append_observations(result, search)
    assert result['output_count'] == 128
    assert result['cross_output_overflow'] == 1 and result['search_truncated']
    assert result['cross_search']['observations'] == search['observations']


def test_component_feature_budget_is_explicit():
    crop = np.zeros((300, 300, 3), np.uint8)
    for y in range(10, 290, 20):
        for x in range(10, 290, 20):
            paint(crop, (x, y))
    got = cross_observations(crop, CrossAppearanceProfile.parse(PROFILE))
    assert got['eligible_components'] == 196
    assert got['checked_components'] == len(got['observations']) == 128
    assert got['unprocessed_eligible_components'] == 68 and got['truncated']


@pytest.mark.parametrize('box', [[20, 25, 13, 13], [0, 0, 13, 13], [87, 87, 13, 13]])
def test_local_component_tile_matches_full_image_sampling(box):
    labels = np.zeros((100, 100), np.int32)
    x, y, w, h = box
    # Isolated support includes irregular boundary pixels and touches image edges.
    rng = np.random.default_rng(613)
    labels[y:y+h, x:x+w] = (rng.random((h, w)) > .5).astype(np.int32)
    local = _shape_options(labels, 1, box)
    full = (labels == 1).astype(np.float32)
    for p in local:
        cx, cy = p['center_roi_px']
        steps = np.linspace(2, min(min(w, h)/2-1, 7), 5)
        arms = [float(np.mean([
            cv2.getRectSubPix(full, (3, 3), (cx+dx*k, cy+dy*k)).mean() for k in steps]))
                for dx, dy in [(-1, -1), (-1, 1), (1, -1), (1, 1)]]
        axes = [float(np.mean([
            cv2.getRectSubPix(full, (3, 3), (cx+dx*k, cy+dy*k)).mean() for k in steps]))
                for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]]
        assert p['arms'] == arms and p['axes'] == axes


@pytest.mark.parametrize('bad', [{}, {**PROFILE, 'hue_center': True},
                                {**PROFILE, 'hue_center': 180},
                                {**PROFILE, 'validated': True},
                                {**PROFILE, 'hue_tolerance': 0}])
def test_invalid_or_semantic_profile_flags_are_not_accepted(bad):
    with pytest.raises(ValueError):
        CrossMarkerDetector(bad)


def test_profile_copy_fingerprint_and_parent_centers(tmp_path):
    crop, pool, _, _ = case(tmp_path)
    profile = PROFILE.copy()
    engine = CrossMarkerDetector(profile)
    fingerprint = engine.cross_profile.fingerprint
    profile['hue_center'] = 10
    assert engine.cross_profile.fingerprint == fingerprint
    before = ExhaustiveMarkerDetector().detect(crop, pool)
    after = engine.detect(crop, pool)
    assert before['reference_fingerprint'] != after['reference_fingerprint']
    assert before['candidates'] == after['candidates'][:len(before['candidates'])]
    assert engine.correlations.image is None and engine.correlations.maps == {}


@pytest.mark.parametrize('change', ['reference', 'pixels', 'profile'])
def test_late_mutation_invalidates_cross_results(tmp_path, monkeypatch, change):
    crop, pool, paths, _ = case(tmp_path)
    engine = CrossMarkerDetector(PROFILE)

    def changed(*args):
        if change == 'reference':
            paths[0].write_bytes(b'corrupt')
        elif change == 'pixels':
            crop[0, 0] = 255
        else:
            engine.cross_profile = CrossAppearanceProfile(40, 12, 80, 50)
        return {'observations': [], 'truncated': False}

    monkeypatch.setattr('valorant_ai_coach.visual.development_marker_cross.cross_observations',
                        changed)
    with pytest.raises(ValueError):
        engine.detect(crop, pool)
    assert engine.execution_evidence == {} and engine._fingerprint is None
    assert engine.correlations.maps == {} and engine.correlations.image is None


@pytest.mark.parametrize('eligible', [False, True])
def test_cross_geometry_has_no_owner_zone_track_or_formal_event(tmp_path, monkeypatch, eligible):
    crop, pool, _, _ = case(tmp_path)
    paint(crop, (65, 45))
    sample = freeze_native_sample({
        'source_id': 'source', 'source_sha256': 'a'*64, 'acquisition_id': 'epoch',
        'native_epoch': 'epoch', 'native_pts_tick': 100, 'native_time_base': '1/1000',
        'acquired_frame_sha256': 'b'*64,
        'native_pixel_sha256': hashlib.sha256(crop.tobytes()).hexdigest(),
    }, frame_size_px=(120, 100))
    engine = DevelopmentCrossMarkerProposals('bind', PROFILE)
    engine.floor[:] = 255
    monkeypatch.setattr(engine.calibrator, 'analyze', lambda *a, **k: CalibrationResult(
        'ok', 1., (0., 0., 1., 1.), 'synthetic', (),
        (1., 0., 0., 0., 1., 0.), (120, 100), (0., 0., 120., 100.)))
    result = engine.observe(crop, sample=sample, minimap_roi=[0., 0., 1., 1.],
                            appearance_pool=pool, calibration_profile={},
                            context_eligible=eligible)
    crosses = [p for p in result['proposals'] if
               p['appearance_evidence']['candidate_kind'] == 'unassigned_cross_appearance']
    assert crosses and all(p['geometry_only_map_position_norm'] is not None for p in crosses)
    assert all(p['ownership'] == 'UNKNOWN' and p['map_position_norm'] is None
               and p['zone_resolution'] is None and p['version_compatibility'] == 'UNKNOWN'
               for p in result['proposals'])
    assert result['formal_self_position_fact'] is result['selected_self_position'] is None
    assert result['track_segments'] == result['development_events'] == []
