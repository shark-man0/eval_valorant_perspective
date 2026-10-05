from __future__ import annotations

from pathlib import Path

import pytest
from test_hud_video_processor import FakeAnalyzer, FakeVideo, build_processor

from valorant_ai_coach.application import HudVideoProcessingError
from valorant_ai_coach.video import FrameSample, VideoMetadata


def metadata(path: Path) -> VideoMetadata:
    return VideoMetadata(
        path=path,
        duration_sec=3.0,
        width=1920,
        height=1080,
        fps=60,
        video_codec="h264",
        audio_codec=None,
        has_audio=False,
        file_size=0,
    )


def test_fixed_frames_use_same_production_final_pipeline_without_extraction(tmp_path: Path) -> None:
    video = FakeVideo()
    extractor_processor = build_processor(video, FakeAnalyzer())
    extractor_progress: list[tuple[float, str]] = []
    extracted_result = extractor_processor.process(
        metadata=metadata(tmp_path / "match.mp4"),
        match_id="M-FIXED",
        output_dir=tmp_path / "hud",
        progress_cb=lambda value, message: extractor_progress.append((value, message)),
    )
    timestamps = sorted({timestamp for batch in video.calls for timestamp in batch})
    fixed_frames = [
        FrameSample(time, tmp_path / f"fixed-{index}.jpg") for index, time in enumerate(timestamps)
    ]

    fixed_video = FakeVideo()
    fixed_analyzer = FakeAnalyzer()
    fixed_processor = build_processor(fixed_video, fixed_analyzer)
    fixed_progress: list[tuple[float, str]] = []
    fixed_result = fixed_processor.process_frames(
        metadata(tmp_path / "match.mp4"),
        "M-FIXED",
        fixed_frames,
        progress_cb=lambda value, message: fixed_progress.append((value, message)),
    )

    assert fixed_video.calls == []
    assert fixed_analyzer.calls == 1
    assert (
        fixed_result.sampled_frame_count
        == len(fixed_frames)
        == extracted_result.sampled_frame_count
    )
    assert fixed_result.observations == extracted_result.observations
    assert fixed_result.hud_events == extracted_result.hud_events
    assert fixed_result.visual_events == extracted_result.visual_events
    assert fixed_result.round_packages == extracted_result.round_packages
    assert fixed_result.visual_observations == extracted_result.visual_observations
    assert fixed_result.visual_candidates == extracted_result.visual_candidates
    assert fixed_result.zone_resolutions == extracted_result.zone_resolutions
    assert [(value, message) for value, message in fixed_progress] == [
        item for item in extractor_progress if item[0] >= 0.72
    ]


@pytest.mark.parametrize(
    ("frames", "message"),
    [
        ([], "must not be empty"),
        ([0.5, 0.5], "must be unique"),
        ([1.0, 0.5], "ascending time order"),
        ([float("nan")], "must be finite"),
    ],
)
def test_fixed_frames_reject_invalid_frame_sets_before_processing(
    tmp_path: Path, frames: list[float], message: str
) -> None:
    video = FakeVideo()
    analyzer = FakeAnalyzer()
    processor = build_processor(video, analyzer)
    fixed = [
        FrameSample(time, tmp_path / f"frame-{index}.jpg") for index, time in enumerate(frames)
    ]
    with pytest.raises(HudVideoProcessingError, match=message):
        processor.process_frames(metadata(tmp_path / "match.mp4"), "M-INVALID", fixed)
    assert video.calls == []
    assert analyzer.calls == 0


class UnknownAnalyzer(FakeAnalyzer):
    def observe_frames(self, *args, **kwargs):
        result = super().observe_frames(*args, **kwargs)
        result.hud_events = ()
        for observation in result.observations:
            observation["primary_state"] = "unknown"
            observation["view_context"]["is_player_world_view_trustworthy"] = False
            observation["values"]["player_specific_hud_valid"] = False
            for key in (
                "round_time_remaining_sec", "score_ally", "score_enemy", "ally_alive",
                "enemy_alive", "hp", "armor", "ammo_current", "ammo_reserve",
            ):
                observation["values"][key] = None
            observation["quality"]["hud_confidence"] = 0.0
            observation["quality"]["state_confidence"] = 0.0
        return result


def test_diagnostic_mode_retains_unknown_observations_without_fabricating_rounds(tmp_path):
    from valorant_ai_coach.rounds import RoundPackageBuildError

    frames = [FrameSample(time, tmp_path / f"{time}.jpg") for time in (0.5, 1.0)]
    processor = build_processor(FakeVideo(), UnknownAnalyzer())
    with pytest.raises(RoundPackageBuildError, match="ラウンド区間"):
        processor.process_frames(metadata(tmp_path / "match.mp4"), "M-UNKNOWN", frames)
    result = processor.process_frames(
        metadata(tmp_path / "match.mp4"), "M-UNKNOWN", frames, require_detected_rounds=False
    )
    assert result.sampled_frame_count == len(frames)
    assert [item["time_sec"] for item in result.observations] == [0.5, 1.0]
    assert all(item["primary_state"] == "unknown" for item in result.observations)
    assert result.round_packages == ()
    assert result.hud_events == result.visual_events == ()
    assert "round_packages_unavailable: no reliable round boundaries" in result.diagnostics


def test_diagnostic_mode_keeps_calibration_failure_fatal(tmp_path):
    processor = build_processor(FakeVideo(), UnknownAnalyzer(calibration_required=True))
    frames = [FrameSample(0.5, tmp_path / "frame.jpg")]
    with pytest.raises(HudVideoProcessingError, match="calibration_required"):
        processor.process_frames(
            metadata(tmp_path / "match.mp4"), "M-UNKNOWN", frames, require_detected_rounds=False
        )


def test_diagnostic_mode_keeps_invalid_fps_fatal(tmp_path):
    from dataclasses import replace

    from valorant_ai_coach.rounds import RoundPackageBuildError

    processor = build_processor(FakeVideo(), UnknownAnalyzer())
    frames = [FrameSample(0.5, tmp_path / "frame.jpg")]
    with pytest.raises(RoundPackageBuildError, match="FPS"):
        processor.process_frames(
            replace(metadata(tmp_path / "match.mp4"), fps=0),
            "M-UNKNOWN", frames, require_detected_rounds=False,
        )
