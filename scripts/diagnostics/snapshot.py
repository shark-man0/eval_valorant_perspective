from __future__ import annotations

import argparse
import json
from pathlib import Path

from valorant_ai_coach.observability import dependency_snapshot

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    parser = argparse.ArgumentParser(description="Write a sanitized dependency snapshot.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/diagnostics/dependency_snapshot.json"),
    )
    parser.add_argument("--pip-check", action="store_true")
    args = parser.parse_args()
    payload = dependency_snapshot(repository_root=ROOT, include_pip_check=args.pip_check)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
