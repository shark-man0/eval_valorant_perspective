"""Synthetic downstream safety coverage, never real-video qualification evidence."""

import importlib.util
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from valorant_ai_coach.events import EventSourceContract
from valorant_ai_coach.facts import FactBuilder
from valorant_ai_coach.hud.models import HudObservationV2, empty_hud_quality, empty_hud_values
from valorant_ai_coach.resources import resource_path
from valorant_ai_coach.rounds import RoundPackageBuilder
from valorant_ai_coach.schema_validation import SchemaValidator
from valorant_ai_coach.video import VideoMetadata


def load_adapter():
    path = Path(__file__).resolve().parents[1] / 'e2e' / 'trace_adapter.py'
    spec = importlib.util.spec_from_file_location('incomplete_fact_trace_adapter', path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize('state', ['unknown', 'spectator_first_person', 'remote_control_view'])
@pytest.mark.parametrize('hud_confidence', [0.0, .95])
def test_missing_end_keeps_next_start_facts_snapshots_and_trace_in_next_round(
        state, hud_confidence):
    validator = SchemaValidator()
    observations = []
    for timestamp in (2, 3, 4, 5, 6, 7):
        values = empty_hud_values()
        values.update(round_time_remaining_sec=120 - timestamp,
                      player_specific_hud_valid=False)
        values['round_time_remaining_display'] = f'1:{60 - timestamp:02d}'
        values['round_time_remaining_display_provenance'] = {
            'reader': 'round_timer', 'sources': ['synthetic-integration-reader'],
            'confidence': .95, 'cross_checked': False,
        }
        quality = empty_hud_quality()
        quality['hud_confidence'] = hud_confidence
        quality['roi_confidence'] = {'round_timer_value': .95, 'hp_value': .99}
        observations.append(HudObservationV2(
            timestamp, timestamp * 60, state, values=values, quality=quality,
            remote_view_type='unknown' if state == 'remote_control_view' else 'none',
            is_player_world_view_trustworthy=False,
        ).to_dict())
    # Already accepted boundary fixtures test the downstream contract only.
    # No fabricated reader qualification is supplied and no video is decoded.
    events = [{
        'event_id': name, 'type': kind, 'time_sec': timestamp,
        'actor': 'system', 'confidence': confidence,
        'attributes': {'evidence_provenance': {'continuity_segment': segment}},
    } for name, kind, timestamp, confidence, segment in (
        ('S1', 'round_start', 2, .94, 'first-source'),
        ('S2', 'round_start', 5, .96, 'second-source'),
        ('E2', 'round_end', 7, .93, 'second-source'),
    )]
    original = deepcopy(observations)
    builder = RoundPackageBuilder(
        contract=EventSourceContract.load(resource_path('config/event_source_contract_v1.json')),
        validator=validator,
    )
    built = builder.build(
        match_id='synthetic-incomplete',
        video_metadata=VideoMetadata(Path('synthetic.mp4'), 8, 1920, 1080, 60,
                                     'h264', None, False, 0),
        hud_observations=observations, hud_events=events,
    )
    assert len(built) == 2
    assert built[0]['observation_quality']['timeline_completeness'] == 0
    enriched = [FactBuilder().enrich(package) for package in built]
    for index, package in enumerate(enriched):
        validator.validate_round_package(package)
        times = {2, 3, 4} if index == 0 else {5, 6, 7}
        timers = [f for f in package['deterministic_facts']
                  if f['key'] == 'round_time_remaining_sec']
        assert {f['time_sec'] for f in timers} == times
        assert all(f['confidence'] == .95 and f['source'] == 'hud' for f in timers)
        assert len({f['fact_id'] for f in package['deterministic_facts']}) == len(
            package['deterministic_facts'])
        assert not {f['key'] for f in package['deterministic_facts']} & {'hp', 'player_died'}
        # PR59 already adopted independent global-field snapshots for unknown
        # identity. Spectator/remote retain the existing aggregate-only path.
        # Neither path establishes player ownership.
        assert {snapshot['time_sec'] for snapshot in package['state_snapshots']} == (
            times if hud_confidence or state == 'unknown' else set())
        assert all(snapshot['hp'] is None and snapshot['weapon'] is None
                   and snapshot.get('ammo_current') is None
                   for snapshot in package['state_snapshots'])
        if state == 'unknown' and not hud_confidence:
            assert all(snapshot['source_confidence'] == {'round_time_remaining_sec': .95}
                       for snapshot in package['state_snapshots'])
    trace = load_adapter().to_e2e_trace(SimpleNamespace(
        round_packages=enriched, observations=observations,
    ))
    boundaries = [e for e in trace['events'] if e['type'] in {'round_start', 'round_end'}]
    assert [(e['round_id'], e['type'], e['time_sec'], e['confidence']) for e in boundaries] == [
        ('sample_round_1', 'round_start', 2, .94),
        ('sample_round_2', 'round_start', 5, .96),
        ('sample_round_2', 'round_end', 7, .93),
    ]
    assert all(e['actor'] == 'system' for e in boundaries)
    assert [e['attributes'] for e in boundaries] == [e['attributes'] for e in events]
    assert len(trace['snapshots']) == (6 if hud_confidence or state == 'unknown' else 0)
    for snapshot in trace['snapshots']:
        assert snapshot['round_id'] == (
            'sample_round_1' if snapshot['time_sec'] < 5 else 'sample_round_2')
        assert snapshot['player_hp'] is None and snapshot.get('ammo_mag') is None
        assert snapshot['source_confidence_by_field']['round_time_remaining_sec'] == .95
        if state == 'unknown':
            assert snapshot['view_owner'] == 'unknown'
    assert observations == original


@pytest.mark.parametrize('field,value', [('hp', 80), ('ammo_current', 20),
                                       ('weapon_text', 'Vandal')])
def test_unowned_player_values_are_rejected_before_downstream_processing(field, value):
    values = empty_hud_values()
    values[field] = value
    with pytest.raises(ValueError, match='player_specific_hud_valid=false'):
        HudObservationV2(2, 120, 'unknown', values=values, quality=empty_hud_quality())


@pytest.mark.parametrize('confidence,expected_count', [(.89, 0), (.90, 1)])
def test_independent_global_snapshot_keeps_existing_field_confidence_floor(
        confidence, expected_count):
    values = empty_hud_values()
    values.update(round_time_remaining_sec=90, round_time_remaining_display='1:30',
                  round_time_remaining_display_provenance={
                      'reader': 'round_timer', 'sources': ['synthetic-reader'],
                      'confidence': confidence, 'cross_checked': False,
                  })
    quality = empty_hud_quality()
    quality['roi_confidence'] = {'round_timer_value': confidence}
    observation = HudObservationV2(2, 120, 'unknown', values=values, quality=quality).to_dict()
    builder = RoundPackageBuilder(
        contract=EventSourceContract.load(resource_path('config/event_source_contract_v1.json')),
        validator=SchemaValidator(),
    )
    snapshots = builder._state_snapshots([observation])
    assert len(snapshots) == expected_count
    assert all(snapshot['hp'] is None and snapshot['weapon'] is None for snapshot in snapshots)
