"""Evaluate a reviewed world reference on existing native development archives.

This consumes source images, hashes and PTS only, never assertion expectations
or historical numeric/phase outputs. It creates no production profile/proof.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from fractions import Fraction
from pathlib import Path

import cv2

from scripts.diagnostics.scene_correspondence import SCALED_BACKGROUND_BOXES, _prepare, sha256
from scripts.diagnostics.scene_reference_support import measure_reference_support


def spatial_support(regions):
    supported = [r["region"] for r in regions if r["reference_supported_descriptive"]]
    cells = {
        (
            int((SCALED_BACKGROUND_BOXES[i][1] + SCALED_BACKGROUND_BOXES[i][3]) / 2 / 120),
            int((SCALED_BACKGROUND_BOXES[i][0] + SCALED_BACKGROUND_BOXES[i][2]) / 2 / (640 / 3)),
        )
        for i in supported
    }
    return {
        "supported_regions": supported,
        "descriptive_witness_cells_full_image": sorted([list(c) for c in cells]),
        "distributed_descriptive_support": (
            len(cells) >= 3 and len({c[0] for c in cells}) >= 2 and len({c[1] for c in cells}) >= 2
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--native-root", type=Path, required=True)
    parser.add_argument("--development-root", type=Path, required=True)
    parser.add_argument("--development-report", type=Path, required=True)
    parser.add_argument("--control-report", type=Path, required=True)
    parser.add_argument("--review-provenance", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output exists")
    started = time.perf_counter()
    bindings = {}

    def bind(path):
        digest = sha256(path)
        if str(path) in bindings and bindings[str(path)] != digest:
            raise ValueError("source binding changed")
        bindings[str(path)] = digest
        return digest

    for name in (
        "scene_reference_support.py",
        "scene_correspondence.py",
        "probe_scene_reference.py",
    ):
        bind(Path(__file__).with_name(name))
    native_report = args.native_root / "results.json"
    for path in (native_report, args.development_report, args.control_report, args.video):
        bind(path)
    native = json.loads(native_report.read_bytes())
    development = json.loads(args.development_report.read_bytes())
    controls = json.loads(args.control_report.read_bytes())
    video_hash = bindings[str(args.video)]
    if (
        native.get("source_video_sha256") != video_hash
        or development["freeze"]["source_video_sha256"] != video_hash
        or controls["source_video_sha256"] != video_hash
        or native.get("native_pts_coverage_verified") is not True
        or development.get("native_coverage_verified") is not True
    ):
        raise ValueError("source integrity/native coverage missing")

    def read(path, row=None):
        file_hash = bind(path)
        image = cv2.imread(str(path))
        if image is None:
            raise ValueError("source decode failed")
        pixel_hash = hashlib.sha256(image.tobytes()).hexdigest()
        if row and (file_hash != row["frame_sha256"] or pixel_hash != row["source_pixel_sha256"]):
            raise ValueError("source PNG/pixel binding mismatch")
        return _prepare(image)

    reference_path = args.native_root / "window-000/frame_000001.png"
    reference = read(reference_path, native["windows"][0]["rows"][0])
    # Only reviewed world boxes are used; region5 is conservatively excluded.
    boxes = SCALED_BACKGROUND_BOXES[:5]
    sets = []
    for cohort, root, windows in (
        ("native_scene_development", args.native_root, native["windows"]),
        ("former_scene_holdout_now_development", args.development_root, development["windows"]),
    ):
        for number, window in enumerate(windows):
            source_rows = window["rows"]
            ticks = [
                Fraction(r["source_pts_ticks"]) * Fraction(r["time_base"]) for r in source_rows
            ]
            if any(b - a != Fraction(1, 60) for a, b in zip(ticks, ticks[1:], strict=False)):
                raise ValueError("not every consecutive native frame")
            rows = []
            for i, source_row in enumerate(source_rows, start=1):
                path = root / f"window-{number:03}/frame_{i:06}.png"
                current = read(path, source_row)
                methods = {}
                for method in ("global", "region"):
                    measured = measure_reference_support(
                        reference, current, boxes, model_scope=method
                    )
                    methods[method] = {**measured, **spatial_support(measured["regions"])}
                rows.append(
                    {
                        "source_pts_ticks": source_row["source_pts_ticks"],
                        "time_base": source_row["time_base"],
                        "pts_sec": source_row["pts_sec"],
                        "source_pixel_sha256": source_row["source_pixel_sha256"],
                        "reference_is_same_source_pixels": path == reference_path,
                        "methods": methods,
                    }
                )
            sets.append(
                {
                    "cohort": cohort,
                    "window_index": number,
                    "frames": len(rows),
                    "rows": rows,
                    "spatial_support_frames": {
                        method: sum(
                            r["methods"][method]["distributed_descriptive_support"] for r in rows
                        )
                        for method in ("global", "region")
                    },
                }
            )
    control_paths = {}
    for control in controls["controls"]:
        for binding in control["source_bindings"]:
            path = Path(binding["local_path"])
            if bind(path) != binding["sha256"]:
                raise ValueError("control binding mismatch")
            control_paths[str(path)] = path
    control_results = []
    for path in control_paths.values():
        if "dense-r1-end" not in str(path):
            continue
        current = read(path)
        control_results.append(
            {
                "local_path": str(path),
                "frame_sha256": bindings[str(path)],
                "methods": {
                    method: spatial_support(
                        measure_reference_support(reference, current, boxes, model_scope=method)[
                            "regions"
                        ]
                    )
                    for method in ("global", "region")
                },
            }
        )
    for path, digest in bindings.items():
        if sha256(Path(path)) != digest:
            raise ValueError("terminal source/code binding changed")
    report = {
        "scope": "World-reference eligibility development probe; not qualification/profile/events",
        "source_video_sha256": video_hash,
        "reference": {
            "local_path": str(reference_path),
            "frame_sha256": bindings[str(reference_path)],
            "reviewed_boxes_640x360": boxes,
            "review_provenance": args.review_provenance,
            "training_references": 1,
            "limits": (
                "One reviewed background view, correlated same-video development; "
                "no independent holdout"
            ),
        },
        "sets": sets,
        "controls": control_results,
        "file_sha256": bindings,
        "frames": sum(s["frames"] for s in sets),
        "native_coverage_verified": True,
        "thresholds": {"ncc": 0.90, "valid_interior_fraction": 0.90, "fb_px": 1, "ransac_px": 2},
        "wall_clock_seconds": time.perf_counter() - started,
        "qualification_created": False,
        "production_changed": False,
        "runtime_events_created": 0,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {
                "frames": report["frames"],
                "wall_clock_seconds": report["wall_clock_seconds"],
                "counts": [s["spatial_support_frames"] for s in sets],
            }
        )
    )


if __name__ == "__main__":
    main()
