"""Image-only exploratory search for reviewed world patches outside their source crop.

No continuity authorization, timer, phase, timestamp or event is consumed or
produced. Candidate destinations are restricted to supplied non-UI crops.
Only unique NCC>=0.90 matches with reciprocal correspondence are retained;
image similarity still does not certify uninterrupted gameplay time.
"""

from __future__ import annotations

import cv2
import numpy as np


def _validate(image, boxes):
    if image.dtype != np.uint8 or image.shape != (360, 640):
        raise ValueError("canonical grayscale uint8 image required")
    if not boxes:
        raise ValueError("explicit non-UI crops required")
    for x1, y1, x2, y2 in boxes:
        if not (0 <= x1 < x2 <= 640 and 0 <= y1 < y2 <= 360):
            raise ValueError("crop outside image")
        # Exclude the entire top clock/score band and padded phase/result area.
        if y1 < 28 or (x1 < 416 and x2 > 224 and y1 < 120 and y2 > 28):
            raise ValueError("search crop intersects protected timer/phase pixels")
        if min(x2 - x1, y2 - y1) < 32:
            raise ValueError("crop too small")


def reviewed_patches(reference, boxes):
    _validate(reference, boxes)
    result = []
    for region, (x1, y1, x2, y2) in enumerate(boxes):
        crop = reference[y1:y2, x1:x2]
        points = cv2.goodFeaturesToTrack(crop, 100, 0.01, 5)
        if points is None:
            continue
        for point in points.reshape(-1, 2):
            x, y = np.round(point).astype(int)
            if not (8 <= x < crop.shape[1] - 8 and 8 <= y < crop.shape[0] - 8):
                continue
            patch = crop[y - 7 : y + 8, x - 7 : x + 8].copy()
            if float(patch.std()) >= 1:
                result.append((region, [int(x + x1), int(y + y1)], patch))
    return result


def unique_match(patch, image, boxes, *, reason_sink=None):
    """Reject a second distinct >=0.90 peak, including across search crops."""
    candidates = []

    def reject(reason):
        if reason_sink is not None:
            reason_sink.append(reason)
        return None

    for x1, y1, x2, y2 in boxes:
        crop = image[y1:y2, x1:x2]
        values = cv2.matchTemplate(crop, patch, cv2.TM_CCOEFF_NORMED)
        if not np.isfinite(values).all():
            continue
        _, best, _, (x, y) = cv2.minMaxLoc(values)
        if best < 0.90:
            continue
        # Adjacent locations describe the same subpixel feature. All farther
        # peaks remain competing correspondences, never silently discarded.
        values[max(0, y - 2) : y + 3, max(0, x - 2) : x + 3] = -1
        runner_up = float(values.max())
        if runner_up >= 0.90:
            return reject("ambiguous_second_peak")
        candidates.append((float(best), [x + 7 + x1, y + 7 + y1]))
    if len(candidates) != 1:
        return reject("no_ncc_qualified_peak" if not candidates else "multiple_search_regions")
    return candidates[0]


def search_reviewed_world(reference, current, boxes, *, patches=None, rejection_sink=None):
    _validate(reference, boxes)
    _validate(current, boxes)
    if patches is None:
        patches = reviewed_patches(reference, boxes)
    tracks = []
    for region, position, patch in patches:
        reasons = []
        match = unique_match(patch, current, boxes, reason_sink=reasons)
        if match is None:
            if rejection_sink is not None:
                rejection_sink.append({"stage": "forward", "reason": reasons[0], "region": region})
            continue
        score, (x, y) = match
        current_patch = current[y - 7 : y + 8, x - 7 : x + 8]
        if float(current_patch.std()) < 1:
            continue
        reasons = []
        reverse = unique_match(current_patch, reference, boxes, reason_sink=reasons)
        if reverse is None:
            if rejection_sink is not None:
                rejection_sink.append({"stage": "reverse", "reason": reasons[0], "region": region})
            continue
        distance = float(np.linalg.norm(np.array(reverse[1]) - position))
        if distance > 1:
            if rejection_sink is not None:
                rejection_sink.append(
                    {"stage": "reverse", "reason": "reciprocal_error", "region": region}
                )
            continue
        tracks.append(
            {
                "region": region,
                "reference_xy": position,
                "current_xy": [x, y],
                "patch_ncc": score,
                "fb_error_px": distance,
                "model_inlier": False,
            }
        )
    model, inliers = None, None
    if len(tracks) >= 3 and len({t["region"] for t in tracks}) >= 3:
        cv2.setRNGSeed(0)
        model, inliers = cv2.estimateAffinePartial2D(
            np.float32([t["reference_xy"] for t in tracks]),
            np.float32([t["current_xy"] for t in tracks]),
            method=cv2.RANSAC,
            ransacReprojThreshold=2,
        )
        if model is None or not np.isfinite(model).all():
            model, inliers = None, None
    if inliers is not None:
        for track, value in zip(tracks, inliers.reshape(-1), strict=True):
            track["model_inlier"] = bool(value)
    return {
        "accepted_reference_tracks": len(tracks),
        "model_inliers": sum(t["model_inlier"] for t in tracks),
        "track_regions": sorted({t["region"] for t in tracks}),
        "reference_to_current_affine": None if model is None else model.tolist(),
        "runtime_proof_authorized": False,
    }, tracks
