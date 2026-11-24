"""Fill evidenced gaps while preserving the incumbent development Map replay."""

from __future__ import annotations

import argparse
from itertools import groupby
from pathlib import Path

from compare_runs import _operable_seconds

from valorant_ai_coach.temporal.evidence import digest, is_sha, native_time
from valorant_ai_coach.temporal.map_path_quality import measure_path_quality
from valorant_ai_coach.temporal.map_recorder_path import (
    join_recorder_seconds,
    measure_operable_coverage,
    measured_native_edges,
)
from valorant_ai_coach.temporal.map_timeline_report import load_map_timeline
from valorant_ai_coach.temporal.replay import file_sha, read_json, write_private


def merge_recovery_candidates(bundle, incumbent_path, candidate_path, reference_path):
    timeline = read_json(bundle)
    for path in (incumbent_path, candidate_path):
        load_map_timeline(path, bundle, timeline)
    incumbent, candidate = map(read_json, (incumbent_path, candidate_path))
    for name in ("primary_report_sha256", "frame_manifest_sha256", "reference_report_sha256",
                 "zone_catalog_sha256"):
        if not is_sha(incumbent.get(name)) or incumbent[name] != candidate.get(name):
            raise ValueError(f"Recovered inputs must have matching {name}")
    eligible = _operable_seconds(reference_path, incumbent["reference_report_sha256"],
                                 file_sha(bundle), timeline)
    operable = set(read_json(reference_path)["comparison_evidence"]["operable_sample_refs"])
    if any(r["operable_coverage"]["operable_seconds_with_current_evidence"] != len(eligible)
           for r in (incumbent, candidate)):
        raise ValueError("Recovered inputs disagree on exact operability evidence")

    vacancies = {
        key for second, row in zip(timeline["seconds"], incumbent["second_rows"], strict=True)
        if second["timestamp"] in eligible and not row["recorder_map_observations"]
        for key in second["sample_refs"]
    }
    atlases = {(p["map_id"], p["reference_sha256"]) for s in incumbent["segments"] for p in s
               if p["kind"] == "selected"}

    def admissible(point):
        residual = point.get("fit_residual_p95_reference_px")
        key = point["sample"]["sample_sha256"]
        view = timeline["native_frames"][key].get("viewed_identity") or {}
        return (
            key in vacancies and point["kind"] == "selected"
            and point["support_count"] >= 2
            and view.get("agent_signature_relation") != "DIFFERENT"
            and (point["map_id"], point["reference_sha256"]) in atlases
            and not point.get("alignment_recovery")
            and type(residual) in (int, float) and 0 <= residual <= 8
        )

    additions = [list(group) for s in candidate["segments"]
                 for keep, group in groupby(s, key=admissible) if keep]
    evidence = {}
    candidate_sha = file_sha(candidate_path)
    recovery_lineage = candidate.get("recovery_candidate_evidence", {})
    for segment in additions:
        for point in segment:
            key = point["sample"]["sample_sha256"]
            frame = timeline["native_frames"][key]
            point_sha = digest(point)
            lineage = recovery_lineage.get(key)
            if lineage is not None and lineage.get("position_sha256") != point_sha:
                raise ValueError("Recovery evidence must match the exact candidate position")
            evidence[key] = {
                "position_sha256": point_sha,
                "candidate_report_sha256": candidate_sha,
                "lineage": lineage,
                "camera_state": frame["camera"]["value"],
                "life_state": frame["life"]["value"],
                "hud_agent_relation": (frame.get("viewed_identity") or {}).get(
                    "agent_signature_relation", "UNKNOWN",
                ),
                "track_support_count": point["support_count"],
                "alignment_residual_p95_reference_px": point["fit_residual_p95_reference_px"],
            }
    segments = sorted([*incumbent["segments"], *additions],
                      key=lambda segment: native_time(segment[0]["sample"]))
    merged = {**incumbent, "segments": segments}
    rows = join_recorder_seconds(merged, timeline)
    if not measured_native_edges(incumbent) <= measured_native_edges(merged):
        raise ValueError("An incumbent measured edge was lost")
    return {
        **merged, "second_rows": rows,
        "operable_coverage": measure_operable_coverage(merged, timeline["seconds"], rows, operable),
        "path_quality": measure_path_quality(merged, timeline["seconds"], rows, operable),
        "recovery_composition": {
            "incumbent_sha256": file_sha(incumbent_path),
            "candidate_sha256": candidate_sha,
            "added_native_selections": sum(map(len, additions)),
            "added_evidence": evidence,
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("bundle", "incumbent", "candidate", "reference", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    if any((p / ".git").exists() for p in args.output.resolve().parents):
        raise ValueError("Private Map paths must remain outside Git checkouts")
    write_private(args.output, merge_recovery_candidates(
        args.bundle, args.incumbent, args.candidate, args.reference,
    ))


if __name__ == "__main__":
    main()
