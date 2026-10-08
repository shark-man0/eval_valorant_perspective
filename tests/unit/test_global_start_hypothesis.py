from copy import deepcopy

import pytest

from scripts.diagnostics.global_round_start_hypothesis import GlobalStartHypothesis
from valorant_ai_coach.hud.models import HudObservationV2, empty_hud_quality, empty_hud_values
from valorant_ai_coach.hud.temporal import HudDirectEventBuilder


def observation(index, time, *, phase=False, timer=99, timer_score=.95, state='unknown'):
    values = empty_hud_values()
    values.update(round_time_remaining_sec=timer, buy_phase_visible=phase)
    quality = empty_hud_quality()
    quality['roi_confidence']['round_timer_value'] = timer_score
    if phase:
        quality['roi_confidence']['center_phase_banner_semantic_text'] = .96
    return HudObservationV2(time, index, state,
                           state_flags=('buy_phase_banner',) if phase else (),
                           values=values, quality=quality).to_dict()


def proposals(rows, cut=None):
    diagnostic = GlobalStartHypothesis()
    return [decision for i, row in enumerate(rows)
            if (decision := diagnostic.advance(row, discontinuity=i == cut)) is not None]


def test_hypothesis_is_not_production_or_player_identity():
    rows = [observation(0, 0, phase=True, timer=0), observation(1, .2),
            observation(2, .4, timer=None, timer_score=0), observation(3, .6, timer=98)]
    original = deepcopy(rows)
    result = proposals(rows)
    assert len(result) == 1
    assert result[0]['candidate_pts_sec'] == .2
    assert result[0]['confirmation_pts_sec'] == .6
    assert result[0]['neutral_timer_pts_sec'] == [.4]
    assert result[0]['confidence'] == .95
    assert result[0]['hypothesis_only'] is True
    assert rows == original
    assert not HudDirectEventBuilder().build(rows)
    assert all(r['primary_state'] == 'unknown' for r in rows)
    assert not any(r['values']['player_specific_hud_valid'] for r in rows)


@pytest.mark.parametrize('interruption', ['cut', 'gap', 'timeout', 'increase', 'weak',
                                        'menu', 'spectator', 'phase'])
def test_hypothesis_rejects_interruption_or_conflicting_evidence(interruption):
    phase = observation(0, 0, phase=True, timer=0)
    start = observation(1, .2)
    end = observation(2, .4, timer=98)
    if interruption == 'gap':
        end['time_sec'] = 1.3
    elif interruption == 'timeout':
        rows = [phase, start, observation(2, .9, timer=None, timer_score=0),
                observation(3, 1.3, timer=98)]
        assert not proposals(rows)
        return
    elif interruption == 'increase':
        end['values']['round_time_remaining_sec'] = 101
    elif interruption == 'weak':
        end['quality']['roi_confidence']['round_timer_value'] = .89
    elif interruption == 'menu':
        end['primary_state'] = 'buy_menu_open'
    elif interruption == 'spectator':
        end['primary_state'] = 'spectator_first_person'
    elif interruption == 'phase':
        end = observation(2, .4, phase=True, timer=0)
    assert not proposals([phase, start, end], cut=2 if interruption == 'cut' else None)


@pytest.mark.parametrize('missing', ['phase', 'timer_before', 'timer_after', 'reader_score',
                                   'phase_score', 'confirmation'])
def test_each_positive_evidence_component_is_required(missing):
    phase = observation(0, 0, phase=True, timer=0)
    start = observation(1, .2)
    if missing == 'phase':
        phase['state_flags'] = []
    elif missing == 'timer_before':
        phase['values']['round_time_remaining_sec'] = None
    elif missing == 'timer_after':
        start['values']['round_time_remaining_sec'] = None
    elif missing == 'reader_score':
        start['quality']['roi_confidence']['round_timer_value'] = .89
    elif missing == 'phase_score':
        phase['quality']['roi_confidence']['center_phase_banner_semantic_text'] = .89
    rows = [phase, start]
    if missing != 'confirmation':
        rows.append(observation(2, .4, timer=98))
    assert not proposals(rows)


def test_phase_rearms_once_without_producing_any_end():
    rows = [observation(0, 0, phase=True, timer=0), observation(1, .2),
            observation(2, .4, timer=98), observation(3, .6, timer=98),
            observation(4, .8, phase=True, timer=0), observation(5, 1, phase=True, timer=0),
            observation(6, 1.2, timer=100), observation(7, 1.4, timer=99)]
    result = proposals(rows)
    assert [r['candidate_pts_sec'] for r in result] == [.2, 1.2]
    assert all('round_end' not in r for r in result)
