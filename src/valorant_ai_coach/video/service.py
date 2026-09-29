from __future__ import annotations

import json
import logging
import math
import shutil
import subprocess
import time
import uuid
from bisect import bisect_left
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from threading import Event
from typing import Any

LOGGER = logging.getLogger(__name__)


class VideoProbeError(RuntimeError):
    pass


class VideoCancelled(InterruptedError):
    pass


class _ProcessCancelled(InterruptedError):
    pass


def _run_cancellable_process(
    command: list[str], timeout_sec: float, cancel_event: Event | None = None
) -> subprocess.CompletedProcess[str]:
    if cancel_event is not None and cancel_event.is_set():
        raise _ProcessCancelled("処理がキャンセルされました")
    process = subprocess.Popen(
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    deadline = time.monotonic() + timeout_sec
    try:
        while True:
            if cancel_event is not None and cancel_event.is_set():
                raise _ProcessCancelled("処理がキャンセルされました")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise subprocess.TimeoutExpired(command, timeout_sec)
            try:
                stdout, stderr = process.communicate(timeout=min(0.1, remaining))
            except subprocess.TimeoutExpired:
                continue
            return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
    except BaseException:
        if process.poll() is None:
            process.terminate()
        try:
            process.communicate(timeout=2.0)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate()
        raise


@dataclass(frozen=True, slots=True)
class AudioTrackMetadata:
    index: int
    codec: str
    language: str | None = None
    title: str | None = None
    is_default: bool | None = None


@dataclass(frozen=True, slots=True)
class VideoMetadata:
    path: Path
    duration_sec: float
    width: int
    height: int
    fps: float
    video_codec: str
    audio_codec: str | None
    has_audio: bool
    file_size: int
    audio_tracks: tuple[AudioTrackMetadata, ...] = ()


@dataclass(frozen=True, slots=True)
class FrameSample:
    time_sec: float
    path: Path


def _rate(value: Any) -> float:
    try:
        parsed = float(Fraction(str(value)))
    except (ValueError, ZeroDivisionError, TypeError, OverflowError):
        return 0.0
    return parsed if math.isfinite(parsed) and parsed > 0 else 0.0


def _audio_track(stream: dict[str, Any], fallback_index: int) -> AudioTrackMetadata:
    try:
        index = int(stream.get("index", -1))
        if index < 0:
            raise ValueError
    except (TypeError, ValueError, OverflowError):
        index = fallback_index

    tags = stream.get("tags")
    tags_by_name = (
        {str(key).casefold(): value for key, value in tags.items()}
        if isinstance(tags, dict)
        else {}
    )

    def optional_tag(name: str) -> str | None:
        value = tags_by_name.get(name)
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    disposition = stream.get("disposition")
    default_value = disposition.get("default") if isinstance(disposition, dict) else None
    if default_value is None:
        is_default = None
    else:
        is_default = str(default_value).strip().casefold() in {"1", "true", "yes"}

    return AudioTrackMetadata(
        index=index,
        codec=str(stream.get("codec_name") or "unknown"),
        language=optional_tag("language"),
        title=optional_tag("title"),
        is_default=is_default,
    )


class VideoService:
    """Read media metadata with ffprobe and extract requested OpenCV frames."""

    def __init__(
        self,
        ffprobe_path: str = "ffprobe",
        *,
        timeout_sec: float = 45.0,
        capture_factory: Callable[[str], Any] | None = None,
        cv2_module: Any | None = None,
    ) -> None:
        self.ffprobe_path = str(ffprobe_path or "ffprobe")
        self.timeout_sec = max(1.0, float(timeout_sec))
        self._capture_factory = capture_factory
        self._cv2 = cv2_module
        self._pts_cache: tuple[tuple[str, int, int], tuple[float, ...]] | None = None

    def presentation_times(
        self, path: Path, *, cancel_event: Event | None = None
    ) -> tuple[float, ...]:
        """Decoded display-order timestamps in container time, not frame_index/fps."""
        path = self._require_video(path)
        stat = path.stat()
        key = (str(path), stat.st_size, stat.st_mtime_ns)
        if self._pts_cache is not None and self._pts_cache[0] == key:
            return self._pts_cache[1]
        try:
            result = _run_cancellable_process(
                [self.ffprobe_path, "-v", "error", "-select_streams", "v:0",
                 "-show_frames", "-show_entries", "frame=best_effort_timestamp_time",
                 "-of", "json", str(path)],
                max(self.timeout_sec, 300.0), cancel_event,
            )
            if result.returncode:
                raise VideoProbeError("動画のpresentation timestampを取得できません")
            points = tuple(float(frame["best_effort_timestamp_time"])
                           for frame in json.loads(result.stdout)["frames"])
            if (not points or any(not math.isfinite(t) or t < 0 for t in points)
                    or any(b <= a for a, b in zip(points, points[1:], strict=False))):
                raise ValueError("invalid presentation timeline")
        except _ProcessCancelled as exc:
            raise VideoCancelled("PTS取得がキャンセルされました") from exc
        except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired) as exc:
            raise VideoProbeError(f"PTS取得に失敗しました: {exc}") from exc
        self._pts_cache = (key, points)
        return points

    @staticmethod
    def _require_video(path: Path) -> Path:
        value = Path(path).expanduser().resolve()
        if not value.is_file():
            raise VideoProbeError(f"動画ファイルが見つかりません: {value}")
        if value.suffix.lower() not in {".mp4", ".mkv", ".mov", ".avi", ".webm"}:
            raise VideoProbeError("対応していない動画形式です（mp4/mkv等を選択してください）")
        return value

    def probe(self, path: Path, *, cancel_event: Event | None = None) -> VideoMetadata:
        video_path = self._require_video(path)
        command = [
            self.ffprobe_path,
            "-v",
            "error",
            "-show_entries",
            (
                "format=duration,size:"
                "stream=index,codec_type,codec_name,width,height,avg_frame_rate,r_frame_rate:"
                "stream_disposition=default:stream_tags=language,title"
            ),
            "-of",
            "json",
            str(video_path),
        ]
        try:
            completed = _run_cancellable_process(command, self.timeout_sec, cancel_event)
            if completed.returncode != 0:
                detail = (completed.stderr or "").strip()[-1200:]
                raise VideoProbeError(f"ffprobeで動画を読み取れません: {detail}")
            payload = json.loads(completed.stdout)
        except _ProcessCancelled as exc:
            raise VideoCancelled("ffprobeがキャンセルされました") from exc
        except subprocess.TimeoutExpired as exc:
            raise VideoProbeError("ffprobeがタイムアウトしました") from exc
        except (OSError, json.JSONDecodeError) as exc:
            raise VideoProbeError(f"ffprobeを実行できません: {exc}") from exc

        streams = payload.get("streams") or []
        valid_streams = [stream for stream in streams if isinstance(stream, dict)]
        video_stream = next(
            (s for s in valid_streams if s.get("codec_type") == "video"), None
        )
        if video_stream is None:
            raise VideoProbeError("動画ストリームが見つかりません")
        audio_streams = [s for s in valid_streams if s.get("codec_type") == "audio"]
        audio_tracks = tuple(
            _audio_track(stream, fallback_index=index)
            for index, stream in enumerate(audio_streams)
        )
        audio_stream = audio_streams[0] if audio_streams else None
        format_info = payload.get("format") or {}
        try:
            duration = float(format_info.get("duration", 0))
            width = int(video_stream.get("width", 0))
            height = int(video_stream.get("height", 0))
        except (TypeError, ValueError) as exc:
            raise VideoProbeError("ffprobeのメタデータが不正です") from exc
        if not math.isfinite(duration) or duration <= 0 or width <= 0 or height <= 0:
            raise VideoProbeError("動画の長さまたは解像度を取得できません")

        try:
            size = int(format_info.get("size") or video_path.stat().st_size)
        except (TypeError, ValueError, OSError):
            size = video_path.stat().st_size
        fps = _rate(video_stream.get("avg_frame_rate")) or _rate(video_stream.get("r_frame_rate"))
        return VideoMetadata(
            path=video_path,
            duration_sec=duration,
            width=width,
            height=height,
            fps=fps,
            video_codec=str(video_stream.get("codec_name") or "unknown"),
            audio_codec=(
                str(audio_stream.get("codec_name") or "unknown") if audio_stream else None
            ),
            has_audio=bool(audio_tracks),
            file_size=max(0, size),
            audio_tracks=audio_tracks,
        )

    def extract_frames(
        self,
        path: Path,
        timestamps_sec: Sequence[float],
        output_dir: Path,
        *,
        max_frames: int = 600,
        jpeg_quality: int = 92,
        max_dimension: int | None = 1600,
        metadata: VideoMetadata | None = None,
        cancel_event: Event | None = None,
    ) -> list[FrameSample]:
        video_path = self._require_video(path)
        if cancel_event is not None and cancel_event.is_set():
            raise VideoCancelled("フレーム抽出がキャンセルされました")
        if len(timestamps_sec) > max_frames:
            raise ValueError(f"1回の抽出上限を超えています（最大 {max_frames} フレーム）")
        if not timestamps_sec:
            return []
        if metadata is None:
            metadata = self.probe(video_path, cancel_event=cancel_event)
        elif Path(metadata.path).expanduser().resolve() != video_path:
            raise ValueError("メタデータの動画パスが入力動画と一致しません")
        times: list[float] = []
        for value in timestamps_sec:
            point = float(value)
            if not math.isfinite(point) or point < 0:
                raise ValueError("フレーム時刻は0以上の有限値で指定してください")
            times.append(min(point, metadata.duration_sec))

        cv2_module: Any = self._cv2
        if cv2_module is None:
            try:
                import cv2 as imported_cv2
            except ImportError as exc:
                raise RuntimeError("OpenCVがインストールされていません") from exc
            cv2_module = imported_cv2
        capture_factory = self._capture_factory or cv2_module.VideoCapture
        # Custom capture backends retain their own timestamp contract (used by tests).
        pts = (self.presentation_times(video_path, cancel_event=cancel_event)
               if self._capture_factory is None else ())
        output = Path(output_dir).expanduser().resolve()
        output.mkdir(parents=True, exist_ok=True)
        capture = capture_factory(str(video_path))
        if not capture.isOpened():
            capture.release()
            raise RuntimeError(f"OpenCVで動画を開けません: {video_path}")

        samples: list[FrameSample] = []
        staged_paths: list[tuple[Path, Path, float]] = []
        staging_dir = output / f".frames-{uuid.uuid4().hex}.staging"
        staging_dir.mkdir(parents=False, exist_ok=False)
        partial: Path | None = None
        try:
            for index, timestamp in enumerate(times):
                if cancel_event is not None and cancel_event.is_set():
                    raise VideoCancelled("フレーム抽出がキャンセルされました")
                if pts:
                    right = min(bisect_left(pts, timestamp), len(pts) - 1)
                    selected = min({max(0, right - 1), right},
                                   key=lambda i: (abs(pts[i] - timestamp), i))
                    next_frame = int(capture.get(cv2_module.CAP_PROP_POS_FRAMES))
                    if 0 <= selected - next_frame <= 120:
                        # Nearby samples decode forward; repeated keyframe seeks
                        # otherwise decode the same GOP hundreds of times.
                        for _ in range(selected - next_frame):
                            if cancel_event is not None and cancel_event.is_set():
                                raise VideoCancelled("フレーム抽出がキャンセルされました")
                            if not capture.grab():
                                raise VideoProbeError("フレームを順次デコードできません")
                    elif not capture.set(cv2_module.CAP_PROP_POS_FRAMES, selected):
                        raise VideoProbeError("指定フレームへシークできません")
                else:
                    capture.set(cv2_module.CAP_PROP_POS_MSEC, timestamp * 1000.0)
                ok, frame = capture.read()
                if cancel_event is not None and cancel_event.is_set():
                    raise VideoCancelled("フレーム抽出がキャンセルされました")
                if not ok or frame is None:
                    continue
                shape = getattr(frame, "shape", None)
                if (
                    max_dimension is not None
                    and max_dimension > 0
                    and isinstance(shape, tuple)
                    and len(shape) >= 2
                    and max(int(shape[0]), int(shape[1])) > max_dimension
                    and hasattr(cv2_module, "resize")
                ):
                    height, width = int(shape[0]), int(shape[1])
                    scale = max_dimension / max(height, width)
                    resized = (max(1, round(width * scale)), max(1, round(height * scale)))
                    frame = cv2_module.resize(
                        frame,
                        resized,
                        interpolation=getattr(cv2_module, "INTER_AREA", 3),
                    )
                frame_index = int(capture.get(cv2_module.CAP_PROP_POS_FRAMES)) - 1
                fps = float(capture.get(cv2_module.CAP_PROP_FPS) or metadata.fps or 0)
                if pts:
                    if frame_index < 0 or frame_index >= len(pts):
                        raise VideoProbeError("デコードフレームとPTSの対応が不正です")
                    actual_time = pts[frame_index]
                else:
                    actual_time = frame_index / fps if frame_index >= 0 and fps > 0 else timestamp
                target = output / f"frame_{index:05d}_{actual_time:010.3f}.jpg"
                staged = staging_dir / target.name
                partial = staging_dir / f".{target.stem}.{uuid.uuid4().hex}.partial.jpg"
                written = bool(
                    cv2_module.imwrite(
                        str(partial),
                        frame,
                        [cv2_module.IMWRITE_JPEG_QUALITY, max(50, min(100, jpeg_quality))],
                    )
                )
                if not written:
                    raise RuntimeError(f"フレームを書き込めません: {target}")
                if cancel_event is not None and cancel_event.is_set():
                    raise VideoCancelled("フレーム抽出がキャンセルされました")
                partial.replace(staged)
                partial = None
                staged_paths.append((staged, target, max(0.0, actual_time)))
            self._publish_staged_frames(staged_paths, cancel_event)
            samples = [
                FrameSample(time_sec=time_sec, path=target)
                for _, target, time_sec in staged_paths
            ]
        except BaseException:
            if partial is not None:
                try:
                    partial.unlink(missing_ok=True)
                except OSError as exc:
                    LOGGER.warning("Frame temporary cleanup failed for %s: %s", partial, exc)
            raise
        finally:
            capture.release()
            self._best_effort_remove_tree(staging_dir)
        return samples

    @staticmethod
    def _publish_staged_frames(
        staged_paths: list[tuple[Path, Path, float]], cancel_event: Event | None
    ) -> None:
        """Publish a complete frame batch, restoring every prior target on failure."""

        backups: list[tuple[Path, Path]] = []
        published: list[Path] = []
        try:
            for staged, target, _time_sec in staged_paths:
                if cancel_event is not None and cancel_event.is_set():
                    raise VideoCancelled("フレーム抽出がキャンセルされました")
                if target.exists():
                    backup = target.with_name(f".{target.name}.{uuid.uuid4().hex}.backup")
                    target.replace(backup)
                    backups.append((target, backup))
                staged.replace(target)
                published.append(target)
                if cancel_event is not None and cancel_event.is_set():
                    raise VideoCancelled("フレーム抽出がキャンセルされました")
        except BaseException:
            for target in published:
                try:
                    target.unlink(missing_ok=True)
                except OSError as exc:
                    LOGGER.warning("Frame rollback could not remove %s: %s", target, exc)
            for target, backup in reversed(backups):
                if backup.exists():
                    try:
                        backup.replace(target)
                    except OSError as exc:
                        LOGGER.warning("Frame rollback could not restore %s: %s", target, exc)
            raise
        else:
            for _target, backup in backups:
                try:
                    backup.unlink(missing_ok=True)
                except OSError as exc:
                    LOGGER.warning("Superseded frame cleanup failed for %s: %s", backup, exc)

    @staticmethod
    def _best_effort_remove_tree(path: Path) -> None:
        try:
            shutil.rmtree(path)
        except FileNotFoundError:
            return
        except OSError as exc:
            LOGGER.warning("Frame staging cleanup failed for %s: %s", path, exc)
