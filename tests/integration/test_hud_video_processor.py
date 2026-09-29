from __future__ import annotations

from pathlib import Path
from threading import Event
from types import SimpleNamespace
from typing import Any

import pytest

from valorant_ai_coach.application import HudVideoProcessingError, HudVideoProcessor
from valorant_ai_coach.events import EventSourceContract
from valorant_ai_coach.rounds import RoundPackageBuilder
from valorant_ai_coach.schema_validation import SchemaValidator
from valorant_ai_coach.video import FrameSample, VideoMetadata
from valorant_ai_coach.video.sampling import HudFrameSampler
from valorant_ai_coach.visual import NullVisualAnalyzer

ROOT = Path(__file__).resolve().parents[2]


def make_observation(time_sec: float) -> dict[str, Any]:
    return {
        "schema_version": "2.0",
        "time_sec": time_sec,
        "frame_index": round(time_sec * 60),
        "primary_state": "live_first_person",
        "state_flags": [],
        "view_context": {
            "remote_view_type": "none",
            "is_player_world_view_trustworthy": True,
        },
        "values": {
            "round_time_remaining_sec": max(0.0, 100 - time_sec),
            "score_ally": 0,
            "score_enemy": 0,
            "ally_alive": 5,
            "enemy_alive": 5,
            "hp": 100,
            "armor": 50,
            "ammo_current": 25,
            "ammo_reserve": 50,
            "weapon_text": None,
            "spike_state": "unknown",
            "location_text": None,
            "kill_feed_rows": [],
            "ability_slots": [],
            "combat_report_visible": False,
            "buy_phase_visible": False,
            "round_end_text": None,
            "zone_id": None,
            "player_specific_hud_valid": True,
        },
        "quality": {
            "hud_confidence": 0.9,
            "visual_confidence": 0.0,
            "occluded_rois": [],
            "notes": [],
            "state_confidence": 0.9,
            "roi_confidence": {},
        },
    }


def hud_event(event_id: str, time_sec: float, event_type: str) -> dict[str, Any]:
    return {
        "event_id": event_id,
        "time_sec": time_sec,
        "type": event_type,
        "actor": "system",
        "attributes": {},
        "confidence": 0.9,
    }


class FakeVideo:
    def __init__(self) -> None:
        self.calls: list[list[float]] = []

    def extract_frames(
        self, _path: Path, timestamps: list[float], output_dir: Path, **kwargs: Any
    ) -> list[FrameSample]:
        assert kwargs["max_dimension"] is None
        self.calls.append(list(timestamps))
        return [FrameSample(value, output_dir / f"{value:.6f}.jpg") for value in timestamps]


class FakeAnalyzer:
    def __init__(self, calibration_required: bool = False) -> None:
        self.calls = 0
        self.calibration_required = calibration_required

    def observe_frames(
        self,
        frames: list[FrameSample],
        *,
        video_metadata: VideoMetadata,
        cancel_event: Event | None = None,
    ) -> Any:
        del video_metadata
        self.calls += 1
        observations = tuple(make_observation(frame.time_sec) for frame in frames)
        events = (
            hud_event("ROUND-START", 0.5, "round_start"),
            hud_event("ROUND-END", 2.5, "round_end"),
        )
        return SimpleNamespace(
            observations=observations,
            hud_events=events,
            change_times_sec=(1.5,) if self.calls == 1 else (),
            calibration={
                "calibration_required": self.calibration_required,
                "reasons": ["anchor mismatch"] if self.calibration_required else [],
            },
            diagnostics=("synthetic HUD",),
        )


def build_processor(video: FakeVideo, analyzer: FakeAnalyzer) -> HudVideoProcessor:
    contract = EventSourceContract.load(ROOT / "config" / "event_source_contract_v1.json")
    validator = SchemaValidator()
    return HudVideoProcessor(
        video=video,
        analyzer=analyzer,
        visual_analyzer=NullVisualAnalyzer(contract),
        package_builder=RoundPackageBuilder(contract=contract, validator=validator),
        validator=validator,
        sampler=HudFrameSampler(
            general_fps=1,
            change_fps=2,
            burst_fps=10,
            burst_radius_sec=0.2,
        ),
    )


def test_processor_runs_two_passes_and_builds_round_package(tmp_path: Path) -> None:
    video = FakeVideo()
    analyzer = FakeAnalyzer()
    metadata = VideoMetadata(
        path=tmp_path / "match.mp4",
        duration_sec=3.0,
        width=1920,
        height=1080,
        fps=60,
        video_codec="h264",
        audio_codec=None,
        has_audio=False,
        file_size=0,
    )
    progress: list[str] = []

    result = build_processor(video, analyzer).process(
        metadata=metadata,
        match_id="M-REAL",
        output_dir=tmp_path / "hud",
        progress_cb=lambda _value, message: progress.append(message),
    )

    assert analyzer.calls == 2
    assert len(video.calls) == 2
    assert result.round_packages[0]["match_id"] == "M-REAL"
    assert result.sampled_frame_count > len(video.calls[0])
    assert all(item["type"] != "shot" for item in result.round_packages[0]["events"])
    assert progress[-1] == "Round Packageを生成しました"


def test_processor_fails_closed_on_calibration_required(tmp_path: Path) -> None:
    metadata = VideoMetadata(
        path=tmp_path / "match.mp4",
        duration_sec=1.0,
        width=1280,
        height=720,
        fps=30,
        video_codec="h264",
        audio_codec=None,
        has_audio=False,
        file_size=0,
    )
    with pytest.raises(HudVideoProcessingError, match="calibration_required"):
        build_processor(FakeVideo(), FakeAnalyzer(calibration_required=True)).process(
            metadata=metadata,
            match_id="M-CAL",
            output_dir=tmp_path / "hud",
        )
