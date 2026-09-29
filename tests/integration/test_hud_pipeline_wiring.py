from __future__ import annotations

import json
from pathlib import Path
from threading import Event
from typing import Any

import pytest

from valorant_ai_coach.application import AnalysisCancelled
from valorant_ai_coach.bootstrap import build_services
from valorant_ai_coach.hud import CalibrationResult, HudFrameAnalysis, HudObservationV2
from valorant_ai_coach.hud.models import empty_hud_values
from valorant_ai_coach.settings import AppSettings, SettingsStore
from valorant_ai_coach.video import FrameSample, VideoMetadata


class TimelineReader:
    def __init__(self, *, cancel: bool = False) -> None:
        self.calls = 0
        self.cancel = cancel

    def observe_frames(
        self,
        frames: list[FrameSample],
        *,
        video_metadata: VideoMetadata,
        cancel_event: Event | None = None,
    ) -> HudFrameAnalysis:
        self.calls += 1
        if self.cancel:
            assert cancel_event is not None
            cancel_event.set()
        observations = []
        for index, frame in enumerate(frames):
            values = empty_hud_values()
            values.update(player_specific_hud_valid=True, hp=100, ally_alive=5, enemy_alive=5)
            observations.append(
                HudObservationV2(
                    time_sec=frame.time_sec,
                    frame_index=index,
                    primary_state="live_first_person",
                    values=values,
                    is_player_world_view_trustworthy=True,
                    quality={
                        "hud_confidence": 0.9,
                        "visual_confidence": 0.0,
                        "state_confidence": 0.9,
                        "roi_confidence": {},
                        "notes": [],
                        "occluded_rois": [],
                    },
                ).to_dict()
            )
        return HudFrameAnalysis(
            tuple(observations),
            tuple(
                {
                    "event_id": kind,
                    "type": kind,
                    "time_sec": time_sec,
                    "actor": "system",
                    "attributes": {},
                    "confidence": 0.9,
                }
                for kind, time_sec in [("round_start", 0.25), ("round_end", 1.75)]
            ),
            (1.0,),
            CalibrationResult(True, (), 4, 0.0, 0.0),
            diagnostics=("test timeline",),
        )


def setup_pipeline(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, cancel: bool = False) -> Any:
    source = tmp_path / "source.mp4"
    source.write_bytes(b"fixture for pipeline identity")
    store = SettingsStore(tmp_path / "settings.json")
    services = build_services(
        store, settings=AppSettings(data_dir=tmp_path / "data", hud_mode="real")
    )
    metadata = VideoMetadata(source, 2.0, 1920, 1080, 60.0, "h264", None, False, 29)

    def extract(
        _path: Path, times: list[float], output_dir: Path, **_kwargs: Any
    ) -> list[FrameSample]:
        output_dir.mkdir(parents=True, exist_ok=True)
        frames = []
        for index, timestamp in enumerate(times):
            target = output_dir / f"frame-{index}.jpg"
            target.write_bytes(b"fixture evidence")
            frames.append(FrameSample(timestamp, target))
        return frames

    monkeypatch.setattr(services.video, "probe", lambda *_args, **_kwargs: metadata)
    monkeypatch.setattr(services.video, "extract_frames", extract)
    processor = services.pipeline.hud_video_processor
    assert processor is not None
    processor.analyzer = TimelineReader(cancel=cancel)

    def no_legacy_entry(*_args: Any, **_kwargs: Any) -> None:
        pytest.fail("real HUD used legacy analyze([])")

    monkeypatch.setattr(services.pipeline.hud, "analyze", no_legacy_entry)
    return services, source, processor


def test_real_mode_selects_two_pass_pipeline_and_persists_observation_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    services, source, processor = setup_pipeline(tmp_path, monkeypatch)
    result = services.pipeline.analyze_video(source, match_id="M-HUD-PIPELINE")
    assert result.status == "completed"
    assert processor.analyzer.calls == 2
    report = json.loads((result.analysis_json.parent / "hud-analysis.json").read_text())
    assert report["observations"]
    assert report["hud_events"]
    assert report["adopted_frames"]
    assert all(Path(frame["path"]).is_file() for frame in report["adopted_frames"])
    assert services.repository.list_round_packages(result.match_id)
    assert not (tmp_path / "data" / "temp" / result.match_id).exists()


def test_cancel_during_hud_read_marks_checkpoint_cancelled_and_cleans_samples(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    services, source, _processor = setup_pipeline(tmp_path, monkeypatch, cancel=True)
    with pytest.raises(AnalysisCancelled):
        services.pipeline.analyze_video(source, match_id="M-HUD-CANCEL")
    assert services.repository.get_job_checkpoint("M-HUD-CANCEL")["status"] == "cancelled"
    assert not (tmp_path / "data" / "temp" / "M-HUD-CANCEL").exists()
