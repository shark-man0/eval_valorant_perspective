"""Frozen affine-oriented appearance competitors; no location selection/refit."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np

from scripts.diagnostics.scene_correspondence import _prepare
from scripts.diagnostics.scene_world_chain import _ncc


def competitors(reference, current, source_box, current_boxes, source_xy, endpoint, model):
    radius = 7
    yy, xx = np.mgrid[-radius : radius + 1, -radius : radius + 1]
    offsets = np.stack([xx, yy], axis=-1) @ np.linalg.inv(np.asarray(model)[:, :2]).T
    sx = (offsets[..., 0] + source_xy[0]).astype(np.float32)
    sy = (offsets[..., 1] + source_xy[1]).astype(np.float32)
    allowed = np.zeros(reference.shape, np.float32)
    x1, y1, x2, y2 = source_box
    allowed[y1:y2, x1:x2] = 1
    if not (cv2.remap(allowed, sx, sy, cv2.INTER_LINEAR) == 1).all():
        return {"reason": "oriented_source_footprint_unavailable"}
    template = cv2.remap(reference, sx, sy, cv2.INTER_LINEAR)
    if float(template.std()) < 1:
        return {"reason": "source_texture_unavailable"}
    projection = np.asarray(model) @ np.r_[source_xy, 1]
    peaks = set()
    for x1, y1, x2, y2 in current_boxes:
        crop = current[y1:y2, x1:x2]
        if min(crop.shape) < 15:
            continue
        scores = cv2.matchTemplate(crop, template, cv2.TM_CCOEFF_NORMED)
        f = crop.astype(np.float32)
        means = cv2.boxFilter(f, -1, (15, 15))[7:-7, 7:-7]
        squares = cv2.boxFilter(f * f, -1, (15, 15))[7:-7, 7:-7]
        textured = squares - means * means >= 1
        ys, xs = np.where(np.isfinite(scores) & (scores >= 0.90) & textured)
        peaks.update(
            (int(x + x1 + radius), int(y + y1 + radius)) for x, y in zip(xs, ys, strict=True)
        )

    def at(center):
        cx, cy = center
        current_allowed = np.zeros(current.shape, np.float32)
        for x1, y1, x2, y2 in current_boxes:
            current_allowed[y1:y2, x1:x2] = 1
        mx, my = (xx + cx).astype(np.float32), (yy + cy).astype(np.float32)
        if not (cv2.remap(current_allowed, mx, my, cv2.INTER_LINEAR) == 1).all():
            return None
        aligned = cv2.remap(current, mx, my, cv2.INTER_LINEAR)
        return _ncc(template, aligned)

    return {
        "reason": "measured",
        "projected_center": projection.tolist(),
        "endpoint_ncc": at(endpoint),
        "projection_ncc": at(projection),
        "integer_peak_count": len(peaks),
        "peaks_outside_endpoint_2px": int(
            sum(np.linalg.norm(np.asarray(p) - endpoint) > 2 for p in peaks)
        ),
        "peaks_outside_projection_2px": int(
            sum(np.linalg.norm(np.asarray(p) - projection) > 2 for p in peaks)
        ),
        "peak_examples": [list(p) for p in sorted(peaks)[:5]],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("declaration", "result", "partition", "profile", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("refuse to overwrite evidence")
    declaration = json.loads(args.declaration.read_text())
    paths = [Path(p) for p in declaration["bindings"]] + [
        args.declaration,
        args.result,
        args.partition,
        args.profile,
        Path(__file__),
    ]
    bindings = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    if any(bindings[p] != digest for p, digest in declaration["bindings"].items()):
        raise ValueError("frozen inputs changed")
    results = json.loads(args.result.read_text())["rows"]
    partition = json.loads(args.partition.read_text())["rows"]
    profile = json.loads(args.profile.read_text())
    refs = {r["id"]: r for r in profile["references"]}
    row, measured = results[4], partition[4]
    if row["image"] != measured["image"]:
        raise ValueError("partition does not correspond to saved query")
    reference = refs[row["reference_id"]]
    source = _prepare(cv2.imread(str(args.profile.parent / reference["asset"])))
    current = _prepare(cv2.imread(row["image"]))
    tracks = row["result"]["tracks"]
    if len(tracks) != len(measured["measurements"]):
        raise ValueError("partition count differs")
    rows = []
    for index, (track, status) in enumerate(zip(tracks, measured["measurements"], strict=True)):
        if status["reason"] != "ncc_supported" or status["camera_residual_px"] <= 2:
            continue
        rows.append(
            {
                "track_index": index,
                "region": track["region"],
                "source_xy": track["reference_xy"],
                "endpoint": track["current_xy"],
                "result": competitors(
                    source,
                    current,
                    reference["world_boxes_640x360"][track["region"]],
                    declaration["current_search_boxes_640x360"],
                    track["reference_xy"],
                    track["current_xy"],
                    row["result"]["model"],
                ),
            }
        )
    if bindings != {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}:
        raise ValueError("terminal binding mismatch")
    report = {
        "scope": "exposed endpoint ambiguity audit; no model/location selection",
        "bindings": bindings,
        "terminal_bindings_match": True,
        "rows": rows,
    }
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps([r["result"] for r in rows]))


if __name__ == "__main__":
    main()
