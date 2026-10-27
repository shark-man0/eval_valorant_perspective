import copy
import hashlib
import math

import cv2
import numpy as np
import pytest

from tests.unit.test_development_marker_quality import case
from valorant_ai_coach.visual.development_marker_attribution import freeze_native_sample
from valorant_ai_coach.visual.development_marker_partial_arc import (
    DevelopmentPartialArcDetector,
    partial_arc_observations,
)

PROFILE = {'mode': 'unassigned_cross_shape_v1', 'hue_center': 120,
           'hue_tolerance': 12, 'saturation_min': 80, 'value_min': 50}


def sample_for(frame):
    return freeze_native_sample({
        'source_id': 'development', 'source_sha256': 'a'*64,
        'acquisition_id': 'epoch', 'native_epoch': 'epoch', 'native_pts_tick': 2,
        'native_time_base': '1/60', 'acquired_frame_sha256': 'b'*64,
        'native_pixel_sha256': hashlib.sha256(frame.tobytes()).hexdigest(),
    }, frame_size_px=(frame.shape[1], frame.shape[0]))


def test_arc_search_finds_partial_shape_without_claiming_semantics():
    image = np.zeros((100, 120, 3), np.uint8)
    cv2.ellipse(image, (55, 50), (10, 10), 0, 20, 300, (255, 255, 255), 2)
    result = partial_arc_observations(image)
    assert any(math.dist(p['center_roi_px'], [55, 50]) <= 3 for p in result['candidates'])
    assert all(p['ownership'] == 'UNKNOWN' and not p['score_calibrated']
               for p in result['candidates'])
    assert result['semantic_class'] == 'UNKNOWN'


def test_blank_and_border_are_not_filled_or_inferred():
    image = np.zeros((100, 120, 3), np.uint8)
    assert partial_arc_observations(image)['candidates'] == []
    cv2.circle(image, (1, 1), 10, (255, 255, 255), 2)
    result = partial_arc_observations(image)
    assert not any(math.dist(p['center_roi_px'], [1, 1]) <= 3 for p in result['candidates'])


def test_union_preserves_actual_parent_candidates_and_sample(tmp_path):
    frame, pool, _, _ = case(tmp_path)
    cv2.ellipse(frame, (75, 55), (10, 10), 0, 10, 300, (255, 255, 255), 2)
    sample = sample_for(frame)
    engine = DevelopmentPartialArcDetector(PROFILE)
    before = engine.parent.detect(frame, pool)
    result = engine.observe(frame, sample=sample, minimap_roi=[0., 0., 1., 1.],
                            appearance_pool=pool)
    assert result['baseline_d'] == before
    parents = [p for p in result['proposals'] if p['source'] == 'D']
    assert [p['candidate'] for p in parents] == before['candidates']
    assert result['sample'] == sample and all(p['sample_sha256'] == sample['sample_sha256']
                                               for p in result['proposals'])
    assert result['ownership'] == result['semantic_class'] == 'UNKNOWN'
    assert result['formal_self_position_fact'] is None and result['development_events'] == []


def test_stale_sample_and_mutation_fail_closed(tmp_path, monkeypatch):
    frame, pool, _, _ = case(tmp_path)
    sample = sample_for(frame)
    engine = DevelopmentPartialArcDetector(PROFILE)
    changed = copy.deepcopy(sample)
    changed['native_pts_tick'] += 1
    with pytest.raises(ValueError, match='Exact native sample'):
        engine.observe(frame, sample=changed, minimap_roi=[0., 0., 1., 1.],
                       appearance_pool=pool)
    def mutate(image):
        image[20, 20] ^= 1
        return {'candidates': []}
    monkeypatch.setattr('valorant_ai_coach.visual.development_marker_partial_arc.'
                        'partial_arc_observations', mutate)
    with pytest.raises(ValueError, match='changed'):
        engine.observe(frame, sample=sample, minimap_roi=[0., 0., 1., 1.],
                       appearance_pool=pool)


def test_truncation_is_reported_without_removing_parent_candidates(tmp_path, monkeypatch):
    frame, pool, _, _ = case(tmp_path)
    # Repeated synthetic rings exercise finite addition budget.
    for y in range(10, frame.shape[0]-10, 12):
        for x in range(10, frame.shape[1]-10, 12):
            cv2.circle(frame, (x, y), 6, (255, 255, 255), 1)
    monkeypatch.setattr('valorant_ai_coach.visual.development_marker_partial_arc.MAX_ADDITIONS', 1)
    engine = DevelopmentPartialArcDetector(PROFILE)
    result = engine.observe(frame, sample=sample_for(frame), minimap_roi=[0., 0., 1., 1.],
                            appearance_pool=pool)
    assert len(result['arc_search']['candidates']) == 1
    assert result['arc_search']['output_overflow'] > 0
    assert (result['arc_search']['search_truncated']
            == bool(result['arc_search']['output_overflow']
                    or result['arc_search']['unprocessed_peaks']))
    parents = [p['candidate'] for p in result['proposals'] if p['source'] == 'D']
    assert parents == result['baseline_d']['candidates']
