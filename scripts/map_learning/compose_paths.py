"""Add eligible CNN observations to an exact development Map reference replay."""

from __future__ import annotations

import argparse
import math
from itertools import groupby
from pathlib import Path
from typing import Any

from valorant_ai_coach.temporal.evidence import digest, freeze_native_sample, native_time
from valorant_ai_coach.temporal.map_recorder_path import (
    VERSION,
    _same_run,
    join_recorder_seconds,
    measure_operable_coverage,
)
from valorant_ai_coach.temporal.replay import file_sha, read_json, write_private


def _check_source(report: dict[str, Any], timeline_sha: str) -> tuple[str, str]:
    if (
        report.get("schema") != VERSION
        or report.get("qualified") is not False
        or report.get("formal_outputs") != 0
        or report.get("interpolated_samples") != 0
        or report.get("timeline_sha256") != timeline_sha
    ):
        raise ValueError("Matching unqualified native Map replay required")
    binding = report.get("recording_agent_uuid_binding")
    if not binding or binding.get("qualified") is not False:
        raise ValueError("Recorder Agent binding required")
    return binding["source_sha256"], binding["uuid"]


def _positions(report, timeline_samples, source_sha):
    points = {}
    for segment in report["segments"]:
        for point in segment:
            sample = freeze_native_sample(point["sample"])
            key = sample["sample_sha256"]
            if (
                key not in timeline_samples
                or key in points
                or sample["source_sha256"] != source_sha
                or point.get("qualified") is not False
                or point.get("position_authority") is not False
            ):
                raise ValueError("Exact distinct unqualified recorder sample required")
            points[key] = point
    return points


def _corroborated_links(segments, known, admitted, operable):
    result = []
    for segment in segments:
        for a, b in zip(segment, segment[1:], strict=False):
            ids = tuple(p["sample"]["sample_sha256"] for p in (a, b))
            if not set(ids) <= operable or not _same_run(a, b):
                continue
            a_new, b_new = (key in admitted for key in ids)
            if a_new == b_new:
                continue
            overlap_id = ids[1] if a_new else ids[0]
            overlap = b if a_new else a
            observed = known.get(overlap_id)
            if (observed is None or observed["kind"] != "selected"
                    or overlap["kind"] != "selected"
                    or observed["map_id"] != overlap["map_id"]
                    or observed["reference_sha256"] != overlap["reference_sha256"]):
                continue
            errors = [
                p.get("fit_residual_p95_reference_px") for p in (a, b, observed)
            ]
            if not all(isinstance(error, (int, float)) and 0 <= error <= 8 for error in errors):
                continue
            disagreement = math.dist(observed["map_reference_px"], overlap["map_reference_px"])
            if not disagreement <= 3:
                continue
            result.append({"sample_refs": list(ids), "overlap_sample_ref": overlap_id,
                           "overlap_disagreement_reference_px": disagreement})
    return result


def compose_paths(
    reference, learned, timeline, timeline_sha, *, link_corroborated=False, marker_companion=False,
):
    source, agent = _check_source(reference, timeline_sha)
    if _check_source(learned, timeline_sha) != (source, agent):
        raise ValueError("Recorder identity differs between replays")
    for key in ("frame_manifest_sha256", "map_catalog_fingerprint", "zone_catalog_sha256"):
        if reference[key] != learned[key]:
            raise ValueError(f"Replay inputs differ in {key}")
    if marker_companion:
        first = reference.get("experimental_model_receipts", {})
        second = learned.get("experimental_model_receipts", {})
        if (
            not reference.get("experimental_direct_tracker")
            or not learned.get("experimental_direct_tracker")
            or set(first) != {"marker", "portrait"} or set(second) != set(first)
            or first["portrait"] != second["portrait"] or first["marker"] == second["marker"]
            or reference.get("registration") != learned.get("registration")
        ):
            raise ValueError("Companion replay must change only the marker model receipt")
    elif (reference.get("experimental_direct_tracker")
          or not learned.get("experimental_direct_tracker")):
        raise ValueError("Expected the reference replay and a CNN replay")
    evidence = reference["comparison_evidence"]
    operable = set(evidence["operable_sample_refs"])
    if operable != set(learned["comparison_evidence"]["operable_sample_refs"]):
        raise ValueError("Current recorder-view evidence differs")
    unresolved = set(evidence["unresolved_portrait_sample_refs"])
    samples = {key for row in timeline["seconds"] for key in row["sample_refs"]}
    if not unresolved <= operable <= samples:
        raise ValueError("Recovery candidates lack exact current recorder evidence")
    known = _positions(reference, samples, source)
    candidates = _positions(learned, samples, source)
    map_uuid = reference["recording_map_uuid"]
    textures = {p["reference_sha256"] for p in known.values() if p["map_id"] == map_uuid}
    admitted = {
        key
        for key in unresolved - known.keys()
        if (point := candidates.get(key)) is not None
        and point["kind"] == "selected"
        and (not marker_companion or point["support_count"] >= 2)
        and point["map_id"] == map_uuid
        and point["reference_sha256"] in textures
    }
    additions = []
    for segment in learned["segments"]:
        # Keep the observed links within each CNN segment. An excluded row starts a gap.
        for take, group in groupby(segment, key=lambda p: p["sample"]["sample_sha256"] in admitted):
            if take:
                additions.append(
                    [
                        {**p, "track_anchor": digest(["learned_map_complement", p["track_anchor"]])}
                        for p in group
                    ]
                )
    paths = {
        "schema": VERSION,
        "segments": sorted(
            [*reference["segments"], *additions], key=lambda s: native_time(s[0]["sample"])
        ),
        "interpolated_samples": 0,
        "qualified": False,
        "formal_outputs": 0,
    }
    if link_corroborated:
        paths["corroborated_native_edges"] = _corroborated_links(
            learned["segments"], known, admitted, operable,
        )
    rows = join_recorder_seconds(paths, timeline)
    return {
        **paths,
        "second_rows": rows,
        "operable_coverage": measure_operable_coverage(paths, timeline["seconds"], rows, operable),
        "new_cnn_native_positions": len(admitted),
        "timeline_sha256": timeline_sha,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("reference-path", "learned-path", "bundle-path", "output"):
        parser.add_argument(f"--{field}", type=Path, required=True)
    parser.add_argument("--link-corroborated", action="store_true")
    parser.add_argument("--marker-companion", action="store_true")
    args = parser.parse_args()
    report = compose_paths(
        read_json(args.reference_path),
        read_json(args.learned_path),
        read_json(args.bundle_path),
        file_sha(args.bundle_path),
        link_corroborated=args.link_corroborated,
        marker_companion=args.marker_companion,
    )
    write_private(
        args.output,
        {
            **report,
            "reference_report_sha256": file_sha(args.reference_path),
            "learned_report_sha256": file_sha(args.learned_path),
        },
    )


if __name__ == "__main__":
    main()
