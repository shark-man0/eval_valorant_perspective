"""Summarize private one-second Map runs by recording, map and recorder Agent candidate."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from pathlib import Path

from compare_runs import _operable_seconds, _verified_file

from valorant_ai_coach.knowledge import load_game_knowledge
from valorant_ai_coach.temporal.map_timeline_report import load_map_timeline
from valorant_ai_coach.temporal.replay import file_sha, read_json, write_private

MODES = ("standard", "recovered")
_OPERABLE = "operable_seconds_with_current_evidence"
_POSITION = "operable_seconds_with_position"
_TRAJECTORY = "operable_seconds_with_native_edge"
_STAGE_FIELDS = ("direct_stage_counts", "direct_selection_reasons", "portrait_rejection_counts")


def _stage(path, name, expected_sha, timeline_sha):
    if file_sha(path) != expected_sha:
        raise ValueError(f"Map {name} stage disagrees with its receipt")
    report = read_json(path)
    if (report["timeline_sha256"] != timeline_sha or report["qualified"] is not False
            or report["formal_outputs"] != 0):
        raise ValueError("Matching development-only Map stage required")
    return report


def _position_gap_seconds(seconds, reference, adaptive, standard, recovered):
    reference_evidence = reference["comparison_evidence"]
    adaptive_evidence = adaptive["comparison_evidence"]
    operable = set(reference_evidence["operable_sample_refs"])
    if operable != set(adaptive_evidence["operable_sample_refs"]):
        raise ValueError("Position gap analysis requires identical operability evidence")
    shared_rejections = (
        set(reference_evidence["unresolved_portrait_sample_refs"])
        & set(adaptive_evidence["unresolved_portrait_sample_refs"])
    )
    counts = Counter()
    for domain, before, after in zip(
        seconds, standard["second_rows"], recovered["second_rows"], strict=True,
    ):
        if domain["timestamp"] != before["timestamp"] or domain["timestamp"] != after["timestamp"]:
            raise ValueError("Position gap analysis requires identical second clocks")
        refs = set(domain["sample_refs"])
        if not refs or not refs <= operable:
            continue
        had_position = bool(before["recorder_map_observations"])
        has_position = bool(after["recorder_map_observations"])
        counts["added_in_recovery"] += has_position and not had_position
        counts["lost_in_recovery"] += had_position and not has_position
        if not has_position:
            counts["remaining"] += 1
            counts["both_portrait_stages_rejected_all"] += refs <= shared_rejections
    before, after = standard["operable_coverage"], recovered["operable_coverage"]
    if (
        counts["remaining"] != after[_OPERABLE] - after[_POSITION]
        or counts["added_in_recovery"] - counts["lost_in_recovery"]
        != after[_POSITION] - before[_POSITION]
    ):
        raise ValueError("Position gaps disagree with measured operable coverage")
    return dict(counts)


def summarize_recording(
    timeline_path, standard_path, recovered_path, reference_path, adaptive_path,
):
    timeline = read_json(timeline_path)
    timeline_sha = file_sha(timeline_path)
    source = timeline["source"]["source_sha256"]
    standard, recovered = map(read_json, (standard_path, recovered_path))
    reference_sha = standard["reference_report_sha256"]
    if (reference_sha != recovered["reference_report_sha256"]
            or recovered["primary_report_sha256"] != file_sha(standard_path)):
        raise ValueError("Standard and recovered paths must belong to the same Map run")
    eligible = _operable_seconds(reference_path, reference_sha, timeline_sha, timeline)
    stages = {
        "reference": _stage(reference_path, "reference", reference_sha, timeline_sha),
        "adaptive": _stage(adaptive_path, "adaptive", standard["learned_report_sha256"],
                           timeline_sha),
    }
    reference = stages["reference"]
    binding = reference["recording_agent_uuid_binding"]
    if binding is not None and (
        binding["qualified"] is not False or binding["source_sha256"] != source
    ):
        raise ValueError("Matching development-only recorder Agent candidate required")
    metrics = {}
    for mode, path, report in zip(MODES, (standard_path, recovered_path), (standard, recovered),
                                  strict=True):
        summary = load_map_timeline(path, timeline_path, timeline)["summary"]
        coverage = report["operable_coverage"]
        if coverage[_OPERABLE] != len(eligible):
            raise ValueError("Coverage denominator disagrees with operability evidence")
        metrics[mode] = {
            **coverage, "unknown_seconds": summary["unknown_seconds"],
            "selected_seconds": summary["seconds_with_recorder_selection"],
            "support_only_seconds": summary["seconds_with_support_only"],
            "named_zone_seconds": summary["unique_selected_zone_observed_seconds"],
        }
    return {
        "source_sha256": source,
        "map_uuid_candidate": reference["recording_map_uuid"],
        "agent_uuid_candidate": binding["uuid"] if binding is not None else None,
        "timeline_seconds": len(timeline["seconds"]),
        "native_frames": len(timeline["native_frames"]),
        "coverage": metrics,
        "operable_position_gap_seconds": _position_gap_seconds(
            timeline["seconds"], reference, stages["adaptive"], standard, recovered,
        ),
        "replay_stages": {name: {field: stage.get(field, {}) for field in _STAGE_FIELDS}
                          for name, stage in stages.items()},
        "gap_recovery": {"status": recovered.get("recovery_status", "completed"),
                         "counts": recovered["recovery_counts"]},
        "formal_outputs": 0,
    }


def summarize_run(run_path):
    receipt = read_json(run_path)
    if (receipt["schema"] != "development_map_recording_run_v1"
            or receipt["formal_map_outputs"] != 0):
        raise ValueError("Complete development Map run required")
    root = run_path.parent
    timeline = _verified_file(root, receipt, "timeline/timeline_PRIVATE.json")
    standard, recovered = (
        _verified_file(root, receipt, f"map_{mode}_PRIVATE.json") for mode in MODES
    )
    row = summarize_recording(timeline, standard, recovered, root / "map_reference_PRIVATE.json",
                              root / "map_adaptive_PRIVATE.json")
    if row["source_sha256"] != receipt["source_sha256"]:
        raise ValueError("Map run receipt is for a different source")
    return {**row, "run_wall_seconds": receipt["run_wall_seconds"],
            "run_sha256": file_sha(run_path)}


def _aggregate(rows):
    coverage = {}
    for mode in MODES:
        values = [row["coverage"][mode] for row in rows]
        totals = {key: sum(v[key] for v in values) for key in (
            _OPERABLE, _POSITION, _TRAJECTORY, "unknown_seconds", "selected_seconds",
            "support_only_seconds",
        )}
        denominator = totals[_OPERABLE]
        zones = Counter()
        for value in values:
            zones.update(value["named_zone_seconds"])
        coverage[mode] = {
            **totals, "position_rate": totals[_POSITION] / denominator if denominator else None,
            "trajectory_rate": totals[_TRAJECTORY] / denominator if denominator else None,
            "named_zone_seconds": dict(zones),
        }
    stages = {name: {field: Counter() for field in _STAGE_FIELDS}
              for name in ("reference", "adaptive")}
    gap_counts, gap_status, position_gaps = Counter(), Counter(), Counter()
    for row in rows:
        for name, fields in row["replay_stages"].items():
            for field, counts in fields.items():
                stages[name][field].update(counts)
        gap_counts.update(row["gap_recovery"]["counts"])
        gap_status[row["gap_recovery"]["status"]] += 1
        position_gaps.update(row.get("operable_position_gap_seconds", {}))
    return {
        "recordings": len(rows), "native_frames": sum(row["native_frames"] for row in rows),
        "timeline_seconds": sum(row["timeline_seconds"] for row in rows),
        "coverage": coverage, "replay_stages": stages,
        "operable_position_gap_seconds": dict(position_gaps),
        "gap_recovery": {"by_status": gap_status, "counts": gap_counts},
    }


def summarize(rows):
    if not rows or len({row["source_sha256"] for row in rows}) != len(rows):
        raise ValueError("Distinct completed Map recordings required")
    knowledge = load_game_knowledge()
    groups = {}
    for kind, entities in (("map", knowledge.maps), ("agent", knowledge.agents)):
        labels = {entity.uuid: entity.name for entity in entities}
        bucket = defaultdict(list)
        for row in rows:
            bucket[row[f"{kind}_uuid_candidate"] or "UNKNOWN"].append(row)
        groups[f"by_{kind}"] = {key: {"name": labels.get(key, key), **_aggregate(items)}
                                for key, items in sorted(bucket.items())}
    return {
        "schema": "development_map_run_summary_v1", "qualification": "development_only",
        "formal_outputs": 0, "by_recording": rows, **groups, "combined": _aggregate(rows),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True, action="append")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if any((p / ".git").exists() for p in args.output.resolve().parents):
        raise ValueError("Private Map summaries must remain outside Git checkouts")
    write_private(args.output, summarize([summarize_run(path) for path in args.run]))


if __name__ == "__main__":
    main()
