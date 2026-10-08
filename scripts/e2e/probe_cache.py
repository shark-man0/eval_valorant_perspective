"""Persistent cache for ffprobe metadata and decoded presentation timestamps."""

from __future__ import annotations

import hashlib
import json
import math
import os
import tempfile
from pathlib import Path
from typing import Any

from valorant_ai_coach.diagnostics.runtime_timing import timing_stage
from valorant_ai_coach.video import AudioTrackMetadata, VideoMetadata, VideoService

_VERSION = 1


def _digest(value: str, label: str) -> str:
    if not isinstance(value, str) or len(value) != 64:
        raise ValueError(f"{label} must be a 64-character SHA-256 digest")
    try:
        int(value, 16)
    except ValueError as exc:
        raise ValueError(f"{label} must be a 64-character SHA-256 digest") from exc
    return value.lower()


def _finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


class CachedVideoService:
    """VideoService proxy that persists successful probe and PTS results.

    The wrapped service remains responsible for all decoding and extraction.
    Cached PTS are installed into its in-memory cache so extraction can reuse the
    real display-order timeline without another ffprobe full-frame scan.
    """

    def __init__(
        self,
        video: VideoService,
        cache_dir: str | Path,
        source_sha256: str,
        ffprobe_fingerprint: str,
    ) -> None:
        self.video = video
        self.source_sha256 = _digest(source_sha256, "source_sha256")
        self.ffprobe_fingerprint = _digest(ffprobe_fingerprint, "ffprobe_fingerprint")
        self.cache_dir = Path(cache_dir)
        if self.cache_dir.exists() and self.cache_dir.is_symlink():
            raise ValueError("probe cache directory must not be a symlink")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        if self.cache_dir.is_symlink() or not self.cache_dir.is_dir():
            raise ValueError("probe cache directory must be a real directory")
        self.stats = {"hits": 0, "misses": 0, "writes": 0}

    def __getattr__(self, name: str) -> Any:
        # Preserve access to VideoService options and methods outside this cache.
        return getattr(self.video, name)

    def _key(self, kind: str) -> str:
        material = f"{self.source_sha256}\0{self.ffprobe_fingerprint}\0{kind}"
        return hashlib.sha256(material.encode("ascii")).hexdigest()

    def _path(self, kind: str) -> Path:
        return self.cache_dir / f"{self._key(kind)}.json"

    def _load(self, kind: str) -> Any | None:
        path = self._path(kind)
        try:
            if path.is_symlink() or not path.is_file():
                return None
            envelope = json.loads(path.read_bytes())
            required_envelope = {"version", "kind", "payload", "payload_sha256"}
            if not isinstance(envelope, dict) or set(envelope) != required_envelope:
                return None
            payload = envelope["payload"]
            serialized = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
            if (envelope["version"] != _VERSION or envelope["kind"] != kind
                    or envelope["payload_sha256"] != hashlib.sha256(serialized).hexdigest()):
                return None
            return payload
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return None

    def _save(self, kind: str, payload: Any) -> None:
        path = self._path(kind)
        # Preserve a valid entry as immutable. Invalid entries are replaced by
        # the successful result just computed by the wrapped ffprobe service.
        if self._load(kind) is not None:
            return
        serialized = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        envelope = {
            "version": _VERSION,
            "kind": kind,
            "payload": payload,
            "payload_sha256": hashlib.sha256(serialized).hexdigest(),
        }
        fd, temporary_name = tempfile.mkstemp(prefix=f".{path.stem}.", dir=self.cache_dir)
        temporary = Path(temporary_name)
        try:
            with os.fdopen(fd, "wb") as file:
                encoded = json.dumps(envelope, sort_keys=True, separators=(",", ":"))
                file.write(encoded.encode("utf-8"))
                file.flush()
                os.fsync(file.fileno())
            os.replace(temporary, path)
            self.stats["writes"] += 1
        finally:
            temporary.unlink(missing_ok=True)

    @staticmethod
    def _metadata_payload(metadata: VideoMetadata) -> dict[str, Any]:
        return {
            "duration_sec": metadata.duration_sec,
            "width": metadata.width,
            "height": metadata.height,
            "fps": metadata.fps,
            "video_codec": metadata.video_codec,
            "audio_codec": metadata.audio_codec,
            "has_audio": metadata.has_audio,
            "file_size": metadata.file_size,
            "audio_tracks": [
                {"index": track.index, "codec": track.codec, "language": track.language,
                 "title": track.title, "is_default": track.is_default}
                for track in metadata.audio_tracks
            ],
        }

    @staticmethod
    def _decode_metadata(payload: Any, current_path: Path) -> VideoMetadata | None:
        required = {"duration_sec", "width", "height", "fps", "video_codec", "audio_codec",
                    "has_audio", "file_size", "audio_tracks"}
        if not isinstance(payload, dict) or set(payload) != required:
            return None
        if (not _finite_number(payload["duration_sec"]) or payload["duration_sec"] <= 0
                or not _finite_number(payload["fps"]) or payload["fps"] < 0
                or any(type(payload[k]) is not int or payload[k] <= 0 for k in ("width", "height"))
                or type(payload["file_size"]) is not int or payload["file_size"] < 0
                or type(payload["has_audio"]) is not bool
                or not isinstance(payload["video_codec"], str)
                or (
                    payload["audio_codec"] is not None
                    and not isinstance(payload["audio_codec"], str)
                )
                or not isinstance(payload["audio_tracks"], list)):
            return None
        tracks: list[AudioTrackMetadata] = []
        for row in payload["audio_tracks"]:
            fields = {"index", "codec", "language", "title", "is_default"}
            if (not isinstance(row, dict) or set(row) != fields or type(row["index"]) is not int
                    or row["index"] < 0 or not isinstance(row["codec"], str)
                    or any(row[field] is not None and not isinstance(row[field], str)
                           for field in ("language", "title"))
                    or (row["is_default"] is not None and type(row["is_default"]) is not bool)):
                return None
            tracks.append(AudioTrackMetadata(**row))
        return VideoMetadata(
            path=current_path,
            duration_sec=float(payload["duration_sec"]),
            width=payload["width"],
            height=payload["height"],
            fps=float(payload["fps"]),
            video_codec=payload["video_codec"],
            audio_codec=payload["audio_codec"],
            has_audio=payload["has_audio"],
            file_size=payload["file_size"],
            audio_tracks=tuple(tracks),
        )

    def probe(self, path: Path, *, cancel_event: Any = None) -> VideoMetadata:
        current_path = self.video._require_video(path)
        payload = self._load("probe")
        metadata = self._decode_metadata(payload, current_path)
        if metadata is not None:
            self.stats["hits"] += 1
            return metadata
        self.stats["misses"] += 1
        metadata = self.video.probe(current_path, cancel_event=cancel_event)
        if Path(metadata.path).expanduser().resolve() != current_path:
            raise ValueError("wrapped VideoService returned metadata for a different video")
        self._save("probe", self._metadata_payload(metadata))
        return metadata

    @staticmethod
    def _decode_pts(payload: Any) -> tuple[float, ...] | None:
        if not isinstance(payload, list) or not payload:
            return None
        if any(not _finite_number(value) or value < 0 for value in payload):
            return None
        points = tuple(float(value) for value in payload)
        if any(right <= left for left, right in zip(points, points[1:], strict=False)):
            return None
        return points

    def presentation_times(self, path: Path, *, cancel_event: Any = None) -> tuple[float, ...]:
        with timing_stage("pts_scan"):
            return self._presentation_times(path, cancel_event=cancel_event)

    def _presentation_times(self, path: Path, *, cancel_event: Any = None) -> tuple[float, ...]:
        current_path = self.video._require_video(path)
        payload = self._load("pts")
        points = self._decode_pts(payload)
        if points is not None:
            self.stats["hits"] += 1
        else:
            self.stats["misses"] += 1
            points = self.video.presentation_times(current_path, cancel_event=cancel_event)
            if self._decode_pts(list(points)) is None:
                raise ValueError("wrapped VideoService returned an invalid presentation timeline")
            points = tuple(float(point) for point in points)
            self._save("pts", list(points))
        stat = current_path.stat()
        self.video._pts_cache = ((str(current_path), stat.st_size, stat.st_mtime_ns), points)
        return points

    def extract_frames(self, *args: Any, **kwargs: Any) -> Any:
        # Prime persistent PTS before extraction, whose implementation calls the
        # wrapped service's presentation_times directly.
        timestamps = args[1] if len(args) > 1 else kwargs.get("timestamps_sec", ())
        if timestamps and getattr(self.video, "_capture_factory", None) is None:
            path = args[0] if args else kwargs["path"]
            cancel_event = kwargs.get("cancel_event")
            self.presentation_times(Path(path), cancel_event=cancel_event)
        return self.video.extract_frames(*args, **kwargs)
