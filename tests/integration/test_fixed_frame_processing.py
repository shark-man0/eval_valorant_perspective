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
