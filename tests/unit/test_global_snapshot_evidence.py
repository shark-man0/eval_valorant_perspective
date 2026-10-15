"""Global source values never authorize unknown player identity or mechanics."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.e2e.trace_adapter import to_e2e_trace
from tests.integration.test_hud_video_processor import hud_event, make_observation
from tests.unit.test_shared_score_snapshot import score_observation
from valorant_ai_coach.events import EventSourceContract
from valorant_ai_coach.facts import FactBuilder
from valorant_ai_coach.resources import resource_path
from valorant_ai_coach.rounds import RoundPackageBuilder
from valorant_ai_coach.schema_validation import SchemaValidator
from valorant_ai_coach.video import VideoMetadata


def source(time=1):
    row = score_observation(time)
    row['primary_state'] = 'unknown'
    row['quality']['hud_confidence'] = 0
    row['quality']['state_confidence'] = 0
    row['view_context']['is_player_world_view_trustworthy'] = False
    row['values']['player_specific_hud_valid'] = False
    for key in ('hp', 'armor', 'ammo_current', 'ammo_reserve', 'weapon_text'):
        row['values'][key] = None
    row['values'].update(round_time_remaining_sec=99,
                         round_time_remaining_display='1:39',
                         round_time_remaining_display_provenance={
                             'reader': 'round_timer', 'sources': ['synthetic_reader'],
                             'confidence': .94, 'cross_checked': False,
                         })
    row['quality']['roi_confidence']['round_timer_value'] = .94
    return row


def builder():
    return RoundPackageBuilder(
        contract=EventSourceContract.load(resource_path('config/event_source_contract_v1.json')),
        validator=SchemaValidator(),
    )


def test_unknown_identity_retains_each_source_point_without_owned_facts():
    rows = [source(t) for t in (1, 1.01, 1.02)]
    original = deepcopy(rows)
    for row in rows:
        SchemaValidator().validate_hud_observation(row)
    packages = builder().build(
        match_id='global-only',
        video_metadata=VideoMetadata(Path('synthetic.mp4'), 2, 1920, 1080, 60,
                                     'h264', None, False, 1),
        hud_observations=rows,
        hud_events=(hud_event('start', .5, 'round_start'),
                    hud_event('end', 1.5, 'round_end')),
    )
    for package in packages:
        SchemaValidator().validate_round_package(package)
        enriched = FactBuilder().enrich(package)
        SchemaValidator().validate_round_package(enriched)
        facts = enriched['deterministic_facts']
        timer = [f for f in facts if f['key'] == 'round_time_remaining_sec']
        assert [f['time_sec'] for f in timer] == [1, 1.01, 1.02]
        assert all(f['confidence'] == .94 for f in timer)
        for key, value, confidence in (('score_ally', 0, .95), ('score_enemy', 1, .96)):
            scores = [f for f in facts if f['key'] == key]
            assert len(scores) == 3
            assert all(f['value'] == value and f['confidence'] == confidence for f in scores)
        assert not any(f['key'] in {'hp', 'weapon', 'utility_available_count',
                                   'numbers_state', 'clutch_state',
                                   'spike_carried_by_player'} for f in facts)
    snapshots = [s for p in packages for s in p['state_snapshots']]
    assert [s['time_sec'] for s in snapshots] == [1, 1.01, 1.02]
    assert all(s['source_confidence'] == {'score_ally': .95, 'score_enemy': .96,
                                        'round_time_remaining_sec': .94} for s in snapshots)
    trace = to_e2e_trace(SimpleNamespace(round_packages=packages, observations=rows))
    for s in trace['snapshots']:
        assert s['primary_state'] == 'unknown' and s['view_owner'] == 'unknown'
        assert s['player_hp'] is None and s['spectator_primary_state'] is None
        assert s['game_timer_display'] == '1:39'
        assert s['source_confidence'] == .94
        assert not {'player_alive', 'ammo_mag', 'weapon', 'muzzle_flash_visible'} & {
            k for k,v in s.items() if v is not None
        }
    assert rows == original
    assert {e['type'] for e in trace['events']} == {'round_start', 'round_end'}


@pytest.mark.parametrize('reason', ['weak', 'occluded', 'uncalibrated', 'unowned_missing',
                                   'incompatible_state', 'numeric_without_display'])
def test_no_evidence_or_unsafe_context_does_not_create_global_snapshot(reason):
    row = source()
    if reason == 'weak':
        row['quality']['roi_confidence'] = dict.fromkeys(
            ('score_ally_value', 'score_enemy_value', 'round_timer_value'), .89)
    elif reason == 'occluded':
        row['quality']['occluded_rois'] = ['round_timer']
    elif reason == 'uncalibrated':
        row['quality']['notes'] = ['calibration_required']
    elif reason == 'unowned_missing':
        row['values'].pop('player_specific_hud_valid')
    elif reason == 'incompatible_state':
        row['primary_state'] = 'spectator_first_person'
    else:
        row['quality']['roi_confidence'] = {'round_timer_value': .99}
        row['values'].pop('round_time_remaining_display')
        row['values'].pop('round_time_remaining_display_provenance')
    assert builder()._state_snapshots([row]) == []


def test_player_poison_and_duplicate_input_do_not_seed_owned_snapshot_or_extra_points():
    row = source()
    row['values'].update(hp=85, weapon_text='Vandal', ammo_current=21,
                         spike_state='carried_by_player')
    snapshots = builder()._state_snapshots([row, row])
    assert len(snapshots) == 1
    assert snapshots[0]['hp'] is None and snapshots[0]['weapon'] is None
    assert snapshots[0]['spike_state'] == 'unknown'


def test_aggregate_hud_gate_and_previous_live_snapshot_are_unchanged():
    live = make_observation(1)
    baseline = builder()._state_snapshots([live])
    assert len(baseline) == 1 and baseline[0]['hp'] == 100
    weak_live = deepcopy(live)
    weak_live['quality']['hud_confidence'] = .649
    assert not builder()._state_snapshots([weak_live])
    assert builder()._state_snapshots([live]) == baseline


def test_global_snapshot_is_not_a_new_player_spatial_or_map_merge_entrance():
    from tests.unit.test_snapshot_clock_fusion import visual
    row = source()
    b = builder()
    snapshots = b._state_snapshots([row])
    original = deepcopy(snapshots)
    merged = b._merge_visual_snapshots(
        snapshots, [visual(1)], [row],
        [{'time_sec': 1, 'calibration_status': 'ok', 'resolution_scope': 'exact_zone',
          'zone_confidence': 1, 'zone_id': 'unowned-zone'}],
    )
    assert merged == original
    assert merged[0]['player_location']['zone_id'] is None
    assert merged[0]['spatial_context']['cover_available'] is None


@pytest.mark.parametrize('value', [None, True, float('nan'), float('inf'), '0.99', 1.1, -.1])
def test_invalid_reader_scores_never_replace_geometry_with_numeric_proof(value):
    row = source()
    row['quality']['roi_confidence'].update(score_ally_value=value, score_enemy_value=value,
                                          round_timer_value=value, round_timer=.999)
    assert builder()._state_snapshots([row]) == []


def test_actual_source_gap_and_round_membership_are_preserved():
    rows = [source(t) for t in (1, 1.01, 4, 4.01)]
    events = [hud_event('s1', .5, 'round_start'), hud_event('e1', 1.5, 'round_end'),
              hud_event('s2', 3.5, 'round_start'), hud_event('e2', 4.5, 'round_end')]
    packages = builder().build(
        match_id='two-rounds',
        video_metadata=VideoMetadata(Path('synthetic.mp4'), 5, 1920, 1080, 60,
                                     'h264', None, False, 1),
        hud_observations=rows, hud_events=events, continuity_breaks=(3,),
    )
    assert len(packages) == 2
    assert [[s['time_sec'] for s in p['state_snapshots']] for p in packages] == [
        [1, 1.01], [4, 4.01],
    ]
    assert all(not (p['round_window']['start_sec'] < 3 < p['round_window']['end_sec'])
               for p in packages)


def test_score_export_keeps_preexisting_fact_ids_and_source_confidence():
    rows = [make_observation(1)]
    package = builder().build(
        match_id='fact-id',
        video_metadata=VideoMetadata(Path('synthetic.mp4'), 2, 1920, 1080, 60,
                                     'h264', None, False, 1),
        hud_observations=rows, hud_events=(),
    )[0]
    legacy = deepcopy(package)
    current = deepcopy(package)
    current['state_snapshots'][0].update(score_ally=0, score_enemy=1)
    current['state_snapshots'][0]['source_confidence'].update(score_ally=.95, score_enemy=.96)
    before = FactBuilder().enrich(legacy)['deterministic_facts']
    after = FactBuilder().enrich(current)['deterministic_facts']
    assert [f for f in after if f['key'] not in {'score_ally', 'score_enemy'}] == before
    assert [(f['key'], f['value'], f['confidence']) for f in after
            if f['key'] in {'score_ally', 'score_enemy'}] == [
                ('score_ally', 0, .95), ('score_enemy', 1, .96),
            ]


def test_unrelated_weak_reader_does_not_destroy_independent_timer():
    row = source()
    row['quality']['roi_confidence'].update(score_ally_value=0, score_enemy_value=0,
                                          weapon=0)
    snapshot = builder()._state_snapshots([row])[0]
    assert snapshot['source_confidence'] == {'round_time_remaining_sec': .94}
    assert snapshot['score_ally'] is None and snapshot['score_enemy'] is None
    assert snapshot['weapon'] is None


@pytest.mark.parametrize('state', ['spectator_first_person', 'remote_control_view'])
def test_context_poison_cannot_enter_unknown_global_snapshot_path(state):
    row = source()
    row['primary_state'] = state
    row['values'].update(hp=85, weapon_text='Vandal')
    assert builder()._state_snapshots([row]) == []


def test_old_observation_without_value_confidence_remains_unknown():
    row = source()
    row['quality'].pop('roi_confidence')
    assert builder()._state_snapshots([row]) == []


def test_adjacent_value_changes_and_json_round_trip_preserve_current_support():
    import json
    rows = [source(1), source(1.01)]
    rows[1]['values']['score_enemy'] = 2
    rows[1]['quality']['roi_confidence']['score_enemy_value'] = .91
    before = deepcopy(rows)
    snapshots = builder()._state_snapshots(rows)
    assert [(s['time_sec'], s['score_enemy'], s['source_confidence']['score_enemy'])
            for s in snapshots] == [(1, 1, .96), (1.01, 2, .91)]
    assert json.loads(json.dumps(snapshots)) == snapshots
    assert rows == before


def test_field_snapshots_do_not_upgrade_package_completeness():
    from valorant_ai_coach.rounds.builder import aggregate_observation_quality
    rows = [source(t) for t in (1, 1.01, 1.02)]
    quality = aggregate_observation_quality(rows, .5, 1.5)
    assert len(builder()._state_snapshots(rows)) == 3
    assert aggregate_observation_quality(rows, .5, 1.5) == quality
    assert quality['timeline_completeness'] == 0


def test_targeted_projection_uses_source_values_not_target_expected():
    from scripts.diagnostics.replay_snapshot_gate import replay
    rows = [source(1)]
    packages = builder().build(
        match_id='projection',
        video_metadata=VideoMetadata(Path('synthetic.mp4'), 2, 1920, 1080, 60,
                                     'h264', None, False, 1),
        hud_observations=rows,
        hud_events=(hud_event('start', .5, 'round_start'),
                    hud_event('end', 1.5, 'round_end')),
    )
    raw = {'round_packages': packages, 'observations': rows}
    original = deepcopy(raw)
    result = replay(raw, [{'assertion_id': 'synthetic', 'target_sec': 1,
                          'tolerance_sec': .01, 'expected': {'score_enemy': 99}}])[0]
    before = result['stages']['aggregate_admission']
    after = result['stages']['field_admission']
    assert before['snapshots'] == []
    assert after['snapshots'][0]['score_enemy'] == 1
    assert after['trace_snapshots'][0]['score_enemy'] == 1
    assert any(f['key'] == 'score_enemy' and f['value'] == 1 for f in after['facts'])
    assert raw == original


def test_global_package_sqlite_checkpoint_restore_preserves_field_support(tmp_path):
    from valorant_ai_coach.storage import SQLiteRepository
    package = builder().build(
        match_id='persist-global',
        video_metadata=VideoMetadata(Path('synthetic.mp4'), 2, 1920, 1080, 60,
                                     'h264', None, False, 1),
        hud_observations=[source(1)],
        hud_events=(hud_event('start', .5, 'round_start'),
                    hud_event('end', 1.5, 'round_end')),
    )[0]
    enriched = FactBuilder().enrich(package)
    repository = SQLiteRepository(tmp_path / 's01.db')
    repository.create_match('persist-global', 'synthetic.mp4')
    repository.save_round_package(enriched)
    repository.save_job_checkpoint('persist-global', 'analyzing', {
        'completed_rounds': [package['round_no']],
    })
    restored_repository = SQLiteRepository(tmp_path / 's01.db')
    restored = restored_repository.get_round_package('persist-global', package['round_no'])
    assert restored == enriched
    SchemaValidator().validate_round_package(restored)
    assert restored_repository.get_job_checkpoint('persist-global')['checkpoint'] == {
        'completed_rounds': [package['round_no']],
    }
    assert FactBuilder().enrich(restored)['deterministic_facts'] == enriched['deterministic_facts']


def test_replay_source_context_rejects_unbound_original_metadata(tmp_path):
    import hashlib
    import json

    from scripts.diagnostics.replay_snapshot_gate import recognition_context
    raw = tmp_path / 'raw_processing.json'
    raw.write_text('{}', encoding='utf-8')
    context, files = recognition_context(raw)
    assert context['status'].startswith('unavailable') and files == []
    metadata = tmp_path / 'run_metadata.json'
    metadata.write_text(json.dumps({'input_hashes': {raw.name: 'invalid'}}), encoding='utf-8')
    with pytest.raises(ValueError, match='does not bind'):
        recognition_context(raw)
    metadata.write_text(json.dumps({'input_hashes': {
        raw.name: hashlib.sha256(raw.read_bytes()).hexdigest(),
    }}), encoding='utf-8')
    context, files = recognition_context(raw)
    assert files == [metadata] and context['status'].startswith('original run bindings')
