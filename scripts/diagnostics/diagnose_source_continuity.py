"""Measure source-image correspondence; never attest runtime continuity.

Fixed camera-region optical flow complements the earlier image-difference
diagnostic. No Validation Pack, expected values, cut labels, confidence policy
or lifecycle state is loaded. Results are descriptive, not qualifications.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
from pathlib import Path

import cv2
import numpy as np

METHOD = {
    "version": "camera_lk_fb_ncc_diagnostic_v1",
    "thumbnail_wh": [640, 360],
    "camera_bounds_norm": [0.20, 0.20, 0.90, 0.80],
    "corners": {"maxCorners": 300, "qualityLevel": 0.01, "minDistance": 8},
    "lk": {"winSize": [21, 21], "maxLevel": 3},
    "forward_backward_error_px": 1.0,
    "patch_width": 11,
    "descriptive_patch_ncc": 0.90,
    "spatial_grid": [3, 3],
    "policy": "measurement only; no continuity confidence, segment or cut decision",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def camera_gray(image: np.ndarray) -> np.ndarray:
    if image.dtype != np.uint8 or image.ndim != 3 or image.shape[2] != 3:
        raise ValueError("uint8 BGR source image required")
    if min(image.shape[:2]) < 32:
        raise ValueError("source image is too small")
    thumb = cv2.resize(image, (640, 360), interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(thumb, cv2.COLOR_BGR2GRAY)
    return np.ascontiguousarray(gray[72:288, 128:576])


def measure_pair(previous: np.ndarray, current: np.ndarray) -> dict:
    before, after = camera_gray(previous), camera_gray(current)
    points = cv2.goodFeaturesToTrack(before, **METHOD["corners"])
    result = {
        "corner_count": 0, "forward_track_count": 0,
        "bidirectional_track_count": 0, "patch_ncc_0_90_count": 0,
        "patch_ncc_cells": [0] * 9, "median_patch_ncc": None,
        "median_flow_px": None, "median_forward_backward_error_px": None,
        "measurement_reason": "no_corners",
    }
    if points is None:
        return result
    points = np.asarray(points, dtype=np.float32).reshape(-1, 1, 2)
    result["corner_count"] = len(points)
    tracked, forward_status, _ = cv2.calcOpticalFlowPyrLK(
        before, after, points, None, winSize=(21, 21), maxLevel=3,
    )
    if tracked is None or forward_status is None:
        result["measurement_reason"] = "no_forward_tracks"
        return result
    tracked = np.asarray(tracked, dtype=np.float32).reshape(-1, 1, 2)
    if not np.isfinite(tracked).all():
        result["measurement_reason"] = "nonfinite_forward_tracks"
        return result
    recovered, backward_status, _ = cv2.calcOpticalFlowPyrLK(
        after, before, tracked, None, winSize=(21, 21), maxLevel=3,
    )
    forward = np.asarray(forward_status).reshape(-1) == 1
    result["forward_track_count"] = int(forward.sum())
    if recovered is None or backward_status is None:
        result["measurement_reason"] = "no_backward_tracks"
        return result
    original = points.reshape(-1, 2)
    destination = tracked.reshape(-1, 2)
    recovered = np.asarray(recovered, dtype=np.float32).reshape(-1, 2)
    error = np.linalg.norm(recovered - original, axis=1)
    height, width = before.shape
    valid = (
        forward & (np.asarray(backward_status).reshape(-1) == 1)
        & np.isfinite(error) & (error <= 1.0)
        & (original[:, 0] >= 6) & (original[:, 0] < width - 6)
        & (original[:, 1] >= 6) & (original[:, 1] < height - 6)
        & (destination[:, 0] >= 6) & (destination[:, 0] < width - 6)
        & (destination[:, 1] >= 6) & (destination[:, 1] < height - 6)
    )
    result["bidirectional_track_count"] = int(valid.sum())
    if not valid.any():
        result["measurement_reason"] = "no_bidirectional_camera_tracks"
        return result
    result["median_forward_backward_error_px"] = float(np.median(error[valid]))
    result["median_flow_px"] = float(np.median(
        np.linalg.norm(destination[valid] - original[valid], axis=1)
    ))
    scores = []
    for source, target in zip(original[valid], destination[valid], strict=True):
        first = cv2.getRectSubPix(before, (11, 11), tuple(map(float, source)))
        second = cv2.getRectSubPix(after, (11, 11), tuple(map(float, target)))
        if float(first.std()) < 1 or float(second.std()) < 1:
            continue
        score = float(cv2.matchTemplate(first, second, cv2.TM_CCOEFF_NORMED)[0, 0])
        if not math.isfinite(score):
            continue
        scores.append(score)
        if score >= 0.90:
            result["patch_ncc_0_90_count"] += 1
            column = min(2, int(source[0] * 3 / width))
            row = min(2, int(source[1] * 3 / height))
            result["patch_ncc_cells"][row * 3 + column] += 1
    result["median_patch_ncc"] = float(np.median(scores)) if scores else None
    result["measurement_reason"] = "measured" if scores else "no_nonflat_patches"
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--source-sha256", required=True)
    parser.add_argument("--pair-manifest", type=Path, required=True)
    parser.add_argument("--frames-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    started = time.perf_counter()
    source_hash = sha256(args.video)
    if source_hash != args.source_sha256:
        raise ValueError("source SHA256 mismatch")
    manifest_hash = sha256(args.pair_manifest)
    manifest = json.loads(args.pair_manifest.read_text(encoding="utf-8"))
    if manifest["status"] != "complete" or manifest["source_video_sha256"] != source_hash:
        raise ValueError("completed source-associated pair manifest required")
    expected = {float(row["pts_sec"]): row["frame_sha256"]
                for row in manifest["source_frames"]}
    paths: dict[int, Path] = {}
    for path in sorted(args.frames_root.rglob("*.jpg")):
        try:
            timestamp = float(path.stem.rsplit("_", 1)[-1])
        except ValueError:
            continue
        if math.isfinite(timestamp):
            paths.setdefault(round(timestamp * 1000), path)
    frames = {}
    for pts, frame_hash in expected.items():
        path = paths.get(round(pts * 1000))
        if path is None or abs(float(path.stem.rsplit("_", 1)[-1]) - pts) > 0.00051:
            raise ValueError(f"missing exact archived PTS {pts}")
        if sha256(path) != frame_hash:
            raise ValueError(f"archived source-frame hash mismatch at {pts}")
        frame = cv2.imread(str(path))
        if frame is None:
            raise ValueError(f"source frame unreadable at {pts}")
        # Retain only thumbnails, avoiding hundreds of full-HD images in Pi RAM.
        frames[pts] = cv2.resize(frame, (640, 360), interpolation=cv2.INTER_AREA)
    # Freeze the descriptive method before processing any pair. Not a candidate profile.
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.with_suffix(".method.json").write_text(
        json.dumps({"method": METHOD, "pair_manifest_sha256": manifest_hash,
                    "source_sha256": source_hash}, indent=2) + "\n", encoding="utf-8",
    )
    rows = []
    for pair in manifest["frame_pairs"]:
        previous, current = float(pair["previous_pts"]), float(pair["current_pts"])
        if not 0 < current - previous <= 1.0:
            raise ValueError("positive source gap no greater than one second required")
        rows.append({"previous_pts": previous, "current_pts": current,
                     "gap_sec": current - previous,
                     "previous_frame_sha256": expected[previous],
                     "current_frame_sha256": expected[current],
                     **measure_pair(frames[previous], frames[current])})
    if sha256(args.video) != source_hash or sha256(args.pair_manifest) != manifest_hash:
        raise ValueError("source/manifest changed during measurements")
    report = {"status": "complete", "scope": __doc__, "method": METHOD,
              "source_video_sha256": source_hash, "pair_manifest_sha256": manifest_hash,
              "source_frame_count": len(frames), "pair_count": len(rows),
              "pairs": rows, "wall_clock_sec": time.perf_counter() - started,
              "qualification_created": False, "production_behavior_changed": False}
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in [
        "status", "source_frame_count", "pair_count", "wall_clock_sec",
        "qualification_created", "production_behavior_changed",
    ]}))


if __name__ == "__main__":
    main()
