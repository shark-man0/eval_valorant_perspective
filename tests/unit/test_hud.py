from __future__ import annotations

import json
from pathlib import Path

import pytest

from valorant_ai_coach.hud import (
    HudAnalysisError,
    HudLayout,
    HudNotCalibratedError,
    MockHudAnalyzer,
    RealHudAnalyzer,
)
from valorant_ai_coach.video import VideoMetadata

ROOT = Path(__file__).resolve().parents[2]


def case(case_id: str) -> dict[str, object]:
    path = ROOT / "tests" / "cases" / case_id / "input.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_example_layout_is_explicitly_uncalibrated() -> None:
    path = ROOT / "config" / "hud_layout.example.json"
    layout = HudLayout.load(path)
    assert not layout.calibrated
    analyzer = RealHudAnalyzer(path)
    with pytest.raises(HudNotCalibratedError, match="未校正"):
        analyzer.analyze([])


def test_layout_rejects_out_of_bounds_roi(tmp_path: Path) -> None:
    path = tmp_path / "hud_layout.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "calibrated": True,
                "reference_resolution": {"width": 1920, "height": 1080},
                "roi_coordinate_system": "normalized_0_to_1",
                "regions": {"timer": {"x": 0.9, "y": 0.1, "width": 0.2, "height": 0.1}},
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="画面範囲"):
        HudLayout.load(path)


def test_mock_hud_adapts_video_metadata_without_mutating_fixture(tmp_path: Path) -> None:
    fixture = case("TC-029")
    original_path = fixture["source_video"]["path"]  # type: ignore[index]
    video_path = tmp_path / "match.mp4"
    video_path.write_bytes(b"video")
    metadata = VideoMetadata(
        path=video_path,
        duration_sec=120,
        width=1280,
        height=720,
        fps=60,
        video_codec="h264",
        audio_codec="aac",
        has_audio=True,
        file_size=5,
    )
    result = MockHudAnalyzer([fixture]).analyze([], video_metadata=metadata, match_id="M-1")
    package = result.round_packages[0]
    assert package["match_id"] == "M-1"
    assert package["source_video"]["path"] == str(video_path)
    assert fixture["source_video"]["path"] == original_path  # type: ignore[index]


def test_mock_hud_rejects_video_shorter_than_round(tmp_path: Path) -> None:
    video_path = tmp_path / "short.mp4"
    video_path.write_bytes(b"video")
    metadata = VideoMetadata(
        path=video_path,
        duration_sec=10,
        width=1280,
        height=720,
        fps=60,
        video_codec="h264",
        audio_codec=None,
        has_audio=False,
        file_size=5,
    )
    with pytest.raises(HudAnalysisError, match="短い"):
        MockHudAnalyzer([case("TC-029")]).analyze([], video_metadata=metadata)


def test_mock_hud_clamps_empty_tail_of_fixture_to_video_duration(tmp_path: Path) -> None:
    video_path = tmp_path / "sixty-seconds.mp4"
    video_path.write_bytes(b"video")
    metadata = VideoMetadata(
        path=video_path,
        duration_sec=60,
        width=1280,
        height=720,
        fps=60,
        video_codec="h264",
        audio_codec="aac",
        has_audio=True,
        file_size=5,
    )

    result = MockHudAnalyzer([case("TC-029")]).analyze([], video_metadata=metadata)

    assert result.round_packages[0]["round_window"]["end_sec"] == 60
