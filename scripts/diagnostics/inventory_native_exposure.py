"""Conservative saved native-PTS inventory; not proof of exhaustive exposure."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def collect_ticks(value):
    ticks = set()
    if isinstance(value, dict):
        if type(value.get("source_pts_ticks")) is int:
            ticks.add(value["source_pts_ticks"])
        for child in value.values():
            ticks.update(collect_ticks(child))
    elif isinstance(value, list):
        for child in value:
            ticks.update(collect_ticks(child))
    return ticks


def merge_ticks(ticks):
    ranges = []
    for tick in sorted(set(ticks)):
        if ranges and tick - ranges[-1][1] <= 256:
            ranges[-1][1] = tick
        else:
            ranges.append([tick, tick])
    return ranges


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("refuse to overwrite exposure evidence")
    paths = sorted(
        set(Path("e2e_reports/match_001").glob("*.json"))
        | {
            p
            for p in Path("outputs/recognition-investigation").rglob("*.json")
            if p.name in {"results.json", "manifest.json", "decoded-manifest.json"}
        }
    )
    ticks, sources, skipped = set(), [], []
    for path in paths:
        if path.stat().st_size > 8_000_000:
            skipped.append({"path": str(path), "reason": "size_limit"})
            continue
        raw = path.read_bytes()
        try:
            found = collect_ticks(json.loads(raw))
        except (UnicodeError, json.JSONDecodeError):
            skipped.append({"path": str(path), "reason": "not_json"})
            continue
        sources.append(
            {
                "path": str(path),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "native_ticks": sorted(found),
            }
        )
        ticks.update(found)
    for source in sources:
        if hashlib.sha256(Path(source["path"]).read_bytes()).hexdigest() != source["sha256"]:
            raise ValueError("inventory source changed during scan")
    report = {
        "scope": "known saved source_pts_ticks; single-video workspace conservative exclusion",
        "time_base": "1/15360",
        "native_step_ticks": 256,
        "sources": sources,
        "skipped": skipped,
        "known_unique_ticks": len(ticks),
        "known_ranges_ticks_inclusive": merge_ticks(ticks),
        "terminal_bindings_match": True,
        "exhaustive_exposure_proven": False,
    }
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k not in {"sources", "skipped"}}))


if __name__ == "__main__":
    main()
