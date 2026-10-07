from __future__ import annotations

import importlib.metadata
import json
import platform
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any, cast

from .sanitize import sanitize_text, sanitize_value

SNAPSHOT_SCHEMA_VERSION = "1.0"
DEFAULT_PACKAGES: tuple[str, ...] = (
    "numpy",
    "jsonschema",
    "keyring",
    "openai",
    "opencv-python",
    "shapely",
    "pywin32-ctypes",
    "PySide6",
    "pytest",
    "ruff",
    "mypy",
    "pyinstaller",
)


def package_versions(names: Sequence[str] = DEFAULT_PACKAGES) -> dict[str, str | None]:
    versions: dict[str, str | None] = {}
    for name in names:
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
    return versions


def tool_version(executable: str, *args: str, timeout_sec: float = 3.0) -> str | None:
    try:
        completed = subprocess.run(
            [executable, *(args or ("--version",))],
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    output = completed.stdout or completed.stderr or ""
    line = next((item.strip() for item in output.splitlines() if item.strip()), "")
    return sanitize_text(line[:1000]) or None


def repository_state(repository_root: Path | None) -> dict[str, str | bool | None]:
    if repository_root is None:
        return {"commit_sha": None, "dirty": None}
    root = Path(repository_root)
    try:
        commit = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=3.0,
            check=False,
        )
        if commit.returncode != 0:
            return {"commit_sha": None, "dirty": None}
        status = subprocess.run(
            ["git", "-C", str(root), "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=3.0,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return {"commit_sha": None, "dirty": None}
    sha = commit.stdout.strip()
    return {
        "commit_sha": sha if len(sha) == 40 else None,
        "dirty": bool(status.stdout.strip()) if status.returncode == 0 else None,
    }


def pip_check() -> dict[str, Any]:
    try:
        completed = subprocess.run(
            [sys.executable, "-m", "pip", "check"],
            capture_output=True,
            text=True,
            timeout=30.0,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"status": "unavailable", "detail": sanitize_text(str(exc))}
    detail = sanitize_text((completed.stdout or completed.stderr or "").strip()[:4000])
    return {"status": "ok" if completed.returncode == 0 else "mismatch", "detail": detail}


def dependency_snapshot(
    *,
    repository_root: Path | None = None,
    package_names: Sequence[str] = DEFAULT_PACKAGES,
    include_pip_check: bool = False,
    ffmpeg_executable: str = "ffmpeg",
    ffprobe_executable: str = "ffprobe",
) -> dict[str, Any]:
    state = repository_state(repository_root)
    result: dict[str, Any] = {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "python": {
            "implementation": platform.python_implementation(),
            "version": platform.python_version(),
        },
        "platform": {
            "os": platform.system(),
            "release": platform.release(),
            "architecture": platform.machine(),
        },
        "repository": state,
        "packages": package_versions(package_names),
        "tools": {
            "ffmpeg": tool_version(ffmpeg_executable, "-version"),
            "ffprobe": tool_version(ffprobe_executable, "-version"),
        },
    }
    if include_pip_check:
        result["pip_check"] = pip_check()
    return cast(dict[str, Any], sanitize_value(result))


def write_dependency_snapshot(
    target: Path,
    *,
    repository_root: Path | None = None,
    package_names: Sequence[str] = DEFAULT_PACKAGES,
    include_pip_check: bool = False,
    ffmpeg_executable: str = "ffmpeg",
    ffprobe_executable: str = "ffprobe",
) -> Path:
    destination = Path(target)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = dependency_snapshot(
        repository_root=repository_root,
        package_names=package_names,
        include_pip_check=include_pip_check,
        ffmpeg_executable=ffmpeg_executable,
        ffprobe_executable=ffprobe_executable,
    )
    destination.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return destination
