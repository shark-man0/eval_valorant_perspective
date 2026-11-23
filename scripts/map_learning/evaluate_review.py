"""Score private independent reviews of exact development Map selections."""

from __future__ import annotations

import argparse
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from valorant_ai_coach.temporal.evidence import digest
from valorant_ai_coach.temporal.map_timeline_report import load_map_timeline
from valorant_ai_coach.temporal.replay import file_sha, read_json, write_private

_VIEWS = {"SELF_LIVE", "REMOTE", "SPECTATOR", "DEAD", "UNKNOWN"}
_ROLES = {"SELF", "OTHER", "UNKNOWN"}


def evaluate(
    bundle: Path, report: Path, review: Path, *, sample_plan: Path | None = None,
) -> dict[str, Any]:
    timeline, labels = read_json(bundle), read_json(review)
    if (labels["schema"] != "development_map_independent_review_v1"
            or labels["timeline_sha256"] != file_sha(bundle)
            or labels["reviewer"] not in {"HUMAN", "AI_VISUAL"}):
        raise ValueError("Exact development review provenance required")
    cohorts: dict[str, str] = {}
    if sample_plan is not None:
        plan = read_json(sample_plan)
        if (
            plan["schema"] != "development_map_stratified_review_v1"
            or plan["timeline_sha256"] != labels["timeline_sha256"]
            or file_sha(report) not in (plan["standard_sha256"], plan["recovered_sha256"])
            or labels.get("sample_plan_sha256") != file_sha(sample_plan)
        ):
            raise ValueError("Review must use the exact frozen sample plan")
        cohorts = {case["sample_sha256"]: case["stratum"] for case in plan["cases"]}
        if len(cohorts) != len(plan["cases"]):
            raise ValueError("Duplicate frame in the sample plan")
    paths = load_map_timeline(report, bundle, timeline)
    selected = {p["sample"]["sample_sha256"]: p
                for row in paths["rows"] for p in row["recorder_map_observations"]
                if p["kind"] == "selected"}
    seen = set()
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    by_cohort: dict[str, Counter[str]] = defaultdict(Counter)
    errors: list[float] = []
    cohort_errors: dict[str, list[float]] = defaultdict(list)
    for case in labels["cases"]:
        key, view, role = (case[k] for k in ("sample_sha256", "view", "candidate_role"))
        if key in seen or key not in timeline["native_frames"] or view not in _VIEWS:
            raise ValueError("Unique review of a known native frame required")
        if role not in _ROLES:
            raise ValueError("Unknown independent role label")
        if sample_plan is not None and key not in cohorts:
            raise ValueError("Reviewed frame is outside the frozen sample")
        seen.add(key)
        view_counts = counts[view]
        cohort = cohorts.get(key, "unstratified")
        cohort_counts = by_cohort[cohort]
        case_counts = Counter(observations=1)
        point = selected.get(key)
        excluded = view in {"REMOTE", "SPECTATOR", "DEAD"}
        if point is None:
            case_counts["abstained"] += 1
            if excluded:
                case_counts["rejected_excluded_view"] += 1
        else:
            case_counts["selected"] += 1
            if excluded:
                case_counts["selection_in_excluded_view"] += 1
            if case.get("candidate_sha256") != digest(point) or role == "UNKNOWN":
                case_counts["unreviewed_selection"] += 1
            else:
                case_counts["correct_role" if role == "SELF" else "wrong_role"] += 1
                truth = case.get("independent_atlas_px")
                if truth is not None and role == "SELF":
                    if (case.get("reference_sha256") != point["reference_sha256"]
                            or not isinstance(truth, list) or len(truth) != 2
                            or any(type(x) not in (int, float) or not math.isfinite(x) or x < 0
                                   for x in truth)):
                        raise ValueError("Position review must use the same exact map reference")
                    error = math.dist(point["map_reference_px"], truth)
                    errors.append(error)
                    cohort_errors[cohort].append(error)
        view_counts.update(case_counts)
        cohort_counts.update(case_counts)
    correct = sum(values["correct_role"] for values in counts.values())
    wrong = sum(values["wrong_role"] for values in counts.values())
    role_total = correct + wrong
    abstained = sum(values["abstained"] for values in counts.values())
    planned = Counter(cohorts.values())
    return {
        "reviewer": labels["reviewer"], "review_cases": len(seen),
        "by_view": {view: dict(result) for view, result in counts.items()},
        "by_stratum": {
            name: {
                **by_cohort[name], "planned": planned.get(name),
                "atlas_error_reference_px": _error_summary(cohort_errors[name]),
            }
            for name in sorted(planned.keys() | by_cohort.keys())
        },
        "abstained": abstained,
        "review_sample_abstention_rate": abstained / len(seen) if seen else None,
        "role_confirmed_selections": role_total,
        "reviewed_selection_correct_rate": correct / role_total if role_total else None,
        "reviewed_selection_error_rate": wrong / role_total if role_total else None,
        "atlas_error_reference_px": _error_summary(errors),
        "qualified": False, "formal_outputs": 0,
    }


def _error_summary(errors: list[float]) -> dict[str, int | float | None]:
    return {
        "count": len(errors), "median": statistics.median(errors) if errors else None,
        "min": min(errors, default=None), "max": max(errors, default=None),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("bundle", "report", "review", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--sample-plan", type=Path)
    args = parser.parse_args()
    write_private(args.output, evaluate(
        args.bundle, args.report, args.review, sample_plan=args.sample_plan,
    ))


if __name__ == "__main__":
    main()
