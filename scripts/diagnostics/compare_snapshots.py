from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("snapshot root must be an object")
    return value


def compare(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    left_python = left.get("python", {})
    right_python = right.get("python", {})
    left_platform = left.get("platform", {})
    right_platform = right.get("platform", {})
    left_packages = left.get("packages", {})
    right_packages = right.get("packages", {})
    left_tools = left.get("tools", {})
    right_tools = right.get("tools", {})
    keys = (
        ("python.version", left_python.get("version"), right_python.get("version")),
        ("platform.os", left_platform.get("os"), right_platform.get("os")),
        (
            "platform.architecture",
            left_platform.get("architecture"),
            right_platform.get("architecture"),
        ),
        ("packages.numpy", left_packages.get("numpy"), right_packages.get("numpy")),
        (
            "packages.opencv-python",
            left_packages.get("opencv-python"),
            right_packages.get("opencv-python"),
        ),
        ("tools.ffmpeg", left_tools.get("ffmpeg"), right_tools.get("ffmpeg")),
        ("tools.ffprobe", left_tools.get("ffprobe"), right_tools.get("ffprobe")),
    )
    return {
        "schema_version": "1.0",
        "differences": [
            {"field": field, "left": a, "right": b}
            for field, a, b in keys
            if a != b
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare two sanitized dependency snapshots.")
    parser.add_argument("left", type=Path)
    parser.add_argument("right", type=Path)
    args = parser.parse_args()
    print(json.dumps(compare(_read(args.left), _read(args.right)), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
