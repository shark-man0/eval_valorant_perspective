import hashlib
import json
from dataclasses import replace
from fractions import Fraction
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from valorant_ai_coach.hud.analyzers import HudNotCalibratedError, RealHudAnalyzer
from valorant_ai_coach.hud.models import HudObservationV2
from valorant_ai_coach.hud.native_system_input import calibration_prefix_provenance
from valorant_ai_coach.hud.readers import ReaderResult
from valorant_ai_coach.resources import resource_path
from valorant_ai_coach.video.native import NativeSourceFrame


@pytest.fixture
def case(tmp_path, monkeypatch):
    raw = json.loads(resource_path('config/hud_layout_1080p_v3.json').read_text(encoding="utf-8"))
    raw['reference_resolution'] = {'width': 640, 'height': 360, 'aspect_ratio': '16:9'}
    layout = tmp_path / 'layout.json'
    layout.write_text(json.dumps(raw), encoding="utf-8")
    layout.with_name('layout.templates.json').write_text(json.dumps({
        'schema_version': '1.0', 'anchors': {}, 'signals': {},
    }),
        encoding="utf-8",
    )
    analyzer = RealHudAnalyzer(layout)

    def frame(name, ticks, color):
        image = np.full((360, 640, 3), color, np.uint8)
        path = tmp_path / name
        assert cv2.imwrite(str(path), image)
        return NativeSourceFrame(
            path, ticks, Fraction(1, 15360), name, 'a'*64,
            hashlib.sha256(path.read_bytes()).hexdigest(),
            hashlib.sha256(image.tobytes()).hexdigest(), 640, 360,
        )

    prefix = frame('prefix.png', 553, 60)
    frames = [frame('one.png', 63017, 61), frame('two.png', 63273, 62)]
    frames[1] = replace(frames[1], source_epoch=frames[0].source_epoch)
    anchors = {name: analyzer.layout.normalized_roi(name)
               for name in ('round_timer', 'top_match_bar', 'player_hp_armor', 'abilities')}
    anchor_calls = []

    def detect(image, layout):
        value = int(image[180, 320, 0])
        anchor_calls.append(value)
        result = anchors if value == 60 else {'round_timer': anchors['round_timer']}
        return result, {name: .96 for name in result}, ()

    monkeypatch.setattr(analyzer.template_profile, 'detect_anchors', detect)
    read_calls = []

    class Timer:
        def read(self, image, roi):
            read_calls.append(int(image[180, 320, 0]))
            return ReaderResult('0:20', .95, ('unit_timer',))

    analyzer.readers['round_timer'] = Timer()
    contract = tmp_path / 'assurance.json'
    contract.write_text(json.dumps({
        'schema_version': 1, 'source_video_sha256': 'a'*64,
        'assurance_provenance': 'explicit unit fixture, not real source qualification',
        'no_user_edit': True, 'no_intentional_frame_deletion_join_or_reorder': True,
        'no_intentional_speed_change': True, 'scene_preserving_edit_excluded': True,
    }),
        encoding="utf-8",
    )
    return analyzer, prefix, frames, contract, read_calls, anchor_calls


def run(case, **kwargs):
    analyzer, prefix, frames, contract, *_ = case
    return analyzer.observe_native_system_frames(
        frames, native_step_ticks=256, calibration_prefix=prefix,
        input_contract_path=contract, **kwargs,
    )


def test_default_cold_entry_unchanged_and_prefix_reads_geometry_only(case, monkeypatch):
    analyzer, prefix, frames, _, calls, anchors = case
    phase_calls = []
    original = analyzer.template_profile.detect_signals

    def detect_signals(image, *args, **kwargs):
        phase_calls.append(int(image[180, 320, 0]))
        return original(image, *args, **kwargs)

    monkeypatch.setattr(analyzer.template_profile, 'detect_signals', detect_signals)
    monkeypatch.setattr('valorant_ai_coach.hud.analyzers.HudDirectEventBuilder.build',
                        lambda *a, **k: pytest.fail('measurement entrance emits no events'))
    cold = analyzer.observe_native_system_frames(frames, native_step_ticks=256)
    assert not calls
    assert all(r['system_observation']['values']['round_time_remaining_sec'] is None for r in cold)
    warm = run(case)
    assert calls == [61, 62]  # Startup image never enters a value/phase reader.
    assert phase_calls == [61, 62]
    assert 60 in anchors
    for i, row in enumerate(warm):
        assert row['system_observation']['frame_index'] == i
        assert row['source_pts_ticks'] == frames[i].pts_ticks
        assert row['system_observation']['values']['round_time_remaining_display'] == '0:20'
        assert row['system_observation']['values']['player_specific_hud_valid'] is False
        assert row['system_observation']['values']['hp'] is None
        assert row['system_evidence'] == {}
        assert row['input_fingerprint'] != cold[i]['input_fingerprint']
    diag = analyzer.last_calibration_diagnostics
    assert diag['native_calibration_prefix']['source_pts_ticks'] == prefix.pts_ticks
    assert diag['native_calibration_prefix']['scope'] == 'calibration_only'
    assert diag['counts']['fresh_geometry_success'] == 0
    assert diag['counts']['effective_geometry_success'] == 2


@pytest.mark.parametrize('mutation', ['video', 'timebase', 'dimensions', 'future',
                                     'bool_pts', 'negative_pts', 'epoch', 'bytes'])
def test_invalid_prefix_rejects_before_reading_values(case, mutation):
    analyzer, prefix, frames, contract, calls, _ = case
    changes = {'video': {'source_video_sha256': 'b'*64},
               'timebase': {'time_base': Fraction(1, 60)},
               'dimensions': {'width': 641}, 'future': {'pts_ticks': frames[0].pts_ticks},
               'bool_pts': {'pts_ticks': True}, 'negative_pts': {'pts_ticks': -1},
               'epoch': {'source_epoch': ''}}
    if mutation == 'bytes':
        prefix.path.write_bytes(prefix.path.read_bytes()+b'changed')
    else:
        prefix = replace(prefix, **changes[mutation])
    with pytest.raises((ValueError, RuntimeError)):
        analyzer.observe_native_system_frames(
            frames, native_step_ticks=256, calibration_prefix=prefix, input_contract_path=contract,
        )
    assert calls == []


def test_prefix_needs_explicit_matching_assurance(case):
    analyzer, prefix, frames, contract, *_ = case
    with pytest.raises(ValueError, match='contract'):
        analyzer.observe_native_system_frames(frames, native_step_ticks=256,
                                             calibration_prefix=prefix)
    data = json.loads(contract.read_text(encoding="utf-8"))
    data['source_video_sha256'] = 'b'*64
    contract.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match='assurance'):
        run(case)


def test_rejected_source_anchors_cannot_initialize_window(case, monkeypatch):
    analyzer, *_ = case
    monkeypatch.setattr(analyzer.template_profile, 'detect_anchors', lambda *a: ({}, {}, ()))
    with pytest.raises(HudNotCalibratedError, match='prefix'):
        run(case)


def test_current_letterbox_contradiction_cannot_borrow_prefix_calibration(case):
    analyzer, prefix, frames, contract, calls, _ = case
    modified = []
    for source in frames:
        image = source.read_image().copy()
        image[:20] = image[-20:] = 0
        assert cv2.imwrite(str(source.path), image)
        modified.append(replace(
            source, encoded_sha256=hashlib.sha256(source.path.read_bytes()).hexdigest(),
            pixel_sha256=hashlib.sha256(image.tobytes()).hexdigest(),
        ))
    rows = analyzer.observe_native_system_frames(
        modified, native_step_ticks=256, calibration_prefix=prefix, input_contract_path=contract,
    )
    assert calls == []
    assert all(r['system_observation']['values']['round_time_remaining_sec'] is None for r in rows)
    assert analyzer.last_calibration_diagnostics['counts']['effective_geometry_success'] == 0


def test_gap_in_real_window_is_not_repaired_by_prefix(case):
    analyzer, prefix, frames, contract, *_ = case
    frames[1] = replace(frames[1], pts_ticks=frames[1].pts_ticks+256)
    with pytest.raises(ValueError, match='contiguous'):
        analyzer.observe_native_system_frames(
            frames, native_step_ticks=256, calibration_prefix=prefix, input_contract_path=contract,
        )


@pytest.mark.parametrize('mutation', ['prefix', 'contract'])
def test_prefix_and_assurance_terminal_mutation_withhold_packet(case, mutation):
    analyzer, prefix, _, contract, _, _ = case

    class MutatingTimer:
        def read(self, image, roi):
            path = prefix.path if mutation == 'prefix' else contract
            path.write_bytes(path.read_bytes()+b'changed')
            return ReaderResult('0:20', .95, ('unit_timer',))

    analyzer.readers['round_timer'] = MutatingTimer()
    with pytest.raises(RuntimeError, match='changed'):
        run(case)


def test_private_prefix_cannot_emit_events_or_skip_source_assurance(case):
    analyzer, prefix, frames, *_ = case
    with pytest.raises(ValueError, match='measurement-only'):
        analyzer.observe_frames(frames, _native_calibration_prefix=prefix)
    with pytest.raises(ValueError, match='measurement-only'):
        analyzer.observe_frames(frames, _native_calibration_prefix=prefix, _build_events=False)
    assert calibration_prefix_provenance(prefix, frames[0])['source_pts_ticks'] == 553


def test_default_entrance_preserves_old_observe_override_signature(case, monkeypatch):
    analyzer, _, frames, *_ = case

    def observe(source, video_metadata=None, *, _build_events):
        assert _build_events is False
        return SimpleNamespace(observations=[
            HudObservationV2(frame.time_sec, index).to_dict()
            for index, frame in enumerate(source)
        ])

    monkeypatch.setattr(analyzer, 'observe_frames', observe)
    rows = analyzer.observe_native_system_frames(frames, native_step_ticks=256)
    assert len(rows) == 2
