"""Synthetic temporal contracts only; no real qualification or GT inputs."""
from copy import deepcopy
from dataclasses import replace

import pytest

from tests.unit.test_native_lifecycle import source_sequence
from tests.unit.test_qualified_ui_transition import scene_qualification
from tests.unit.test_unedited_ui_start import make_contract
from valorant_ai_coach.hud.unedited_lifecycle import UneditedRoundLifecycle
from valorant_ai_coach.hud.unedited_ui_start import UneditedUiStartTracker


def fixture(tmp_path, *, enabled=True, next_round=False):
    q = scene_qualification(tmp_path)
    rows, _, _ = source_sequence(q, two_rounds=True)
    # Extend synthetic native cadence, without loading source video or GT.
    template = deepcopy(rows[-1])
    for index in range(30, 90):
        row = deepcopy(template)
        row.update(source_pts_ticks=index * 20, source_pts_sec=index / 50,
                   source_pixel_sha256=f'{index:064x}')
        row['system_observation'].update(time_sec=index / 50, frame_index=index)
        rows.append(row)
    for index, row in enumerate(rows):
        obs = row['system_observation']
        if index >= 14:
            phase = next_round and 55 <= index <= 60
            timer = (0 if phase or next_round and index == 61 else
                     137 if next_round and index in (62, 63) else
                     97 if next_round and index >= 64 else 35 if index < 20 else 8)
            obs['state_flags'] = ['buy_phase_banner'] if phase else []
            obs['values'].update(buy_phase_visible=phase, round_time_remaining_sec=timer,
                                 round_time_remaining_display=f'{timer // 60}:{timer % 60:02}',
                                 score_ally=0, score_enemy=int(index >= 22))
            if phase:
                obs['quality']['roi_confidence']['center_phase_banner_semantic_text'] = .96
        row['system_evidence'] = {
            'assured_phase_scan_valid': True,
            'assured_round_result_present': 38 <= index <= 50,
            'assured_round_result_confidence': .95,
        }
    _, contract = make_contract(tmp_path, rows[0]['source_video_sha256'])
    if enabled:
        q = replace(q, components=q.components | {'ui_end_transition'})
    return rows, UneditedRoundLifecycle(
        UneditedUiStartTracker(contract, native_step_ticks=20), q,
    )


def replay(rows, tracker):
    return [d for row in rows if (d := tracker.advance(row, phase_scan_valid=True))]


def test_late_result_is_opt_in_and_retains_observed_timestamp_and_unknowns(tmp_path):
    rows, tracker = fixture(tmp_path)
    for row in rows[30:]:
        row['system_observation']['values'].update(score_ally=None, score_enemy=None)
    original = deepcopy(rows)
    decisions = replay(rows, tracker)
    assert [(d.kind, d.time_sec) for d in decisions] == [
        ('round_start', .12), ('round_end', .44),
    ]
    proof = decisions[-1].attributes['evidence_provenance']
    assert proof['timestamp_rule'] == 'first_observed_score_change'
    assert proof['confirmation_pts_sec'] == .82
    assert proof['clock_change']['after']['pts_sec'] == .40
    assert proof['clock_change']['after']['observed_display'] == '0:08'
    assert proof['score_after']['first']['values'] == [0, 1]
    assert proof['scope'] == 'global_system'
    assert decisions[-1].confidence == .95
    assert rows == original
    assert rows[41]['system_observation']['values']['score_enemy'] is None
    assert rows[41]['system_observation']['values']['hp'] is None


def test_existing_qualification_cannot_enable_delayed_result_path(tmp_path):
    rows, tracker = fixture(tmp_path, enabled=False)
    assert tracker.pending_end is None
    assert [d.kind for d in replay(rows, tracker)] == ['round_start']


def test_rearm_next_start_with_no_inferred_second_end(tmp_path):
    rows, tracker = fixture(tmp_path, next_round=True)
    decisions = replay(rows, tracker)
    assert [d.kind for d in decisions] == ['round_start', 'round_end', 'round_start']
    assert tracker.state == 'round_active'
    assert tracker.pending_end.pending is False


@pytest.mark.parametrize('failure', [
    'menu', 'spectator', 'occlusion', 'scan', 'phase', 'raw_phase', 'score_rollback',
    'partial_score_conflict', 'additional_clock', 'weak_result', 'brief_result',
    'result_jitter', 'no_result', 'weak_score', 'score_abstention_before_stability',
    'score_two_points', 'timer_weak', 'result_timeout',
])
def test_conflicts_and_missing_support_cannot_close_round(tmp_path, failure):
    rows, tracker = fixture(tmp_path)
    obs = rows[30]['system_observation']
    if failure in {'menu', 'spectator'}:
        obs['primary_state'] = 'buy_menu_open' if failure == 'menu' else 'spectator_first_person'
    elif failure == 'occlusion':
        obs['quality']['occluded_rois'] = ['round_timer']
    elif failure == 'scan':
        rows[30]['system_evidence']['assured_phase_scan_valid'] = False
    elif failure == 'phase':
        obs['values']['buy_phase_visible'] = True
    elif failure == 'raw_phase':
        rows[30]['system_evidence'].update(assured_phase_present=True,
                                          assured_phase_confidence=.95)
    elif failure in {'score_rollback', 'partial_score_conflict'}:
        obs['values'].update(score_enemy=0,
                             score_ally=0 if failure == 'score_rollback' else None)
    elif failure == 'additional_clock':
        obs['values'].update(round_time_remaining_sec=21, round_time_remaining_display='0:21')
    elif failure in {'weak_result', 'brief_result', 'result_jitter', 'no_result', 'result_timeout'}:
        for index, row in enumerate(rows):
            evidence = row['system_evidence']
            if failure == 'weak_result':
                evidence['assured_round_result_confidence'] = .89
            else:
                evidence['assured_round_result_present'] = (
                    index in (38, 39) if failure == 'brief_result' else
                    index in (38, 39, 42, 43) if failure == 'result_jitter' else
                    index >= 72 if failure == 'result_timeout' else False
                )
    elif failure == 'weak_score':
        for row in rows:
            row['system_observation']['quality']['roi_confidence']['score_enemy_value'] = .89
    elif failure == 'score_abstention_before_stability':
        rows[23]['system_observation']['values']['score_enemy'] = None
    elif failure == 'score_two_points':
        for row in rows[22:]:
            row['system_observation']['values']['score_enemy'] = 2
    else:
        rows[20]['system_observation']['quality']['roi_confidence']['round_timer_value'] = .89
        # Do not let the subsequent accepted read independently propose the same change.
        for row in rows[21:]:
            row['system_observation']['quality']['roi_confidence']['round_timer_value'] = .89
    assert [d.kind for d in replay(rows, tracker)] == ['round_start']
    assert tracker.start.started is True


@pytest.mark.parametrize('failure', ['gap', 'epoch', 'repeated_pixel', 'discontinuity'])
def test_source_break_discards_active_and_pending_state(tmp_path, failure):
    rows, tracker = fixture(tmp_path)
    if failure == 'gap':
        rows.pop(30)
    elif failure == 'epoch':
        rows[30]['source_epoch'] = 'next-epoch'
    elif failure == 'repeated_pixel':
        rows[30]['source_pixel_sha256'] = rows[29]['source_pixel_sha256']
    else:
        rows[30]['system_evidence']['discontinuity'] = True
    assert [d.kind for d in replay(rows, tracker)] == ['round_start']
    assert tracker.start.started is False
    assert tracker.pending_end.pending is False


def test_pending_state_is_visible_without_duplicate_event(tmp_path):
    rows, tracker = fixture(tmp_path)
    decisions = replay(rows[:38], tracker)
    assert [d.kind for d in decisions] == ['round_start']
    assert tracker.state == 'round_end_candidate'
    assert [d.kind for d in replay(rows[38:], tracker)] == ['round_end']
    assert tracker.state == 'round_ended'


def test_invalid_binding_clears_pending_even_when_caller_catches_error(tmp_path):
    rows, tracker = fixture(tmp_path)
    replay(rows[:30], tracker)
    assert tracker.pending_end.pending
    rows[30]['source_video_sha256'] = 'b' * 64
    with pytest.raises(ValueError, match='source binding'):
        tracker.advance(rows[30], phase_scan_valid=True)
    assert not tracker.pending_end.pending
    assert not tracker.start.started


def test_streaming_end_retains_system_actor_through_native_packages_and_trace(tmp_path):
    from pathlib import Path
    from types import SimpleNamespace

    from tests.e2e.trace_adapter import to_e2e_trace
    from valorant_ai_coach.events import EventSourceContract
    from valorant_ai_coach.hud.native_assured_start import replay_assured_starts
    from valorant_ai_coach.resources import resource_path
    from valorant_ai_coach.rounds import RoundPackageBuilder
    from valorant_ai_coach.schema_validation import SchemaValidator
    from valorant_ai_coach.video import VideoMetadata

    rows, tracker = fixture(tmp_path, next_round=True)
    original = deepcopy(rows)
    events, _ = replay_assured_starts(rows, tracker.qualification, tracker.start.contract)
    assert [(e['type'], e['actor']) for e in events] == [
        ('round_start', 'system'), ('round_end', 'system'), ('round_start', 'system'),
    ]
    assert events[1]['time_sec'] == .44
    proof = events[1]['attributes']['evidence_provenance']
    assert proof['source_pts_ticks'] == 440
    assert proof['confirmation_pts_sec'] == .82
    observations = tuple(row['system_observation'] for row in rows)
    packages = RoundPackageBuilder(
        contract=EventSourceContract.load(resource_path('config/event_source_contract_v1.json')),
        validator=SchemaValidator(),
    ).build(
        match_id='synthetic-streaming-end',
        video_metadata=VideoMetadata(Path('source.mp4'), 2, 1920, 1080, 50,
                                     'h264', None, False, 1),
        hud_observations=observations, hud_events=events,
    )
    assert len(packages) == 2
    trace = to_e2e_trace(SimpleNamespace(
        round_packages=packages, observations=observations, visual_observations=(),
    ))
    assert [(e['type'], e['actor'], e['time_sec']) for e in trace['events']] == [
        (e['type'], e['actor'], e['time_sec']) for e in events
    ]
    assert trace['events'][1]['attributes'] == events[1]['attributes']
    phase = [s for s in trace['state_intervals'] if s['state'] == 'buy_phase_banner'
             and s['interval'][0] >= 1.1]
    assert phase and all(s['round_id'] == 'sample_round_2' for s in phase)
    assert rows == original


def test_temporal_component_requires_source_assurance_and_qualified_readers(tmp_path):
    import json

    from tests.unit.test_global_round_lifecycle import report
    from valorant_ai_coach.hud.global_lifecycle import GlobalLifecycleQualification

    data = report()
    data['components']['ui_transition'] = deepcopy(data['components']['continuity'])
    data['components']['ui_end_transition'] = deepcopy(data['components']['round_result'])
    path = tmp_path / 'qualification.json'
    path.write_text(json.dumps(data))
    _, contract = make_contract(tmp_path, 'a' * 64)
    with pytest.raises(ValueError, match='source assurance'):
        GlobalLifecycleQualification.load(path, data['profile_fingerprint'])
    q = GlobalLifecycleQualification.load(
        path, data['profile_fingerprint'], unedited_input_contract=contract,
    )
    assert 'ui_end_transition' in q.components
    data['components'].pop('score')
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='qualified inputs'):
        GlobalLifecycleQualification.load(
            path, data['profile_fingerprint'], unedited_input_contract=contract,
        )
