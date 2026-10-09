"""Background-only image diagnostics; never authorize runtime continuity/events.

Each local optical-flow pyramid and descriptor sees only its background crop.
Timer/phase labels and PTS are absent from measure_background_pair inputs.
Similar-looking scenes, duplicates and edits preserving a view require separate
content-time evidence. Metrics are descriptive, not a qualification report.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from fractions import Fraction
from pathlib import Path

import cv2
import numpy as np

BACKGROUND_BOXES_PX = (
    (500, 160, 640, 350),
    (520, 360, 850, 520),
    (30, 520, 500, 740),
    (1320, 160, 1700, 350),
    (1320, 370, 1700, 530),
    (520, 550, 800, 760),
)
SCALED_BACKGROUND_BOXES = tuple(tuple(round(v / 3) for v in box) for box in BACKGROUND_BOXES_PX)


def _prepare(image):
    if image is None or image.shape != (1080, 1920, 3) or image.dtype != np.uint8:
        raise ValueError("1920x1080 uint8 BGR source image required")
    return cv2.cvtColor(
        cv2.resize(image, (640, 360), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY
    )


def _ncc(a, b):
    if min(float(a.std()), float(b.std())) < 1:
        return None
    v = float(cv2.matchTemplate(a, b, cv2.TM_CCOEFF_NORMED)[0, 0])
    return v if np.isfinite(v) else None


def measure_background_pair(a, b, *, track_sink=None):
    a, b = (_prepare(a), _prepare(b))
    cv2.setRNGSeed(0)
    rois = []
    tracks = []
    dense = []
    orb_points_before = []
    orb_points_after = []
    corner_count = 0
    orb_total = 0
    for region, (x1, y1, x2, y2) in enumerate(SCALED_BACKGROUND_BOXES):
        u, v = (a[y1:y2, x1:x2], b[y1:y2, x1:x2])
        rois.append(
            {
                "region": region,
                "std_previous": float(u.std()),
                "std_current": float(v.std()),
                "ncc": _ncc(u, v),
                "mean_absolute_difference": float(np.abs(u.astype(float) - v).mean()),
            }
        )
        p = cv2.goodFeaturesToTrack(u, 100, 0.01, 5)
        if p is not None:
            corner_count += len(p)
            q, ok, _ = cv2.calcOpticalFlowPyrLK(u, v, p, None, winSize=(21, 21), maxLevel=3)
            back, ok2, _ = cv2.calcOpticalFlowPyrLK(v, u, q, None, winSize=(21, 21), maxLevel=3)
            for prev, cur, rev, yes, yes2 in zip(
                p.reshape(-1, 2),
                q.reshape(-1, 2),
                back.reshape(-1, 2),
                ok.ravel(),
                ok2.ravel(),
                strict=True,
            ):
                x, y = np.round(cur).astype(int)
                px, py = np.round(prev).astype(int)
                fb = float(np.linalg.norm(prev - rev))
                if (
                    not yes
                    or not yes2
                    or fb > 1
                    or (
                        not (
                            8 <= x < u.shape[1] - 8
                            and 8 <= y < u.shape[0] - 8
                            and (8 <= px < u.shape[1] - 8)
                            and (8 <= py < u.shape[0] - 8)
                        )
                    )
                ):
                    continue
                patch = _ncc(u[py - 7 : py + 8, px - 7 : px + 8], v[y - 7 : y + 8, x - 7 : x + 8])
                offset = np.array([x1, y1])
                tracks.append(
                    {
                        "previous": (prev + offset).tolist(),
                        "current": (cur + offset).tolist(),
                        "fb_error_px": fb,
                        "patch_ncc": patch,
                        "region": region,
                    }
                )
        flow = cv2.calcOpticalFlowFarneback(u, v, None, 0.5, 3, 15, 3, 5, 1.2, 0)
        dense.append(
            {
                "median_vector_px": np.median(flow.reshape(-1, 2), axis=0).tolist(),
                "magnitude_p90_px": float(np.quantile(np.linalg.norm(flow, axis=2), 0.9)),
            }
        )
        orb = cv2.ORB_create(nfeatures=250, edgeThreshold=15, patchSize=21)
        k1, d1 = orb.detectAndCompute(u, None)
        k2, d2 = orb.detectAndCompute(v, None)
        if d1 is not None and d2 is not None:
            matcher = cv2.BFMatcher(cv2.NORM_HAMMING)
            forward = matcher.knnMatch(d1, d2, k=2)
            reverse = matcher.knnMatch(d2, d1, k=2)
            reverse_good = {
                pair[0].queryIdx: pair[0].trainIdx
                for pair in reverse
                if len(pair) == 2 and pair[0].distance < 0.75 * pair[1].distance
            }
            matches = [
                pair[0]
                for pair in forward
                if len(pair) == 2
                and pair[0].distance < 0.75 * pair[1].distance
                and (reverse_good.get(pair[0].trainIdx) == pair[0].queryIdx)
            ]
            orb_total += len(matches)
            for m in matches:
                orb_points_before.append(np.array(k1[m.queryIdx].pt) + [x1, y1])
                orb_points_after.append(np.array(k2[m.trainIdx].pt) + [x1, y1])
    good = [t for t in tracks if t["patch_ncc"] is not None and t["patch_ncc"] >= 0.9]
    if track_sink is not None:
        track_sink.extend(good)
    aff, inliers = (None, None)
    oa, oi = (None, None)
    if len(good) >= 3:
        aff, inliers = cv2.estimateAffinePartial2D(
            np.float32([t["previous"] for t in good]),
            np.float32([t["current"] for t in good]),
            method=cv2.RANSAC,
            ransacReprojThreshold=2,
        )
    if orb_total >= 3:
        oa, oi = cv2.estimateAffinePartial2D(
            np.float32(orb_points_before),
            np.float32(orb_points_after),
            method=cv2.RANSAC,
            ransacReprojThreshold=2,
        )
    compensated = []
    for region, (x1, y1, x2, y2) in enumerate(SCALED_BACKGROUND_BOXES):
        previous_crop, current_crop = a[y1:y2, x1:x2], b[y1:y2, x1:x2]
        score = None
        valid_fraction = 0.0
        if aff is not None:
            local = aff.copy()
            offset = np.array([x1, y1], dtype=float)
            local[:, 2] += aff[:, :2] @ offset - offset
            size = (previous_crop.shape[1], previous_crop.shape[0])
            warped = cv2.warpAffine(previous_crop, local, size, flags=cv2.INTER_LINEAR)
            source_mask = np.full(previous_crop.shape, 255, dtype=np.uint8)
            valid = cv2.warpAffine(source_mask, local, size, flags=cv2.INTER_LINEAR) == 255
            valid[:8] = valid[-8:] = False
            valid[:, :8] = valid[:, -8:] = False
            valid_fraction = float(valid.mean())
            left, right = warped[valid].astype(float), current_crop[valid].astype(float)
            if len(left) >= 32 and min(float(left.std()), float(right.std())) >= 1:
                value = float(np.corrcoef(left, right)[0, 1])
                if np.isfinite(value):
                    score = value
        compensated.append(
            {
                "region": region,
                "ncc": score,
                "valid_fraction": valid_fraction,
                "scope": "crop-local warp only; descriptive, not occlusion qualification",
            }
        )
    return {
        "regions": rois,
        "motion_compensated_regions": compensated,
        "lk_corners": corner_count,
        "lk_bidirectional_tracks": len(tracks),
        "lk_patch_ncc_0_90_tracks": len(good),
        "lk_supported_regions": sorted({t["region"] for t in good}),
        "lk_affine": None if aff is None else aff.tolist(),
        "lk_affine_inliers": 0 if inliers is None else int(inliers.sum()),
        "lk_median_fb_error_px": None
        if not good
        else float(np.median([t["fb_error_px"] for t in good])),
        "orb_mutual_ratio_matches": orb_total,
        "orb_affine": None if oa is None else oa.tolist(),
        "orb_affine_inliers": 0 if oi is None else int(oi.sum()),
        "dense_flow_regions": dense,
    }


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(args):
    started = time.perf_counter()
    report_hash = sha256(args.source_report)
    script_hash = sha256(Path(__file__))
    data = json.loads(args.source_report.read_text())
    video_hash = sha256(args.video)
    if video_hash != data["source_video_sha256"]:
        raise ValueError("source video hash mismatch")
    if data.get("native_pts_coverage_verified") is not True:
        raise ValueError("native source coverage evidence required")
    rows = data["windows"][args.window_index]["rows"]
    if len(rows) < 2:
        raise ValueError("at least two source frames required")
    ticks = [Fraction(r["source_pts_ticks"]) * Fraction(r["time_base"]) for r in rows]
    if any(b - a != Fraction(1, 60) for a, b in zip(ticks, ticks[1:], strict=False)):
        raise ValueError("expected every native frame of this 60fps source interval")
    paths = [args.frames_root / f"frame_{i:06d}.png" for i in range(1, len(rows) + 1)]
    images = []
    for path, row in zip(paths, rows, strict=True):
        if sha256(path) != row["frame_sha256"]:
            raise ValueError("source image hash mismatch")
        image = cv2.imread(str(path))
        if (
            image is None
            or hashlib.sha256(image.tobytes()).hexdigest() != row["source_pixel_sha256"]
        ):
            raise ValueError("source decoded-pixel hash mismatch")
        images.append(image)
    measurements = []
    for i in range(1, len(images)):
        measurements.append(
            {
                "previous_source_pts_ticks": rows[i - 1]["source_pts_ticks"],
                "source_pts_ticks": rows[i]["source_pts_ticks"],
                "time_base": rows[i]["time_base"],
                "previous_frame_sha256": rows[i - 1]["frame_sha256"],
                "frame_sha256": rows[i]["frame_sha256"],
                "previous_pts_sec": float(ticks[i - 1]),
                "pts_sec": float(ticks[i]),
                "image_measurements": measure_background_pair(images[i - 1], images[i]),
            }
        )
    for path, row in zip(paths, rows, strict=True):
        if sha256(path) != row["frame_sha256"]:
            raise ValueError("source image changed")
    if (
        sha256(args.video) != video_hash
        or sha256(args.source_report) != report_hash
        or sha256(Path(__file__)) != script_hash
    ):
        raise ValueError("source/code binding changed")
    return {
        "scope": "background-only descriptive image correspondence; no runtime qualification",
        "source_video_sha256": video_hash,
        "source_report_sha256": report_hash,
        "script_sha256": script_hash,
        "background_boxes_px": BACKGROUND_BOXES_PX,
        "source_frames": len(images),
        "native_pts_coverage_verified": True,
        "rows": measurements,
        "runtime_events_generated": False,
        "qualification_created": False,
        "wall_clock_seconds": time.perf_counter() - started,
        "opencv_version": cv2.__version__,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-report", type=Path, required=True)
    parser.add_argument("--frames-root", type=Path, required=True)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--window-index", type=int, default=0)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output already exists; preserve frozen diagnostics")
    result = run(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"source_frames": result["source_frames"], "links": len(result["rows"])}))


if __name__ == "__main__":
    main()
