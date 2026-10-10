"""Synthetic qualification/transport fixtures, never real reader qualification."""
from copy import deepcopy
from dataclasses import replace

import pytest

from tests.e2e.trace_adapter import to_e2e_trace
from tests.unit.test_native_event_merge import qualified_processor
from tests.unit.test_native_lifecycle_provider import provider
from tests.unit.test_unedited_ui_start import make_contract
from valorant_ai_coach.application.hud_video_processor import NativeLifecycleOptions
from valorant_ai_coach.hud.native_assured_start import replay_assured_starts
from valorant_ai_coach.hud.native_event_merge import validated_native_boundaries


def assured(tmp_path):
    tmp_path.mkdir(parents=True, exist_ok=True)
    processor, metadata, frames, original = qualified_processor(tmp_path)
    path, contract = make_contract(tmp_path, original.source_rows[0]['source_video_sha256'])
    rows = tuple({**deepcopy(row), 'system_evidence': {'assured_phase_scan_valid': True}}
                 for row in original.source_rows)
    events, diagnostics = replay_assured_starts(rows, original.qualification, contract)
    native = replace(original, source_rows=rows, hud_events=events, diagnostics=diagnostics,
                     unedited_input_contract=contract, input_contract_path=path)
    processor.analyzer._native_profile_readers = True
    processor.analyzer._native_loaded_base_fingerprint = original.qualification.profile_fingerprint
    return processor, metadata, frames, native


def test_qualified_system_start_reaches_package_and_trace(tmp_path):
    processor, metadata, frames, native = assured(tmp_path)
    assert len(native.hud_events) == 1
    assert native.hud_events[0]['actor'] == 'system'
    result = processor.process_frames(metadata, 'assured', frames, require_detected_rounds=False,
                                      native_lifecycle=native)
    assert len(result.round_packages) == 1
    trace = to_e2e_trace(result)
    event = next(e for e in trace['events'] if e['type'] == 'round_start')
    assert event['actor'] == 'system'
    assert event['time_sec'] == native.hud_events[0]['time_sec']
    assert event['attributes']['evidence_provenance']['input_contract_sha256'] == (
        native.unedited_input_contract.fingerprint
    )
    assert not any(e['type'] == 'round_end' for e in trace['events'])


def lifecycle_rows(tmp_path):
    processor, metadata, frames, native = assured(tmp_path)
    rows = deepcopy(native.source_rows)
    rows[15]['system_evidence'].update(
        assured_round_result_present=True, assured_round_result_confidence=.95,
    )
    return processor, metadata, frames, native, rows


def test_qualified_assured_end_rearms_next_round_and_reaches_trace(tmp_path):
    processor, metadata, frames, native, rows = lifecycle_rows(tmp_path)
    events, diagnostics = replay_assured_starts(
        rows, native.qualification, native.unedited_input_contract,
    )
    assert [(e['type'], e['actor'], e['time_sec']) for e in events] == [
        ('round_start', 'system', .12), ('round_end', 'system', .30),
        ('round_start', 'system', .46),
    ]
    assert diagnostics[15]['state'] == 'round_ended'
    assert diagnostics[17]['state'] == 'next_round_preparation'
    native = replace(native, source_rows=rows, observations=tuple(
        r['system_observation'] for r in rows
    ), hud_events=events, diagnostics=diagnostics)
    result = processor.process_frames(metadata, 'assured', frames,
                                      require_detected_rounds=False, native_lifecycle=native)
    assert len(result.round_packages) == 2
    trace = to_e2e_trace(result)
    boundaries = [e for e in trace['events'] if e['type'] in {'round_start', 'round_end'}]
    assert [(e['type'], e['actor'], e['time_sec']) for e in boundaries] == [
        (e['type'], e['actor'], e['time_sec']) for e in events
    ]


@pytest.mark.parametrize('invalid', [
    'score_unknown', 'score_low', 'score_bool', 'two_points', 'result_low',
    'result_absent', 'menu', 'occluded', 'previous_scan', 'previous_occluded',
    'spectator', 'remote', 'conflicting_flag',
    'score_confidence_missing', 'legacy_or_geometry_confidence_only',
    'raw_phase', 'previous_raw_phase',
])
@pytest.mark.parametrize('combat_report', [False, True])
def test_assured_end_requires_current_result_and_distinct_accepted_scores(
    tmp_path, invalid, combat_report,
):
    _, _, _, native, rows = lifecycle_rows(tmp_path)
    row = rows[15]
    obs = row['system_observation']
    if combat_report:
        for index in (14, 15):
            rows[index]['system_observation']['state_flags'].append('combat_report_visible')
    if invalid == 'score_unknown':
        obs['values']['score_ally'] = None
    elif invalid == 'score_low':
        obs['quality']['roi_confidence']['score_ally_value'] = .89
    elif invalid == 'score_bool':
        obs['values']['score_ally'] = True
    elif invalid == 'two_points':
        obs['values']['score_ally'] = 2
    elif invalid == 'result_low':
        row['system_evidence']['assured_round_result_confidence'] = .89
    elif invalid == 'result_absent':
        row['system_evidence']['assured_round_result_present'] = False
    elif invalid == 'menu':
        obs['primary_state'] = 'buy_menu_open'
    elif invalid == 'occluded':
        obs['quality']['occluded_rois'] = ['center_phase_banner']
    elif invalid == 'previous_scan':
        rows[14]['system_evidence']['assured_phase_scan_valid'] = False
    elif invalid in {'raw_phase', 'previous_raw_phase'}:
        rows[15 if invalid == 'raw_phase' else 14]['system_evidence'].update(
            assured_phase_present=True, assured_phase_confidence=.95,
        )
    elif invalid == 'previous_occluded':
        rows[14]['system_observation']['quality']['occluded_rois'] = ['round_timer']
    elif invalid == 'spectator':
        obs['primary_state'] = 'spectator_first_person'
    elif invalid == 'remote':
        obs['primary_state'] = 'remote_control_view'
    elif invalid in {'score_confidence_missing', 'legacy_or_geometry_confidence_only'}:
        obs['quality']['roi_confidence'].pop('score_ally_value')
        if invalid == 'legacy_or_geometry_confidence_only':
            obs['quality']['roi_confidence'].update(ally_score_value=.99, ally_score=.99)
    else:
        obs['state_flags'].append('vision_obscured_smoke')
    events, _ = replay_assured_starts(rows, native.qualification, native.unedited_input_contract)
    assert [e['type'] for e in events] == ['round_start']


@pytest.mark.parametrize('invalid', ['partial', 'bool_confidence', 'low', 'invalid_scan'])
def test_raw_phase_contract_rejects_partial_or_unaccepted_producer_evidence(tmp_path, invalid):
    _, _, _, native = assured(tmp_path)
    rows = deepcopy(native.source_rows)
    evidence = rows[6]['system_evidence']
    evidence.update(assured_phase_present=True, assured_phase_confidence=.95)
    if invalid == 'partial':
        evidence.pop('assured_phase_confidence')
    elif invalid == 'bool_confidence':
        evidence['assured_phase_confidence'] = True
    elif invalid == 'low':
        evidence['assured_phase_confidence'] = .89
    else:
        evidence['assured_phase_scan_valid'] = False
    with pytest.raises(ValueError, match='current phase presence'):
        replay_assured_starts(rows, native.qualification, native.unedited_input_contract)


@pytest.mark.parametrize('indices', [(14,), (15,), (14, 15)])
def test_combat_report_does_not_claim_ownership_or_veto_qualified_global_end(tmp_path, indices):
    _, _, _, native, rows = lifecycle_rows(tmp_path)
    for index in indices:
        observation = rows[index]['system_observation']
        observation['primary_state'] = 'unknown'
        observation['state_flags'].append('combat_report_visible')
        observation['values']['combat_report_visible'] = True
    original = deepcopy(rows)
    events, _ = replay_assured_starts(rows, native.qualification, native.unedited_input_contract)
    assert [(event['type'], event['actor']) for event in events] == [
        ('round_start', 'system'), ('round_end', 'system'), ('round_start', 'system'),
    ]
    assert rows == original
    for index in indices:
        values = rows[index]['system_observation']['values']
        assert values['player_specific_hud_valid'] is False
        assert values['hp'] is None and values['weapon_text'] is None
        assert rows[index]['system_observation']['view_context'][
            'is_player_world_view_trustworthy'
        ] is False


def test_assured_end_cannot_inherit_start_only_qualification(tmp_path):
    _, _, _, native, rows = lifecycle_rows(tmp_path)
    q = replace(native.qualification, components=frozenset({'timer', 'purchase_phase',
                                                          'ui_transition'}))
    with pytest.raises(ValueError, match='qualified producer-owned result'):
        replay_assured_starts(rows, q, native.unedited_input_contract)


@pytest.mark.parametrize('tamper', ['contract', 'scan', 'hp_zero', 'event', 'index', 'result'])
def test_assured_transport_cannot_publish_tampered_inputs(tmp_path, tamper):
    _, _, _, native = assured(tmp_path)
    native = deepcopy(native)
    if tamper == 'contract':
        native.input_contract_path.write_bytes(native.input_contract_path.read_bytes()+b'\n')
    elif tamper == 'scan':
        native.source_rows[6]['system_evidence']['assured_phase_scan_valid'] = False
    elif tamper == 'hp_zero':
        native.source_rows[0]['system_observation']['values']['hp'] = 0
    elif tamper == 'event':
        native.hud_events[0]['actor'] = 'player'
    elif tamper == 'result':
        native.source_rows[15]['system_evidence'].update(
            assured_round_result_present=True, assured_round_result_confidence=.95,
        )
    else:
        native.source_rows[0]['system_observation']['frame_index'] += 1
    with pytest.raises(ValueError):
        validated_native_boundaries(native, native.qualification,
                                    native.source_rows[0]['source_video_sha256'])


def test_auto_collection_selects_assured_provider_without_scene_assets(tmp_path, monkeypatch):
    processor, metadata, original, calls = provider(tmp_path, monkeypatch)
    _, _, _, native = assured(tmp_path / 'assured')
    processor.analyzer._native_profile_readers = True
    processor.analyzer._native_loaded_base_fingerprint = original.qualification.profile_fingerprint
    processor.analyzer.scene_source_binding = None

    def collect(frames, **kwargs):
        assert kwargs['input_contract_path'] == native.input_contract_path
        calls.append('assured')
        return native

    processor.analyzer.observe_qualified_unedited_native_start_frames = collect
    measured = processor.collect_native_lifecycle(metadata, NativeLifecycleOptions(
        1000, unedited_input_contract_path=native.input_contract_path,
    ))
    assert measured == native
    assert calls[-1] == 'terminal'
    assert calls.count('assured') == 1
    assert 'observe' not in calls


def test_injected_reader_cannot_inherit_assured_qualification(tmp_path):
    processor, metadata, frames, native = assured(tmp_path)
    processor.analyzer._native_profile_readers = False
    with pytest.raises(ValueError, match='injected'):
        processor.process_frames(metadata, 'test', frames, native_lifecycle=native)


@pytest.mark.parametrize('break_kind', [None, 'content_jump', 'discontinuity'])
def test_analyzer_owned_collection_and_terminal_reader_guard(tmp_path, monkeypatch, break_kind):
    from types import SimpleNamespace

    from valorant_ai_coach.hud.native_assured_start import collect_qualified_assured_start

    processor, metadata, original, _ = provider(tmp_path, monkeypatch)
    _, _, _, expected = assured(tmp_path / 'source')
    analyzer = processor.analyzer
    analyzer._native_profile_readers = True
    analyzer._native_loaded_base_fingerprint = original.qualification.profile_fingerprint
    analyzer.fingerprint = analyzer._base_fingerprint
    calls = []

    def observe(frames, received_metadata, **kwargs):
        assert received_metadata == metadata
        assert kwargs == {'_build_events': False}
        calls.append(len(frames))
        scans = [{'phase_scan_valid': True} for _ in frames]
        if break_kind:
            scans[6][break_kind] = True
        return SimpleNamespace(
            observations=original.observations,
            native_ui_measurements=scans,
        )

    analyzer.observe_frames = observe
    with processor.video.native_window(metadata.path) as frames:
        result = collect_qualified_assured_start(
            analyzer, frames, native_step_ticks=20,
            input_contract_path=expected.input_contract_path, video_metadata=metadata,
        )
    if break_kind:
        assert result.source_rows[6]['system_evidence'][break_kind] is True
        assert result.diagnostics[6]['state'] == 'unobserved'
        assert all(e['time_sec'] > .12 for e in result.hud_events)
        assert all(e['attributes']['evidence_provenance']['continuity_segment'] == 1
                   for e in result.hud_events)
    else:
        assert result.hud_events == expected.hud_events
    assert calls == [30]
    assert all(r['system_observation']['values']['hp'] is None for r in result.source_rows)


@pytest.mark.parametrize('break_kind', ['content_jump', 'discontinuity', 'repeated_pixel'])
@pytest.mark.parametrize('index', [14, 29])
def test_receiver_rejects_package_extension_across_native_break(tmp_path, break_kind, index):
    _, _, _, native = assured(tmp_path)
    rows = deepcopy(native.source_rows)
    if break_kind == 'repeated_pixel':
        rows[index]['source_pixel_sha256'] = rows[index-1]['source_pixel_sha256']
    else:
        rows[index]['system_evidence'][break_kind] = True
    events, diagnostics = replay_assured_starts(
        rows, native.qualification, native.unedited_input_contract,
    )
    assert events[0]['time_sec'] == .12
    assert diagnostics[index]['state'] == 'unobserved'
    native = replace(native, source_rows=rows, hud_events=events, diagnostics=diagnostics)
    with pytest.raises(ValueError, match='segment-local package transport'):
        validated_native_boundaries(native, native.qualification,
                                    rows[0]['source_video_sha256'])


@pytest.mark.parametrize('value', [1, 'true', None])
def test_break_marker_requires_explicit_boolean(tmp_path, value):
    _, _, _, native = assured(tmp_path)
    rows = deepcopy(native.source_rows)
    rows[6]['system_evidence']['discontinuity'] = value
    with pytest.raises(ValueError, match='producer-owned phase scan'):
        replay_assured_starts(rows, native.qualification, native.unedited_input_contract)


@pytest.mark.parametrize('marker', ['content_jump', 'discontinuity', 'repeated_pixel'])
def test_native_source_break_reaches_hud_visual_packages_and_trace(tmp_path, marker):
    from valorant_ai_coach.hud.native_event_merge import native_source_breaks

    processor, metadata, frames, native = assured(tmp_path)
    rows = deepcopy(native.source_rows)
    if marker == 'repeated_pixel':
        rows[14]['source_pixel_sha256'] = rows[13]['source_pixel_sha256']
    else:
        rows[14]['system_evidence'][marker] = True
    events, diagnostics = replay_assured_starts(
        rows, native.qualification, native.unedited_input_contract,
    )
    native = replace(native, source_rows=rows, hud_events=events, diagnostics=diagnostics)
    assert native_source_breaks(native) == (.28,)
    seen = []
    observe = processor.analyzer.observe_frames
    processor.analyzer.supports_native_source_breaks = True

    def observe_with_cuts(frames, *, additional_signals, **kwargs):
        assert [f.time_sec for f, s in zip(frames, additional_signals, strict=True)
                if s.get('discontinuity')] == [.40]
        seen.append('hud')
        return observe(frames, **kwargs)

    processor.analyzer.observe_frames = observe_with_cuts
    visual = processor.visual_analyzer.analyze

    def visual_with_cuts(*args, continuity_breaks, **kwargs):
        assert continuity_breaks == (.28,)
        seen.append('visual')
        return visual(*args, continuity_breaks=continuity_breaks, **kwargs)

    processor.visual_analyzer.analyze = visual_with_cuts
    result = processor.process_frames(metadata, 'break', frames, native_lifecycle=native,
                                      require_detected_rounds=False)
    assert seen == ['hud', 'visual']
    assert all(not p['round_window']['start_sec'] < .28 < p['round_window']['end_sec']
               for p in result.round_packages)
    trace = to_e2e_trace(result)
    boundaries = [e for e in trace['events'] if e['type'] in {'round_start', 'round_end'}]
    assert [(e['type'], e['time_sec']) for e in boundaries] == [
        ('round_start', .12), ('round_start', .46),
    ]
    assert all(e['actor'] == 'system' for e in boundaries)


def test_source_break_input_cannot_be_silently_ignored_by_consumer(tmp_path):
    from valorant_ai_coach.application.hud_video_processor import HudVideoProcessingError

    processor, metadata, frames, native = assured(tmp_path)
    rows = deepcopy(native.source_rows)
    rows[29]['system_evidence']['discontinuity'] = True
    events, diagnostics = replay_assured_starts(
        rows, native.qualification, native.unedited_input_contract,
    )
    native = replace(native, source_rows=rows, hud_events=events, diagnostics=diagnostics)
    with pytest.raises(HudVideoProcessingError, match='compatible consumers'):
        processor.process_frames(metadata, 'unsupported', frames, native_lifecycle=native)


def test_caller_cut_list_must_match_replayed_source_breaks(tmp_path):
    _, _, _, native = assured(tmp_path)
    with pytest.raises(ValueError, match='source-break transport mismatch'):
        validated_native_boundaries(native, native.qualification,
                                    native.source_rows[0]['source_video_sha256'],
                                    continuity_breaks=(.28,))


def test_pass_a_preflight_detects_late_native_cut_mutation(tmp_path, monkeypatch):
    from valorant_ai_coach.application.hud_video_processor import HudVideoProcessingError

    processor, metadata, _, native = assured(tmp_path)
    processor.analyzer.supports_native_source_breaks = True
    calls = []

    def finish(**kwargs):
        calls.append('finish')
        # The events remain identical, but the source segmentation changes.
        native.source_rows[29]['system_evidence']['discontinuity'] = True
        return object()

    monkeypatch.setattr(processor, '_process_frames', finish)
    with pytest.raises(HudVideoProcessingError, match='after Pass A preflight'):
        processor.process(metadata=metadata, match_id='mutation', output_dir=tmp_path / 'frames',
                          native_lifecycle=native, require_detected_rounds=False)
    assert calls == ['finish']


def test_sampled_break_mapping_keeps_native_time_and_frame_order():
    from pathlib import Path

    from valorant_ai_coach.application.hud_video_processor import HudVideoProcessor
    from valorant_ai_coach.video import FrameSample

    frames = [FrameSample(.4, Path('b.jpg')), FrameSample(.2, Path('a.jpg'))]
    signals = HudVideoProcessor._hud_break_inputs(frames, (.1, .25, .3, .8))
    assert signals['additional_signals'] == [{'discontinuity': True}, {'discontinuity': True}]
    assert [frame.time_sec for frame in frames] == [.4, .2]
