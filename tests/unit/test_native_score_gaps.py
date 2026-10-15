import json

import pytest

from scripts.diagnostics.native_score_gaps import summarize_native_score_gaps


def rows(pairs):
    return [{
        'source_video_sha256': 'a' * 64, 'source_epoch': 'test-native',
        'source_time_base': '1/15360', 'input_fingerprint': 'b' * 64,
        'source_pts_ticks': index * 256, 'source_pixel_sha256': 'c' * 64,
        'system_observation': {'values': dict(
            zip(('score_ally', 'score_enemy'), pair, strict=True)),
                               'quality': {'notes': [], 'roi_confidence': {
                                   'score_ally_value': .95, 'score_enemy_value': .95}}},
        'system_measurements': {'native_ui': {}},
    } for index, pair in enumerate(pairs)]


def test_gap_is_not_an_adjacent_transition_and_has_no_private_payload():
    data = rows([(0, 0), (None, 0), (None, 0), (1, 0)])
    result = summarize_native_score_gaps(data, 256)
    assert result['counts']['adjacent_score_changes'] == 0
    assert result['counts']['nonadjacent_score_changes'] == 1
    assert result['change_gap_reasons'] == {'ally_score_unavailable': 2}
    assert result['events_released'] == 0
    assert result['continuity_proven'] is False
    assert 'source_pts_ticks' not in json.dumps(result)
    assert 'source_pixel_sha256' not in json.dumps(result)


def test_adjacent_change_is_only_input_availability_not_an_event():
    result = summarize_native_score_gaps(rows([(0, 0), (1, 0)]), 256)
    assert result['counts']['adjacent_score_changes'] == 1
    assert result['qualification_created'] is False
    assert result['events_released'] == 0


def test_low_confidence_value_and_geometry_gap_are_not_accepted():
    data = rows([(0, 0), (1, 0), (1, 0)])
    data[1]['system_observation']['quality']['roi_confidence']['score_ally_value'] = .89
    data[1]['system_observation']['quality']['notes'] = ['calibration_required']
    result = summarize_native_score_gaps(data, 256)
    assert result['change_gap_reasons'] == {'geometry_unavailable': 1}
    assert result['counts']['adjacent_score_changes'] == 0


def test_source_break_discards_prior_score_and_gap():
    data = rows([(0, 0), (None, 0), (1, 0)])
    data[1]['system_measurements']['native_ui']['content_jump'] = True
    result = summarize_native_score_gaps(data, 256)
    assert result['counts']['source_break_resets'] == 1
    assert result['counts']['nonadjacent_score_changes'] == 0
    assert result['counts']['adjacent_score_changes'] == 0


@pytest.mark.parametrize('key,value', [
    ('source_epoch', 'other'), ('source_time_base', '1/60'),
    ('source_pts_ticks', 512), ('source_pixel_sha256', 'invalid'),
    ('input_fingerprint', 'd' * 64),
])
def test_gapped_or_mixed_native_provenance_is_rejected(key, value):
    data = rows([(0, 0), (1, 0)])
    data[1][key] = value
    with pytest.raises(ValueError, match='contiguous'):
        summarize_native_score_gaps(data, 256)


def test_return_to_same_score_does_not_claim_an_update():
    result = summarize_native_score_gaps(rows([(0, 0), (None, None), (0, 0)]), 256)
    assert result['counts']['nonadjacent_score_changes'] == 0
    assert result['change_gap_reasons'] == {}


def test_empty_entrance_is_not_positive_evidence():
    result = summarize_native_score_gaps([], 256)
    assert all(value == 0 for value in result['counts'].values())
    assert result['continuity_proven'] is False
