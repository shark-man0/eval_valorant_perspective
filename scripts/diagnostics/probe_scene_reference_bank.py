"""Same-reference support of adjacent native frames; development only.

References are reviewed source background views, selected without numeric or
assertion inputs. Both ends of a link must share at least three matching world
regions in one reference, over two rows/columns. No mosaic of different refs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from fractions import Fraction
from pathlib import Path

import cv2

from scripts.diagnostics.probe_scene_reference import spatial_support
from scripts.diagnostics.scene_correspondence import SCALED_BACKGROUND_BOXES, _prepare, sha256
from scripts.diagnostics.scene_reference_support import measure_reference_support
from scripts.diagnostics.scene_world_feature_support import common_world_feature_support


def common_reference_support(previous, current):
    common = {r["region"] for r in previous["regions"] if r["reference_supported_descriptive"]} & {
        r["region"] for r in current["regions"] if r["reference_supported_descriptive"]
    }
    regions = [
        {"region": i, "reference_supported_descriptive": i in common}
        for i in range(len(current["regions"]))
    ]
    return spatial_support(regions)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--native-root", type=Path, required=True)
    parser.add_argument("--single-reference-report", type=Path, required=True)
    parser.add_argument("--references", type=int, nargs="+", required=True)
    parser.add_argument("--review-provenance", required=True)
    parser.add_argument("--support", choices=("regions", "world_features"), default="regions")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or len(set(args.references)) != len(args.references):
        parser.error("new output and unique reviewed reference indices required")
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
        "probe_scene_reference_bank.py",
        "scene_world_feature_support.py",
    ):
        bind(Path(__file__).with_name(name))
    source_report = args.native_root / "results.json"
    for path in (source_report, args.video, args.single_reference_report):
        bind(path)
    source = json.loads(source_report.read_bytes())
    earlier = json.loads(args.single_reference_report.read_bytes())
    if (
        source.get("native_pts_coverage_verified") is not True
        or bindings[str(args.video)] != source["source_video_sha256"]
        or earlier["source_video_sha256"] != source["source_video_sha256"]
    ):
        raise ValueError("source integrity/coverage missing")

    def read(path, row):
        if bind(path) != row["frame_sha256"]:
            raise ValueError("source image changed")
        image = cv2.imread(str(path))
        if (
            image is None
            or hashlib.sha256(image.tobytes()).hexdigest() != row["source_pixel_sha256"]
        ):
            raise ValueError("source pixels changed")
        return _prepare(image)

    references, reference_bindings = {}, []
    boxes = SCALED_BACKGROUND_BOXES[:5]
    for index in args.references:
        if not 1 <= index <= len(source["windows"][0]["rows"]):
            raise ValueError("reference outside reviewed source archive")
        path = args.native_root / f"window-000/frame_{index:06}.png"
        row = source["windows"][0]["rows"][index - 1]
        references[str(index)] = read(path, row)
        reference_bindings.append(
            {
                "id": str(index),
                "local_path": str(path),
                "frame_sha256": row["frame_sha256"],
                "source_pixel_sha256": row["source_pixel_sha256"],
                "reviewed_boxes_640x360": boxes,
                "review_provenance": args.review_provenance,
            }
        )
    sets = []
    comparison_equal = True
    for number, window in enumerate(source["windows"]):
        ticks = [Fraction(r["source_pts_ticks"]) * Fraction(r["time_base"]) for r in window["rows"]]
        if any(b - a != Fraction(1, 60) for a, b in zip(ticks, ticks[1:], strict=False)):
            raise ValueError("missing native frame")
        rows, previous, previous_tracks = [], None, None
        for index, row in enumerate(window["rows"], start=1):
            image = read(args.native_root / f"window-{number:03}/frame_{index:06}.png", row)
            measurements, tracks = {}, {}
            for key, reference in references.items():
                tracks[key] = []
                measurements[key] = measure_reference_support(
                    reference, image, boxes, track_sink=tracks[key]
                )
            if "1" in measurements:
                earlier_row = earlier["sets"][number]["rows"][index - 1]["methods"]["global"]
                comparison_equal &= all(earlier_row[k] == v for k, v in measurements["1"].items())
            accepted = {}
            if previous is not None:
                for key in references:
                    common = (
                        common_reference_support(previous[key], measurements[key])
                        if args.support == "regions"
                        else common_world_feature_support(
                            previous_tracks[key], tracks[key], previous[key], measurements[key]
                        )
                    )
                    if common["distributed_descriptive_support"]:
                        accepted[key] = common
            rows.append(
                {
                    "pts_sec": row["pts_sec"],
                    "source_pts_ticks": row["source_pts_ticks"],
                    "time_base": row["time_base"],
                    "source_pixel_sha256": row["source_pixel_sha256"],
                    "reference_measurements": measurements,
                    "shared_reference_support": accepted,
                    "link_supported_descriptive": bool(accepted),
                    "runtime_proof_authorized": False,
                }
            )
            previous = measurements
            previous_tracks = tracks
        sets.append(
            {
                "window_index": number,
                "rows": rows,
                "frames": len(rows),
                "links": len(rows) - 1,
                "single_reference_links": sum("1" in r["shared_reference_support"] for r in rows),
                "bank_links": sum(r["link_supported_descriptive"] for r in rows),
            }
        )
    if not comparison_equal:
        raise ValueError("original reference method metrics changed")
    control_paths = [Path(row["local_path"]) for row in earlier["controls"]]
    control_results = []
    control_previous, control_previous_tracks = None, None
    for path in control_paths:
        if bind(path) != earlier["file_sha256"][str(path)]:
            raise ValueError("control changed")
        image = cv2.imread(str(path))
        if image is None:
            raise ValueError("control decode failed")
        image = _prepare(image)
        results, control_tracks = {}, {}
        for key, reference in references.items():
            control_tracks[key] = []
            results[key] = measure_reference_support(
                reference, image, boxes, track_sink=control_tracks[key]
            )
        control_results.append(
            {
                "local_path": str(path),
                "frame_sha256": bindings[str(path)],
                "supported_reference_ids": [
                    key
                    for key, measured in results.items()
                    if (
                        spatial_support(measured["regions"])
                        if args.support == "regions"
                        else common_world_feature_support(
                            control_tracks[key], control_tracks[key], measured, measured
                        )
                    )["distributed_descriptive_support"]
                ],
                "shared_previous_reference_ids": []
                if control_previous is None
                else [
                    key
                    for key in references
                    if (
                        common_reference_support(control_previous[key], results[key])
                        if args.support == "regions"
                        else common_world_feature_support(
                            control_previous_tracks[key],
                            control_tracks[key],
                            control_previous[key],
                            results[key],
                        )
                    )["distributed_descriptive_support"]
                ],
            }
        )
        control_previous = results
        control_previous_tracks = control_tracks
    for path, digest in bindings.items():
        if sha256(Path(path)) != digest:
            raise ValueError("terminal source/code changed")
    report = {
        "scope": "Same-background-reference development; not holdout or runtime qualification",
        "support_method": args.support,
        "source_video_sha256": source["source_video_sha256"],
        "references": reference_bindings,
        "sets": sets,
        "controls": control_results,
        "file_sha256": bindings,
        "earlier_single_reference_metrics_equal": comparison_equal,
        "frames": sum(s["frames"] for s in sets),
        "wall_clock_seconds": time.perf_counter() - started,
        "production_changed": False,
        "qualification_created": False,
        "runtime_events_created": 0,
        "canonical_current": None,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {
                "counts": [
                    {k: s[k] for k in ("window_index", "single_reference_links", "bank_links")}
                    for s in sets
                ],
                "wall_clock_seconds": report["wall_clock_seconds"],
            }
        )
    )


if __name__ == "__main__":
    main()
