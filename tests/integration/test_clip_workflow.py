"""Clip workflow: real ClipService + real pipeline, FFmpeg mocked at the process seam.

No raw video or FFmpeg binary is needed. The point is the contract between an evaluation and
its clip: the clip generation must never move the evaluated timestamps.
"""

from __future__ import annotations

from pathlib import Path
from threading import Event
from types import SimpleNamespace
from typing import Any

import pytest
from test_mock_e2e import build_pipeline

from valorant_ai_coach.clips import ClipService


class FfmpegRecorder:
    def __init__(self) -> None:
        self.commands: list[list[str]] = []

    def __call__(self, command: list[str], _timeout: float, _cancel: Event | None) -> Any:
        self.commands.append(command)
        Path(command[-1]).write_bytes(b"encoded clip")
        return SimpleNamespace(returncode=0, stderr="")

    @staticmethod
    def window(command: list[str]) -> tuple[float, float]:
        start = float(command[command.index("-ss") + 1])
        length = float(command[command.index("-t") + 1])
        return start, start + length


@pytest.fixture
def workflow(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    recorder = FfmpegRecorder()
    monkeypatch.setattr("valorant_ai_coach.clips.service._run_cancellable_process", recorder)
    video = tmp_path / "match.mp4"
    video.write_bytes(b"video")
    pipeline, repository, _video, _fake_clips = build_pipeline(tmp_path, video)
    pipeline.clips = ClipService(output_dir=tmp_path / "clips")
    result = pipeline.analyze_video(video, lambda _value, _message: None, match_id="M-CLIP")
    return SimpleNamespace(
        result=result, repository=repository, recorder=recorder, clips_dir=tmp_path / "clips"
    )


def test_every_scored_evaluation_has_an_existing_owned_clip(workflow: Any) -> None:
    assert workflow.result.status == "completed"
    stored = workflow.repository.get_match_result("M-CLIP")
    assert stored is not None
    scored = [item for item in stored["evaluations"] if item["label"] in {"good", "improve"}]
    assert scored
    for item in scored:
        clip = item["clip"]
        assert clip is not None
        path = Path(clip["file_path"])
        assert path.is_file()
        assert path.resolve().is_relative_to(workflow.clips_dir.resolve())
        assert path.read_bytes() == b"encoded clip"


def test_ffmpeg_is_asked_for_exactly_the_evaluations_display_clip_window(workflow: Any) -> None:
    stored = workflow.repository.get_match_result("M-CLIP")
    assert stored is not None
    asked = {workflow.recorder.window(command) for command in workflow.recorder.commands}
    for item in stored["evaluations"]:
        if item["label"] not in {"good", "improve"}:
            continue
        expected = (item["display_clip"]["start_sec"], item["display_clip"]["end_sec"])
        assert any(
            start == pytest.approx(expected[0], abs=1e-3)
            and end == pytest.approx(expected[1], abs=1e-3)
            for start, end in asked
        ), f"clip for {item['evaluation_id']} does not match its evaluated window"


def test_clip_generation_does_not_change_the_stored_evaluations(workflow: Any) -> None:
    stored = workflow.repository.get_match_result("M-CLIP")
    assert stored is not None
    for item in stored["evaluations"]:
        if item["label"] not in {"good", "improve"}:
            continue
        clip = item["clip"]
        assert clip["start_sec"] == pytest.approx(item["display_clip"]["start_sec"], abs=1e-3)
        assert clip["end_sec"] == pytest.approx(item["display_clip"]["end_sec"], abs=1e-3)
        evidence = item["evidence_range"]
        assert clip["start_sec"] <= evidence["start_sec"] <= evidence["end_sec"] <= clip["end_sec"]


def test_unscored_evaluations_never_get_a_clip(workflow: Any) -> None:
    stored = workflow.repository.get_match_result("M-CLIP")
    assert stored is not None
    for item in stored["evaluations"]:
        if item["label"] == "unscored":
            assert item["clip"] is None
            assert item.get("clip_id") is None


def test_shared_evidence_window_is_encoded_once(workflow: Any) -> None:
    windows = [workflow.recorder.window(command) for command in workflow.recorder.commands]
    assert len(windows) == len(set(windows))
    assert not list(workflow.clips_dir.glob("*.partial.mp4"))
