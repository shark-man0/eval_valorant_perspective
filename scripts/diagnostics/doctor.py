from __future__ import annotations

import argparse
import importlib.util
import json
import os
import platform
import sqlite3
import sys
from pathlib import Path
from typing import Any

from valorant_ai_coach.observability.environment import tool_version
from valorant_ai_coach.settings import default_data_dir

CORE_IMPORTS = ("numpy", "cv2", "jsonschema", "shapely", "openai", "keyring")


def _writable_target(target: Path) -> bool:
    probe = target
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    return probe.is_dir() and os.access(probe, os.W_OK)


def doctor(data_dir: Path | None = None) -> dict[str, Any]:
    target = Path(data_dir) if data_dir is not None else default_data_dir()
    imports = {name: importlib.util.find_spec(name) is not None for name in CORE_IMPORTS}
    checks: dict[str, Any] = {
        "python": {
            "version": platform.python_version(),
            "implementation": platform.python_implementation(),
            "supported": sys.version_info[:2] == (3, 12),
        },
        "platform": {"os": platform.system(), "architecture": platform.machine()},
        "imports": imports,
        "external_tools": {
            "ffmpeg": tool_version("ffmpeg", "-version"),
            "ffprobe": tool_version("ffprobe", "-version"),
        },
        "data_directory": {
            "exists": target.exists(),
            "writable": _writable_target(target),
        },
        "sqlite": {"available": sqlite3.sqlite_version_info > (0, 0, 0)},
        "gui": {"PySide6": importlib.util.find_spec("PySide6") is not None},
    }
    checks["ok"] = bool(
        checks["python"]["supported"]
        and all(imports.values())
        and checks["external_tools"]["ffmpeg"]
        and checks["external_tools"]["ffprobe"]
        and checks["sqlite"]["available"]
    )
    return checks


def main() -> int:
    parser = argparse.ArgumentParser(description="Check the local runtime without analyzing video.")
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    payload = doctor(args.data_dir)
    encoded = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
