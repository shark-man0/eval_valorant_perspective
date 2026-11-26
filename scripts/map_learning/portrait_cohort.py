"""Freeze and audit all-portrait-rejected seconds in a development Map handoff."""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

from valorant_ai_coach.temporal.evidence import native_time
from valorant_ai_coach.temporal.replay import file_sha, read_json, write_private

if __package__:
    from .bracket_portraits import _camera, _continuous, load_inputs
else:
    from bracket_portraits import _camera, _continuous, load_inputs

ASSETS = {
    "bundle": "native_and_second_timeline",
    "manifest": "native_frame_manifest",
    "reference": "reference_replay",
    "adaptive": "adaptive_replay",
    "incumbent": "recovered_replay",
}


def bound_path(item):
    path = Path(item["path"])
    if file_sha(path) != item["sha256"]:
        raise ValueError("Handoff artifact digest mismatch")
    return path


def portrait_seconds(timeline, incumbent, reference, adaptive):
    """Freeze the seconds where all source samples received both portrait rejections."""
    rejected = set(reference["comparison_evidence"]["unresolved_portrait_sample_refs"])
    rejected.intersection_update(adaptive["comparison_evidence"]["unresolved_portrait_sample_refs"])
    operable = set(reference["comparison_evidence"]["operable_sample_refs"])
    return {
        row["timestamp"]: tuple(row["sample_refs"])
        for row, current in zip(timeline["seconds"], incumbent["second_rows"], strict=True)
        if row["timestamp"] == current["timestamp"]
        and row["sample_refs"]
        and not current["recorder_map_observations"]
        and set(row["sample_refs"]) <= operable & rejected
    }


def episodes(timeline, operable):
    """Split on native timing, source, observed lifecycle changes and camera witnesses."""
    frames = timeline["native_frames"]
    observations = timeline["observations"]
    episode = []
    view = None
    for key in sorted(frames, key=lambda k: native_time(frames[k]["sample"])):
        frame = frames[key]
        measured = (
            _camera(frame, [observations[i] for i in frame["observation_ids"]])
            if key in operable
            else None
        )
        if episode and (measured != view or not _continuous(frames[episode[-1]], frame)):
            yield view, tuple(episode)
            episode.clear()
        if measured is not None:
            episode.append(key)
        view = measured
    if episode:
        yield view, tuple(episode)


def audit_recording(args, row):
    timeline, reference, adaptive, incumbent, operable, _, paths, rec = load_inputs(args)
    if rec.learning.get("split") != row["learning_split"]:
        raise ValueError("Recording learning split differs from the handoff")
    seconds = portrait_seconds(timeline, incumbent, reference, adaptive)
    if len(seconds) != row["operable_position_gap_seconds"]["both_portrait_stages_rejected_all"]:
        raise ValueError("Portrait gap cohort differs from the frozen handoff")
    targets = {key: second for second, refs in seconds.items() for key in refs}
    points = {p["sample"]["sample_sha256"]: p for seg in incumbent["segments"] for p in seg}
    anchors = {
        key
        for key, point in points.items()
        if point["kind"] == "selected"
        and not point.get("alignment_recovery")
        and not point.get("portrait_anchor_sample_refs")
    }
    native = timeline["native_frames"]
    groups = []
    for _, episode in episodes(timeline, operable):
        missing = [key for key in episode if key in targets]
        if not missing:
            continue
        anchor_keys = [key for key in episode if key in anchors]
        groups.append({"samples": missing, "episode_anchors": anchor_keys})
    return {
        "index": row["index"],
        "learning_split": row["learning_split"],
        "source_sha256": rec.source_sha256,
        "seconds": seconds,
        "episodes": groups,
        "native_targets": len(targets),
        "cached_targets": sum(paths[key].is_file() for key in targets),
        "target_seconds_with_lifecycle_and_anchor": len(
            {
                targets[key]
                for group in groups
                if group["episode_anchors"]
                for key in group["samples"]
            }
        ),
        "target_seconds_with_lifecycle": len(
            {targets[key] for group in groups for key in group["samples"]}
        ),
        "incumbent": incumbent["operable_coverage"],
        "frame_assets": {
            key: {"sample": native[key]["sample"], "path": str(paths[key])}
            for key in targets | dict.fromkeys(anchors)
        },
    }


def audit_handoff(path, output):
    handoff = read_json(path)
    if handoff["formal_outputs"] != 0 or handoff["qualification"] != "development_only":
        raise ValueError("An unqualified development handoff is required")
    seen = set()
    result = []
    for row in handoff["recordings"]:
        if row["physical_match_id"] in seen:
            raise ValueError("Repeated physical match in the handoff")
        seen.add(row["physical_match_id"])
        args = SimpleNamespace(
            recording_catalog=Path(handoff["catalog"]),
            recording_id=row["recording_id"],
            **{key: bound_path(row["artifacts"][name]) for key, name in ASSETS.items()},
        )
        result.append(audit_recording(args, row))
        current = result[-1]
        print(
            current["index"],
            len(current["seconds"]),
            current["native_targets"],
            current["cached_targets"],
            current["target_seconds_with_lifecycle_and_anchor"],
            flush=True,
        )
    totals = Counter()
    for row in result:
        totals["target_seconds"] += len(row["seconds"])
        totals.update(
            {
                name: row[name]
                for name in (
                    "native_targets",
                    "cached_targets",
                    "target_seconds_with_lifecycle_and_anchor",
                    "target_seconds_with_lifecycle",
                )
            }
        )
    write_private(
        output,
        {
            "schema": "development_map_portrait_gap_cohort_v1",
            "formal_outputs": 0,
            "handoff_sha256": file_sha(path),
            "counts": dict(totals),
            "recordings": result,
        },
    )
    print(dict(totals), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--handoff", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    audit_handoff(args.handoff, args.output)


if __name__ == "__main__":
    main()
