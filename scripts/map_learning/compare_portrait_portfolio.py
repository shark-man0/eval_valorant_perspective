"""Measure coverage on a frozen portfolio of paired development Map replays."""

from __future__ import annotations

import argparse
from pathlib import Path

from valorant_ai_coach.temporal.replay import file_sha, read_json, write_private

if __package__:
    from .compare_runs import compare, regression_failures
    from .portrait_cohort import bound_path
else:
    from compare_runs import compare, regression_failures
    from portrait_cohort import bound_path

SCHEMA = "development_map_portrait_comparison_plan_v1"
COUNTS = (
    "operable_seconds_with_current_evidence",
    "operable_seconds_with_position",
    "operable_seconds_with_native_edge",
)


def summarize(rows):
    result = {"recordings": len(rows)}
    for phase in ("before", "after"):
        coverage = {key: sum(row[phase][key] for row in rows) for key in COUNTS}
        operable, position, trajectory = coverage.values()
        result[phase] = {
            **coverage,
            "position_rate": position / operable if operable else None,
            "trajectory_rate": trajectory / operable if operable else None,
        }
    for field in ("portrait_gap_seconds", "portrait_gap_seconds_recovered"):
        result[field] = sum(row[field] for row in rows)
    return result


def compare_portfolio(plan):
    if plan.get("schema") != SCHEMA or plan.get("formal_outputs") != 0:
        raise ValueError("An unqualified development Map comparison plan is required")
    cohort = read_json(bound_path(plan["cohort"]))
    if (cohort.get("schema") != "development_map_portrait_gap_cohort_v1"
            or cohort.get("formal_outputs") != 0):
        raise ValueError("A frozen development portrait cohort is required")
    expected = cohort["recordings"]
    roster = {entry["index"]: entry for entry in plan["recordings"]}
    fixed = plan.get("fixed_indices", [])
    if (not roster or len(roster) != len(plan["recordings"]) or len(roster) != len(expected)
            or roster.keys() != {row["index"] for row in expected}
            or not set(fixed) <= roster.keys() or len(fixed) != len(set(fixed))):
        raise ValueError("The comparison must cover every frozen recording exactly once")

    rows = []
    for freeze in expected:
        index = freeze["index"]
        baseline = bound_path(roster[index]["baseline"])
        candidate = bound_path(roster[index]["candidate"])
        baseline_receipt, candidate_receipt = read_json(baseline), read_json(candidate)
        if any(receipt["source_sha256"] != freeze["source_sha256"]
               for receipt in (baseline_receipt, candidate_receipt)):
            raise ValueError("The recording receipt differs from the frozen source")
        comparison = compare(baseline, candidate)
        coverage = comparison["outputs"]["recovered"]
        if any(coverage["before"][key] != freeze["incumbent"][key] for key in COUNTS):
            raise ValueError("The baseline coverage differs from the frozen cohort")
        recovered_path = candidate.parent / "map_recovered_PRIVATE.json"
        checksum = candidate_receipt["output_sha256s"][recovered_path.name]
        if file_sha(recovered_path) != checksum:
            raise ValueError("The recovered report changed during portfolio comparison")
        gaps = {int(timestamp) for timestamp in freeze["seconds"]}
        filled = {row["timestamp"] for row in read_json(recovered_path)["second_rows"]
                  if row["recorder_map_observations"]}
        rows.append({
            "index": index,
            "learning_split": freeze["learning_split"],
            "before": {key: coverage["before"][key] for key in COUNTS},
            "after": {key: coverage["after"][key] for key in COUNTS},
            "portrait_gap_seconds": len(gaps),
            "portrait_gap_seconds_recovered": len(gaps & filled),
            "regression_failures": regression_failures(comparison),
        })
    return {
        "schema": "development_map_portrait_portfolio_comparison_v1",
        "formal_outputs": 0,
        "all": summarize(rows),
        "fixed": summarize([row for row in rows if row["index"] in fixed]),
        "learning_splits": {
            split: summarize([row for row in rows if row["learning_split"] == split])
            for split in sorted({row["learning_split"] for row in rows})
        },
        "recordings": rows,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = compare_portfolio(read_json(args.plan))
    write_private(args.output, result)
    if any(row["regression_failures"] for row in result["recordings"]):
        raise SystemExit("Map portfolio non-regression gate failed; see the private comparison")


if __name__ == "__main__":
    main()
