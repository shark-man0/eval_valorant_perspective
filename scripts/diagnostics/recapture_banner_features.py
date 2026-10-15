"""Recapture feature-selected development images with decoder identities.

Retained JPEG filenames are selection hints only, never recovered exact PTS.
This diagnostic does not use GT, assign semantics or qualify temporal events.
"""
from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path

import cv2

from scripts.diagnostics.discover_banner_references import text_rows
from scripts.diagnostics.prospective_numeric_probe import verify_partition
from scripts.e2e.frame_replay import decoder_fingerprints
from scripts.e2e.probe_cache import CachedVideoService
from scripts.e2e.run_dataset_case import sha256_file
from valorant_ai_coach.hud.calibrate_temporal import _check_output_privacy
from valorant_ai_coach.hud.layout import HudLayout
from valorant_ai_coach.video import VideoService


def select(root, layout, end, top, height):
    """Filter development filenames before opening any pixels; no GT input."""
    if (type(end) not in (int, float) or not math.isfinite(end) or end <= .001
            or type(top) is not int or type(height) is not int
            or top < 0 or height <= 0 or top % 10 or height % 10):
        raise ValueError("finite development bound and explicit ten-pixel feature bins required")
    root = root.resolve()
    paths = []
    for path in root.rglob("*.jpg"):
        match = re.fullmatch(r"frame_\d+_(\d+\.\d{3})\.jpg", path.name)
        if match and 0 <= float(match[1]) < end - .001:
            if not path.resolve().is_relative_to(root):
                raise ValueError("retained image escapes source directory")
            paths.append((float(match[1]), path))
    x1, y1, x2, y2 = layout.normalized_roi("round_end_banner").pixel_bounds(
        *layout.reference_resolution)
    rows, inputs = [], {}
    for requested, path in sorted(paths):
        digest = sha256_file(path)
        image = cv2.imread(str(path))
        if image is None or (image.shape[1], image.shape[0]) != layout.reference_resolution:
            raise ValueError("native retained source dimensions required")
        if sha256_file(path) != digest:
            raise ValueError("retained image changed during feature selection")
        inputs[str(path.resolve())] = digest
        gray = cv2.cvtColor(image[y1:y2, x1:x2], cv2.COLOR_BGR2GRAY)
        boxes = [b for b in text_rows(gray, minimum_glyphs=3)
                 if round(b[1] / 10) * 10 == top
                 and round((b[3] - b[1]) / 10) * 10 == height]
        if boxes:
            rows.append({"requested_sec": requested, "retained_image_sha256": digest,
                         "retained_path": str(path.resolve()), "feature_boxes": boxes})
    if (not 3 <= len(rows) <= 256
            or len({r["requested_sec"] for r in rows}) != len(rows)):
        raise ValueError("3..256 unambiguous feature-selected requests required")
    return rows, inputs


def freeze(video, root, layout_path, partition_path, source_sha, output, top, height):
    _check_output_privacy(output.resolve())
    if output.exists():
        raise FileExistsError("new diagnostic plan required")
    end = json.loads(partition_path.read_text(encoding="utf-8"))["development"]["end_sec_exclusive"]
    verify_partition(partition_path, source_sha, end)
    if sha256_file(video) != source_sha:
        raise ValueError("source SHA mismatch")
    layout = HudLayout.load(layout_path)
    rows, inputs = select(root, layout, end, top, height)
    for path in (layout_path, partition_path, Path(__file__),
                 Path(text_rows.__code__.co_filename),
                 Path(CachedVideoService.extract_frames.__code__.co_filename),
                 Path(VideoService.extract_frames.__code__.co_filename),
                 Path(HudLayout.load.__code__.co_filename)):
        inputs[str(path.resolve())] = sha256_file(path)
    plan = {"kind": "feature_selected_banner_recapture_not_qualification",
            "source_path": str(video.resolve()), "source_sha256": source_sha,
            "partition_path": str(partition_path.resolve()), "development_end_sec": end,
            "source_resolution": list(layout.reference_resolution),
            "feature_top_bin": top, "feature_height_bin": height,
            "minimum_glyphs": 3, "requests": rows, "inputs_sha256": inputs,
            "decoder_fingerprints": list(decoder_fingerprints(VideoService().ffprobe_path)),
            "selection_timestamps_are_approximate": True,
            "selection_is_feature_conditioned": True, "independent_temporal_cohort": False,
            "semantic_labels_assigned": False, "evaluation_holdout_used": False}
    if (sha256_file(video) != source_sha
            or any(sha256_file(Path(p)) != h for p, h in inputs.items())):
        raise ValueError("inputs changed during plan creation")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    return plan


def capture(plan_path, output):
    _check_output_privacy(output.resolve())
    if output.exists():
        raise FileExistsError("new diagnostic capture directory required")
    plan_hash = sha256_file(plan_path)
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    if plan.get("kind") != "feature_selected_banner_recapture_not_qualification":
        raise ValueError("explicit frozen feature-selection plan required")
    video = Path(plan["source_path"])
    end = plan["development_end_sec"]
    service = VideoService()

    def verify():
        verify_partition(Path(plan["partition_path"]), plan["source_sha256"], end)
        if (sha256_file(plan_path) != plan_hash or sha256_file(video) != plan["source_sha256"]
                or list(decoder_fingerprints(service.ffprobe_path)) != plan["decoder_fingerprints"]
                or any(sha256_file(Path(p)) != h for p, h in plan["inputs_sha256"].items())):
            raise ValueError("frozen inputs/source/decoder changed")

    verify()
    times = [r["requested_sec"] for r in plan["requests"]]
    if (not 3 <= len(times) <= 256 or len(set(times)) != len(times)
            or any(type(t) not in (int, float) or not math.isfinite(t)
                   or not 0 <= t < end - .001 for t in times) or times != sorted(times)):
        raise ValueError("bounded frozen development requests required")
    cached = CachedVideoService(service, Path("outputs/e2e_cache/probe"),
                                plan["source_sha256"], plan["decoder_fingerprints"][0])
    metadata = cached.probe(video)
    if (not math.isfinite(metadata.duration_sec) or end > metadata.duration_sec
            or not math.isfinite(metadata.fps) or metadata.fps <= 0
            or [metadata.width, metadata.height] != plan["source_resolution"]):
        raise ValueError("valid source duration/fps required")
    output.mkdir(parents=True)
    frames = cached.extract_frames(video, times, output / "pool_frames",
                                    max_frames=256, max_dimension=None, metadata=metadata)
    if len(frames) != len(times):
        raise ValueError("complete source recapture required")
    records = []
    for frame, requested in zip(frames, times, strict=True):
        digest = sha256_file(frame.path)
        if (frame.source_pts_ticks is None or frame.source_time_base is None
                or frame.source_video_sha256 != plan["source_sha256"]
                or frame.source_image_sha256 != digest or not 0 <= frame.time_sec < end
                or abs(frame.time_sec - requested) > 1 / metadata.fps + .000501):
            raise ValueError("verified decoder identity and development PTS required")
        records.append({"requested_sec": requested, "source_frame_pts": frame.time_sec,
                        "source_pts_ticks": frame.source_pts_ticks,
                        "source_time_base": frame.source_time_base,
                        "source_video_sha256": frame.source_video_sha256, "sha256": digest})
    verify()
    selection = {"pool_records": records, "selected_pool_indices": [],
                 "method": "feature_selected_recapture_not_independent_temporal_cohort",
                 "plan_sha256": plan_hash}
    report = {"source_sha256": plan["source_sha256"], "plan_sha256": plan_hash,
              "validation_frames": records, "selection_is_feature_conditioned": True,
              "independent_temporal_cohort": False, "semantic_labels_assigned": False,
              "probe_cache_stats": dict(getattr(cached, "stats", {})),
              "qualification_created": False, "events_generated": 0}
    for name, obj in (("review_selection.json", selection), ("candidate_report.json", report)):
        (output / name).write_text(json.dumps(obj, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)
    plan = sub.add_parser("freeze")
    for name in ("video", "frames", "layout", "partition", "output"):
        plan.add_argument("--" + name, type=Path, required=True)
    plan.add_argument("--source-sha256", required=True)
    plan.add_argument("--row-top", type=int, required=True)
    plan.add_argument("--row-height", type=int, required=True)
    acquire = sub.add_parser("capture")
    for name in ("plan", "output"):
        acquire.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    result = (freeze(args.video, args.frames, args.layout, args.partition, args.source_sha256,
                     args.output, args.row_top, args.row_height) if args.mode == "freeze"
              else capture(args.plan, args.output))
    print(json.dumps({"frames": len(result.get("requests", result.get("validation_frames", []))),
                      "qualification_created": False}))


if __name__ == "__main__":
    main()
