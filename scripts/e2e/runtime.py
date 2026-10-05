"""Portable E2E input/runtime resolution; no shell, GUI startup or Git mutation."""

from __future__ import annotations

import importlib
import os
import shutil
import sys
from collections.abc import Mapping
from pathlib import Path, PureWindowsPath


class CaseError(RuntimeError):
    """Controlled public error code, never a private path or command output."""


IS_WINDOWS = os.name == "nt"

LOCAL_KEYS = frozenset(
    {
        "VALORANT_E2E_VIDEO",
        "VALORANT_E2E_PACK",
        "VALORANT_E2E_HUD_LAYOUT",
        "VALORANT_E2E_VISUAL_PROFILE",
        "VALORANT_E2E_MANUAL_MAP_ID",
        "VALORANT_E2E_MAP_CLIENT_BUILD",
        "FFMPEG_BIN",
        "FFPROBE_BIN",
        "GIT_BIN",
    }
)


def repository_root(entrypoint: Path) -> Path:
    return entrypoint.resolve().parents[2]


def local_settings(root: Path) -> dict[str, str]:
    path = root / ".env.local"
    if not path.is_file():
        return {}
    result = {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        key, sep, value = line.partition("=")
        key = key.strip()
        if not sep or key not in LOCAL_KEYS or key in result:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if value:
            result[key] = value
    return result


def setting(cli: str | None, name: str, env: Mapping[str, str], local: Mapping[str, str]):
    return cli or env.get(name) or local.get(name)


def native_path(value: str | Path, root: Path) -> Path:
    """Use host-native paths. Relative inputs are consistently repository-relative."""
    text = str(value)
    # A copied Windows machine-local config is not a Linux relative filename.
    if not IS_WINDOWS and PureWindowsPath(text).drive:
        raise CaseError("FOREIGN_WINDOWS_PATH")
    path = Path(value).expanduser()
    return (path if path.is_absolute() else root / path).resolve()


def resolve_tool(
    name: str,
    *,
    explicit: str | None = None,
    env: Mapping[str, str] | None = None,
    root: Path | None = None,
) -> str:
    env = os.environ if env is None else env
    candidate = explicit or env.get(name.upper() + "_BIN") or name
    if root is not None and ("/" in candidate or "\\" in candidate):
        candidate = str(native_path(candidate, root))
    executable = shutil.which(candidate)
    if executable is None:
        raise CaseError(name.upper() + "_MISSING")
    return executable


def check_environment(
    *,
    root: Path,
    overrides: Mapping[str, str | None] | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, str]:
    if sys.version_info[:2] != (3, 12):
        raise CaseError("PYTHON_312_REQUIRED")
    for module in ("numpy", "cv2", "jsonschema", "shapely", "openai", "keyring"):
        try:
            importlib.import_module(module)
        except (ImportError, OSError) as exc:
            raise CaseError("DEPENDENCY_UNAVAILABLE_" + module.upper()) from exc
    overrides = overrides or {}
    return {
        name: resolve_tool(name, explicit=overrides.get(name), env=env, root=root)
        for name in ("git", "ffmpeg", "ffprobe")
    }
