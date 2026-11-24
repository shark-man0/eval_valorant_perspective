"""Compare completed development Map runs on identical native pixels and clocks."""

from __future__ import annotations

import argparse
import math
from pathlib import Path

from valorant_ai_coach.temporal.map_timeline_report import load_map_timeline
from valorant_ai_coach.temporal.replay import file_sha, read_json, write_private


def _verified_file(base: Path, receipt, name: str) -> Path:
    path = base / name
    if file_sha(path) != receipt["output_sha256s"][name]:
        raise ValueError(f"Completed Map artifact changed: {name}")
    return path


def _native_key(point):
    sample = point["sample"]
    return sample["native_time_base"], sample["native_pts_tick"]


def _native_observations(rows):
    selected = {}
    links = set()
    for row in rows:
        selected.update({
            _native_key(p): p for p in row["recorder_map_observations"]
            if p["kind"] == "selected"
        })
        links.update(tuple(_native_key(p) for p in pair)
                     for pair in row["native_edges_ending_here"])
    return selected, links


def compare(baseline: Path, candidate: Path):
    manifests = []
    modes = ("standard", "recovered")
    for run in (baseline, candidate):
        receipt = read_json(run)
        if (receipt["schema"] != "development_map_recording_run_v1"
                or receipt["formal_map_outputs"] != 0):
            raise ValueError("Complete development Map run required")
        path = _verified_file(run.parent, receipt, "timeline/timeline_PRIVATE.json")
        timeline = read_json(path)
        native = [v["sample"] for v in timeline["native_frames"].values()]
        clock = tuple((s["source_sha256"], s["native_time_base"], s["native_pts_tick"],
                       s["native_pixel_sha256"]) for s in native)
        reports = {}
        for mode in modes:
            report = _verified_file(run.parent, receipt, f"map_{mode}_PRIVATE.json")
            rows = load_map_timeline(report, path, timeline)["rows"]
            reports[mode] = (read_json(report)["operable_coverage"], rows)
        manifests.append((receipt["source_sha256"], clock, reports))
    (old_source, old_clock, old), (new_source, new_clock, new) = manifests
    if old_source != new_source or not old_clock or old_clock != new_clock:
        raise ValueError("Regression comparison requires the same source, native PTS and pixels")
    result = {}
    for mode in modes:
        (before, a), (after, b) = old[mode], new[mode]
        lost = gained = 0
        for first, second in zip(a, b, strict=True):
            if first["timestamp"] != second["timestamp"]:
                raise ValueError("Comparison seconds differ")
            x, y = [bool(row["recorder_map_observations"]) for row in (first, second)]
            lost += x and not y
            gained += y and not x
        old_points, old_links = _native_observations(a)
        new_points, new_links = _native_observations(b)
        same_reference_drifts = []
        reference_changes = zone_changes = 0
        for key in old_points.keys() & new_points.keys():
            left, right = old_points[key], new_points[key]
            if (left["map_id"], left["reference_sha256"]) != (
                right["map_id"], right["reference_sha256"],
            ):
                reference_changes += 1
                continue
            same_reference_drifts.append(
                math.dist(left["map_reference_px"], right["map_reference_px"])
            )
            zone_changes += left.get("zone_candidate") != right.get("zone_candidate")
        result[mode] = {
            "before": before, "after": after,
            "seconds_with_new_observations": gained, "seconds_with_lost_observations": lost,
            "native_selections_gained": len(new_points.keys() - old_points.keys()),
            "native_selections_lost": len(old_points.keys() - new_points.keys()),
            "native_edges_gained": len(new_links - old_links),
            "native_edges_lost": len(old_links - new_links),
            "changed_map_references": reference_changes, "changed_zone_candidates": zone_changes,
            "compared_positions_on_same_reference": len(same_reference_drifts),
            "max_position_change_reference_px": max(same_reference_drifts, default=None),
        }
    return {"native_observations": len(old_clock), "exact_native_input_match": True,
            "outputs": result, "formal_outputs": 0}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("baseline", "candidate", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    write_private(args.output, compare(args.baseline, args.candidate))


if __name__ == "__main__":
    main()
