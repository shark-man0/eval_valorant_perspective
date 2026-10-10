"""Shared image-only source acquisition calculations; no runtime authorization.

Reviewed reference support, fixed source crops and unique reciprocal patch search
retain all existing acceptance/ambiguity conditions. PTS, phase, timer, GT and OS
are absent from this layer; its results cannot authorize semantic world masks.
"""

from __future__ import annotations

from typing import Any, cast

import cv2
import numpy as np

from .scene_domains import Boxes, ImageU8, _validate


def reviewed_patches(reference: ImageU8, boxes: Boxes) -> list[Any]:
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


def unique_match(
    patch: ImageU8,
    image: ImageU8,
    boxes: Boxes,
    *,
    reason_sink: list[str] | None = None,
) -> Any:
    """Reject a second distinct >=0.90 peak, including across search crops."""
    candidates = []

    def reject(reason: str) -> None:
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


def search_reviewed_world(
    reference: ImageU8,
    current: ImageU8,
    boxes: Boxes,
    *,
    patches: Any = None,
    rejection_sink: list[dict[str, Any]] | None = None,
    current_boxes: Boxes | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    _validate(reference, boxes)
    destinations = boxes if current_boxes is None else current_boxes
    _validate(current, destinations)
    if patches is None:
        patches = reviewed_patches(reference, boxes)
    tracks = []
    for region, position, patch in patches:
        reasons: list[str] = []
        match = unique_match(patch, current, destinations, reason_sink=reasons)
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
        model, inliers = cast(Any, cv2.estimateAffinePartial2D)(
            cast(Any, np.float32)([t["reference_xy"] for t in tracks]),
            cast(Any, np.float32)([t["current_xy"] for t in tracks]),
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


def measure_reference_support(
    reference: ImageU8,
    current: ImageU8,
    boxes: Boxes,
    *,
    model_scope: str = "global",
    model_family: str = "partial_affine",
    track_sink: list[dict[str, Any]] | None = None,
    rejection_sink: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if model_scope not in {"global", "region"}:
        raise ValueError("known descriptive model scope required")
    if model_family not in {"partial_affine", "homography"}:
        raise ValueError("known descriptive model family required")

    def fit(selected: list[Any]) -> tuple[Any, Any]:
        minimum = 4 if model_family == "homography" else 3
        if len(selected) < minimum:
            return None, None
        before, after = (
            cast(Any, np.float32)([t[1] for t in selected]),
            cast(Any, np.float32)([t[2] for t in selected]),
        )
        cv2.setRNGSeed(0)
        if model_family == "homography":
            fitted, support = cast(Any, cv2.findHomography)(before, after, cv2.RANSAC, 2)
        else:
            fitted, support = cast(Any, cv2.estimateAffinePartial2D)(
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
        counts = {
            "region": region,
            "source_features": 0,
            "forward_unavailable": 0,
            "reverse_unavailable": 0,
            "invalid_flow": 0,
            "forward_backward_rejected": 0,
            "patch_outside_crop": 0,
            "texture_unavailable": 0,
            "patch_ncc_rejected": 0,
            "accepted": 0,
        }
        if rejection_sink is not None:
            rejection_sink.append(counts)
        left, right = reference[y1:y2, x1:x2], current[y1:y2, x1:x2]
        points = cv2.goodFeaturesToTrack(left, 100, 0.01, 5)
        if points is None:
            continue
        counts["source_features"] = len(points)
        forward, ok, _ = cast(Any, cv2.calcOpticalFlowPyrLK)(
            left, right, points, None, winSize=(21, 21), maxLevel=3
        )
        if forward is None:
            counts["forward_unavailable"] = len(points)
            continue
        reverse, back_ok, _ = cast(Any, cv2.calcOpticalFlowPyrLK)(
            right, left, forward, None, winSize=(21, 21), maxLevel=3
        )
        if reverse is None:
            counts["reverse_unavailable"] = len(points)
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
                counts["invalid_flow"] += 1
                continue
            if np.linalg.norm(before - back) > 1:
                counts["forward_backward_rejected"] += 1
                continue
            px, py = np.round(before).astype(int)
            qx, qy = np.round(after).astype(int)
            if not (
                8 <= px < left.shape[1] - 8
                and 8 <= qx < left.shape[1] - 8
                and 8 <= py < left.shape[0] - 8
                and 8 <= qy < left.shape[0] - 8
            ):
                counts["patch_outside_crop"] += 1
                continue
            a, b = left[py - 7 : py + 8, px - 7 : px + 8], right[qy - 7 : qy + 8, qx - 7 : qx + 8]
            if min(float(a.std()), float(b.std())) < 1:
                counts["texture_unavailable"] += 1
                continue
            ncc = float(cv2.matchTemplate(a, b, cv2.TM_CCOEFF_NORMED)[0, 0])
            if np.isfinite(ncc) and ncc >= 0.90:
                tracks.append((region, before + [x1, y1], after + [x1, y1]))
                track_quality.append((ncc, float(np.linalg.norm(before - back))))
                counts["accepted"] += 1
            else:
                counts["patch_ncc_rejected"] += 1
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
    result: dict[str, Any] = {
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
