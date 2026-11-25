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

from valorant_ai_coach.application.timeline_evaluation import load_bundle, openai_coach, run
from valorant_ai_coach.facts.second_feature_promotion import records_source_sha256

# One input per recording: a full HUD bundle beats a replay projection.
_KIND_PRIORITY = {"timeline": 0, "replay": 1}


def deduplicate(
    inputs: Sequence[tuple[str, str, Path]],
) -> tuple[list[tuple[str, str, Path, str]], list[dict[str, str]]]:
    """Keep one input per source SHA-256 so no recording is counted twice."""
    keyed: dict[str, tuple[str, str, Path, str]] = {}
    skipped: list[dict[str, str]] = []
    for name, kind, path in inputs:
        sha = str((load_bundle(path if kind == "timeline" else None,
                               path if kind == "replay" else None).get("source") or {})
                  .get("source_sha256"))
        current = keyed.get(sha)
        if current is None or _KIND_PRIORITY[kind] < _KIND_PRIORITY[current[1]]:
            if current is not None:
                skipped.append({"name": current[0], "kept": name, "source_sha256": sha})
            keyed[sha] = (name, kind, path, sha)
        else:
            skipped.append({"name": name, "kept": current[0], "source_sha256": sha})
    return list(keyed.values()), skipped


def _pair(text: str) -> tuple[str, Path]:
    name, _, path = text.partition("=")
    if not name or not path:
        raise argparse.ArgumentTypeError("NAME=PATH の形式で指定してください")
    return name, Path(path)


def _motion_sha(path: Path) -> str | None:
    """Source video SHA-256 of a #169 row file (first row's native sample)."""
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                return (json.loads(line).get("sample") or {}).get("source_sha256")
    return None


def measure(
    inputs: Sequence[tuple[str, str, Path]], output: Path,
    features: Sequence[Path] = (), catalog: Path | None = None,
    coach_model: str | None = None, motion: Sequence[Path] = (), ammo: Sequence[Path] = (),
) -> dict[str, Any]:
    """``coach_model`` runs the OpenAI coach (API key required); otherwise the offline
    coach, whose GOOD/IMPROVE are never formal (only Rule Engine decisions are)."""
    output.mkdir(parents=True, mode=0o700)
    unique, skipped = deduplicate(inputs)
    by_sha = {str(records_source_sha256(path)): path for path in features}
    motion_by_sha = {_motion_sha(path): path for path in motion}
    ammo_by_sha = {_motion_sha(path): path for path in ammo}
    rows: list[dict[str, Any]] = []
    for name, kind, path, sha in unique:
        started = time.perf_counter()
        report = run(
            timeline_path=path if kind == "timeline" else None,
            replay_path=path if kind == "replay" else None,
            output=output / name,
            match_id=f"DEV-{name}",
            database=output / f"{name}.db",
            second_features_path=by_sha.get(sha),
            engagement_motion_path=motion_by_sha.get(sha),
            ammo_path=ammo_by_sha.get(sha),
            coach=None if coach_model is None else openai_coach(coach_model),
        )
        feature = report.get("second_feature_promotion") or {}
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
                "second_features": None if not feature else {
                    "recorder_agent": feature["recorder_agent"],
                    "side_status": feature["side_status"],
                    "counts": feature["counts"],
                    "rejected": feature["rejected"],
                    "cross_reader_checks": feature["cross_reader_checks"],
                },
                "result_tiers": report["result_tiers"],
                "scorability": report["scorability"]["totals"],
                "scorability_per_rule": report["scorability"]["per_rule"],
                "consistency_problems": len(report["consistency_problems"]),
                "seconds": round(time.perf_counter() - started, 2),
            }
        )
    totals: Counter[str] = Counter()
    checks: dict[str, Counter[str]] = {}
    rules: dict[str, Counter[str]] = {}
    ready: dict[str, Counter[str]] = {}
    for row in rows:
        for rule, counts in row["scorability_per_rule"].items():
            ready.setdefault(rule, Counter()).update(counts)
        feature = row["second_features"] or {}
        totals.update({f"feature:{k}": v for k, v in feature.get("counts", {}).items()})
        for kind, counts in feature.get("cross_reader_checks", {}).items():
            checks.setdefault(f"feature:{kind}", Counter()).update(counts)
        for key in ("rounds_segmented", "rounds_confirmed", "formal_events", "formal_facts",
                    "state_snapshots", "consistency_problems"):
            totals[key] += int(row[key])
        for tier, counts in row["result_tiers"].items():
            totals.update({f"tier:{tier}:{k}": v for k, v in counts.items()})
        totals.update({f"event:{k}": v for k, v in row["formal_event_counts"].items()})
        totals.update({f"label:{k}": v for k, v in row["evaluation_counts"].items()})
        for kind, counts in row["independent_signal_checks"].items():
            checks.setdefault(kind, Counter()).update(counts)
        for rule, counts in row["rule_outputs"].items():
            rules.setdefault(rule, Counter()).update(counts)
    covered = {sha for *_, sha in unique}
    without_timeline: list[str] = []
    if catalog is not None:
        recordings = json.loads(catalog.read_text(encoding="utf-8"))["recordings"]
        without_timeline = sorted(
            r["recording_id"] for r in recordings if r["source_sha256"] not in covered
        )
    summary = {
        "qualification": "development_only",
        # Labels are AI-coach results only when the API ran; otherwise GOOD/IMPROVE
        # come from the deterministic Rule Engine alone.
        "coach": "openai:" + coach_model if coach_model else "offline_no_api",
        "inputs": len(rows),
        "distinct_sources": len({row["source_id"] for row in rows}),
        "duplicates_skipped": skipped,
        "recordings_without_timeline": without_timeline,
        "scorability_per_rule": {k: dict(sorted(v.items())) for k, v in sorted(ready.items())},
        "rules_ready_for_api": sorted(r for r, c in ready.items() if c.get("ready_for_api")),
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
    parser.add_argument("--ammo", type=Path, action="append", default=[],
                        help="#169 --ammo-only の出力（SHA-256で自動対応）")
    parser.add_argument("--motion", type=Path, action="append", default=[],
                        help="#169 extract_engagement_motion.py の出力（SHA-256で自動対応）")
    parser.add_argument("--features", type=Path, action="append", default=[],
                        help="extract_second_features.py の出力（SHA-256で自動対応）")
    parser.add_argument("--catalog", type=Path, help="録画カタログ（タイムライン未作成の一覧用）")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--coach-model", help="指定するとOpenAI APIで採点する（APIキーが必要）")
    args = parser.parse_args(argv)
    inputs = [(n, "timeline", p) for n, p in args.timeline] + [
        (n, "replay", p) for n, p in args.replay
    ]
    if not inputs:
        parser.error("--timeline か --replay を1件以上指定してください")
    summary = measure(inputs, args.output, args.features, args.catalog, args.coach_model,
                      args.motion, args.ammo)
    print(json.dumps({k: summary[k] for k in ("coach", "inputs", "distinct_sources", "totals",
                                              "independent_signal_checks",
                                              "rules_ready_for_api")},
                     ensure_ascii=False))
    return 1 if summary["totals"].get("consistency_problems") else 0


if __name__ == "__main__":
    raise SystemExit(main())
