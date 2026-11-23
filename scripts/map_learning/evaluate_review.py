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


def evaluate(bundle: Path, report: Path, review: Path) -> dict[str, Any]:
    timeline, labels = read_json(bundle), read_json(review)
    if (labels["schema"] != "development_map_independent_review_v1"
            or labels["timeline_sha256"] != file_sha(bundle)
            or labels["reviewer"] not in {"HUMAN", "AI_VISUAL"}):
        raise ValueError("Exact development review provenance required")
    paths = load_map_timeline(report, bundle, timeline)
    selected = {p["sample"]["sample_sha256"]: p
                for row in paths["rows"] for p in row["recorder_map_observations"]
                if p["kind"] == "selected"}
    seen = set()
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    errors: list[float] = []
    for case in labels["cases"]:
        key, view, role = (case[k] for k in ("sample_sha256", "view", "candidate_role"))
        if key in seen or key not in timeline["native_frames"] or view not in _VIEWS:
            raise ValueError("Unique review of a known native frame required")
        if role not in _ROLES:
            raise ValueError("Unknown independent role label")
        seen.add(key)
        point = selected.get(key)
        if point is None:
            counts[view]["abstained"] += 1
            if view in {"REMOTE", "SPECTATOR", "DEAD"}:
                counts[view]["rejected_excluded_view"] += 1
            continue
        if view in {"REMOTE", "SPECTATOR", "DEAD"}:
            counts[view]["selection_in_excluded_view"] += 1
        if case.get("candidate_sha256") != digest(point) or role == "UNKNOWN":
            counts[view]["unreviewed_selection"] += 1
            continue
        counts[view]["correct_role" if role == "SELF" else "wrong_role"] += 1
        truth = case.get("independent_atlas_px")
        if truth is None or role != "SELF":
            continue
        if (case.get("reference_sha256") != point["reference_sha256"]
                or not isinstance(truth, list) or len(truth) != 2
                or any(type(x) not in (int, float) or not math.isfinite(x) or x < 0
                       for x in truth)):
            raise ValueError("Position review must use the same exact map reference")
        errors.append(math.dist(point["map_reference_px"], truth))
    correct = sum(values["correct_role"] for values in counts.values())
    wrong = sum(values["wrong_role"] for values in counts.values())
    role_total = correct + wrong
    return {
        "reviewer": labels["reviewer"], "review_cases": len(seen),
        "by_view": {view: dict(result) for view, result in counts.items()},
        "role_confirmed_selections": role_total,
        "reviewed_selection_correct_rate": correct / role_total if role_total else None,
        "reviewed_selection_error_rate": wrong / role_total if role_total else None,
        "atlas_error_reference_px": {
            "count": len(errors), "median": statistics.median(errors) if errors else None,
            "min": min(errors, default=None), "max": max(errors, default=None),
        },
        "qualified": False, "formal_outputs": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("bundle", "report", "review", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    write_private(args.output, evaluate(args.bundle, args.report, args.review))


if __name__ == "__main__":
    main()
