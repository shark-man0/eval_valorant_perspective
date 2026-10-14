import hashlib
import json
import sys
from types import SimpleNamespace

import pytest

from scripts.diagnostics import run_continuous_window
from scripts.diagnostics.run_continuous_window import window_schedule
from valorant_ai_coach.application.hud_video_processor import HudVideoProcessingResult
from valorant_ai_coach.video import FrameSample, VideoMetadata


def test_window_retains_native_source_scope_and_includes_endpoint():
    assert window_schedule(30, 31, 100, 4) == [30, 30.25, 30.5, 30.75, 31]
    assert window_schedule(30, 30.3, 100, 4) == [30, 30.25, 30.3]


@pytest.mark.parametrize("start,end,duration,fps", [
    (-1, 3, 100, 4), (3, 3, 100, 4), (0, 100, 100, 4),
    (0, 3, 100, 0), (0, 200, 300, 60), (0, float("nan"), 100, 4),
])
def test_invalid_windows_reject(start, end, duration, fps):
    with pytest.raises(ValueError):
        window_schedule(start, end, duration, fps)


@pytest.mark.parametrize("processing_error", [False, True])
@pytest.mark.parametrize("source_fault", [None, "duplicate", "reversed", "nonfinite", "outside"])
@pytest.mark.parametrize("trace_error", [False, True])
@pytest.mark.parametrize("integrity_fault", [None, "source", "profile"])
def test_cli_uses_fresh_native_window_without_external_prefix_or_fake_events(
    tmp_path, monkeypatch, processing_error, source_fault, trace_error, integrity_fault,
):
    video_path = tmp_path / "video.mp4"
    video_path.write_bytes(b"source")
    digest = hashlib.sha256(b"source").hexdigest()
    output = tmp_path / "private-output"
    calls = []
    metadata = VideoMetadata(video_path, 100, 1920, 1080, 60, "h264", None, False, 6)
    analyzer = SimpleNamespace(fingerprint=lambda: "profile", last_calibration_diagnostics={})

    def process_frames(actual_metadata, match_id, frames, *, require_detected_rounds):
        assert actual_metadata == metadata
        assert require_detected_rounds is False
        assert [frame.time_sec for frame in frames] == [30, 30.25, 30.5, 30.75, 31]
        calls.append("native_processing")
        if processing_error:
            raise RuntimeError("calibration_required")
        if integrity_fault == "source":
            video_path.write_bytes(b"changed source")
        elif integrity_fault == "profile":
            analyzer.fingerprint = lambda: "changed profile"
        return HudVideoProcessingResult((), (), (), (), (), len(frames))

    processor = SimpleNamespace(analyzer=analyzer, process_frames=process_frames)
    services = SimpleNamespace(video=SimpleNamespace(ffprobe_path="ffprobe"),
                               pipeline=SimpleNamespace(hud_video_processor=processor))

    def build_services(*args, settings):
        calls.append("fresh_services")
        assert settings.visual_semantic_enabled is False and settings.mock_ai is True
        assert settings.hud_mode == "real"
        return services

    class Video:
        def __init__(self, *args):
            pass

        def probe(self, path):
            return metadata

        def extract_frames(self, path, schedule, frame_output, **kwargs):
            frame_output.mkdir()
            image = frame_output / "frame.jpg"
            image.write_bytes(b"local-image")
            frames = [FrameSample(time, image) for time in schedule]
            if source_fault == "duplicate":
                frames[1] = FrameSample(frames[0].time_sec, image)
            elif source_fault == "reversed":
                frames.reverse()
            elif source_fault == "nonfinite":
                frames[0] = FrameSample(float("nan"), image)
            elif source_fault == "outside":
                frames[0] = FrameSample(29.99, image)
            return frames

    monkeypatch.setattr(run_continuous_window, "build_services", build_services)
    monkeypatch.setattr(run_continuous_window, "CachedVideoService", Video)
    monkeypatch.setattr(run_continuous_window, "decoder_fingerprints", lambda _: ("probe", "frame"))
    monkeypatch.setattr(
        run_continuous_window, "git_identity", lambda _: {"analyzer_commit": "test"},
    )
    def trace(result):
        if trace_error:
            raise ValueError("trace conversion failed")
        return {"events": []}

    monkeypatch.setattr(run_continuous_window, "to_e2e_trace", trace)
    monkeypatch.setattr(sys, "argv", [
        "window", "--video", str(video_path), "--source-sha256", digest,
        "--hud-layout", str(tmp_path / "layout.json"), "--start", "30", "--end", "31",
        "--output", str(output),
    ])
    failed = bool(processing_error or source_fault or trace_error or integrity_fault)
    assert run_continuous_window.main() == int(failed)
    expected_calls = (["fresh_services"] if source_fault
                      else ["fresh_services", "native_processing"])
    assert calls == expected_calls
    raw = json.loads((output / "raw_processing.json").read_text(encoding="utf-8"))
    mutated = integrity_fault == "source" and not processing_error and not source_fault
    assert raw["source_hash_verified_after_processing"] is not mutated
    assert raw["runtime_mode"]["ground_truth_loaded"] is False
    assert raw["runtime_mode"]["input_scope"] == "continuous_window"
    if source_fault:
        assert raw["status"] == "error"
        assert raw["failure_stage"] == "source_frame_validation"
        assert raw["processing_completed"] is False
        assert "hud_events" not in raw
        assert not (output / "e2e_trace.json").exists()
    elif processing_error:
        assert raw["status"] == "error"
        assert raw["failure_stage"] == "hud_processing"
        assert raw["processing_completed"] is False
        assert "hud_events" not in raw
        assert not (output / "e2e_trace.json").exists()
    elif integrity_fault:
        assert raw["status"] == "error"
        assert raw["failure_stage"] == integrity_fault + "_integrity"
        assert raw["error_type"] == "IntegrityError"
        assert raw["processing_completed"] is True
        assert not (output / "e2e_trace.json").exists()
    elif trace_error:
        assert raw["status"] == "error"
        assert raw["failure_stage"] == "trace_export"
        assert raw["processing_completed"] is True
        assert raw["hud_events"] == []
        assert not (output / "e2e_trace.json").exists()
    else:
        assert raw["status"] == "complete"
        assert raw["processing_completed"] is True
        assert raw["hud_events"] == []
        assert (output / "e2e_trace.json").is_file()
