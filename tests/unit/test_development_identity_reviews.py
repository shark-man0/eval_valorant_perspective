import copy

import cv2
import numpy as np
import pytest

from tests.unit.test_development_position_review import review_case
from tests.unit.test_development_trajectory import observation
from valorant_ai_coach.hud.readers import ReaderResult
from valorant_ai_coach.visual.development_actor_alias import DevelopmentActorAlias
from valorant_ai_coach.visual.development_position_review import observation_fingerprint
from valorant_ai_coach.visual.development_review_boundary import compare_review_boundaries
from valorant_ai_coach.visual.development_trajectory import analyze_candidate_path
from valorant_ai_coach.visual.development_view_review import compare_view_review


def test_boundary_differences_and_annotation_flips_never_become_error_bound():
    record, review = review_case()
    record['map_position_norm'] = [.49, .5]
    review['prediction_sha256'] = observation_fingerprint(record)
    zones = [{'zone_id': 'limited', 'polygon_norm': [[.5, 0], [1, 0], [1, 1], [.5, 1]]}]
    result = compare_review_boundaries(record, review, frame_sha256='frame',
        reference_sha256='ref', roi_size_px=(100, 100), reference_bbox=(0, 0, 1000, 1000),
        zones=zones)['reference_polygon_review']
    assert result['independent_membership'] == ['limited']
    assert result['prediction_membership'] == [] and result['membership_agrees'] is False
    assert result['membership_changes_under_single_coordinate_perturbation'] is True
    assert result['joint_annotation_error_bound'] is None
    assert record['formal_self_position_fact'] is None


def reviewed_view(record, role):
    review = {k: record[k] for k in ['source_id', 'acquisition_id', 'time_sec', 'frame_index',
                                     'map_id', 'geometry_version']}
    review.update(status='human_confirmed', label_origin='source_frame_view_review',
                  not_used_for_fitting=True, frame_sha256='frame', role=role,
                  prediction_sha256=observation_fingerprint(record))
    return compare_view_review(record, review, frame_sha256='frame')


def test_exact_human_view_labels_do_not_spread_or_promote_automatic_ownership():
    records = [observation(i) for i in range(4)]
    for record in records[:2]:
        record['view_review'] = reviewed_view(record, 'SELF_LIVE')
    result = analyze_candidate_path(records, reference_size_px=(1000, 1000))
    assert result['recorder_view_support']['human_self_live_position_observations'] == 2
    assert result['recorder_view_support']['both_endpoints_human_self_live_span_sec'] == .2
    assert result['recorder_view_support']['qualified_self_observations'] == 0
    assert result['samples'][2].get('view_review') is None
    records[2]['view_review'] = copy.deepcopy(records[0]['view_review'])
    with pytest.raises(ValueError, match='this frozen'):
        analyze_candidate_path(records, reference_size_px=(1000, 1000))


@pytest.mark.parametrize('role', ['SPECTATOR', 'DEATH', 'SELF_PURCHASE', 'PURCHASE'])
def test_reviewed_non_live_context_breaks_path(role):
    records = [observation(i) for i in range(3)]
    records[1]['view_review'] = reviewed_view(records[1], role)
    result = analyze_candidate_path(records, reference_size_px=(1000, 1000))
    assert len(result['segments']) == 2 and not result['edges']
    assert result['samples'][1]['point_norm'] is None


def test_recorder_review_without_phase_does_not_connect_a_live_path():
    records = [observation(i) for i in range(3)]
    records[1]['view_review'] = reviewed_view(records[1], 'SELF_PHASE_UNKNOWN')
    result = analyze_candidate_path(records, reference_size_px=(1000, 1000))
    assert not result['edges'] and len(result['segments']) == 2
    assert result['samples'][1]['break_reason'] == 'human_recorder_phase_unresolved'
    assert result['recorder_view_support']['human_self_live_position_observations'] == 0
    assert records[1]['map_position_norm'] is not None  # The frozen candidate survives.


class FakeText:
    def __init__(self, text):
        self.text = text
        self.calls = 0

    def read(self, image, roi):
        self.calls += 1
        return ReaderResult(self.text, .99, ('synthetic-reviewed-slot',))


def test_name_slot_needs_positive_activation_and_spectator_name_never_establishes_self(tmp_path):
    frame = np.zeros((240, 600, 3), np.uint8)
    glyph = np.random.default_rng(28).integers(0, 256, (15, 51, 3), np.uint8)
    path = tmp_path/'chrome.png'
    cv2.imwrite(str(path), glyph)
    reader = FakeText('recorder')
    engine = DevelopmentActorAlias(reader)
    spec = {'frame_size_px': [600, 240], 'slot_kind': 'spectated_player_name',
            'slot_review': 'source_reviewed_not_qualified', 'name_roi': [.5, .4, .8, .5],
            'activation': {'mode': 'spectator_switch_v1', 'roi': [.5, .6, .8, .9],
                           'reference_frame_size_px': [600, 240], 'template_path': str(path)}}
    args = {'minimap_roi': [0, 0, .4, .4], 'recorder_alias': 'recorder'}
    absent = engine.inspect(frame, spec, **args)
    assert absent['status'] == 'not_detected' and reader.calls == 0
    frame[150:165, 305:356] = glyph
    present = engine.inspect(frame, spec, **args)
    assert present['alias_association'] == 'alias_matches_recorder'
    assert present['block_position_candidate'] is True
    assert present['positive_current_alias_support'] is False
    spec['slot_kind'] = 'current_actor_identifier'
    assert engine.inspect(frame, spec, **args)['positive_current_alias_support'] is True
    assert engine.inspect(frame, spec, **args)['ownership'] == 'UNKNOWN'
    reader.text = 'other'
    assert engine.inspect(frame, spec, **args)['alias_association'] == 'different_alias_supported'
    path.unlink()
    assert engine.inspect(frame, spec, **args)['status'] == 'unavailable'
