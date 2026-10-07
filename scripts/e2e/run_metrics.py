"""Runtime summary, provenance checks, and cross-platform full-run locking."""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any


def code_fingerprint(root: str | Path) -> str:
    """Hash source paths and bytes used by E2E, excluding generated and doc files."""
    base = Path(root).expanduser().resolve()
    sources = (
        base / "src",
        base / "scripts" / "e2e",
        base / "tests" / "e2e",
    )
    files = sorted(
        path
        for directory in sources
        if directory.is_dir()
        for path in directory.rglob("*.py")
        if path.is_file()
    )
    digest = hashlib.sha256()
    for path in files:
        relative = path.relative_to(base).as_posix().encode("utf-8")
        content = path.read_bytes()
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return digest.hexdigest()


def build_runtime_summary(
    mode: str,
    processed_frames: int,
    wall_sec: float,
    timing: Mapping[str, Any],
    input_fingerprint: Any,
    source_sha256: str | None,
    metrics: Mapping[str, Any],
    previous: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a concise summary and compare only runs on identical inputs/video."""
    wall = max(0.0, float(wall_sec))
    frame_count = max(0, int(processed_frames))
    stages = timing.get("stages", timing)
    normalized_stages: dict[str, dict[str, float | int]] = {}
    if isinstance(stages, Mapping):
        for name, raw in sorted(stages.items()):
            if not isinstance(name, str) or not isinstance(raw, Mapping):
                continue
            calls = _nonnegative_int(raw.get("calls"))
            total = _nonnegative_float(raw.get("total_sec"))
            normalized_stages[name] = {
                "calls": calls,
                "total_sec": total,
                "average_sec": total / calls if calls else 0.0,
                "wall_share": total / wall if wall else 0.0,
            }

    summary: dict[str, Any] = {
        "mode": mode,
        "frame_count": frame_count,
        "wall_sec": wall,
        "fps": frame_count / wall if wall else 0.0,
        "timing": {"wall_sec": wall, "stages": normalized_stages},
        "input_fingerprint": input_fingerprint,
        "source_sha256": source_sha256,
        "metrics": dict(metrics),
    }
    summary["current_previous_delta"] = _comparison(summary, previous)
    return summary


def _comparison(
    current: Mapping[str, Any], previous: Mapping[str, Any] | None
) -> dict[str, Any]:
    if previous is None:
        return {"comparable": False, "reason": "no_previous_run", "deltas": {}}
    reasons = []
    if current.get("mode") != previous.get("mode"):
        reasons.append("mode_mismatch")
    if _stable_fingerprint(current.get("input_fingerprint")) != _stable_fingerprint(
        previous.get("input_fingerprint")
    ):
        reasons.append("input_fingerprint_mismatch")
    if _video_identity(current) is None or _video_identity(current) != _video_identity(previous):
        reasons.append("video_mismatch")
    if reasons:
        return {"comparable": False, "reason": ",".join(reasons), "deltas": {}}

    wall_delta = _delta(current.get("wall_sec"), previous.get("wall_sec"))
    assert wall_delta is not None
    deltas: dict[str, dict[str, float | None]] = {"wall_sec": wall_delta}
    current_metrics = current.get("metrics")
    previous_metrics = previous.get("metrics")
    if isinstance(current_metrics, Mapping) and isinstance(previous_metrics, Mapping):
        for name in sorted(set(current_metrics) & set(previous_metrics)):
            if isinstance(name, str):
                delta = _delta(current_metrics[name], previous_metrics[name])
                if delta is not None:
                    deltas[name] = delta
    return {"comparable": True, "reason": None, "deltas": deltas}


def _video_identity(summary: Mapping[str, Any]) -> str | None:
    source = summary.get("source_sha256")
    if isinstance(source, str) and source:
        return source
    fingerprint = summary.get("input_fingerprint")
    if isinstance(fingerprint, Mapping):
        video_id = fingerprint.get("video_id")
        return str(video_id) if isinstance(video_id, str) and video_id else None
    return None


def _stable_fingerprint(value: Any) -> Any:
    """Drop implementation/profile identity while retaining data-input identity."""
    if isinstance(value, Mapping):
        return {
            key: _stable_fingerprint(child)
            for key, child in value.items()
            if str(key).casefold() not in {"profile_fingerprint", "code_fingerprint"}
        }
    if isinstance(value, (list, tuple)):
        return [_stable_fingerprint(child) for child in value]
    return value


def _delta(current: Any, previous: Any) -> dict[str, float | None] | None:
    if not _is_number(current) or not _is_number(previous):
        return None
    now = float(current)
    old = float(previous)
    diff = now - old
    return {
        "current": now,
        "previous": old,
        "delta": diff,
        "percent_change": diff / old * 100 if old else None,
    }


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _nonnegative_float(value: Any) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError, OverflowError):
        return 0.0
    return parsed if parsed >= 0 and parsed < float("inf") else 0.0


def _nonnegative_int(value: Any) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError, OverflowError):
        return 0
    return max(0, parsed)


def load_previous(path: str | Path) -> dict[str, Any] | None:
    """Load a previous result only when any recorded input/artifact hashes verify."""
    source = Path(path).expanduser().resolve()
    if source.is_dir():
        source = source / "runtime_summary.json"
    try:
        result = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(result, dict):
        return None
    if result.get("comparison_eligible") is False:
        return None

    context = result.get("terminal_context")
    if not isinstance(context, Mapping):
        return None
    exit_code = context.get("exit_code")
    if type(exit_code) is not int or exit_code not in (0, 1):
        return None
    input_hashes = context.get("input_hashes")
    if not isinstance(input_hashes, Mapping):
        return None
    if not {"raw_processing.json", "evaluation_report.json"}.issubset(input_hashes):
        return None
    verified_hashes: dict[str, str] = {}
    for name, expected in input_hashes.items():
        if not isinstance(name, str) or not name:
            return None
        artifact = (source.parent / name).resolve()
        if (
            not isinstance(expected, str)
            or not re.fullmatch(r"[a-fA-F0-9]{64}", expected)
            or source.parent not in artifact.parents
            or not artifact.is_file()
            or _sha256(artifact) != expected.lower()
        ):
            return None
        verified_hashes[name] = expected.lower()

    try:
        raw_result = json.loads((source.parent / "raw_processing.json").read_text(encoding="utf-8"))
        evaluation = json.loads(
            (source.parent / "evaluation_report.json").read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError):
        return None
    if (
        not isinstance(raw_result, Mapping)
        or raw_result.get("status") != "complete"
        or not isinstance(evaluation, Mapping)
        or type(evaluation.get("pass")) is not bool
    ):
        return None

    result_artifact = context.get("result_artifact")
    if isinstance(result_artifact, Mapping):
        artifact_name = result_artifact.get("path")
        expected_hash = result_artifact.get("sha256")
    else:
        artifact_name = result_artifact
        expected_hash = None
    if not isinstance(artifact_name, str):
        return None
    artifact = (source.parent / artifact_name).resolve()
    if source.parent not in artifact.parents or not artifact.is_file():
        return None
    if expected_hash is None:
        expected_hash = verified_hashes.get(artifact_name)
    if expected_hash is None and artifact == source:
        expected_hash = verified_hashes.get(Path(artifact_name).name)
    if (
        not isinstance(expected_hash, str)
        or not re.fullmatch(r"[a-fA-F0-9]{64}", expected_hash)
        or _sha256(artifact) != expected_hash.lower()
    ):
        return None
    return result


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class FullRunLock:
    """Nonblocking process-wide lock for full E2E runs; the OS releases it on exit."""

    def __init__(self, root: str | Path) -> None:
        self.path = Path(root).expanduser().resolve() / ".e2e_full_run.lock"
        self._fd: int | None = None

    def __enter__(self) -> FullRunLock:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fd = os.open(self.path, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt_api: Any = msvcrt
                if os.fstat(self._fd).st_size == 0:
                    os.write(self._fd, b"\0")
                os.lseek(self._fd, 0, os.SEEK_SET)
                msvcrt_api.locking(self._fd, msvcrt_api.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(self._fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (ImportError, OSError) as exc:
            os.close(self._fd)
            self._fd = None
            raise ValueError("another full E2E run holds the repository lock") from exc
        return self

    def __exit__(self, *_exc: object) -> None:
        if self._fd is None:
            return
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt_api: Any = msvcrt
                os.lseek(self._fd, 0, os.SEEK_SET)
                msvcrt_api.locking(self._fd, msvcrt_api.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(self._fd, fcntl.LOCK_UN)
        finally:
            os.close(self._fd)
            self._fd = None
