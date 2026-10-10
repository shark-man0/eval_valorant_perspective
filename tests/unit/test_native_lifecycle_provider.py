"""Synthetic transport contracts; these fixtures do not qualify real images."""
from contextlib import contextmanager
from dataclasses import replace
from fractions import Fraction
from pathlib import Path
from threading import Event
from types import SimpleNamespace

import pytest

from tests.unit.test_native_event_merge import qualified_processor
from valorant_ai_coach.application.hud_video_processor import (
    HudVideoProcessingError,
    NativeLifecycleOptions,
)
from valorant_ai_coach.video.native import NativeSourceFrame


def provider(tmp_path, monkeypatch):
    processor, metadata, _, native = qualified_processor(tmp_path)
    frames = tuple(NativeSourceFrame(
        Path('synthetic.png'), row['source_pts_ticks'], Fraction(row['source_time_base']),
        row['source_epoch'], row['source_video_sha256'], 'a' * 64,
        row['source_pixel_sha256'], metadata.width, metadata.height,
    ) for row in native.source_rows)
    monkeypatch.setattr(NativeSourceFrame, 'read_image', lambda self: None)
    calls = []
    processor.analyzer.scene_source_binding = SimpleNamespace(verify=lambda: calls.append('verify'))

    @contextmanager
    def decode(path, **kwargs):
        calls.append(kwargs)
        yield frames
        calls.append('terminal')

    def observe(actual, **kwargs):
        assert actual == frames
        assert kwargs == {'native_step_ticks': 20, 'video_metadata': metadata}
        calls.append('observe')
        return native

    processor.video.native_window = decode
    processor.analyzer.observe_qualified_native_lifecycle_frames = observe
    return processor, metadata, native, calls


def test_single_epoch_origin_to_eof_and_terminal_verification(tmp_path, monkeypatch):
    processor, metadata, native, calls = provider(tmp_path, monkeypatch)
    assert processor.collect_native_lifecycle(metadata, NativeLifecycleOptions(1234)) == native
    assert calls == ['verify', {
        'start_sec': 0, 'end_sec': None,
        'source_video_sha256': native.source_rows[0]['source_video_sha256'],
        'max_png_bytes': 1234, 'png_prediction': 'up',
    }, 'observe', 'verify', 'terminal']


@pytest.mark.parametrize('missing', ['global_qualification', 'scene_source_binding'])
def test_missing_qualification_rejects_before_decode(tmp_path, monkeypatch, missing):
    processor, metadata, _, calls = provider(tmp_path, monkeypatch)
    setattr(processor.analyzer, missing, None)
    with pytest.raises(HudVideoProcessingError, match='qualified'):
        processor.collect_native_lifecycle(metadata, NativeLifecycleOptions(1234))
    assert calls == []


@pytest.mark.parametrize('tamper', ['coverage', 'pixel'])
def test_producer_must_cover_exact_decoded_source(tmp_path, monkeypatch, tamper):
    processor, metadata, native, _ = provider(tmp_path, monkeypatch)
    rows = tuple(dict(row) for row in native.source_rows)
    if tamper == 'coverage':
        rows = rows[:-1]
    else:
        rows[0]['source_pixel_sha256'] = 'b' * 64
    processor.analyzer.observe_qualified_native_lifecycle_frames = lambda *a, **k: replace(
        native, source_rows=rows,
    )
    with pytest.raises(HudVideoProcessingError, match='coverage|binding'):
        processor.collect_native_lifecycle(metadata, NativeLifecycleOptions(1234))


def test_cancel_before_decode_and_conflicting_inputs(tmp_path, monkeypatch):
    processor, metadata, native, calls = provider(tmp_path, monkeypatch)
    cancel = Event()
    cancel.set()
    with pytest.raises(InterruptedError):
        processor.collect_native_lifecycle(
            metadata, NativeLifecycleOptions(1234), cancel_event=cancel,
        )
    with pytest.raises(HudVideoProcessingError, match='choose'):
        processor.process(
            metadata=metadata, match_id='test', output_dir=tmp_path,
            native_lifecycle=native, native_lifecycle_options=NativeLifecycleOptions(1234),
        )
    assert calls == []


@pytest.mark.parametrize('budget', [None, 0, -1, True, 1.5])
def test_mandatory_positive_integer_budget(budget):
    with pytest.raises(ValueError, match='budget'):
        NativeLifecycleOptions(budget)


@pytest.mark.parametrize('failure', ['overflow', 'terminal'])
def test_decoder_failure_never_falls_back_to_sampled_analysis(tmp_path, monkeypatch, failure):
    processor, metadata, _, calls = provider(tmp_path, monkeypatch)
    original = processor.video.native_window

    @contextmanager
    def decode(*args, **kwargs):
        if failure == 'overflow':
            raise RuntimeError('budget exceeded')
        with original(*args, **kwargs) as frames:
            yield frames
        raise RuntimeError('terminal source changed')

    processor.video.native_window = decode
    processor.analyzer.observe_frames = lambda *a, **k: pytest.fail('sampled fallback')
    with pytest.raises(RuntimeError, match='budget exceeded|terminal source changed'):
        processor.process(metadata=metadata, match_id='test', output_dir=tmp_path,
                          native_lifecycle_options=NativeLifecycleOptions(1234))
    assert ('observe' in calls) == (failure == 'terminal')
