from __future__ import annotations

import json
import os
import re
import zipfile
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

from .sanitize import sanitize_text, sanitize_value

BUNDLE_SCHEMA_VERSION = "1.0"
_MAX_JSON_BYTES = 1_000_000
_MAX_LOG_BYTES = 64_000
_MAX_LOG_LINES = 400
_MAX_STACK_CHARS = 16_000
_SAFE_RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


@dataclass(frozen=True, slots=True)
class DiagnosticBundleRequest:
    run_id: str
    output_path: Path
    performance_path: Path | None = None
    dependency_snapshot_path: Path | None = None
    log_path: Path | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


def _load_bounded_json(path: Path) -> dict[str, Any]:
    if path.is_symlink():
        return {"status": "omitted", "reason": "symlink"}
    try:
        raw = path.read_bytes()
    except OSError as exc:
        return {"status": "unavailable", "error": type(exc).__name__}
    if len(raw) > _MAX_JSON_BYTES:
        return {"status": "omitted", "reason": "size_limit", "bytes": len(raw)}
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {"status": "malformed", "error": type(exc).__name__}
    if not isinstance(value, dict):
        return {"status": "malformed", "error": "root_not_object"}
    return cast(dict[str, Any], sanitize_value(value))


def _bounded_log_tail(path: Path) -> str:
    if path.is_symlink():
        return ""
    try:
        with path.open("rb") as stream:
            stream.seek(0, 2)
            size = stream.tell()
            stream.seek(max(0, size - _MAX_LOG_BYTES))
            raw = stream.read(_MAX_LOG_BYTES)
    except OSError:
        return ""
    text = raw.decode("utf-8", errors="replace")
    lines = text.splitlines()[-_MAX_LOG_LINES:]
    return sanitize_text("\n".join(lines)[-_MAX_STACK_CHARS:]) + "\n"


def create_diagnostic_bundle(request: DiagnosticBundleRequest) -> Path:
    if not _SAFE_RUN_ID.fullmatch(request.run_id) or request.run_id in {".", ".."}:
        raise ValueError("diagnostic run_id contains unsafe characters")
    destination = Path(request.output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema_version": BUNDLE_SCHEMA_VERSION,
        "run_id": request.run_id,
        "metadata": sanitize_value(request.metadata),
        "included": [],
        "excluded_by_policy": [
            "raw_video",
            "screenshots",
            "hud_crops",
            "validation_pack",
            "database",
            "environment_dump",
            "api_credentials",
            "raw_api_response",
            "private_profile_images",
            "arbitrary_user_files",
        ],
    }

    entries: dict[str, str] = {}
    if request.performance_path is not None:
        entries["performance.json"] = json.dumps(
            _load_bounded_json(Path(request.performance_path)), ensure_ascii=False, indent=2
        ) + "\n"
    if request.dependency_snapshot_path is not None:
        entries["dependency_snapshot.json"] = json.dumps(
            _load_bounded_json(Path(request.dependency_snapshot_path)), ensure_ascii=False, indent=2
        ) + "\n"
    if request.log_path is not None:
        tail = _bounded_log_tail(Path(request.log_path))
        if tail:
            entries["recent.log"] = tail

    manifest["included"] = sorted(entries)
    entries["manifest.json"] = (
        json.dumps(sanitize_value(manifest), ensure_ascii=False, indent=2) + "\n"
    )

    with zipfile.ZipFile(destination, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(entries):
            archive.writestr(name, entries[name])
    if os.name != "nt":
        with suppress(OSError):
            destination.chmod(0o600)
    return destination
