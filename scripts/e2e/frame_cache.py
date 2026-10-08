"""Immutable, content-verified cache for decoded E2E frame JPEGs."""

from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from valorant_ai_coach.video import FrameSample

_FORMAT_VERSION = 1
_SHA256_LENGTH = 64


def _sha256(value: str, field: str) -> str:
    if not isinstance(value, str) or len(value) != _SHA256_LENGTH:
        raise ValueError(f"{field} must be a 64-character SHA-256 hex digest")
    try:
        int(value, 16)
    except ValueError as exc:
        raise ValueError(f"{field} must be a 64-character SHA-256 hex digest") from exc
    return value.lower()


def _timestamp(value: object) -> float:
    if isinstance(value, bool):
        raise ValueError("frame timestamp must be a finite nonnegative number")
    try:
        result = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("frame timestamp must be a finite nonnegative number") from exc
    if not math.isfinite(result) or result < 0:
        raise ValueError("frame timestamp must be a finite nonnegative number")
    return result


@dataclass(slots=True)
class FrameCacheStats:
    hits: int = 0
    misses: int = 0
    writes: int = 0


class DecodedFrameCache:
    """Cache the exact JPEG bytes emitted by a decoder/preprocessor.

    A cache entry is a directory published atomically. Its strict metadata binds
    the asset bytes to the source, exact timestamp, and preprocessing version.
    Recognition output and profile-dependent results are intentionally absent.
    """

    def __init__(self, cache_dir: str | Path, source_sha256: str,
                 preprocessing_fingerprint: str) -> None:
        self.source_sha256 = _sha256(source_sha256, "source_sha256")
        self.preprocessing_fingerprint = _sha256(
            preprocessing_fingerprint, "preprocessing_fingerprint"
        )
        self.cache_dir = Path(cache_dir)
        if self.cache_dir.exists() and self.cache_dir.is_symlink():
            raise ValueError("cache directory must not be a symlink")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        if self.cache_dir.is_symlink() or not self.cache_dir.is_dir():
            raise ValueError("cache directory must be a real directory")
        self.stats = FrameCacheStats()

    def _key(self, pts: float) -> str:
        data = (f"{self.source_sha256}\0{pts.hex()}\0"
                f"{self.preprocessing_fingerprint}").encode("ascii")
        return hashlib.sha256(data).hexdigest()

    def _paths(self, key: str) -> tuple[Path, Path, Path]:
        directory = self.cache_dir / key
        return directory, directory / "frame.jpg", directory / "metadata.json"

    def _read(self, pts: float) -> FrameSample | None:
        key = self._key(pts)
        directory, image_path, metadata_path = self._paths(key)
        try:
            if directory.is_symlink() or not directory.is_dir():
                return None
            if image_path.is_symlink() or metadata_path.is_symlink():
                return None
            if not image_path.is_file() or not metadata_path.is_file():
                return None
            raw = metadata_path.read_bytes()
            metadata = json.loads(raw)
            expected = {
                "format_version": _FORMAT_VERSION,
                "source_sha256": self.source_sha256,
                "pts_hex": pts.hex(),
                "preprocessing_fingerprint": self.preprocessing_fingerprint,
                "asset_sha256": hashlib.sha256(image_path.read_bytes()).hexdigest(),
            }
            if not isinstance(metadata, dict) or metadata != expected:
                return None
            return FrameSample(time_sec=pts, path=image_path)
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return None

    def get(self, pts_sec: float) -> FrameSample | None:
        pts = _timestamp(pts_sec)
        sample = self._read(pts)
        if sample is None:
            self.stats.misses += 1
        else:
            self.stats.hits += 1
        return sample

    def put(self, frame: FrameSample) -> FrameSample:
        if not isinstance(frame, FrameSample):
            raise TypeError("frame must be a FrameSample")
        pts = _timestamp(frame.time_sec)
        source = Path(frame.path)
        if source.is_symlink() or not source.is_file():
            raise ValueError("frame path must be a regular file, not a symlink")
        payload = source.read_bytes()
        key = self._key(pts)
        directory, image_path, metadata_path = self._paths(key)
        existing = self._read(pts)
        if existing is not None:
            # Entries are immutable: retain the first valid byte sequence.
            return existing

        metadata = {
            "format_version": _FORMAT_VERSION,
            "source_sha256": self.source_sha256,
            "pts_hex": pts.hex(),
            "preprocessing_fingerprint": self.preprocessing_fingerprint,
            "asset_sha256": hashlib.sha256(payload).hexdigest(),
        }
        temporary: Path | None = Path(tempfile.mkdtemp(prefix=f".{key}.", dir=self.cache_dir))
        try:
            assert temporary is not None
            (temporary / "frame.jpg").write_bytes(payload)
            (temporary / "metadata.json").write_text(
                json.dumps(metadata, sort_keys=True, separators=(",", ":")),
                encoding="utf-8",
            )
            # Ensure file contents reach the filesystem before publishing.
            for name in ("frame.jpg", "metadata.json"):
                # On Windows, os.fsync delegates to the CRT commit operation,
                # which rejects read-only descriptors. Reopen read/write solely
                # for the durability barrier; the file contents are not changed.
                with (temporary / name).open("r+b") as file:
                    os.fsync(file.fileno())
            try:
                os.rename(temporary, directory)
                temporary = None
                self.stats.writes += 1
            except FileExistsError:
                pass  # Another writer won; the next read validates its entry.
        finally:
            if temporary is not None and temporary.exists():
                shutil.rmtree(temporary)
        result = self._read(pts)
        if result is None:
            raise OSError("published decoded frame cache entry could not be verified")
        return result
