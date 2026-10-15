"""Offline subject experiments cannot silently become native events or HUD facts."""
from copy import deepcopy

from jsonschema import Draft202012Validator

from tests.unit.test_hud_temporal_regressions import observation
from tests.unit.test_subject_death_probe import evidence, frame, seeded_probe
from valorant_ai_coach.experimental.subject_death import SubjectRole
from valorant_ai_coach.hud.temporal import HudDirectEventBuilder
from valorant_ai_coach.schema_validation import ContractSchemas


def test_complete_offline_candidate_cannot_be_inserted_as_a_native_event():
    probe = seeded_probe()
    decision = probe.observe(frame(1, [evidence(1, SubjectRole.DEATH_TRANSITION)]))
    assert decision.status == 'candidate' and decision.to_dict()['formal_events'] == []
    schema = ContractSchemas.load_canonical().round_package
    native_event = schema['properties']['events']['items']
    validator = Draft202012Validator({'$defs': schema.get('$defs', {}), **native_event})
    assert not validator.is_valid(decision.to_dict())


def test_probe_serialization_does_not_mutate_unowned_hud_or_reenable_legacy_death():
    row = observation(0)
    row['primary_state'] = 'unknown'
    row['values']['player_specific_hud_valid'] = False
    row['values']['combat_report_visible'] = True
    original = deepcopy(row)
    probe = seeded_probe()
    decision = probe.observe(frame(1, [evidence(1, SubjectRole.DEATH_TRANSITION)]))
    assert not decision.to_dict()['formal_events']
    events = HudDirectEventBuilder().build([row], evidence_by_frame={0: {
        'spectator_transition': True, 'self_hud_identity_lost': True,
    }})
    assert row == original
    assert not any(event['type'] == 'player_death' for event in events)
