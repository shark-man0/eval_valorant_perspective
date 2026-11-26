"""Measure how far published Map packages reach the canonical shared timeline.

Development only. Each ``--map NAME=RECEIPT::REPORT`` is a Map library receipt
(``development_map_library_entry_v1``) and its recovered report; each
``--timeline NAME=PATH`` is the canonical timeline bundle of the same recording.
One package per recording: a second package for the same recording is an error, so
the caller chooses which one is measured.

For every recording the Round boundaries are confirmed exactly as for Fact promotion,
and the report counts the canonical own-live seconds inside confirmed Rounds and how
many of them received a projected Map observation. Nothing is promoted.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections import Counter
from pathlib import Path
from typing import Any

from valorant_ai_coach.application.map_projection import project_map_package
from valorant_ai_coach.application.timeline_evaluation import load_bundle, segment_rounds
from valorant_ai_coach.facts.timeline_promotion import TimelinePromoter


def _pair(text: str) -> tuple[str, str]:
    name, _, value = text.partition("=")
    if not name or not value:
        raise argparse.ArgumentTypeError("NAME=VALUE の形式で指定してください")
    return name, value


def _own_live(row: dict[str, Any]) -> bool:
    def observed(state: dict[str, Any] | None, value: str) -> bool:
        return bool(state) and state.get("value") == value and state.get("status") == "OBSERVED"

    return observed(row.get("camera_state"), "SELF") and observed(row.get("life_state"), "ALIVE")


def _file_sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def measure(timeline_path: Path, receipt_path: Path, report_path: Path) -> dict[str, Any]:
    bundle = load_bundle(timeline_path, None)
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    file_sha = _file_sha(timeline_path)
    # A slim bundle names the canonical timeline JSON it was cut from.
    timeline_sha = str(bundle.get("slim", {}).get("timeline_json_sha256") or file_sha)
    projection = project_map_package(
        receipt_path, report_path, bundle, timeline_sha256=timeline_sha
    )
    rounds, _ = segment_rounds(bundle)
    promoted = TimelinePromoter().promote(
        bundle, [(r.round_no, r.start_sec, r.end_sec) for r in rounds]
    )
    confirmed = [
        (item.start.time_sec, item.end.time_sec) for item in promoted.rounds if item.confirmed
    ]

    def inside(second: int) -> bool:
        return any(start <= second <= end for start, end in confirmed)

    counts = Counter(projection.counts)
    own = [s for s, row in enumerate(bundle["seconds"]) if _own_live(row) and inside(s)]
    counts["own_live_seconds_in_confirmed_rounds"] = len(own)
    with_map = [s for s in own if s in projection.rows]
    counts["projected_seconds_in_confirmed_rounds"] = len(with_map)
    counts["zone_candidate_seconds_in_confirmed_rounds"] = sum(
        1 for s in with_map if any(item["zone_candidate"] for item in projection.rows[s])
    )
    return {
        "recording_id": projection.recording_id,
        "source_sha256": projection.source_sha256,
        "report_sha256": projection.report_sha256,
        "receipt_sha256": projection.receipt_sha256,
        "map_artifact_sha256": projection.map_artifact_sha256,
        "map_timeline_sha256": projection.map_timeline_sha256,
        "timeline_sha256": projection.timeline_sha256,
        "timeline_file_sha256": file_sha,
        "label": receipt.get("label"),
        "confirmed_rounds": len(confirmed),
        "counts": dict(sorted(counts.items())),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeline", type=_pair, action="append", default=[])
    parser.add_argument("--map", type=_pair, action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    timelines = dict(args.timeline)
    packages: dict[str, tuple[Path, Path]] = {}
    for name, value in args.map:
        if name in packages:
            parser.error(f"{name}: 1録画に1パッケージだけ指定してください")
        receipt, sep, report = value.partition("::")
        if not sep:
            parser.error("--map は NAME=RECEIPT::REPORT の形式です")
        packages[name] = (Path(receipt), Path(report))
    rows = []
    for name, (receipt, report) in sorted(packages.items()):
        if name not in timelines:
            parser.error(f"{name}: 対応する --timeline がありません")
        rows.append({"name": name, **measure(Path(timelines[name]), receipt, report)})
    total: Counter[str] = Counter()
    for row in rows:
        total.update(row["counts"])
    own = total["own_live_seconds_in_confirmed_rounds"]
    summary = {
        "schema": "development_map_projection_measurement_v1",
        "qualification": "development_only",
        "formal_outputs": 0,
        "recordings": len(rows),
        "totals": dict(sorted(total.items())),
        "coverage_of_own_live_confirmed_seconds": (
            round(total["projected_seconds_in_confirmed_rounds"] / own, 4) if own else None
        ),
        "per_recording": rows,
    }
    args.output.mkdir(parents=True, exist_ok=True, mode=0o700)
    target = args.output / "map_projection_PRIVATE.json"
    target.write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    os.chmod(target, 0o600)
    print(json.dumps({k: v for k, v in summary.items() if k != "per_recording"}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
