import copy

import pytest

from valorant_ai_coach.visual.development_marker_attribution import (
    assess_marker_attribution,
    freeze_native_sample,
    summarize_marker_attribution,
)


def sample():
    return freeze_native_sample({
        'source_id': 'recording', 'source_sha256': '1'*64,
        'acquisition_id': 'epoch', 'native_epoch': 'epoch',
        'native_pts_tick': 123, 'native_time_base': '1/60',
        'acquired_frame_sha256': '2'*64, 'native_pixel_sha256': '3'*64,
    }, frame_size_px=(640, 480))


def prediction():
    return {'qualification': 'development_only', 'ownership': 'UNKNOWN',
            'sample_sha256': sample()['sample_sha256'],
            'method_fingerprint': '4'*64, 'center_frame_px': [100., 200.],
            'explicit_context_rejection': False}


def review(role='TEAMMATE'):
    return {'status': 'human_confirmed', 'sample_sha256': sample()['sample_sha256'],
            'sample_scope': 'this_image_only', 'purpose': 'evaluation',
            'view_state': 'UNKNOWN', 'independent_episode_id': None,
            'markers': [{'center_frame_px': [100., 200.], 'role': role,
                         'tolerance_px': 2.}]}


def test_teammate_candidate_never_counts_as_correct_self():
    result = assess_marker_attribution(sample(), prediction(), review())
    assert result['candidate_role'] == 'TEAMMATE'
    assert result['ownership'] == 'UNKNOWN'
    summary = summarize_marker_attribution([result])
    assert summary['teammate_candidates_if_used_as_self'] == 1
    assert summary['self_position_candidates'] == 0
    assert summary['formal_misattributions'] == 0
    assert summary['independent_episodes_reviewed'] == 0
    assert summary['observations_without_episode_review'] == 1


def test_no_role_extension_between_native_observations():
    changed = copy.deepcopy(sample())
    changed['native_pts_tick'] += 1
    with pytest.raises(ValueError):
        assess_marker_attribution(changed, prediction(), review('SELF'))


def test_unreviewed_miss_and_rejection_are_distinct():
    p = prediction()
    p['center_frame_px'] = None
    assert assess_marker_attribution(sample(), p, None)['outcome'] == 'HUMAN_UNREVIEWED'
    assert assess_marker_attribution(sample(), p, review())['outcome'] == 'NO_CANDIDATE'
    p['explicit_context_rejection'] = True
    r = review()
    r['view_state'] = 'SPECTATOR'
    result = assess_marker_attribution(sample(), p, r)
    assert result['outcome'] == 'EXPLICIT_REJECTION'
    assert result['confirmed_non_live_rejection'] is True


def test_overlapping_role_annotations_stay_unknown_and_fitting_is_excluded():
    r = review('SELF')
    r['markers'].append({**r['markers'][0], 'role': 'TEAMMATE'})
    result = assess_marker_attribution(sample(), prediction(), r)
    assert result['candidate_role'] == 'UNKNOWN'
    assert result['outcome'] == 'UNKNOWN'
    r['purpose'] = 'reference_authoring'
    summary = summarize_marker_attribution([
        assess_marker_attribution(sample(), prediction(), r)])
    assert summary['evaluation_observations'] == 0
    assert summary['fitting_observations'] == 1


@pytest.mark.parametrize('field,value', [
    ('source_sha256', 'x'), ('native_pts_tick', True),
    ('native_time_base', '0/1'), ('native_time_base', 'NaN'),
    ('acquisition_id', 'other'), ('native_pixel_sha256', None),
])
def test_native_identity_requires_valid_complete_binding(field, value):
    record = sample()
    record[field] = value
    with pytest.raises(ValueError):
        freeze_native_sample(record, frame_size_px=(640, 480))


def test_repeated_frame_is_not_another_independent_episode():
    result = assess_marker_attribution(sample(), prediction(), review('SELF'))
    with pytest.raises(ValueError):
        summarize_marker_attribution([result, result])
