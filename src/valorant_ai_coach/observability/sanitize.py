from __future__ import annotations

import os
import re
from collections.abc import Mapping, Sequence
from pathlib import Path, PureWindowsPath
from typing import Any

_PRIVATE_KEY = re.compile(
    r"(?:^|_)(?:host_?name|user_?name|home_?path|mac_?address|ip_?address|serial_?number)(?:$|_)",
    re.IGNORECASE,
)
_SECRET_KEY = re.compile(
    r"(?:^|_)(?:api_?key|authorization|credential|password|secret|token|request_?headers?|"
    r"prompt_?payload|raw_?response)(?:$|_)",
    re.IGNORECASE,
)
_REDACTIONS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"),
    re.compile(r"(?i)(authorization\s*[:=]\s*bearer\s+)[^\s,;]+"),
    re.compile(r"(?i)((?:api[_-]?key|token|password|secret)\s*[:=]\s*)[^\s,;]+"),
)
_WINDOWS_USER_PATH = re.compile(r"(?i)\b[A-Z]:\\Users\\[^\\\s]+(?:\\[^\s\"']*)?")
_POSIX_USER_PATH = re.compile(r"/(?:home|Users)/[^/\s]+(?:/[^\s\"']*)?")
_WINDOWS_ABSOLUTE_PATH = re.compile(r"(?i)(?<![A-Za-z0-9])(?:[A-Z]:\\|\\\\)[^\s\"']+")
_POSIX_ABSOLUTE_PATH = re.compile(r"(?<![:/A-Za-z0-9])/(?:[^/\s\"']+/)*[^/\s\"']+")


def _looks_absolute_path(value: str) -> bool:
    if not value:
        return False
    if Path(value).is_absolute():
        return True
    return bool(PureWindowsPath(value).drive and PureWindowsPath(value).root)


def _path_placeholder(value: str) -> str:
    name = PureWindowsPath(value).name if "\\" in value else Path(value).name
    return f"<path>/{name}" if name else "<path>"


def sanitize_text(value: str) -> str:
    text = value
    home = str(Path.home())
    if home and home not in {"/", "."}:
        text = text.replace(home, "<home>")
    for pattern in _REDACTIONS:
        text = pattern.sub(
            lambda match: f"{match.group(1)}[redacted]" if match.groups() else "[redacted]",
            text,
        )
    text = _WINDOWS_USER_PATH.sub("<path>", text)
    text = _POSIX_USER_PATH.sub("<path>", text)
    text = _WINDOWS_ABSOLUTE_PATH.sub(lambda match: _path_placeholder(match.group(0)), text)
    text = _POSIX_ABSOLUTE_PATH.sub(lambda match: _path_placeholder(match.group(0)), text)
    if _looks_absolute_path(text) and not any(char.isspace() for char in text):
        text = _path_placeholder(text)
    return text


def sanitize_value(value: Any, *, _depth: int = 0) -> Any:
    if _depth > 8:
        return "[truncated]"
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for index, (key, item) in enumerate(value.items()):
            if index >= 256:
                result["__truncated__"] = True
                break
            name = str(key)
            result[name] = (
                "[redacted]"
                if _SECRET_KEY.search(name) or _PRIVATE_KEY.search(name)
                else sanitize_value(item, _depth=_depth + 1)
            )
        return result
    if isinstance(value, str):
        return sanitize_text(value[:100_000])
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        return [sanitize_value(item, _depth=_depth + 1) for item in value[:256]]
    if isinstance(value, (bytes, bytearray)):
        return f"<binary:{len(value)} bytes>"
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return sanitize_text(str(value))


class RedactingFormatter:
    """Mixin helper used by logging_setup to sanitize a rendered log line."""

    @staticmethod
    def redact(rendered: str) -> str:
        return sanitize_text(rendered)


def safe_environment_subset(names: Sequence[str]) -> dict[str, str]:
    """Return only explicitly allowlisted environment variables, sanitized."""
    result: dict[str, str] = {}
    for name in names:
        if name in os.environ:
            result[name] = sanitize_text(os.environ[name])
    return result
