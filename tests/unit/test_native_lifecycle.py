from copy import deepcopy
from types import SimpleNamespace

import numpy as np
import pytest

from tests.e2e.trace_adapter import to_e2e_trace
from tests.unit.test_global_round_lifecycle import digest
from tests.unit.test_global_start_hypothesis import observation
from tests.unit.test_native_scene_evidence import inputs as inputs
from tests.unit.test_native_scene_evidence import setup as setup
from tests.unit.test_qualified_ui_transition import scene_qualification
from tests.unit.test_semantic_text import _profile
from valorant_ai_coach.events import EventSourceContract
from valorant_ai_coach.hud.native_lifecycle import _join_native_lifecycle
from valorant_ai_coach.hud.templates import HudTemplateProfile
from valorant_ai_coach.resources import resource_path
from valorant_ai_coach.rounds import RoundPackageBuilder
from valorant_ai_coach.schema_validation import SchemaValidator
from valorant_ai_coach.video import VideoMetadata


def source_sequence(q, two_rounds=False):
    # Uniform synthetic native cadence. No actual qualification is claimed.
    systems, scenes, measurements = [], [], []
    for i in range(30 if two_rounds else 15):
        phase = i <= 5 or 17 <= i <= 22
        timer = 0 if phase or i in (6, 23) else (128 if i in (7, 8) else 93)
        display = f'{timer // 60}:{timer % 60:02}'
        obs = observation(i, i / 50, phase=phase, timer=timer)
        obs['values'].update(
            round_time_remaining_display=display,
            round_time_remaining_display_provenance={
                'reader': 'round_timer', 'sources': ['synthetic-reader'],
                'confidence': .95, 'cross_checked': True,
            }, score_ally=int(i >= 15), score_enemy=0,
        )
        obs['quality']['roi_confidence'].update(score_ally_value=.95, score_enemy_value=.95)
        source = {
            'source_video_sha256': digest('synthetic-video'), 'source_epoch': 'synthetic-epoch',
            'source_pts_ticks': i * 20, 'source_time_base': '1/1000',
            'source_pts_sec': i / 50, 'source_pixel_sha256': digest(f'synthetic-pixel-{i}'),
        }
        systems.append({**source, 'system_observation': obs, 'system_evidence': {}})
        proof = {
            **source, 'previous_source_pts_ticks': (i - 1) * 20,
            'previous_source_pts_sec': (i - 1) / 50,
            'previous_source_pixel_sha256': digest(f'synthetic-pixel-{i-1}'),
            'segment': 'synthetic-epoch', 'scope': 'scene_only',
            'clock_independent': True, 'background_checked': True,
            'qualification_sha256': q.report_sha256, 'profile_fingerprint': q.profile_fingerprint,
            'recognizer_fingerprint': q.recognizer_fingerprint,
            'witness_cells': [[0, 0], [0, 2], [2, 1]], 'witness_ncc': [.95, .96, .97],
            'confidence': .95,
        }
        scenes.append({**source, 'system_scene_evidence':
                       {'global_scene_continuity': proof} if i else {}})
        measurements.append({
            'phase_absence_matched': i in (6, 23), 'confidence': .95,
            'round_result_matched': i in (15, 16), 'round_result_confidence': .95,
        })
    return systems, scenes, measurements


def test_native_start_end_next_start_preserve_actor_provenance_packages_and_trace(tmp_path):
    from pathlib import Path

    q = scene_qualification(tmp_path)
    systems, scenes, measurements = source_sequence(q, two_rounds=True)
    original = deepcopy((systems, scenes, measurements))
    result = _join_native_lifecycle(systems, scenes, measurements, q)
    assert [(e['type'], e['actor'], e['time_sec']) for e in result.hud_events] == [
        ('round_start', 'system', .12), ('round_end', 'system', .30),
        ('round_start', 'system', .46),
    ]
    assert (systems, scenes, measurements) == original
    for event in result.hud_events:
        provenance = event['attributes']['evidence_provenance']
        assert provenance['source_epoch'] == 'synthetic-epoch'
        assert provenance['source_pts_sec'] == event['time_sec']
        assert provenance['source_pts_ticks'] == round(event['time_sec'] * 1000)
    packages = RoundPackageBuilder(
        contract=EventSourceContract.load(resource_path('config/event_source_contract_v1.json')),
        validator=SchemaValidator(),
    ).build(
        match_id='synthetic-native-lifecycle',
        video_metadata=VideoMetadata(Path('source.mp4'), 1, 1920, 1080, 60, 'h264', None, False, 1),
        hud_observations=result.observations, hud_events=result.hud_events,
    )
    assert len(packages) == 2
    trace = to_e2e_trace(SimpleNamespace(
        round_packages=packages, observations=result.observations, visual_observations=(),
    ))
    assert [(e['type'], e['actor'], e['time_sec']) for e in trace['events']] == [
        ('round_start', 'system', .12), ('round_end', 'system', .30),
        ('round_start', 'system', .46),
    ]
    for native, traced in zip(result.hud_events, trace['events'], strict=True):
        assert native['attributes'] == traced['attributes']
    assert not any(row['owner'] == 'self' for row in trace['ownership_intervals'])
    preparation = [row for row in trace['state_intervals']
                   if row['state'] == 'buy_phase_banner' and row['interval'][0] >= .34]
    assert preparation
    assert all(row['round_id'] == 'sample_round_2' for row in preparation)
    assert any(row['interval'][0] < .46 for row in preparation)


@pytest.mark.parametrize('mutation', ['missing_absence', 'weak_absence', 'scene_break',
                                    'spectator', 'phase_still_present'])
def test_missing_or_conflicting_positive_ui_evidence_cannot_start(tmp_path, mutation):
    q = scene_qualification(tmp_path)
    systems, scenes, measurements = source_sequence(q)
    if mutation == 'missing_absence':
        measurements[6]['phase_absence_matched'] = False
    elif mutation == 'weak_absence':
        measurements[6]['confidence'] = .89
    elif mutation == 'scene_break':
        scenes[6]['system_scene_evidence'] = {}
    elif mutation == 'spectator':
        systems[6]['system_observation']['primary_state'] = 'spectator_first_person'
    else:
        systems[6]['system_observation']['state_flags'] = ['buy_phase_banner']
    assert _join_native_lifecycle(systems, scenes, measurements, q).hud_events == ()


@pytest.mark.parametrize('mutation', ['pixel', 'epoch', 'ticks', 'video', 'previous_pixel',
                                    'scene_supplies_ui', 'coverage'])
def test_native_join_rejects_mismatched_or_external_producer_bindings(tmp_path, mutation):
    q = scene_qualification(tmp_path)
    systems, scenes, measurements = source_sequence(q)
    names = {'pixel': 'source_pixel_sha256', 'epoch': 'source_epoch',
             'ticks': 'source_pts_ticks', 'video': 'source_video_sha256'}
    if mutation in names:
        scenes[6][names[mutation]] = 'other-source'
    elif mutation == 'previous_pixel':
        scenes[6]['system_scene_evidence']['global_scene_continuity'][
            'previous_source_pixel_sha256'
        ] = digest('other-previous')
    elif mutation == 'scene_supplies_ui':
        scenes[6]['system_scene_evidence']['global_ui_transition'] = {'confidence': 1}
    else:
        measurements.pop()
    with pytest.raises(ValueError):
        _join_native_lifecycle(systems, scenes, measurements, q)


def test_positive_absence_role_requires_three_group_reference_and_does_not_use_nonmatch(tmp_path):
    path, layout, frame = _profile(tmp_path, signal='phase_absence_template')
    profile = HudTemplateProfile.load(path)
    assert not profile.reader_diagnostics
    assert profile.detect_signals(frame, layout)['phase_absence_template'] is True
    assert 'phase_absence_template' not in profile.detect_signals(np.zeros_like(frame), layout)


def test_analyzer_owned_native_entrance_cannot_start_without_absence_reference(setup):
    analyzer, frames, _, _, _, _ = setup
    result = analyzer.observe_qualified_native_lifecycle_frames(frames, native_step_ticks=256)
    assert len(result.observations) == 2
    assert result.hud_events == ()
    assert not any('global_ui_transition' in r['system_evidence'] for r in result.source_rows)


@pytest.mark.parametrize('changed', ['native', 'report'])
def test_native_lifecycle_withholds_output_after_terminal_mutation(setup, monkeypatch, changed):
    analyzer, frames, report_path, _, _, _ = setup
    original = analyzer.collect_qualified_native_scene_window

    def mutate(*args, **kwargs):
        rows = original(*args, **kwargs)
        path = frames[-1].path if changed == 'native' else report_path
        path.write_bytes(path.read_bytes() + b'changed')
        return rows

    monkeypatch.setattr(analyzer, 'collect_qualified_native_scene_window', mutate)
    with pytest.raises((RuntimeError, ValueError)):
        analyzer.observe_qualified_native_lifecycle_frames(frames, native_step_ticks=256)
