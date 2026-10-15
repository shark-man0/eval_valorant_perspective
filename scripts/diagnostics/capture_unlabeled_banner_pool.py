"""Freeze then capture a bounded, source-only development pool; no recognizer.

Cadence/exclusions are fixed before decoding. No OCR, expected state, GT,
reference fitting, lifecycle event or model-based sample selection is run.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from time import perf_counter

import cv2

from scripts.diagnostics.prospective_numeric_probe import verify_partition
from scripts.e2e.frame_replay import decoder_fingerprints
from scripts.e2e.probe_cache import CachedVideoService
from scripts.e2e.run_dataset_case import sha256_file
from valorant_ai_coach.hud.calibrate_temporal import _check_output_privacy
from valorant_ai_coach.video import VideoService


def fixed_times(end, previous):
    values = [end, *previous]
    if any(type(v) not in (int, float) or not math.isfinite(v) or v < 0 for v in values):
        raise ValueError("finite development/history timestamps required")
    times = [1.375 + 3 * i for i in range(math.ceil(end / 3))
             if 1.375 + 3 * i < end and all(abs(1.375 + 3 * i - t) >= .5 for t in previous)]
    if not 8 <= len(times) <= 256:
        raise ValueError("bounded development pool of 8..256 points required")
    return times


def freeze(video, source_sha, partition, histories, output):
    _check_output_privacy(output.resolve())
    if output.exists():
        raise FileExistsError("new frozen source plan required")
    end = json.loads(partition.read_text(encoding="utf-8"))["development"]["end_sec_exclusive"]
    verify_partition(partition, source_sha, end)
    previous, reserved, inputs = [], set(), [partition, Path(__file__)]
    for directory in histories:
        path = directory / "candidate_report.json"
        raw = json.loads(path.read_text(encoding="utf-8"))
        if raw.get("source_sha256") != source_sha:
            raise ValueError("same-source sampling history required")
        inputs.append(path)
        rows = raw.get("training_frames", []) + raw.get("validation_frames", [])
        pool = directory / "review_selection.json"
        if pool.exists():
            inputs.append(pool)
            rows += json.loads(pool.read_text(encoding="utf-8"))["pool_records"]
        for row in rows:
            previous.append(row["source_frame_pts"])
            reserved.add(row["sha256"])
    times = fixed_times(end, previous)
    if sha256_file(video) != source_sha:
        raise ValueError("source SHA mismatch")
    toolchain = decoder_fingerprints(VideoService().ffprobe_path)
    plan = {"kind": "source_only_banner_pool_plan", "source_sha256": source_sha,
            "source_path": str(video.resolve()), "partition_path": str(partition.resolve()),
            "development_end_sec": end, "times": times,
            "sampling_phase_sec": 1.375, "sampling_period_sec": 3,
            "previous_source_pts": sorted(set(previous)),
            "exclusion_radius_sec": .5, "reserved_source_hashes": sorted(reserved),
            "inputs_sha256": {str(p.resolve()): sha256_file(p) for p in inputs},
            "decoder_fingerprints": list(toolchain), "labels_available": False,
            "evaluation_holdout_used": False}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    return plan


def capture(plan_path, output):
    _check_output_privacy(output.resolve())
    if output.exists():
        raise FileExistsError("capture once into a new source directory")
    plan_hash = sha256_file(plan_path)
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    if plan.get("kind") != "source_only_banner_pool_plan":
        raise ValueError("frozen source-only plan required")
    video, partition = Path(plan["source_path"]), Path(plan["partition_path"])
    service = VideoService()

    def verify():
        verify_partition(partition, plan["source_sha256"], plan["development_end_sec"])
        if (sha256_file(plan_path) != plan_hash or sha256_file(video) != plan["source_sha256"]
                or list(decoder_fingerprints(service.ffprobe_path)) != plan["decoder_fingerprints"]
                or any(sha256_file(Path(p)) != h for p, h in plan["inputs_sha256"].items())):
            raise ValueError("frozen source/decoder/plan changed")
    verify()
    times = plan["times"]
    end = plan["development_end_sec"]
    if (plan.get("sampling_phase_sec") != 1.375 or plan.get("sampling_period_sec") != 3
            or plan.get("exclusion_radius_sec") != .5
            or times != fixed_times(end, plan["previous_source_pts"])
            or not 8 <= len(times) <= 256 or len(set(times)) != len(times)
            or times != sorted(times) or any(type(t) not in (int, float)
            or not math.isfinite(t) or not 0 <= t < end for t in times)):
        raise ValueError("bounded fixed development timestamps required")
    started = perf_counter()
    output.mkdir(parents=True)
    cached = CachedVideoService(service, Path("outputs/e2e_cache/probe"),
                                plan["source_sha256"], plan["decoder_fingerprints"][0])
    metadata = cached.probe(video)
    if end > metadata.duration_sec or metadata.fps <= 0:
        raise ValueError("development within valid source duration required")
    frames = cached.extract_frames(video, times, output / "pool_frames",
                                   max_frames=256, max_dimension=None, metadata=metadata)
    if len(frames) != len(times):
        raise ValueError("complete sampled source coverage required")
    records = []
    for frame, requested in zip(frames, times, strict=True):
        image = cv2.imread(str(frame.path))
        if (image is None or image.shape[:2] != (metadata.height, metadata.width)
                or not 0 <= frame.time_sec < end
                or abs(frame.time_sec - requested) > 1 / metadata.fps + 1e-6):
            raise ValueError("sampled source PTS/resolution mismatch")
        records.append({"requested_sec": requested, "source_frame_pts": frame.time_sec,
                        "sha256": sha256_file(frame.path)})
    verify()
    excluded = [i for i, r in enumerate(records) if r["sha256"] in plan["reserved_source_hashes"]]
    selection = {"pool_records": records, "selected_pool_indices": excluded,
                 "method": "fixed_source_only_no_model_selection", "plan_sha256": plan_hash}
    (output / "review_selection.json").write_text(
        json.dumps(selection, indent=2) + "\n", encoding="utf-8")
    report = {"source_sha256": plan["source_sha256"], "plan_sha256": plan_hash,
              "validation_frames": records, "source_only": True,
              "prior_source_hash_overlap": len(excluded),
              "distinct_source_hashes": len({r["sha256"] for r in records}),
              "wall_clock_sec": perf_counter() - started, "ocr_calls": 0,
              "analyzer_calls": 0, "events_generated": 0, "qualification_created": False}
    (output / "candidate_report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)
    plan = sub.add_parser("freeze")
    for name in ("video", "partition", "output"):
        plan.add_argument("--" + name, type=Path, required=True)
    plan.add_argument("--source-sha256", required=True)
    plan.add_argument("--history-dir", type=Path, action="append", default=[])
    measure = sub.add_parser("capture")
    for name in ("plan", "output"):
        measure.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    if args.mode == "freeze":
        result = freeze(args.video, args.source_sha256, args.partition,
                        args.history_dir, args.output)
        print(json.dumps({"frozen_points": len(result["times"]), "decoded_frames": 0}))
    else:
        result = capture(args.plan, args.output)
        print(json.dumps({k: result[k] for k in ("distinct_source_hashes", "ocr_calls",
                                                "analyzer_calls", "wall_clock_sec")}))


if __name__ == "__main__":
    main()
