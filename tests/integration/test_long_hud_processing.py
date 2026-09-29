from pathlib import Path
from threading import Event
from types import SimpleNamespace

import pytest

from valorant_ai_coach.application.hud_video_processor import HudVideoProcessor
from valorant_ai_coach.video import FrameSample, VideoMetadata
from valorant_ai_coach.visual import VisualAnalysis


class RecordingExtractor:
    def __init__(self, cancel=None):
        self.calls = []
        self.cancel = cancel

    def extract_frames(self, path, timestamps, output_dir, **kwargs):
        self.calls.append(list(timestamps))
        if self.cancel is not None:
            self.cancel.set()
        return [FrameSample(time, output_dir / f"{time:.6f}.jpg") for time in timestamps]


class TimelineAnalyzer:
    def observe_frames(self, frames, **kwargs):
        return SimpleNamespace(
            observations=tuple(
                {
                    "time_sec": frame.time_sec,
                    "quality": {},
                    "primary_state": "unknown",
                    "state_flags": [],
                    "values": {},
                }
                for frame in frames
            ),
            hud_events=(),
            change_times_sec=(),
            diagnostics=(),
            calibration={"calibration_required": False},
        )


class TimelinePackages:
    def build(self, **kwargs):
        observations = kwargs["hud_observations"]
        return ({"first": observations[0]["time_sec"], "last": observations[-1]["time_sec"]},)


def _processor(video):
    return HudVideoProcessor(
        video=video,
        analyzer=TimelineAnalyzer(),
        package_builder=TimelinePackages(),
        visual_analyzer=SimpleNamespace(analyze=lambda *args, **kwargs: VisualAnalysis(())),
        validator=SimpleNamespace(validate_hud_observation=lambda observation: None),
    )


def _metadata(tmp_path: Path):
    return VideoMetadata(tmp_path / "long.mp4", 3600, 1920, 1080, 60, "h264", None, False, 0)


def test_one_hour_timeline_reaches_both_passes_without_duration_rejection(tmp_path):
    # Timing/extraction-interface simulation; real decoding is exercised by the
    # separate FFmpeg pixel E2E test, not claimed for this one-hour fixture.
    video = RecordingExtractor()
    result = _processor(video).process(
        metadata=_metadata(tmp_path), match_id="long", output_dir=tmp_path
    )
    assert all(len(call) <= 500 for call in video.calls)
    assert result.sampled_frame_count == 14401
    assert result.round_packages == ({"first": 0, "last": 3600},)
    all_times = [time for call in video.calls for time in call]
    assert all_times == [index / 4 for index in range(14401)]


def test_cancel_stops_long_recording_between_extraction_batches(tmp_path):
    cancel = Event()
    video = RecordingExtractor(cancel)
    with pytest.raises(InterruptedError):
        _processor(video).process(
            metadata=_metadata(tmp_path),
            match_id="cancel",
            output_dir=tmp_path,
            cancel_event=cancel,
        )
    assert len(video.calls) == 1
