import copy

import pytest

from valorant_ai_coach.visual.development_identity_metrics import (
    compare_stationary_review,
    identity_factors,
    marker_binding_matches,
    summarize_reviewed_identity,
)
from valorant_ai_coach.visual.development_position_review import observation_fingerprint
from valorant_ai_coach.visual.development_view_review import compare_view_review


def row(index, point=(.5, .5)):
    return {'qualification': 'development_only', 'formal_self_position_fact': None,
            'ownership': {'identity': 'UNKNOWN', 'view_eligible': True},
            'source_id': 's', 'acquisition_id': 'a', 'context_sha256': 'c', 'map_id': 'm',
            'geometry_version': 'g', 'time_sec': index*.2, 'frame_index': index,
            'acquired_frame_sha256': str(index)*64, 'map_position_norm': point,
            'ownership_evidence': {'status': 'observed', 'block_position_candidate': False},
            'recorder_view_evidence': {'status': 'observed', 'positive_agent_association': True,
                                       'positive_view_support': True}}


def label(record, role):
    review = {k: record[k] for k in ['source_id', 'acquisition_id', 'time_sec', 'frame_index',
                                    'map_id', 'geometry_version']}
    review.update(status='human_confirmed', label_origin='source_frame_view_review',
                  not_used_for_fitting=True, frame_sha256=record['acquired_frame_sha256'],
                  prediction_sha256=observation_fingerprint(record), role=role)
    record['view_review'] = compare_view_review(
        record, review, frame_sha256=record['acquired_frame_sha256'])


def stationary_review(records):
    return {'status': 'human_confirmed', 'label_origin': 'source_stationary_sample_review',
            'not_used_for_fitting': True, 'sample_scope': 'listed_observations_only',
            'prediction_sha256': [observation_fingerprint(r) for r in records],
            'frame_sha256': [r['acquired_frame_sha256'] for r in records]}


def test_correlated_agent_hud_and_alias_still_lack_qualified_owner():
    result = identity_factors(
        {'view_candidate': 'first_person_hud_context',
         'observed_cues': [{'claim': 'first_person_hud', 'status': 'present'}]},
        {'association': 'recorder_agent_supported', 'actor_alias_evidence': {
            'positive_current_alias_support': True, 'alias_association': 'alias_matches_recorder'}})
    assert result['shared_first_person_hud_observed'] is True
    assert result['current_actor_alias_support'] is True
    assert result['qualified_current_actor_link'] is result['qualified_live_recorder_view'] is False
    assert result['ownership'] == 'UNKNOWN' and len(result['missing_evidence']) == 2


@pytest.mark.parametrize('changed', ['source_id', 'source_sha256', 'recorder_agent_id',
                                   'reference_fingerprint', 'review_sha256', None])
def test_marker_binding_rejects_cross_source_agent_and_reference(changed):
    spec = {'source_id': 's', 'source_sha256': 'a'*64, 'recorder_agent_id': 'agent',
            'reference_fingerprint': 'b'*64, 'review_sha256': 'c'*64}
    if changed is not None:
        spec[changed] = 'wrong'
    actual = marker_binding_matches(spec, source_id='s', source_sha256='a'*64,
                                    recorder_agent_id='agent', reference_fingerprint='b'*64)
    assert actual is (changed is None)
    assert marker_binding_matches(None, source_id='s', source_sha256=None,
                                  recorder_agent_id=None, reference_fingerprint=None) is True


def test_review_metrics_separate_context_rejection_from_appearance_misses():
    live, purchase, spectator, unreviewed = [row(i) for i in range(4)]
    label(live, 'SELF_LIVE')
    purchase['map_position_norm'] = None  # An appearance miss alone earns no rejection credit.
    label(purchase, 'PURCHASE')
    spectator['ownership_evidence']['block_position_candidate'] = True
    spectator['recorder_view_evidence']['positive_view_support'] = False
    spectator['map_position_norm'] = None
    label(spectator, 'SPECTATOR')
    report = summarize_reviewed_identity([live, purchase, spectator, unreviewed])
    assert report['groups']['SELF_LIVE']['reviewed_self_live_support_candidate'] == 1
    assert report['groups']['PURCHASE']['confirmed_non_live_context_rejection'] == 0
    assert report['groups']['PURCHASE']['non_live_view_support_candidate'] == 1
    assert report['groups']['SPECTATOR']['confirmed_non_live_context_rejection'] == 1
    assert report['groups']['UNREVIEWED']['observations'] == 1
    assert report['qualified_self_observations'] == 0
    assert report['qualified_account_misattribution_rate'] is None
    purchase['time_sec'] += .1
    with pytest.raises(ValueError, match='frozen'):
        summarize_reviewed_identity([purchase])


def test_stationary_spread_preserves_misses_breaks_and_unknown_ownership():
    records = [row(0, (.1, .1)), row(1, (.13, .14)), row(2, None), row(3, (.9, .9))]
    report = compare_stationary_review(
        records, stationary_review(records), reference_size_px=(100, 100))
    assert report['missing_positions'] == 1
    assert len(report['runs']) == 2
    assert report['runs'][0]['diameter_reference_px'] == pytest.approx(5)
    assert report['runs'][0]['rms_about_mean_reference_px'] == pytest.approx(2.5)
    assert report['runs'][1]['spread_measured'] is False
    assert report['transferable_error_bound_reference_px'] is None
    changed = copy.deepcopy(records)
    changed[1]['context_sha256'] = 'different'
    changed_report = compare_stationary_review(
        changed, stationary_review(changed), reference_size_px=(100, 100))
    assert len(changed_report['runs']) == 3


def test_missing_reference_and_marker_authoring_are_not_correct_context_rejections():
    record = row(0, None)
    record['ownership_evidence'].update(status='unavailable', block_position_candidate=True)
    record['recorder_view_evidence']['marker_reference_binding_valid'] = False
    record['ownership']['view_eligible'] = False
    label(record, 'DEATH')
    group = summarize_reviewed_identity([record])['groups']['DEATH']
    assert group['confirmed_non_live_context_rejection'] == 0
    assert group['authoring_or_unavailable_rejection'] == 1


@pytest.mark.parametrize('mutation', ['fitted', 'wrong_image', 'wrong_prediction', 'formal'])
def test_stationary_review_cannot_be_fitted_transferred_or_production(mutation):
    records = [row(0), row(1)]
    review = stationary_review(records)
    if mutation == 'fitted':
        review['not_used_for_fitting'] = False
    elif mutation == 'wrong_image':
        review['frame_sha256'][0] = 'a'*64
    elif mutation == 'wrong_prediction':
        records[0]['time_sec'] = 10
    else:
        records[0]['formal_self_position_fact'] = {'actor': 'player'}
    with pytest.raises(ValueError):
        compare_stationary_review(records, review, reference_size_px=(100, 100))
