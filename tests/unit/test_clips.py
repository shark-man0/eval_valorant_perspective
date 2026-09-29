from __future__ import annotations

from pathlib import Path
from threading import Event
from types import SimpleNamespace
from typing import Any

import pytest

from valorant_ai_coach.clips import ClipGenerationError, ClipService
from valorant_ai_coach.clips.service import ClipCancelled
from valorant_ai_coach.video.service import _ProcessCancelled


def test_clip_range_is_clamped_to_source_duration() -> None:
    assert ClipService.clamp_range(-4, 20, 12) == (0, 12)
    with pytest.raises(ValueError, match="終了時刻"):
        ClipService.clamp_range(12, 14, 12)


def test_create_clip_uses_argument_vector_and_atomic_partial(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source recording.mp4"
    source.write_bytes(b"video")
    calls: list[list[str]] = []

    def fake_run(command: list[str], _timeout: float, _cancel: Event | None) -> Any:
        calls.append(command)
        Path(command[-1]).write_bytes(b"encoded clip")
        return SimpleNamespace(returncode=0, stderr="")

    monkeypatch.setattr("valorant_ai_coach.clips.service._run_cancellable_process", fake_run)
    output_dir = tmp_path / "clips"
    artifact = ClipService(
        ffmpeg_path="C:/Program Files/ffmpeg/ffmpeg.exe", output_dir=output_dir
    ).create_clip(source, -2, 30, 12, "clip_001")

    assert artifact.path == output_dir / "clip_001.mp4"
    assert artifact.path.read_bytes() == b"encoded clip"
    assert (artifact.start_sec, artifact.end_sec) == (0, 12)
    assert calls[0][0] == "C:/Program Files/ffmpeg/ffmpeg.exe"
    assert "-nostdin" in calls[0]
    assert str(source.resolve()) in calls[0]
    map_args = [
        calls[0][index + 1]
        for index, argument in enumerate(calls[0][:-1])
        if argument == "-map"
    ]
    assert map_args == ["0:v:0", "0:a?"]
    assert calls[0].count("-map") == 2
    assert not list(output_dir.glob("*.partial.mp4"))


def test_failed_ffmpeg_removes_partial_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source.mp4"
    source.write_bytes(b"video")

    def fake_run(command: list[str], _timeout: float, _cancel: Event | None) -> Any:
        Path(command[-1]).write_bytes(b"partial")
        return SimpleNamespace(returncode=1, stderr="encoder failed")

    monkeypatch.setattr("valorant_ai_coach.clips.service._run_cancellable_process", fake_run)
    output_dir = tmp_path / "clips"
    with pytest.raises(ClipGenerationError, match="encoder failed"):
        ClipService(output_dir=output_dir).create_clip(source, 1, 2, 10, "failed")
    assert not list(output_dir.glob("*.partial.mp4"))
    assert not (output_dir / "failed.mp4").exists()


def test_mid_operation_cancel_cleans_partial_and_preserves_prior_clip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source.mp4"
    source.write_bytes(b"video")
    output_dir = tmp_path / "clips"
    output_dir.mkdir()
    prior = output_dir / "same.mp4"
    cancel = Event()

    def fake_run(command: list[str], _timeout: float, event: Event | None) -> Any:
        assert event is cancel
        Path(command[-1]).write_bytes(b"partial")
        # Another process materializes a same-ID file after our initial target
        # check. Cancellation cleanup must not delete it.
        prior.write_bytes(b"prior clip")
        cancel.set()
        raise _ProcessCancelled("cancelled")

    monkeypatch.setattr("valorant_ai_coach.clips.service._run_cancellable_process", fake_run)
    with pytest.raises(ClipCancelled):
        ClipService(output_dir=output_dir).create_clip(
            source, 1, 2, 10, "same", cancel_event=cancel
        )
    assert prior.read_bytes() == b"prior clip"
    assert not list(output_dir.glob("*.partial.mp4"))


def test_existing_clip_target_is_never_overwritten(tmp_path: Path) -> None:
    source = tmp_path / "source.mp4"
    source.write_bytes(b"video")
    output_dir = tmp_path / "clips"
    output_dir.mkdir()
    target = output_dir / "owned.mp4"
    target.write_bytes(b"original")

    with pytest.raises(ClipGenerationError, match="既に存在"):
        ClipService(output_dir=output_dir).create_clip(source, 1, 2, 10, "owned")

    assert target.read_bytes() == b"original"


@pytest.mark.parametrize("clip_id", ["../outside", "bad/name", ".", "space id"])
def test_clip_id_cannot_escape_output_directory(tmp_path: Path, clip_id: str) -> None:
    source = tmp_path / "source.mp4"
    source.write_bytes(b"video")
    with pytest.raises(ValueError, match="clip_id"):
        ClipService(output_dir=tmp_path / "clips").create_clip(source, 1, 2, 10, clip_id)
