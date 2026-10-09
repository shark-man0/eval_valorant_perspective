"""Reference-attested visible background diagnostics; not runtime qualification.

Reference boxes must be independently reviewed as world background. Local
tracking pyramids never see pixels outside those boxes. A correspondence model
cannot label new backgrounds, foreground, or uninterrupted game time. Changed
views safely abstain. This module does not read timers, phases, PTS or GT.
"""

from __future__ import annotations

import cv2
import numpy as np


def measure_reference_support(
    reference,
    current,
    boxes,
    *,
    model_scope="global",
    model_family="partial_affine",
    track_sink=None,
):
    if model_scope not in {"global", "region"}:
        raise ValueError("known descriptive model scope required")
    if model_family not in {"partial_affine", "homography"}:
        raise ValueError("known descriptive model family required")

    def fit(selected):
        minimum = 4 if model_family == "homography" else 3
        if len(selected) < minimum:
            return None, None
        before, after = np.float32([t[1] for t in selected]), np.float32([t[2] for t in selected])
        cv2.setRNGSeed(0)
        if model_family == "homography":
            fitted, support = cv2.findHomography(before, after, cv2.RANSAC, 2)
        else:
            fitted, support = cv2.estimateAffinePartial2D(
                before, after, method=cv2.RANSAC, ransacReprojThreshold=2
            )
        if fitted is not None and not np.isfinite(fitted).all():
            return None, None
        return fitted, support

    if (
        reference.dtype != np.uint8
        or current.dtype != np.uint8
        or reference.ndim != 2
        or current.shape != reference.shape
        or not boxes
    ):
        raise ValueError("same-size grayscale source arrays and reviewed boxes required")
    for box in boxes:
        if (
            len(box) != 4
            or any(type(v) is not int for v in box)
            or not (0 <= box[0] < box[2] <= reference.shape[1])
            or not (0 <= box[1] < box[3] <= reference.shape[0])
            or min(box[2] - box[0], box[3] - box[1]) < 32
        ):
            raise ValueError("reviewed crop coordinates/size invalid")
    tracks = []
    track_quality = []
    for region, (x1, y1, x2, y2) in enumerate(boxes):
        left, right = reference[y1:y2, x1:x2], current[y1:y2, x1:x2]
        points = cv2.goodFeaturesToTrack(left, 100, 0.01, 5)
        if points is None:
            continue
        forward, ok, _ = cv2.calcOpticalFlowPyrLK(
            left, right, points, None, winSize=(21, 21), maxLevel=3
        )
        if forward is None:
            continue
        reverse, back_ok, _ = cv2.calcOpticalFlowPyrLK(
            right, left, forward, None, winSize=(21, 21), maxLevel=3
        )
        if reverse is None:
            continue
        for before, after, back, yes, back_yes in zip(
            points.reshape(-1, 2),
            forward.reshape(-1, 2),
            reverse.reshape(-1, 2),
            ok.ravel(),
            back_ok.ravel(),
            strict=True,
        ):
            if not yes or not back_yes or not np.isfinite([before, after, back]).all():
                continue
            if np.linalg.norm(before - back) > 1:
                continue
            px, py = np.round(before).astype(int)
            qx, qy = np.round(after).astype(int)
            if not (
                8 <= px < left.shape[1] - 8
                and 8 <= qx < left.shape[1] - 8
                and 8 <= py < left.shape[0] - 8
                and 8 <= qy < left.shape[0] - 8
            ):
                continue
            a, b = left[py - 7 : py + 8, px - 7 : px + 8], right[qy - 7 : qy + 8, qx - 7 : qx + 8]
            if min(float(a.std()), float(b.std())) < 1:
                continue
            ncc = float(cv2.matchTemplate(a, b, cv2.TM_CCOEFF_NORMED)[0, 0])
            if np.isfinite(ncc) and ncc >= 0.90:
                tracks.append((region, before + [x1, y1], after + [x1, y1]))
                track_quality.append((ncc, float(np.linalg.norm(before - back))))
    model, inliers = None, None
    supported_regions = sorted({t[0] for t in tracks})
    if len(tracks) >= 3 and len(supported_regions) >= 3:
        model, inliers = fit(tracks)
    if track_sink is not None:
        for i, (region, before, after) in enumerate(tracks):
            track_sink.append(
                {
                    "region": region,
                    "reference_xy": before.tolist(),
                    "current_xy": after.tolist(),
                    "patch_ncc": track_quality[i][0],
                    "fb_error_px": track_quality[i][1],
                    "model_inlier": inliers is not None and bool(inliers.reshape(-1)[i]),
                }
            )
    regions = []
    for region, (x1, y1, x2, y2) in enumerate(boxes):
        left, right = reference[y1:y2, x1:x2], current[y1:y2, x1:x2]
        score, coverage = None, 0.0
        valid_pixels = 0
        warp_model = model
        local_tracks = [t for t in tracks if t[0] == region]
        if model_scope == "region":
            warp_model, _ = fit(local_tracks)
        if warp_model is not None:
            local = warp_model.copy()
            offset = np.array([x1, y1], dtype=float)
            if model_family == "homography":
                origin = np.eye(3)
                origin[:2, 2] = offset
                target = np.eye(3)
                target[:2, 2] = -offset
                local = target @ warp_model @ origin
                warp = cv2.warpPerspective
            else:
                local[:, 2] += warp_model[:, :2] @ offset - offset
                warp = cv2.warpAffine
            size = (left.shape[1], left.shape[0])
            aligned = warp(left, local, size, flags=cv2.INTER_LINEAR)
            valid = (
                warp(np.full(left.shape, 255, np.uint8), local, size, flags=cv2.INTER_LINEAR) == 255
            )
            interior = np.zeros(left.shape, bool)
            interior[8:-8, 8:-8] = True
            valid &= interior
            valid_pixels = int(valid.sum())
            coverage = valid_pixels / int(interior.sum())
            a, b = aligned[valid].astype(float), right[valid].astype(float)
            if len(a) >= 32 and min(float(a.std()), float(b.std())) >= 1:
                value = float(np.corrcoef(a, b)[0, 1])
                if np.isfinite(value):
                    score = value
        regions.append(
            {
                "region": region,
                "model_scope": model_scope,
                "region_reference_tracks": len(local_tracks),
                "warp_model": None if warp_model is None else warp_model.tolist(),
                "ncc": score,
                "valid_pixels": valid_pixels,
                "interior_valid_fraction": coverage,
                "reference_supported_descriptive": (
                    score is not None
                    and score >= 0.90
                    and coverage >= 0.90
                    and region in supported_regions
                ),
            }
        )
    result = {
        "regions": regions,
        "accepted_reference_tracks": len(tracks),
        "track_regions": supported_regions,
        "reference_to_current_affine": (
            None if model is None or model_family == "homography" else model.tolist()
        ),
        "model_inliers": 0 if inliers is None else int(inliers.sum()),
        "scope": "Reviewed reference background correspondence only; unqualified",
        "runtime_proof_authorized": False,
    }
    if model_family == "homography":
        result["model_family"] = model_family
        result["reference_to_current_homography"] = None if model is None else model.tolist()
    return result
