"""A report/transition cannot turn unowned current evidence into self death."""
from copy import deepcopy

import pytest

from tests.unit.test_hud_temporal_regressions import observation
from valorant_ai_coach.hud.temporal import HudDirectEventBuilder


@pytest.mark.parametrize('state,owned', [
    ('unknown', False), ('spectator_first_person', False),
    ('remote_control_view', False), ('live_first_person', False),
    ('unknown', True), ('live_first_person', None), ('live_first_person', 1),
])
def test_unowned_report_and_transition_cannot_generate_player_death(state, owned):
    row = observation(0)
    row['primary_state'] = state
    row['values']['player_specific_hud_valid'] = owned
    row['values']['combat_report_visible'] = True
    before = deepcopy(row)
    events = HudDirectEventBuilder().build([row], evidence_by_frame={0: {
        'spectator_transition': True, 'self_hud_identity_lost': True,
        'death_source_confidence': .99,
    }})
    assert not any(e['type'] == 'player_death' for e in events)
    assert row == before


def test_existing_owned_death_contract_is_unchanged():
    row = observation(0)
    row['values']['combat_report_visible'] = True
    events = HudDirectEventBuilder().build([row], evidence_by_frame={0: {
        'self_hud_identity_lost': True, 'death_source_confidence': .99,
    }})
    death = [e for e in events if e['type'] == 'player_death']
    assert len(death) == 1
    assert death[0]['actor'] == 'player' and death[0]['confidence'] == .95


def test_spectator_jitter_with_persistent_report_is_not_a_new_self_death():
    rows = [observation(i) for i in range(4)]
    states = ['unknown', 'spectator_first_person', 'unknown', 'spectator_first_person']
    for row, state in zip(rows, states, strict=True):
        row['primary_state'] = state
        row['values']['player_specific_hud_valid'] = False
        row['values']['combat_report_visible'] = True
        row['view_context']['is_player_world_view_trustworthy'] = False
    events = HudDirectEventBuilder().build(rows, evidence_by_frame={
        1: {'spectator_transition': True}, 3: {'spectator_transition': True},
    })
    assert not any(e['type'] == 'player_death' for e in events)
