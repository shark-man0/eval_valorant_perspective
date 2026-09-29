from __future__ import annotations

import json
import subprocess
from pathlib import Path
from threading import Event
from types import SimpleNamespace
from typing import Any

import pytest

from valorant_ai_coach.video import AudioTrackMetadata, VideoMetadata, VideoProbeError, VideoService
from valorant_ai_coach.video.service import _ProcessCancelled, _run_cancellable_process


def test_probe_parses_ffprobe_streams_and_uses_argument_vector(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    video_path = tmp_path / "round one.mp4"
    video_path.write_bytes(b"video")
    calls: list[list[str]] = []
    response = {
        "format": {"duration": "12.5", "size": "987"},
        "streams": [
            {
                "codec_type": "video",
                "codec_name": "h264",
                "width": 1920,
                "height": 1080,
                "avg_frame_rate": "30000/1001",
                "r_frame_rate": "30/1",
            },
            {
                "index": 1,
                "codec_type": "audio",
                "codec_name": "aac",
                "tags": {"language": "jpn", "title": "Commentary"},
                "disposition": {"default": 1},
            },
            {
                "index": 2,
                "codec_type": "audio",
                "codec_name": "aac",
                "tags": {"language": "eng"},
                "disposition": {"default": 0},
            },
            {"index": 3, "codec_type": "audio", "codec_name": "opus"},
        ],
    }

    def fake_run(command: list[str], _timeout: float, _cancel: Event | None) -> Any:
        calls.append(command)
        return SimpleNamespace(returncode=0, stdout=json.dumps(response))

    monkeypatch.setattr("valorant_ai_coach.video.service._run_cancellable_process", fake_run)
    service = VideoService(ffprobe_path="C:/Program Files/ffmpeg/ffprobe.exe")
    metadata = service.probe(video_path)

    assert metadata.duration_sec == 12.5
    assert (metadata.width, metadata.height) == (1920, 1080)
    assert metadata.fps == pytest.approx(30000 / 1001)
    assert metadata.has_audio and metadata.audio_codec == "aac"
    assert metadata.audio_tracks == (
        AudioTrackMetadata(1, "aac", "jpn", "Commentary", True),
        AudioTrackMetadata(2, "aac", "eng", None, False),
        AudioTrackMetadata(3, "opus", None, None, None),
    )
    assert metadata.file_size == 987
    assert calls[0][0] == "C:/Program Files/ffmpeg/ffprobe.exe"
    assert str(video_path.resolve()) in calls[0]
    assert "shell" not in " ".join(calls[0])
    entries = calls[0][calls[0].index("-show_entries") + 1]
    assert "stream_disposition=default" in entries
    assert "stream_tags=language,title" in entries


def test_video_metadata_old_positional_constructor_remains_compatible(tmp_path: Path) -> None:
    metadata = VideoMetadata(tmp_path / "old.mp4", 1, 10, 10, 30, "h264", "aac", True, 1)
    assert metadata.audio_tracks == ()


def test_probe_requires_existing_supported_video(tmp_path: Path) -> None:
    service = VideoService()
    with pytest.raises(VideoProbeError, match="見つかりません"):
        service.probe(tmp_path / "missing.mp4")
    unsupported = tmp_path / "recording.txt"
    unsupported.write_text("x", encoding="utf-8")
    with pytest.raises(VideoProbeError, match="対応していない"):
        service.probe(unsupported)


def test_extract_frames_clamps_times_and_writes_jpegs(tmp_path: Path) -> None:
    video_path = tmp_path / "input.mkv"
    video_path.write_bytes(b"video")
    metadata = VideoMetadata(
        path=video_path.resolve(),
        duration_sec=1.0,
        width=100,
        height=60,
        fps=30,
        video_codec="h264",
        audio_codec=None,
        has_audio=False,
        file_size=5,
    )
    seeks: list[float] = []

    class FakeCapture:
        current_time = 0.0

        def isOpened(self) -> bool:
            return True

        def set(self, prop: int, value: float) -> bool:
            assert prop == 0
            self.current_time = value / 1000
            seeks.append(self.current_time)
            return True

        def read(self) -> tuple[bool, object]:
            return True, object()

        def get(self, prop: int) -> float:
            if prop == 1:
                return round(self.current_time * 30) + 1
            if prop == 2:
                return 30.0
            return 0.0

        def release(self) -> None:
            pass

    class FakeCv2:
        CAP_PROP_POS_MSEC = 0
        CAP_PROP_POS_FRAMES = 1
        CAP_PROP_FPS = 2
        IMWRITE_JPEG_QUALITY = 3

        @staticmethod
        def imwrite(path: str, _frame: object, _params: list[int]) -> bool:
            Path(path).write_bytes(b"jpeg")
            return True

    service = VideoService(capture_factory=lambda _path: FakeCapture(), cv2_module=FakeCv2())
    service.probe = lambda _path, **_kwargs: metadata  # type: ignore[method-assign]
    frames = service.extract_frames(video_path, [0.5, 9.0], tmp_path / "frames")

    assert seeks == [0.5, 1.0]
    assert [frame.time_sec for frame in frames] == pytest.approx([0.5, 1.0])
    assert all(frame.path.is_file() for frame in frames)


def test_process_runner_terminates_after_mid_operation_cancel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cancel = Event()
    processes: list[Any] = []

    class FakeProcess:
        returncode: int | None = None
        terminated = False

        def __init__(self, command: list[str], **_kwargs: Any) -> None:
            self.command = command
            processes.append(self)

        def communicate(self, timeout: float) -> tuple[str, str]:
            if not self.terminated:
                cancel.set()
                raise subprocess.TimeoutExpired(self.command, timeout)
            return "", ""

        def poll(self) -> int | None:
            return self.returncode

        def terminate(self) -> None:
            self.terminated = True
            self.returncode = -15

        def kill(self) -> None:
            raise AssertionError("terminate should suffice")

    monkeypatch.setattr("valorant_ai_coach.video.service.subprocess.Popen", FakeProcess)
    with pytest.raises(_ProcessCancelled):
        _run_cancellable_process(["ffprobe", "example.mp4"], 5, cancel)
    assert len(processes) == 1 and processes[0].terminated


def test_frame_cancel_removes_created_frames_and_skips_reprobe(tmp_path: Path) -> None:
    video_path = tmp_path / "input.avi"
    video_path.write_bytes(b"video")
    metadata = VideoMetadata(video_path.resolve(), 2.0, 64, 48, 10, "mjpeg", None, False, 5)
    cancel = Event()
    released: list[bool] = []
    writes = 0

    class FakeCapture:
        current_ms = 0.0

        def isOpened(self) -> bool:
            return True

        def set(self, _prop: int, value: float) -> bool:
            self.current_ms = value
            return True

        def read(self) -> tuple[bool, object]:
            return True, object()

        def get(self, prop: int) -> float:
            return self.current_ms / 100 if prop == 1 else 10.0

        def release(self) -> None:
            released.append(True)

    class FakeCv2:
        CAP_PROP_POS_MSEC = 0
        CAP_PROP_POS_FRAMES = 1
        CAP_PROP_FPS = 2
        IMWRITE_JPEG_QUALITY = 3

        @staticmethod
        def imwrite(path: str, _frame: object, _params: list[int]) -> bool:
            nonlocal writes
            writes += 1
            Path(path).write_bytes(b"partial jpeg")
            if writes == 2:
                cancel.set()
            return True

    service = VideoService(capture_factory=lambda _path: FakeCapture(), cv2_module=FakeCv2())
    service.probe = lambda _path: pytest.fail("metadata should avoid ffprobe")  # type: ignore[method-assign]
    output = tmp_path / "frames"
    with pytest.raises(InterruptedError):
        service.extract_frames(
            video_path, [0.2, 0.8], output, metadata=metadata, cancel_event=cancel
        )
    assert released == [True]
    assert list(output.iterdir()) == []


def test_publish_cancel_restores_preexisting_frame_targets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "frames"
    output.mkdir()
    staging = output / ".staging"
    staging.mkdir()
    first_target = output / "frame_00000_000000.100.jpg"
    second_target = output / "frame_00001_000000.200.jpg"
    first_target.write_bytes(b"old first")
    second_target.write_bytes(b"old second")
    first_staged = staging / first_target.name
    second_staged = staging / second_target.name
    first_staged.write_bytes(b"new first")
    second_staged.write_bytes(b"new second")
    cancel = Event()
    original_replace = Path.replace

    def cancel_after_first_publish(source: Path, target: Path) -> Path:
        result = original_replace(source, target)
        if source == first_staged:
            cancel.set()
        return result

    monkeypatch.setattr(Path, "replace", cancel_after_first_publish)
    with pytest.raises(InterruptedError):
        VideoService._publish_staged_frames(
            [(first_staged, first_target, 0.1), (second_staged, second_target, 0.2)], cancel
        )

    assert first_target.read_bytes() == b"old first"
    assert second_target.read_bytes() == b"old second"


def test_large_evidence_frame_is_resized_before_jpeg_encoding(tmp_path: Path) -> None:
    video_path = tmp_path / "input.mp4"
    video_path.write_bytes(b"video")
    metadata = VideoMetadata(video_path.resolve(), 2.0, 1920, 1080, 30, "h264", None, False, 5)
    resize_calls: list[tuple[int, int]] = []

    class Frame:
        shape = (1080, 1920, 3)

    class FakeCapture:
        def isOpened(self) -> bool:
            return True

        def set(self, _prop: int, _value: float) -> bool:
            return True

        def read(self) -> tuple[bool, object]:
            return True, Frame()

        def get(self, prop: int) -> float:
            return 1 if prop == 1 else 30

        def release(self) -> None:
            return None

    class FakeCv2:
        CAP_PROP_POS_MSEC = 0
        CAP_PROP_POS_FRAMES = 1
        CAP_PROP_FPS = 2
        IMWRITE_JPEG_QUALITY = 3
        INTER_AREA = 4

        @staticmethod
        def resize(_frame: object, size: tuple[int, int], *, interpolation: int) -> object:
            assert interpolation == 4
            resize_calls.append(size)
            return object()

        @staticmethod
        def imwrite(path: str, _frame: object, _params: list[int]) -> bool:
            Path(path).write_bytes(b"jpeg")
            return True

    service = VideoService(capture_factory=lambda _path: FakeCapture(), cv2_module=FakeCv2())
    samples = service.extract_frames(
        video_path,
        [0.5],
        tmp_path / "frames",
        metadata=metadata,
        max_dimension=1600,
    )

    assert resize_calls == [(1600, 900)]
    assert len(samples) == 1 and samples[0].path.is_file()
