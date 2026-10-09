"""Score a pre-reserved native image cohort with the frozen world-feature method.

No labels, numeric readers, validation pack, lifecycle events or qualification
are generated. Review follows scoring in a separate ledger. All source frames
and method bytes are bound and checked before and after the measurement.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import time
from fractions import Fraction
from pathlib import Path

import cv2

from scripts.diagnostics.diagnose_native_global_lifecycle import extract_window, probe_json
from scripts.diagnostics.scene_correspondence import SCALED_BACKGROUND_BOXES, _prepare, sha256
from scripts.diagnostics.scene_reference_support import measure_reference_support
from scripts.diagnostics.scene_world_feature_support import common_world_feature_support


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reservation", type=Path, required=True)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists() or args.output.exists():
        parser.error("new output directory/report required; do not restart an existing cohort")
    started = time.perf_counter()
    bindings = {}

    def bind(path):
        value = sha256(path)
        if str(path) in bindings and bindings[str(path)] != value:
            raise ValueError("input bytes changed")
        bindings[str(path)] = value
        return value

    bind(args.reservation)
    freeze = json.loads(args.reservation.read_bytes())
    candidate_path = Path(freeze["candidate_report"])
    if bind(candidate_path) != freeze["candidate_report_sha256"]:
        raise ValueError("reserved candidate changed")
    candidate = json.loads(candidate_path.read_bytes())
    method_code = {
        p: h
        for p, h in candidate["file_sha256"].items()
        if "scripts/diagnostics/" in p and p.endswith(".py")
    }
    if len(method_code) < 5:
        raise ValueError("reserved candidate needs explicit nonempty method code bindings")
    for path, expected in method_code.items():
        if bind(Path(path)) != expected:
            raise ValueError("frozen method bytes changed")
    # The original reservation pins this map through its candidate-report SHA.
    # Its empty direct code field is not interpreted as unrestricted code.
    for name in ("validate_scene_world_holdout.py", "diagnose_native_global_lifecycle.py"):
        bind(Path(__file__).with_name(name))
    if bind(args.video) != freeze["source_video_sha256"]:
        raise ValueError("source video changed")
    ffmpeg, ffprobe = shutil.which("ffmpeg"), shutil.which("ffprobe")
    if ffmpeg is None or ffprobe is None:
        raise ValueError("FFmpeg/ffprobe required")
    metadata = probe_json(
        ffprobe,
        args.video,
        [
            "-show_streams",
            "-show_format",
            "-show_entries",
            "stream=time_base,r_frame_rate,width,height:format=duration",
        ],
    )
    stream = metadata["streams"][0]
    if (stream["width"], stream["height"], Fraction(stream["r_frame_rate"])) != (1920, 1080, 60):
        raise ValueError("frozen method requires this source geometry/native frame rate")
    time_base = Fraction(stream["time_base"])
    references = {}
    if {r["frame_sha256"] for r in candidate["references"]} != set(
        freeze["training_reference_hashes"]
    ):
        raise ValueError("reserved reference split changed")
    for row in candidate["references"]:
        path = Path(row["local_path"])
        if bind(path) != row["frame_sha256"]:
            raise ValueError("reviewed reference changed")
        image = cv2.imread(str(path))
        if (
            image is None
            or hashlib.sha256(image.tobytes()).hexdigest() != row["source_pixel_sha256"]
        ):
            raise ValueError("reviewed reference pixels changed")
        references[row["id"]] = _prepare(image)
    excluded = set(freeze["excluded_development_frame_hashes"])
    args.output_dir.mkdir(parents=True)
    predecode = {
        "reservation_sha256": bindings[str(args.reservation)],
        "candidate_report_sha256": bindings[str(candidate_path)],
        "resolved_frozen_code_sha256": method_code,
        "extraction_code_sha256": {
            p: h
            for p, h in bindings.items()
            if p.endswith(
                ("validate_scene_world_holdout.py", "diagnose_native_global_lifecycle.py")
            )
        },
        "decoded": False,
        "classification_labels_assigned": False,
    }
    (args.output_dir / "predecode-bindings.json").write_text(json.dumps(predecode, indent=2) + "\n")
    boxes = SCALED_BACKGROUND_BOXES[:5]
    windows, all_hashes, known_overlaps = [], set(), set()
    for index, (start, end) in enumerate(freeze["windows_sec"]):
        if not (0 <= start < end <= float(metadata["format"]["duration"])):
            raise ValueError("invalid reserved source window")
        root = args.output_dir / f"window-{index:03}"
        paths, ticks = extract_window(ffmpeg, ffprobe, args.video, root, start, end, time_base)
        previous, previous_tracks, previous_pixel = None, None, None
        rows = []
        for path, tick in zip(paths, ticks, strict=True):
            frame_hash = bind(path)
            known = frame_hash in excluded
            repeated = frame_hash in all_hashes
            if known:
                known_overlaps.add(frame_hash)
            all_hashes.add(frame_hash)
            source_image = cv2.imread(str(path))
            if source_image is None:
                raise ValueError("heldout source decode failed")
            pixel_hash = hashlib.sha256(source_image.tobytes()).hexdigest()
            image = _prepare(source_image)
            metrics, tracks, matches = {}, {}, {}
            for key, reference in references.items():
                tracks[key] = []
                metrics[key] = measure_reference_support(
                    reference, image, boxes, track_sink=tracks[key]
                )
                if previous is not None:
                    support = common_world_feature_support(
                        previous_tracks[key], tracks[key], previous[key], metrics[key]
                    )
                    if support["distributed_descriptive_support"]:
                        matches[key] = support
            rows.append(
                {
                    "source_pts_ticks": tick,
                    "time_base": str(time_base),
                    "pts_sec": float(tick * time_base),
                    "frame_sha256": frame_hash,
                    "source_pixel_sha256": pixel_hash,
                    "duplicate_previous_pixels": pixel_hash == previous_pixel,
                    "known_development_image_overlap": known,
                    "repeated_heldout_image_hash": repeated,
                    "reference_measurements": metrics,
                    "shared_reference_support": matches,
                    "link_supported_descriptive": (
                        bool(matches) and pixel_hash != previous_pixel and not known
                    ),
                    "runtime_proof_authorized": False,
                }
            )
            # Private point locations support subsequent image review; no GT or
            # correctness label is attached to this unreviewed measurement.
            tracks_path = path.with_suffix(".world-tracks.json")
            tracks_path.write_text(json.dumps(tracks) + "\n")
            bind(tracks_path)
            previous, previous_tracks, previous_pixel = metrics, tracks, pixel_hash
        windows.append(
            {
                "window_sec": [start, end],
                "frames": len(rows),
                "links": len(rows) - 1,
                "supported_links_descriptive": sum(r["link_supported_descriptive"] for r in rows),
                "rows": rows,
                "review_status": "unreviewed",
            }
        )
    for path, expected in bindings.items():
        if sha256(Path(path)) != expected:
            raise ValueError("terminal source/method/reference binding changed")
    report = {
        "scope": "Pre-reserved native world-feature measurements; unreviewed, not qualification",
        "reservation_sha256": bindings[str(args.reservation)],
        "source_video_sha256": freeze["source_video_sha256"],
        "predecode_bindings": predecode,
        "windows": windows,
        "file_sha256": bindings,
        "native_coverage_verified": True,
        "training_development_holdout_frame_hashes_disjoint": not known_overlaps,
        "known_development_overlaps": sorted(known_overlaps),
        "total_frames": sum(w["frames"] for w in windows),
        "unique_frame_hashes": len(all_hashes),
        "total_links": sum(w["links"] for w in windows),
        "wall_clock_seconds": time.perf_counter() - started,
        "review_status": "unreviewed",
        "qualification_created": False,
        "runtime_events_created": 0,
    }
    (args.output_dir / "results.json").write_text(json.dumps(report, indent=2) + "\n")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {
                "frames": report["total_frames"],
                "links": report["total_links"],
                "support": [w["supported_links_descriptive"] for w in windows],
                "wall_clock_seconds": report["wall_clock_seconds"],
            }
        )
    )


if __name__ == "__main__":
    main()
