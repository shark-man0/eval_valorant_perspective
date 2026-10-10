from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.e2e.trace_adapter import to_e2e_trace
from tests.integration.test_hud_video_processor import FakeAnalyzer, FakeVideo, build_processor
from tests.unit.test_native_lifecycle import source_sequence
from tests.unit.test_qualified_ui_transition import scene_qualification
from valorant_ai_coach.hud.native_event_merge import (
    merge_native_boundaries,
    validated_native_boundaries,
)
from valorant_ai_coach.hud.native_lifecycle import _join_native_lifecycle
from valorant_ai_coach.video import FrameSample, VideoMetadata


def result(tmp_path):
    q = scene_qualification(tmp_path)
    rows, scenes, measurements = source_sequence(q, two_rounds=True)
    return q, _join_native_lifecycle(rows, scenes, measurements, q)


def test_native_events_replay_and_identical_duplicate_suppression(tmp_path):
    q, native = result(tmp_path)
    events = validated_native_boundaries(native, q, native.source_rows[0]['source_video_sha256'])
    assert events == native.hud_events
    assert merge_native_boundaries(events, events) == events
    assert native.hud_events == events


def test_stale_qualification_is_rejected_even_when_transport_has_no_events(tmp_path):
    q, native = result(tmp_path)
    stale = replace(native, hud_events=(), qualification=replace(
        q, recognizer_fingerprint='a' * 64,
    ))
    with pytest.raises(ValueError, match='qualification/code/profile changed'):
        validated_native_boundaries(stale, q, native.source_rows[0]['source_video_sha256'])


@pytest.mark.parametrize('changed', ['video', 'event', 'pixel', 'cadence', 'ownership', 'ui'])
def test_transport_tampering_or_foreign_source_cannot_reach_sampled_processing(tmp_path, changed):
    q, native = result(tmp_path)
    native = deepcopy(native)
    video_sha = native.source_rows[0]['source_video_sha256']
    if changed == 'video':
        video_sha = 'b' * 64
    elif changed == 'event':
        native.hud_events[0]['time_sec'] += .01
    elif changed == 'pixel':
        native.source_rows[6]['source_pixel_sha256'] = 'b' * 64
    elif changed == 'cadence':
        native.source_rows[6]['source_pts_ticks'] += 1
    elif changed == 'ownership':
        native.source_rows[6]['system_observation']['values']['hp'] = 100
    else:
        native.source_rows[6]['system_evidence']['global_ui_transition']['source_epoch'] = 'other'
    with pytest.raises(ValueError):
        validated_native_boundaries(native, q, video_sha)


def test_competing_sampled_boundary_is_rejected_instead_of_relabelled(tmp_path):
    _, native = result(tmp_path)
    conflict = deepcopy(native.hud_events[0])
    conflict['time_sec'] += .01
    with pytest.raises(ValueError, match='conflict'):
        merge_native_boundaries((conflict,), native.hud_events)


def test_player_event_cannot_be_injected_through_native_merge(tmp_path):
    _, native = result(tmp_path)
    wrong = deepcopy(native.hud_events[0])
    wrong.update(type='player_death', actor='player')
    with pytest.raises(ValueError, match='system round'):
        merge_native_boundaries((), (wrong,))


def qualified_processor(tmp_path):
    q, native = result(tmp_path)
    analyzer = FakeAnalyzer()
    original = analyzer.observe_frames

    def observe(*args, **kwargs):
        measured = original(*args, **kwargs)
        measured.hud_events = ()
        return measured

    analyzer.observe_frames = observe
    analyzer._base_fingerprint = lambda: q.profile_fingerprint
    analyzer.global_qualification = q
    analyzer.global_qualification_path = tmp_path / 'qualification.json'
    video = tmp_path / 'source.mp4'
    video.write_bytes(b'synthetic-video')
    metadata = VideoMetadata(video, 1, 1920, 1080, 60, 'h264', None, False, video.stat().st_size)
    processor = build_processor(FakeVideo(), analyzer)
    frames = [FrameSample(time, Path(f'{time}.jpg')) for time in (.04, .10, .20, .40, .50, .58)]
    return processor, metadata, frames, native


def test_sampled_processing_preserves_player_observations_during_native_merge(tmp_path):
    processor, metadata, frames, native = qualified_processor(tmp_path)
    processed = processor.process_frames(
        metadata, 'synthetic-merge', frames, native_lifecycle=native,
    )
    assert len(processed.round_packages) == 2
    assert processed.sampled_frame_count == len(frames)
    assert [obs['time_sec'] for obs in processed.observations] == [f.time_sec for f in frames]
    assert all(obs['values']['hp'] == 100 for obs in processed.observations)
    assert processed.round_packages[0]['round_window']['start_sec'] <= .04
    assert processed.round_packages[1]['round_window']['start_sec'] <= .40
    trace = to_e2e_trace(SimpleNamespace(
        round_packages=processed.round_packages, observations=processed.observations,
        visual_observations=(),
    ))
    boundaries = [e for e in trace['events'] if e['type'] in {'round_start', 'round_end'}]
    assert [(e['type'], e['actor'], e['time_sec']) for e in boundaries] == [
        ('round_start', 'system', .12), ('round_end', 'system', .30),
        ('round_start', 'system', .46),
    ]
    assert any(e['type'] == 'state_snapshot' for e in trace['events'])
    assert [e['attributes'] for e in boundaries] == [e['attributes'] for e in native.hud_events]


@pytest.mark.parametrize('invalid', ['short', 'epoch', 'hash', 'future', 'weak'])
def test_unqualified_preparation_provenance_cannot_suppress_leading_fragment(tmp_path, invalid):
    processor, metadata, frames, native = qualified_processor(tmp_path)
    events = deepcopy(native.hud_events)
    proof = events[0]['attributes']['evidence_provenance']
    if invalid == 'short':
        proof['preparation_pts_sec'] = [.09, .10]
    elif invalid == 'epoch':
        proof['source_epoch'] = ''
    elif invalid == 'hash':
        proof['qualification_sha256'] = 'q' * 64
    elif invalid == 'future':
        proof['preparation_pts_sec'] = [.13, .20]
    else:
        events[0]['confidence'] = .89
    observations = processor.analyzer.observe_frames(frames, video_metadata=metadata).observations
    packages = processor.package_builder.build(
        match_id='synthetic-invalid-preparation', video_metadata=metadata,
        hud_observations=observations, hud_events=events,
    )
    assert len(packages) == 3


@pytest.mark.parametrize('changed', ['video', 'qualification'])
def test_terminal_mutation_withholds_complete_processing_result(tmp_path, changed):
    processor, metadata, frames, native = qualified_processor(tmp_path)
    original = processor.package_builder.build

    def build(*args, **kwargs):
        packages = original(*args, **kwargs)
        path = metadata.path if changed == 'video' else processor.analyzer.global_qualification_path
        path.write_bytes(path.read_bytes() + b'changed')
        return packages

    processor.package_builder.build = build
    with pytest.raises((ValueError, RuntimeError)):
        processor.process_frames(metadata, 'synthetic-merge', frames, native_lifecycle=native)


def test_processor_rejects_native_result_without_analyzer_qualification(tmp_path):
    processor, metadata, frames, native = qualified_processor(tmp_path)
    processor.analyzer.global_qualification = None
    with pytest.raises(RuntimeError, match='qualified native analyzer'):
        processor.process_frames(metadata, 'synthetic-merge', frames, native_lifecycle=native)
