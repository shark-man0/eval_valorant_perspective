"""Print the 44-rule readiness table (before/after) as Markdown.

    PYTHONPATH=src python3 scripts/rules/rule_coverage_report.py [--occurrences REPORT.json]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from valorant_ai_coach.rules.coverage import blocker_ranking, coverage, summarize

MARK = {"none": "なし", "contract": "契約のみ", "development": "開発観測", "qualified": "認定"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--occurrences", type=Path)
    args = parser.parse_args()
    report = json.loads(args.occurrences.read_text("utf-8")) if args.occurrences else None
    before = {r.rule_id: r for r in coverage("before")}
    after = coverage("after")
    header = ("| ルール | 項目 | 判定方式 | 変更前 | 変更後 | 実動画の候補（試合数） "
              "| 残る阻害要因 |")
    lines = [header, "|---|---|---|---|---|---|---|"]
    for row in after:
        old = before[row.rule_id].readiness
        mark = MARK[row.readiness] + (" 🟢" if row.readiness != old else "")
        seen = ""
        if report:
            seen = str(report["rule_matches_with_candidates"].get(row.rule_id, 0))
        blockers = ", ".join(row.blocking) or "-"
        lines.append(f"| {row.rule_id} | {row.item} | {row.label_mode} | {MARK[old]} | {mark} "
                     f"| {seen} | {blockers} |")
    print("\n".join(lines))
    print()
    print("before:", summarize(coverage("before")))
    print("after:", summarize(after))
    print("blockers:", blocker_ranking(after)[:10])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
