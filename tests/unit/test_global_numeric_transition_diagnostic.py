from copy import deepcopy
from fractions import Fraction

import pytest

from scripts.diagnostics.global_numeric_transitions import describe


def rows():
    result = []
    # An artificial different-valued sequence exercises the rule without GT.
    for tick in range(10):
        timer = 41 if tick < 3 else 9
        score = [1, 3 if tick < 5 else 4]
        result.append({'source_pts_ticks': tick, 'pts_sec': tick / 100,
                       'observation': {'time_sec': tick / 100, 'values': {
                           'score_ally': score[0], 'score_enemy': score[1],
                           'round_time_remaining_sec': timer,
                           'round_time_remaining_display': f'0:{timer:02d}',
                           'round_time_remaining_display_provenance': {
                               'reader': 'round_timer', 'sources': ['synthetic_test'],
                               'confidence': .95, 'cross_checked': False,
                           },
                       }, 'quality': {'roi_confidence': {
                           'score_ally_value': .95, 'score_enemy_value': .96,
                           'round_timer_value': .95,
                       }}}})
    # Exact .05s support requires one more frame after tick9.
    last = deepcopy(result[-1])
    last.update(source_pts_ticks=10, pts_sec=.10)
    last['observation']['time_sec'] = .10
    result.append(last)
    return result


def test_numeric_pattern_is_descriptive_immutable_and_never_an_event():
    source = rows()
    original = deepcopy(source)
    result = describe(source, Fraction(1, 100), 1)
    assert len(result['conditional_patterns']) == 1
    assert result['conditional_patterns'][0]['clock_change_tick'] == 3
    assert result['conditional_patterns'][0]['score_stability_tick'] == 10
    assert result['released_events'] == 0 and result['qualification_created'] is False
    assert source == original


@pytest.mark.parametrize('invalid', ['score_gap', 'low_confidence', 'two_points',
                                   'short_plateau', 'missing_clock'])
def test_insufficient_numeric_pattern_is_not_correlated(invalid):
    source = rows()
    if invalid == 'score_gap':
        source[4]['observation']['values']['score_enemy'] = None
    elif invalid == 'low_confidence':
        source[5]['observation']['quality']['roi_confidence']['score_enemy_value'] = .89
    elif invalid == 'two_points':
        for row in source[5:]:
            row['observation']['values']['score_enemy'] = 5
    elif invalid == 'short_plateau':
        source.pop()
    else:
        for row in source:
            row['observation']['values']['round_time_remaining_sec'] = None
    assert not describe(source, Fraction(1, 100), 1)['conditional_patterns']


def test_native_gap_cannot_be_correlated():
    source = rows()
    del source[4]
    with pytest.raises(ValueError, match='cadence'):
        describe(source, Fraction(1, 100), 1)


@pytest.mark.parametrize('invalid', ['epoch', 'timebase', 'pixels', 'observation_pts'])
def test_source_mismatch_cannot_correlate_a_numeric_pattern(invalid):
    source = rows()
    for i, row in enumerate(source):
        row.update(source_epoch='synthetic-epoch', source_time_base='1/100',
                   source_pixel_sha256=f'{i:064x}')
    if invalid == 'epoch':
        source[5]['source_epoch'] = 'other-epoch'
    elif invalid == 'timebase':
        source[5]['source_time_base'] = '1/200'
    elif invalid == 'pixels':
        source[5]['source_pixel_sha256'] = source[4]['source_pixel_sha256']
    else:
        source[5]['observation']['time_sec'] += .01
    with pytest.raises(ValueError):
        describe(source, Fraction(1, 100), 1)
