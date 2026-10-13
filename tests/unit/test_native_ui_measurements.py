import hashlib
from fractions import Fraction
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from valorant_ai_coach.hud.analyzers import RealHudAnalyzer
from valorant_ai_coach.hud.models import HudObservationV2, empty_hud_values
from valorant_ai_coach.hud.native_assured_start import validate_assured_row
from valorant_ai_coach.hud.native_system_input import bind_native_ui_measurements
from valorant_ai_coach.resources import resource_path
from valorant_ai_coach.video.native import NativeSourceFrame


@pytest.fixture
def native_case(tmp_path, monkeypatch):
    frames = []
    for i in range(2):
        image = np.full((64, 64, 3), 60+i, np.uint8)
        path = tmp_path / f'{i}.png'
        assert cv2.imwrite(str(path), image)
        frames.append(NativeSourceFrame(
            path, 63017+i*256, Fraction(1, 15360), 'test-epoch', 'a'*64,
            hashlib.sha256(path.read_bytes()).hexdigest(),
            hashlib.sha256(image.tobytes()).hexdigest(), 64, 64,
        ))
    analyzer = RealHudAnalyzer(resource_path('config/hud_layout_1080p_v3.json'))
    scans = [{
        'phase_scan_valid': bool(i), 'phase_present': False, 'phase_confidence': 0.0,
        'phase_absence_matched': False, 'confidence': 0.0,
        'round_result_matched': False, 'round_result_confidence': 0.0,
        'content_jump': False, 'discontinuity': bool(i),
    } for i in range(2)]
    observations = [HudObservationV2(
        time_sec=f.time_sec, frame_index=i, primary_state='unknown',
        values=empty_hud_values(),
    ).to_dict() for i, f in enumerate(frames)]
    calls = []

    def observe(source, metadata, *, _build_events):
        assert _build_events is False
        assert tuple(source) == tuple(frames)
        calls.append(1)
        return SimpleNamespace(observations=observations, native_ui_measurements=scans)

    monkeypatch.setattr(analyzer, 'observe_frames', observe)
    return analyzer, frames, scans, calls


def test_opt_in_transports_same_pass_measurements_without_evidence_or_owned_facts(native_case):
    analyzer, frames, scans, calls = native_case
    old = analyzer.observe_native_system_frames(frames, native_step_ticks=256)
    rows = analyzer.observe_native_system_frames(
        frames, native_step_ticks=256, include_ui_measurements=True,
    )
    assert calls == [1, 1]
    for row, previous, frame, scan in zip(rows, old, frames, scans, strict=True):
        assert 'system_measurements' not in previous
        assert row['system_evidence'] == previous['system_evidence'] == {}
        assert row['system_observation'] == previous['system_observation']
        assert row['input_fingerprint'] != previous['input_fingerprint']
        measurement = row['system_measurements']
        assert measurement['scope'] == 'unqualified_current_frame'
        assert measurement['qualification_required'] is True
        assert measurement['native_ui'] == scan
        assert measurement['source_pts_ticks'] == frame.pts_ticks
        assert measurement['source_pixel_sha256'] == frame.pixel_sha256
        assert measurement['input_fingerprint'] == row['input_fingerprint']
        assert row['system_observation']['values']['hp'] is None
    # Invalid scans stay invalid; a nonmatch does not become positive absence.
    assert rows[0]['system_measurements']['native_ui']['phase_scan_valid'] is False
    assert rows[1]['system_measurements']['native_ui']['discontinuity'] is True
    rows[0]['system_measurements']['native_ui']['phase_confidence'] = .99
    assert scans[0]['phase_confidence'] == 0


@pytest.mark.parametrize('invalid', [None, 1, 'true'])
def test_opt_in_requires_explicit_boolean(native_case, invalid):
    analyzer, frames, _, calls = native_case
    with pytest.raises(ValueError, match='boolean'):
        analyzer.observe_native_system_frames(
            frames, native_step_ticks=256, include_ui_measurements=invalid,
        )
    assert calls == []


@pytest.mark.parametrize('mutation', ['missing', 'extra', 'nan', 'bool_confidence',
                                     'negative', 'high', 'non_boolean', 'coverage'])
def test_invalid_scan_withholds_entire_packet(native_case, mutation):
    analyzer, frames, scans, _ = native_case
    if mutation == 'missing':
        scans[-1].pop('phase_present')
    elif mutation == 'extra':
        scans[-1]['qualification_sha256'] = 'b'*64
    elif mutation == 'coverage':
        scans.pop()
    elif mutation == 'non_boolean':
        scans[-1]['phase_scan_valid'] = 1
    else:
        scans[-1]['phase_confidence'] = {
            'nan': float('nan'), 'bool_confidence': True, 'negative': -.01, 'high': 1.01,
        }[mutation]
    with pytest.raises(ValueError, match='measurement'):
        analyzer.observe_native_system_frames(
            frames, native_step_ticks=256, include_ui_measurements=True,
        )


def test_missing_measurement_coverage_is_not_silently_negative():
    with pytest.raises(ValueError, match='coverage'):
        bind_native_ui_measurements([{}], [])


def test_input_mutation_withholds_optional_measurements(native_case, monkeypatch):
    analyzer, frames, _, _ = native_case
    observe = analyzer.observe_frames

    def mutate(*args, **kwargs):
        result = observe(*args, **kwargs)
        frames[-1].path.write_bytes(frames[-1].path.read_bytes()+b'changed')
        return result

    monkeypatch.setattr(analyzer, 'observe_frames', mutate)
    with pytest.raises(RuntimeError, match='asset changed'):
        analyzer.observe_native_system_frames(
            frames, native_step_ticks=256, include_ui_measurements=True,
        )


def test_measurements_do_not_satisfy_qualified_evidence_admission(native_case):
    analyzer, frames, _, _ = native_case
    rows = analyzer.observe_native_system_frames(
        frames, native_step_ticks=256, include_ui_measurements=True,
    )
    with pytest.raises(ValueError, match='producer-owned phase scan evidence'):
        validate_assured_row(
            rows[0], first=rows[0], prior=None, index=0, step=256,
            qualification=None, contract=SimpleNamespace(source_video_sha256='a'*64),
        )
