"""Cache #194 self-ring readings on the exact pixels used by a Map development run."""

from __future__ import annotations

import argparse
import hashlib
from collections import Counter
from pathlib import Path

import cv2
import numpy as np

from valorant_ai_coach.recordings.catalog import RecordingCatalog
from valorant_ai_coach.temporal.map_direct_recorder import measured_direct_view
from valorant_ai_coach.temporal.map_recorder_knowledge import KnowledgeRecorderMap
from valorant_ai_coach.temporal.map_self_ring import read_self_ring
from valorant_ai_coach.temporal.map_timeline_report import load_map_timeline
from valorant_ai_coach.temporal.public_map_pixels import PublicMapPixels
from valorant_ai_coach.temporal.replay import file_sha, read_json, write_private

if __package__:
    from .replay_marker_tracks import ContextPixels, acceptable_fit, raw_fit
    from .replay_self_ring import bound
else:
    from replay_marker_tracks import ContextPixels, acceptable_fit, raw_fit
    from replay_self_ring import bound


def measure(args):
    handoff = read_json(args.handoff)
    row = next(r for r in handoff["recordings"] if r["index"] == args.index)
    cat = RecordingCatalog(Path(handoff["catalog"]))
    cat.guard([row["recording_id"]], "development_analysis")
    rec = cat.state.recordings[row["recording_id"]]
    if rec.split != "DEVELOPMENT":
        raise ValueError("Development recordings only")
    timeline_receipt = row["artifacts"]["native_and_second_timeline"]
    timeline, baseline = bound(timeline_receipt), bound(args.baseline)
    if timeline["source"]["source_sha256"] != rec.source_sha256:
        raise ValueError("Timeline source differs from admitted recording")
    bundle = Path(timeline_receipt["path"])
    load_map_timeline(Path(args.baseline["path"]), bundle, timeline)
    reference = bound(row["artifacts"]["reference_replay"])
    context = ContextPixels(args.context, bundle, rec.source_sha256, args.layout)
    knowledge = KnowledgeRecorderMap.load(args.asset_cache, args.map_catalog)
    projector = PublicMapPixels(
        args.map_catalog, args.layout, verified_references=knowledge.map_references
    )
    map_id = reference["recording_map_uuid"]
    projector.references = [r for r in projector.references if r[1] == map_id]
    paths = {
        r["sample"]["sample_sha256"]: Path(r["path"])
        for r in bound(row["artifacts"]["native_frame_manifest"])["frames"]
    }
    gaps = {r["timestamp"] for r in baseline["second_rows"] if not r["recorder_map_observations"]}
    seconds = {s + d for s in gaps for d in (-1, 0, 1)}
    operable = set(reference["comparison_evidence"]["operable_sample_refs"])
    selected = {p["sample"]["sample_sha256"]: p for s in baseline["segments"] for p in s}
    keys = {
        k for s in timeline["seconds"] if s["timestamp"] in seconds for k in s["sample_refs"]
    } & operable
    keys.update(sorted(selected)[:: max(1, len(selected) // 100)][:100])
    native = timeline["native_frames"]
    frames, counts = {}, Counter()
    previous = {}
    if args.previous is not None:
        prior = read_json(args.previous)
        current_context = read_json(args.context)
        parent = current_context.get("restoration", {}).get("parent_context")
        if (
            prior["timeline"] != timeline_receipt
            or prior["baseline"] != args.baseline
            or prior["formal_outputs"] != 0
            or prior["context"]
            not in (parent, {"path": str(args.context), "sha256": file_sha(args.context)})
        ):
            raise ValueError("Previous measurements do not belong to these native inputs")
        previous = prior["frames"]
    for key in sorted(keys, key=lambda k: native[k]["sample"]["native_pts_tick"]):
        if key in previous:
            frames[key] = previous[key]
            counts["reused_exact_readings"] += 1
            continue
        frame = native[key]
        if not measured_direct_view(
            frame, [timeline["observations"][k] for k in frame["observation_ids"]]
        ):
            counts["no_measured_view"] += 1
            continue
        image = context.read(frame["sample"], paths[key], args.pixels, projector.layout)
        if image is None:
            counts["pixels_unavailable"] += 1
            continue
        bounds = projector.layout.normalized_roi("minimap_normal").pixel_bounds(
            image.shape[1], image.shape[0]
        )
        left, top, right, bottom = bounds
        roi = image[top:bottom, left:right]
        ring = read_self_ring(roi, scale=image.shape[1] / 1920)
        entry = {
            "ring": ring,
            "roi_pixel_sha256": hashlib.sha256(roi.tobytes()).hexdigest(),
            "baseline": key in selected,
            "bounds": list(bounds),
        }
        counts["measured"] += 1
        counts[ring["status"]] += 1
        if ring["status"] == "UNIQUE":
            center = [ring["center_roi_px"][0] + left, ring["center_roi_px"][1] + top]
            entry["center_frame_px"] = center
            raw = raw_fit(image, frame["sample"], projector, args.alignment_cache)
            if not acceptable_fit(raw, map_id):
                recovered = projector.recover_contrast(image, raw, map_id, center)
                if acceptable_fit(recovered, map_id):
                    raw = recovered
            entry["fit"] = raw if acceptable_fit(raw, map_id) else None
            if key in selected and entry["fit"]:
                matrix = np.asarray(
                    raw["map_name_candidates"][0]["reference_to_roi_homography_candidate"]
                )
                placed = matrix @ np.array([*selected[key]["map_reference_px"], 1.0])
                entry["baseline_center_roi_px"] = (placed[:2] / placed[2]).tolist()
        frames[key] = entry

    return {
        "schema": "development_exact_ring_comparison_v1",
        "index": args.index,
        "split": rec.learning["split"],
        "timeline": timeline_receipt,
        "baseline": args.baseline,
        "context": {"path": str(args.context), "sha256": file_sha(args.context)},
        "counts": dict(counts),
        "frames": frames,
        "formal_outputs": 0,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in (
        "handoff",
        "baseline",
        "context",
        "layout",
        "asset-cache",
        "map-catalog",
        "pixels",
        "output",
    ):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--alignment-cache", type=Path)
    parser.add_argument(
        "--previous", type=Path, help="Reuse pinned readings after crop restoration"
    )
    parser.add_argument("--index", type=int, required=True)
    args = parser.parse_args()
    args.baseline = read_json(args.baseline)
    cv2.setNumThreads(1)
    result = measure(args)
    write_private(args.output, result)
    print(result["counts"], flush=True)


if __name__ == "__main__":
    main()
