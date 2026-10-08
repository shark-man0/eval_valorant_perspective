"""Measure current source-image correspondence; never attest continuity or cuts.

No thresholds here create runtime evidence, source segments, events or labels.
The frozen method describes measurements, not a qualified continuity policy.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import cv2
import numpy as np

from scripts.diagnostics.diagnose_round_lifecycle import archived_frames, sha256_file
from valorant_ai_coach.hud.calibrate_temporal import _check_output_privacy


def load_method(path):
    method = json.loads(path.read_bytes())["method"]
    if method.get("version") != "camera_lk_fb_ncc_diagnostic_v1":
        raise ValueError("unsupported frozen correspondence method")
    if (
        method.get("thumbnail_wh") != [640, 360]
        or method.get("camera_bounds_norm") != [.2, .2, .9, .8]
        or method.get("corners") != {"maxCorners": 300, "qualityLevel": .01, "minDistance": 8}
        or method.get("lk") != {"winSize": [21, 21], "maxLevel": 3}
        or method.get("forward_backward_error_px") != 1.0
        or method.get("patch_width") != 11
        or method.get("descriptive_patch_ncc") != .90
        or method.get("spatial_grid") != [3, 3]
    ):
        raise ValueError("method differs from frozen measurement declaration")
    return method


def measure(before, after, method):
    if (
        not isinstance(before, np.ndarray) or not isinstance(after, np.ndarray)
        or before.dtype != np.uint8 or after.dtype != np.uint8
        or before.shape != after.shape or before.ndim != 3 or before.shape[2] != 3
        or min(before.shape[:2]) < 2
    ):
        raise ValueError("same-size uint8 BGR source images required")
    width, height = method["thumbnail_wh"]
    gray = [cv2.cvtColor(cv2.resize(image, (width, height), interpolation=cv2.INTER_AREA),
                         cv2.COLOR_BGR2GRAY) for image in (before, after)]
    x1, y1, x2, y2 = [round(value * size) for value, size in zip(
        method["camera_bounds_norm"], (width, height, width, height), strict=True,
    )]
    mask = np.zeros((height, width), np.uint8)
    mask[y1:y2, x1:x2] = 255
    delta = np.abs(gray[0][y1:y2, x1:x2].astype(float) - gray[1][y1:y2, x1:x2])
    result = {
        "source_pixels_identical": bool(np.array_equal(before, after)),
        "camera_pixels_identical": bool(np.array_equal(gray[0][y1:y2, x1:x2],
                                                       gray[1][y1:y2, x1:x2])),
        "camera_mean_absolute_difference": float(delta.mean() / 255),
        "corner_count": 0, "forward_backward_count": 0, "nonflat_patch_count": 0,
        "descriptive_ncc_match_count": 0, "grid_match_counts": [0] * 9,
        "patch_ncc": {"min": None, "median": None, "max": None},
        "continuity_attested": False,
    }
    p0 = cv2.goodFeaturesToTrack(gray[0], mask=mask, **method["corners"])
    if p0 is None:
        return result
    result["corner_count"] = len(p0)
    options = {**method["lk"], "winSize": tuple(method["lk"]["winSize"])}
    p1, status1, _ = cv2.calcOpticalFlowPyrLK(gray[0], gray[1], p0, None, **options)
    if p1 is None or status1 is None or not np.isfinite(p1).all():
        return result
    pback, status2, _ = cv2.calcOpticalFlowPyrLK(gray[1], gray[0], p1, None, **options)
    if pback is None or status2 is None:
        return result
    valid = (
        status1.ravel().astype(bool) & status2.ravel().astype(bool)
        & np.isfinite(pback).all(axis=(1, 2))
        & (np.linalg.norm(p0[:, 0] - pback[:, 0], axis=1)
           <= method["forward_backward_error_px"])
    )
    result["forward_backward_count"] = int(valid.sum())
    scores = []
    patch_width = method["patch_width"]
    radius = patch_width // 2
    for initial, moved in zip(p0[valid, 0], p1[valid, 0], strict=True):
        if any(not radius <= p[0] < width - radius or not radius <= p[1] < height - radius
               for p in (initial, moved)):
            continue
        if not x1 <= moved[0] < x2 or not y1 <= moved[1] < y2:
            continue
        patches = [cv2.getRectSubPix(image, (patch_width, patch_width), tuple(map(float, point)))
                   for image, point in zip(gray, (initial, moved), strict=True)]
        if min(float(patch.std()) for patch in patches) < 1.0:
            continue
        score = float(cv2.matchTemplate(patches[0], patches[1], cv2.TM_CCOEFF_NORMED)[0, 0])
        if not math.isfinite(score):
            continue
        scores.append(score)
        if score >= method["descriptive_patch_ncc"]:
            result["descriptive_ncc_match_count"] += 1
            column = min(2, int((initial[0] - x1) * 3 / (x2 - x1)))
            row = min(2, int((initial[1] - y1) * 3 / (y2 - y1)))
            result["grid_match_counts"][row * 3 + column] += 1
    result["nonflat_patch_count"] = len(scores)
    if scores:
        result["patch_ncc"] = {"min": min(scores), "median": float(np.median(scores)),
                               "max": max(scores)}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("video", "raw-processing", "frames-root", "method", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--window", nargs=2, type=float, action="append", required=True)
    args = parser.parse_args()
    _check_output_privacy(args.output.resolve())
    video_hash, raw_hash, method_hash = map(sha256_file,
                                          (args.video, args.raw_processing, args.method))
    metadata = json.loads(args.raw_processing.with_name("run_metadata.json").read_bytes())
    if (metadata["metadata"]["source_sha256"] != video_hash
            or metadata["input_hashes"][args.raw_processing.name] != raw_hash):
        raise ValueError("source archive integrity mismatch")
    raw = json.loads(args.raw_processing.read_bytes())
    if raw.get("status") != "complete":
        raise ValueError("completed native archive required")
    method = load_method(args.method)
    windows = []
    for start, end in args.window:
        if not 0 <= start < end <= raw["video_metadata"]["duration_sec"]:
            raise ValueError("diagnostic window outside source")
        times = sorted({float(row["time_sec"]) for row in raw["observations"]
                        if start <= float(row["time_sec"]) <= end})
        if len(times) < 2:
            raise ValueError("at least two archived native observations required")
        samples, hashes = archived_frames(times, args.frames_root)
        pairs = []
        previous_image = None
        for i, sample in enumerate(samples):
            image = cv2.imdecode(np.frombuffer(sample.path.read_bytes(), np.uint8),
                                 cv2.IMREAD_COLOR)
            if i:
                pairs.append({"before_pts_sec": times[i - 1], "after_pts_sec": times[i],
                              **measure(previous_image, image, method)})
            previous_image = image
        if any(sha256_file(sample.path) != row["frame_sha256"]
               for sample, row in zip(samples, hashes, strict=True)):
            raise ValueError("source frames changed during measurement")
        windows.append({"window_sec": [start, end], "source_frames": hashes, "pairs": pairs})
    if [sha256_file(path) for path in (args.video, args.raw_processing, args.method)] != [
        video_hash, raw_hash, method_hash,
    ]:
        raise ValueError("measurement input changed")
    output = {"scope": __doc__, "source_video_sha256": video_hash,
              "raw_processing_sha256": raw_hash, "method_sha256": method_hash,
              "diagnostic_implementation_sha256": sha256_file(Path(__file__)),
              "method": method, "windows": windows, "qualification_created": False}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"windows": len(windows), "pairs": sum(len(w["pairs"]) for w in windows),
                      "qualification_created": False}))


if __name__ == "__main__":
    main()
