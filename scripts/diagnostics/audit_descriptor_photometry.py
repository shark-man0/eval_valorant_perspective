"""Partition saved descriptor proposals; never filters or refits their model."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from collections import Counter
from pathlib import Path

import cv2
import numpy as np

from scripts.diagnostics.scene_correspondence import _prepare
from scripts.diagnostics.scene_world_chain import _ncc


def measure(reference, current, allowed, xy, model):
    x, y = np.round(xy).astype(int)
    patch = reference[y - 7 : y + 8, x - 7 : x + 8]
    result = {"source_patch_std": float(patch.std())}
    if patch.shape != (15, 15):
        return {**result, "reason": "source_footprint_unavailable"}
    if result["source_patch_std"] < 1:
        return {**result, "reason": "source_texture_unavailable"}
    if model is None:
        return {**result, "reason": "model_unavailable"}
    yy, xx = np.mgrid[y - 7 : y + 8, x - 7 : x + 8]
    model = np.asarray(model)
    mx = (model[0, 0] * xx + model[0, 1] * yy + model[0, 2]).astype(np.float32)
    my = (model[1, 0] * xx + model[1, 1] * yy + model[1, 2]).astype(np.float32)
    if not (cv2.remap(allowed, mx, my, cv2.INTER_LINEAR) == 1.0).all():
        return {**result, "reason": "current_footprint_unavailable"}
    aligned = cv2.remap(current, mx, my, cv2.INTER_LINEAR)
    result["current_patch_std"] = float(aligned.std())
    if result["current_patch_std"] < 1:
        return {**result, "reason": "current_texture_unavailable"}
    result["ncc"] = _ncc(patch, aligned)
    return {
        **result,
        "reason": "ncc_supported"
        if result["ncc"] is not None and result["ncc"] >= 0.90
        else "ncc_rejected",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("declaration", "result", "profile", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("refuse to overwrite evidence")
    declaration = json.loads(args.declaration.read_text())
    for path, digest in declaration["bindings"].items():
        if hashlib.sha256(Path(path).read_bytes()).hexdigest() != digest:
            raise ValueError(f"binding changed: {path}")
    paths = list(map(Path, declaration["bindings"])) + [
        args.declaration,
        args.result,
        Path(__file__),
    ]
    bindings = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    saved = json.loads(args.result.read_text())
    profile = json.loads(args.profile.read_text())
    references = {r["id"]: r for r in profile["references"]}
    start = time.perf_counter()
    rows = []
    allowed = np.zeros((360, 640), np.float32)
    for x1, y1, x2, y2 in declaration["current_search_boxes_640x360"]:
        allowed[y1:y2, x1:x2] = 1
    for row in saved["rows"]:
        reference = references[row["reference_id"]]
        source = _prepare(cv2.imread(str(args.profile.parent / reference["asset"])))
        current = _prepare(cv2.imread(row["image"]))
        tracks, model = row["result"]["tracks"], row["result"]["model"]
        measurements = []
        for track in tracks:
            measured = measure(source, current, allowed, track["reference_xy"], model)
            if model is not None:
                projected = np.asarray(model) @ np.r_[track["reference_xy"], 1]
                measured["camera_residual_px"] = float(
                    np.linalg.norm(projected - track["current_xy"])
                )
            measurements.append({"region": track["region"], **measured})
        rows.append(
            {
                "reference_id": row["reference_id"],
                "image": row["image"],
                "original_track_count": len(tracks),
                "partition": dict(Counter(m["reason"] for m in measurements)),
                "source_texture_unavailable_camera_outliers": sum(
                    m["reason"] == "source_texture_unavailable"
                    and m.get("camera_residual_px", 0) > 2
                    for m in measurements
                ),
                "measurements": measurements,
            }
        )
    if bindings != {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}:
        raise ValueError("terminal binding mismatch")
    report = {
        "scope": "passive saved-proposal audit; no filtering/refit/qualification",
        "bindings": bindings,
        "terminal_bindings_match": True,
        "rows": rows,
        "wall_clock_sec": time.perf_counter() - start,
    }
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps([{k: v for k, v in r.items() if k != "measurements"} for r in rows]))


if __name__ == "__main__":
    main()
