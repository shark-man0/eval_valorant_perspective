"""Freeze a private, recording-balanced review sample before looking at outcomes."""

from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path
from typing import Any

from valorant_ai_coach.temporal.evidence import digest
from valorant_ai_coach.temporal.map_timeline_report import load_map_timeline
from valorant_ai_coach.temporal.replay import file_sha, read_json, write_private

SCHEMA = "development_map_stratified_review_v1"


def _selected(report: Path, bundle: Path, timeline: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        point["sample"]["sample_sha256"]: point
        for row in load_map_timeline(report, bundle, timeline)["rows"]
        for point in row["recorder_map_observations"]
        if point["kind"] == "selected"
    }


def sample_review(
    bundle: Path, standard: Path, recovered: Path, *,
    per_stratum: int, split_view_controls: bool = False,
) -> dict[str, Any]:
    if per_stratum < 1:
        raise ValueError("A positive per-recording stratum budget is required")
    standard_sha = file_sha(standard)
    if read_json(recovered).get("primary_report_sha256") != standard_sha:
        raise ValueError("Recovery must name the matching standard report")
    timeline = read_json(bundle)
    old = _selected(standard, bundle, timeline)
    final = _selected(recovered, bundle, timeline)
    populations: dict[str, dict[int, list[tuple[str, str]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for row in timeline["seconds"]:
        for key in row["sample_refs"]:
            frame = timeline["native_frames"][key]
            camera = frame.get("camera", {}).get("value")
            life = frame.get("life", {}).get("value")
            sample = frame["sample"]
            if camera in {"REMOTE", "SPECTATOR"} or life in {"DEAD", "DOWNED"}:
                if not split_view_controls:
                    stratum = "excluded_view_control"
                elif camera in {"REMOTE", "SPECTATOR"}:
                    stratum = f"{camera.lower()}_view_control"
                else:
                    stratum = "dead_or_downed_control"
            elif camera != "SELF" or life != "ALIVE":
                stratum = "uncertain_view_control"
            elif key in old and key in final:
                stratum = "retained_selection"
            elif key in final:
                stratum = "new_selection"
            elif key in old:
                stratum = "lost_selection"
            else:
                stratum = "abstained"
            priority = digest([
                SCHEMA, sample["source_sha256"], sample["native_time_base"],
                sample["native_pts_tick"], sample["native_pixel_sha256"],
            ])
            populations[stratum][row["timestamp"]].append((priority, key))
    counts, cases = {}, []
    for stratum, seconds in sorted(populations.items()):
        counts[stratum] = {
            "native_observations": sum(len(points) for points in seconds.values()),
            "seconds": len(seconds),
        }
        # Limit adjacent-frame duplication without favouring any acceptance score or location.
        chosen = sorted(min(points) for points in seconds.values())[:per_stratum]
        for priority, key in chosen:
            cases.append((priority, {"sample_sha256": key, "stratum": stratum}))
    return {
        "schema": SCHEMA, "timeline_sha256": file_sha(bundle),
        "standard_sha256": standard_sha, "recovered_sha256": file_sha(recovered),
        "per_stratum": per_stratum, "populations": counts,
        **({"split_view_controls": True} if split_view_controls else {}),
        "cases": [case for _, case in sorted(cases)],
        "qualification": "development_only", "formal_outputs": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("bundle", "standard", "recovered", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--per-stratum", type=int, default=2)
    parser.add_argument("--split-view-controls", action="store_true")
    args = parser.parse_args()
    write_private(
        args.output,
        sample_review(
            args.bundle, args.standard, args.recovered, per_stratum=args.per_stratum,
            split_view_controls=args.split_view_controls,
        ),
    )


if __name__ == "__main__":
    main()
