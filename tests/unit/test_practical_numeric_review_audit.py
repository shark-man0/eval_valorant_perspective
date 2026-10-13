from copy import deepcopy

import pytest

from scripts.diagnostics.audit_practical_numeric_reviews import compare_reviews


def inputs():
    shared = {'source_video_sha256': 'a' * 64, 'profile_fingerprint': 'b' * 64,
              'recognizer_fingerprint': 'c' * 64}
    values = {'round_time_remaining_display': '1:29', 'score_ally': 0, 'score_enemy': 2}
    binding = {'source_pts_ticks': 10, 'source_pixel_sha256': 'd' * 64}
    current = {**shared, 'source_rows': [{**binding, 'source_pts_sec': 1.,
                                        'system_observation': {'values': values}}]}
    previous = {**shared, 'rows': [{**binding, 'pts_sec': 1., 'observation': {'values': {
        'round_time_remaining_display': '1:28', 'score_ally': None, 'score_enemy': 2,
    }}}]}
    review = {**shared, 'review_provenance': 'Synthetic audit test; not source qualification',
              'labels': [{**binding, 'pts_sec': 1., 'expected': deepcopy(values)}]}
    return current, previous, review


def test_audit_counts_safety_transitions_without_creating_qualification():
    report = compare_reviews(*inputs())
    assert report['comparison']['round_time_remaining_display']['transitions'] == {
        'wrong -> correct': 1,
    }
    assert report['comparison']['score_ally']['transitions'] == {'unknown -> correct': 1}
    assert not report['qualification_created'] and not report['independent_holdout_proven']


@pytest.mark.parametrize('mutation', ['pixel', 'time', 'source', 'duplicate', 'missing'])
def test_audit_rejects_invalid_source_associations(mutation):
    current, previous, review = inputs()
    row = current['source_rows'][0]
    if mutation == 'pixel':
        row['source_pixel_sha256'] = 'e' * 64
    elif mutation == 'time':
        row['source_pts_sec'] = 2.
    elif mutation == 'source':
        previous['source_video_sha256'] = 'e' * 64
    elif mutation == 'duplicate':
        review['labels'].append(deepcopy(review['labels'][0]))
    else:
        current['source_rows'] = []
    with pytest.raises(ValueError):
        compare_reviews(current, previous, review)


def test_boolean_score_cannot_be_counted_as_correct_zero():
    current, previous, review = inputs()
    current['source_rows'][0]['system_observation']['values']['score_ally'] = False
    with pytest.raises(ValueError, match='prediction value type'):
        compare_reviews(current, previous, review)
