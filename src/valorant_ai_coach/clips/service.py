from __future__ import annotations

import logging
import math
import os
import re
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path
from threading import Event

from valorant_ai_coach.video import VideoService
from valorant_ai_coach.video.service import _ProcessCancelled, _run_cancellable_process

LOGGER = logging.getLogger(__name__)


class ClipGenerationError(RuntimeError):
    pass


class ClipCancelled(InterruptedError):
    pass


@dataclass(frozen=True, slots=True)
class ClipArtifact:
    clip_id: str
    path: Path
    start_sec: float
    end_sec: float
    duration_sec: float
    source_path: Path


class ClipService:
    """Generate bounded MP4 clips using argument-vector subprocess calls."""

    _safe_id = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,95}$")

    def __init__(
        self,
        ffmpeg_path: str = "ffmpeg",
        ffprobe_path: str = "ffprobe",
        output_dir: Path | None = None,
        *,
        timeout_sec: float = 300.0,
        video_service: VideoService | None = None,
    ) -> None:
        self.ffmpeg_path = str(ffmpeg_path or "ffmpeg")
        self.ffprobe_path = str(ffprobe_path or "ffprobe")
        self.output_dir = Path(output_dir) if output_dir else Path("clips")
        self.timeout_sec = max(1.0, float(timeout_sec))
        self.video_service = video_service or VideoService(self.ffprobe_path)

    @staticmethod
    def clamp_range(start_sec: float, end_sec: float, duration_sec: float) -> tuple[float, float]:
        start = float(start_sec)
        end = float(end_sec)
        duration = float(duration_sec)
        if not all(math.isfinite(value) for value in (start, end, duration)) or duration <= 0:
            raise ValueError("動画時間とクリップ範囲は有限値で指定してください")
        start = min(max(0.0, start), duration)
        end = min(max(0.0, end), duration)
        if end <= start:
            raise ValueError("クリップの終了時刻は開始時刻より後にしてください")
        return start, end

    def create_clip(
        self,
        video_path: Path,
        start_sec: float,
        end_sec: float,
        source_duration_sec: float | None = None,
        clip_id: str | None = None,
        *,
        cancel_event: Event | None = None,
    ) -> ClipArtifact:
        if cancel_event is not None and cancel_event.is_set():
            raise ClipCancelled("クリップ生成がキャンセルされました")
        source = Path(video_path).expanduser().resolve()
        if not source.is_file():
            raise ClipGenerationError(f"入力動画が見つかりません: {source}")
        if source.suffix.lower() not in {".mp4", ".mkv", ".mov", ".avi", ".webm"}:
            raise ClipGenerationError("対応していない入力動画形式です")
        if source_duration_sec is None:
            if cancel_event is None:
                duration = self.video_service.probe(source).duration_sec
            else:
                duration = self.video_service.probe(source, cancel_event=cancel_event).duration_sec
        else:
            duration = float(source_duration_sec)
        if cancel_event is not None and cancel_event.is_set():
            raise ClipCancelled("クリップ生成がキャンセルされました")
        start, end = self.clamp_range(start_sec, end_sec, duration)
        identifier = clip_id or uuid.uuid4().hex
        if not self._safe_id.fullmatch(identifier) or identifier in {".", ".."}:
            raise ValueError("clip_idに使用できない文字が含まれています")

        target_dir = self.output_dir.expanduser().resolve()
        target_dir.mkdir(parents=True, exist_ok=True)
        target = (target_dir / f"{identifier}.mp4").resolve()
        if target.parent != target_dir:
            raise ValueError("クリップ保存先が出力ディレクトリ外です")
        # A clip ID is a durable identity.  Never let a direct caller replace an
        # already materialized artifact; the pipeline first verifies DB ownership
        # and reuses a valid owned artifact instead.
        if target.exists():
            raise ClipGenerationError(
                f"同じclip_idのクリップが既に存在します: {identifier}"
            )
        partial = target_dir / f".{identifier}.{uuid.uuid4().hex}.partial.mp4"
        command = [
            self.ffmpeg_path,
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-ss",
            f"{start:.6f}",
            "-i",
            str(source),
            "-t",
            f"{end - start:.6f}",
            "-map",
            "0:v:0",
            "-map",
            "0:a?",
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "23",
            "-c:a",
            "aac",
            "-movflags",
            "+faststart",
            str(partial),
        ]
        try:
            completed = _run_cancellable_process(command, self.timeout_sec, cancel_event)
            if cancel_event is not None and cancel_event.is_set():
                raise ClipCancelled("クリップ生成がキャンセルされました")
            if completed.returncode != 0 or not partial.is_file() or partial.stat().st_size == 0:
                detail = (completed.stderr or "").strip()[-1200:]
                raise ClipGenerationError(f"クリップを生成できません: {detail}")
            try:
                # link(2) is an atomic create-only publication, unlike replace(),
                # which overwrites on both POSIX and Windows.  The partial and target
                # reside in the same directory, so this is supported by normal local
                # Windows filesystems as well as POSIX filesystems.
                os.link(partial, target)
            except FileExistsError as exc:
                raise ClipGenerationError(
                    f"同じclip_idのクリップが既に存在します: {identifier}"
                ) from exc
            except OSError as exc:
                raise ClipGenerationError(
                    f"クリップを安全に公開できません: {exc}"
                ) from exc
            try:
                partial.unlink()
            except OSError as exc:
                LOGGER.warning("Published clip temporary cleanup failed for %s: %s", partial, exc)
        except _ProcessCancelled as exc:
            raise ClipCancelled("クリップ生成がキャンセルされました") from exc
        except subprocess.TimeoutExpired as exc:
            raise ClipGenerationError("FFmpegのクリップ生成がタイムアウトしました") from exc
        except OSError as exc:
            raise ClipGenerationError(f"FFmpegを起動できません: {exc}") from exc
        finally:
            try:
                partial.unlink(missing_ok=True)
            except OSError as exc:
                LOGGER.warning("Clip temporary cleanup failed for %s: %s", partial, exc)
        return ClipArtifact(
            clip_id=identifier,
            path=target,
            start_sec=start,
            end_sec=end,
            duration_sec=end - start,
            source_path=source,
        )
