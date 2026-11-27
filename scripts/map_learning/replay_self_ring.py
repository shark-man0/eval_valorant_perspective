"""Replay the unchanged #194 reader on frozen Map inputs and append corroborated runs.

Measurement files and outputs are private development artifacts. The measurement
receipt is a cache of observations, never independent identity ground truth.
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import cv2
import numpy as np

from valorant_ai_coach.recordings.catalog import RecordingCatalog
from valorant_ai_coach.temporal.map_recorder_knowledge import KnowledgeRecorderMap
from valorant_ai_coach.temporal.map_reference_support import atlas_distances_for
from valorant_ai_coach.temporal.map_self_ring import RingParameters
from valorant_ai_coach.temporal.map_timeline_report import load_map_timeline
from valorant_ai_coach.temporal.replay import file_sha, read_json, write_private

if __package__:
    from .replay_marker_tracks import _read
    from .ring_complement import complement
else:
    from replay_marker_tracks import _read
    from ring_complement import complement


def bound(receipt):
    path = Path(receipt["path"])
    if file_sha(path) != receipt["sha256"]:
        raise ValueError("Pinned development input changed")
    return read_json(path)


def replay(args):
    handoff = read_json(args.handoff)
    row = next(r for r in handoff["recordings"] if r["index"] == args.index)
    catalog = RecordingCatalog(Path(handoff["catalog"]))
    catalog.guard([row["recording_id"]], "development_analysis")
    rec = catalog.state.recordings[row["recording_id"]]
    if rec.split != "DEVELOPMENT":
        raise ValueError("Development recordings only")
    cache = read_json(args.measurements)
    if (
        cache["schema"] != "development_exact_ring_comparison_v1"
        or cache["formal_outputs"] != 0
        or cache["split"] != rec.learning["split"]
        or cache["index"] != args.index
        or cache["timeline"] != row["artifacts"]["native_and_second_timeline"]
    ):
        raise ValueError("Measurement cache belongs to another experiment")
    timeline, baseline, context = [bound(cache[key]) for key in ("timeline", "baseline", "context")]
    if timeline["source"]["source_sha256"] != rec.source_sha256:
        raise ValueError("Timeline source differs from the admitted recording")
    load_map_timeline(Path(cache["baseline"]["path"]), Path(cache["timeline"]["path"]), timeline)
    if (
        context["source_sha256"] != rec.source_sha256
        or context["timeline_sha256"] != cache["timeline"]["sha256"]
        or context["layout_sha256"] != file_sha(args.layout)
        or context["formal_outputs"] != 0
    ):
        raise ValueError("Context differs from the native recording")
    root = Path(cache["context"]["path"]).resolve().parent
    paths = {
        r["sample"]["sample_sha256"]: Path(r["path"])
        for r in bound(row["artifacts"]["native_frame_manifest"])["frames"]
    }
    expected_parameters = RingParameters().fingerprint()
    # Only a hash-verified crop from the original native acquisition may supply
    # a new point. No padded image is represented as a complete native frame.
    for key, measurement in cache["frames"].items():
        if measurement["ring"]["status"] != "UNIQUE":
            continue
        if measurement["ring"]["parameters_sha256"] != expected_parameters:
            raise ValueError("Self-ring parameters changed")
        frame = timeline["native_frames"][key]
        receipt = context["frames"].get(key)
        if receipt is None:
            image = _read(frame["sample"], paths[key], args.pixels)
            if image is None:
                raise ValueError("An exact original crop or full frame is required")
            left, top, right, bottom = context["bounds"]
            crop = image[top:bottom, left:right]
        else:
            path = (root / receipt["file"]).resolve()
            if (
                path.parent != root
                or file_sha(path) != receipt["crop_sha256"]
                or receipt["native_pixel_sha256"] != frame["sample"]["native_pixel_sha256"]
            ):
                raise ValueError("Original crop changed")
            crop = cv2.imdecode(np.frombuffer(path.read_bytes(), np.uint8), cv2.IMREAD_COLOR)
        if (
            crop is None
            or hashlib.sha256(crop.tobytes()).hexdigest() != measurement["roi_pixel_sha256"]
        ):
            raise ValueError("Ring and crop pixels differ")
        left, top, right, bottom = context["bounds"]
        if (
            measurement["bounds"] != context["bounds"]
            or crop.shape[:2] != (bottom - top, right - left)
            or measurement["center_frame_px"]
            != [
                measurement["ring"]["center_roi_px"][0] + left,
                measurement["ring"]["center_roi_px"][1] + top,
            ]
        ):
            raise ValueError("Ring coordinates differ from the native crop")
    reference = bound(row["artifacts"]["reference_replay"])
    knowledge = KnowledgeRecorderMap.load(args.asset_cache, args.map_catalog)
    map_id = reference["recording_map_uuid"]
    sha = next(
        p["reference_sha256"] for s in baseline["segments"] for p in s if p["map_id"] == map_id
    )
    atlas = atlas_distances_for(args.map_catalog, map_id, sha, knowledge.map_references)
    if atlas is None:
        raise ValueError("A verified floor mask is required for complementary ring readings")
    result = complement(
        timeline,
        baseline,
        cache["frames"],
        map_id=map_id,
        reference_sha256=sha,
        atlas_distances=atlas,
        operable=set(reference["comparison_evidence"]["operable_sample_refs"]),
        receipt_sha256=file_sha(args.measurements),
    )
    result["ring_complement"].update(
        baseline_sha256=cache["baseline"]["sha256"],
        split=rec.learning["split"],
        code_sha256s={
            name: file_sha(Path(__file__).with_name(name))
            for name in ("replay_self_ring.py", "ring_complement.py")
        },
        ring_parameters_sha256=expected_parameters,
    )
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in (
        "handoff",
        "measurements",
        "asset-cache",
        "map-catalog",
        "layout",
        "pixels",
        "output",
    ):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--index", type=int, required=True)
    args = parser.parse_args()
    cv2.setNumThreads(1)
    report = replay(args)
    write_private(args.output, report)
    print(report["ring_complement"]["counts"], flush=True)


if __name__ == "__main__":
    main()
