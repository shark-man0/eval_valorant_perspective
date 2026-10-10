"""Same-image calibration of candidate loss; never authorizes scene continuity."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import cv2
import numpy as np

from scripts.diagnostics.scene_correspondence import _prepare
from scripts.diagnostics.scene_descriptor_acquisition import _descriptors


def audit(image, source_boxes, current_boxes):
    source_points, source_values = _descriptors(
        image, source_boxes, feature_source="reviewed_corners"
    )
    current_points, _ = _descriptors(image, current_boxes, feature_source="reviewed_corners")
    current_xy = np.asarray([p[1] for p in current_points]).reshape(-1, 2)
    sift = cv2.SIFT_create(nfeatures=500, edgeThreshold=15)
    rows = []
    for (region, xy), descriptor in zip(source_points, source_values, strict=True):
        x, y = xy
        contexts = []
        for index, (x1, y1, x2, y2) in enumerate(current_boxes):
            if not (x1 + 9 <= x < x2 - 9 and y1 + 9 <= y < y2 - 9):
                continue
            crop = image[y1:y2, x1:x2]
            response = cv2.cornerMinEigenVal(crop, 3)
            relative_response = float(response[round(y - y1), round(x - x1)]) / max(
                float(response.max()), np.finfo(np.float32).tiny
            )
            _, forced = sift.compute(crop, [cv2.KeyPoint(x - x1, y - y1, 3, 0)])
            contexts.append(
                {
                    "current_region": index,
                    "relative_corner_response": relative_response,
                    "above_existing_quality_floor": relative_response >= 0.01,
                    "forced_same_point_descriptor_distance": float(
                        np.linalg.norm(descriptor - forced[0])
                    ),
                }
            )
        nearest = float(np.linalg.norm(current_xy - xy, axis=1).min()) if len(current_xy) else None
        rows.append(
            {
                "source_region": region,
                "xy": xy,
                "nearest_current_candidate_distance": nearest,
                "same_location_candidate": nearest is not None and nearest <= 1,
                "contexts": contexts,
            }
        )
    groups = []
    for region in range(len(source_boxes)):
        selected = [r for r in rows if r["source_region"] == region]
        groups.append(
            {
                "region": region,
                "source_candidates": len(selected),
                "same_location_current_candidates": sum(
                    r["same_location_candidate"] for r in selected
                ),
                "current_context_eligible": sum(bool(r["contexts"]) for r in selected),
                "below_quality_in_all_contexts": sum(
                    bool(r["contexts"])
                    and not any(c["above_existing_quality_floor"] for c in r["contexts"])
                    for r in selected
                ),
            }
        )
    return {"groups": groups, "points": rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--declaration", type=Path, required=True)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("refuse to overwrite diagnostic evidence")
    declaration = json.loads(args.declaration.read_text())
    profile = json.loads(args.profile.read_text())
    paths = [args.declaration, args.profile, Path(__file__)] + [
        args.profile.parent / reference["asset"] for reference in profile["references"]
    ]
    bindings = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    started = time.perf_counter()
    rows = []
    for reference in profile["references"]:
        image = _prepare(cv2.imread(str(args.profile.parent / reference["asset"])))
        rows.append(
            {
                "reference_id": reference["id"],
                "result": audit(
                    image,
                    reference["world_boxes_640x360"],
                    declaration["current_search_boxes_640x360"],
                ),
            }
        )
    terminal = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    if bindings != terminal:
        raise ValueError("input changed during measurement")
    args.output.write_text(
        json.dumps(
            {
                "scope": "same-image calibration only; no acquisition or holdout claim",
                "bindings": bindings,
                "terminal_bindings_match": True,
                "qualification_created": False,
                "runtime_proof_authorized": False,
                "rows": rows,
                "wall_clock_sec": time.perf_counter() - started,
            },
            indent=2,
        )
        + "\n"
    )
    print(
        json.dumps(
            [{"reference_id": r["reference_id"], "groups": r["result"]["groups"]} for r in rows]
        )
    )


if __name__ == "__main__":
    main()
