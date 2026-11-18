"""Measure formal Fact/Event promotion over several shared-timeline outputs.

Each input is an application bundle (``--timeline NAME=PATH``, .json or .json.gz)
or a replay export (``--replay NAME=PATH``, ``events_and_states``). Every input goes
through the same path as ``timeline_evaluation evaluate`` (promotion, Round Packages,
RoundAnalyzer, Match aggregation, SQLite storage and the stored-view consistency
check) and the counts are written as one private JSON plus a Markdown table.

The recordings are DEVELOPMENT data. The independent-signal checks are consistency
checks against other HUD readers of the same recording, not human labels.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from valorant_ai_coach.application.timeline_evaluation import run


def _pair(text: str) -> tuple[str, Path]:
    name, _, path = text.partition("=")
    if not name or not path:
        raise argparse.ArgumentTypeError("NAME=PATH の形式で指定してください")
    return name, Path(path)


def measure(
    inputs: Sequence[tuple[str, str, Path]], output: Path
) -> dict[str, Any]:
    output.mkdir(parents=True, mode=0o700)
    rows: list[dict[str, Any]] = []
    for name, kind, path in inputs:
        started = time.perf_counter()
        report = run(
            timeline_path=path if kind == "timeline" else None,
            replay_path=path if kind == "replay" else None,
            output=output / name,
            match_id=f"DEV-{name}",
            database=output / f"{name}.db",
        )
        promotion = report["formal_promotion"] or {}
        checks = report.get("independent_signal_checks", {}).get("counts", {})
        rows.append(
            {
                "name": name,
                "input": kind,
                "source_id": report["source"]["source_id"],
                "rounds_segmented": report["rounds_segmented"],
                "rounds_confirmed": report["formal_input_counts"]["rounds_confirmed"],
                "formal_events": report["formal_input_counts"]["formal_events"],
                "formal_event_counts": promotion.get("formal_event_counts", {}),
                "formal_facts": report["formal_input_counts"]["formal_facts_after_fact_builder"],
                "state_snapshots": report["formal_input_counts"]["state_snapshots"],
                "evaluation_counts": report["evaluation_counts"],
                "rule_outputs": report["rule_outputs"],
                "abstentions": promotion.get("abstentions", {}),
                "rejected_candidates": promotion.get("rejected_candidates", {}),
                "independent_signal_checks": checks,
                "consistency_problems": len(report["consistency_problems"]),
                "seconds": round(time.perf_counter() - started, 2),
            }
        )
    totals: Counter[str] = Counter()
    checks: dict[str, Counter[str]] = {}
    rules: dict[str, Counter[str]] = {}
    for row in rows:
        for key in ("rounds_segmented", "rounds_confirmed", "formal_events", "formal_facts",
                    "state_snapshots", "consistency_problems"):
            totals[key] += int(row[key])
        totals.update({f"event:{k}": v for k, v in row["formal_event_counts"].items()})
        totals.update({f"label:{k}": v for k, v in row["evaluation_counts"].items()})
        for kind, counts in row["independent_signal_checks"].items():
            checks.setdefault(kind, Counter()).update(counts)
        for rule, counts in row["rule_outputs"].items():
            rules.setdefault(rule, Counter()).update(counts)
    summary = {
        "qualification": "development_only",
        "inputs": len(rows),
        "distinct_sources": len({row["source_id"] for row in rows}),
        "totals": dict(sorted(totals.items())),
        "independent_signal_checks": {k: dict(sorted(v.items())) for k, v in checks.items()},
        "rules_with_output": {k: dict(sorted(v.items())) for k, v in sorted(rules.items())},
        "rows": rows,
    }
    text = json.dumps(summary, ensure_ascii=False, indent=2) + "\n"
    with open(output / "summary_PRIVATE.json", "x", encoding="utf-8",
              opener=lambda p, f: os.open(p, f, 0o600)) as stream:
        stream.write(text)
    with open(output / "summary_PRIVATE.md", "x", encoding="utf-8",
              opener=lambda p, f: os.open(p, f, 0o600)) as stream:
        stream.write(render(summary))
    return summary


def render(summary: dict[str, Any]) -> str:
    lines = [
        "| 入力 | 種別 | Round | 境界確定 | 正式Event | 正式Fact | snapshot | 死亡 "
        "| G/I/U | 開始 正/誤/保留/棄権 | 勝敗 正/誤/保留 | 死亡 正/誤/保留 |",
        "|---|---|---:|---:|---:|---:|---:|---:|---|---|---|---|",
    ]
    for row in summary["rows"]:
        checks = row["independent_signal_checks"]

        def fmt(kind: str, abstained: bool = False, checks: dict[str, Any] = checks) -> str:
            c = checks.get(kind, {})
            parts = [c.get("correct", 0), c.get("false", 0), c.get("undetermined", 0)]
            if abstained:
                parts.append(c.get("abstained", 0))
            return "/".join(str(p) for p in parts)

        labels = row["evaluation_counts"]
        lines.append(
            f"| {row['name']} | {row['input']} | {row['rounds_segmented']} | "
            f"{row['rounds_confirmed']} | {row['formal_events']} | {row['formal_facts']} | "
            f"{row['state_snapshots']} | {row['formal_event_counts'].get('player_death', 0)} | "
            f"{labels['good']}/{labels['improve']}/{labels['unscored']} | "
            f"{fmt('round_start', True)} | {fmt('round_result')} | {fmt('player_death')} |"
        )
    return "\n".join(lines) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--timeline", type=_pair, action="append", default=[])
    parser.add_argument("--replay", type=_pair, action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    inputs = [(n, "timeline", p) for n, p in args.timeline] + [
        (n, "replay", p) for n, p in args.replay
    ]
    if not inputs:
        parser.error("--timeline か --replay を1件以上指定してください")
    summary = measure(inputs, args.output)
    print(json.dumps({k: summary[k] for k in ("inputs", "distinct_sources", "totals",
                                              "independent_signal_checks")},
                     ensure_ascii=False))
    return 1 if summary["totals"].get("consistency_problems") else 0


if __name__ == "__main__":
    raise SystemExit(main())
