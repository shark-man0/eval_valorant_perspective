"""Diagnostic descriptor projection followed by unchanged appearance gates.

Descriptors only propose geometry. No descriptor score authorizes continuity,
semantic world masks, player ownership, temporal history or production proof.
"""

from __future__ import annotations

import math

import cv2
import numpy as np

from scripts.diagnostics.scene_domain_ambiguity import domain_displacement_audit
from scripts.diagnostics.scene_joint_domains import joint_domain_audit
from scripts.diagnostics.scene_patch_search import _validate
from scripts.diagnostics.scene_world_chain import _ncc


def _descriptors(image, boxes, *, feature_source="sift"):
    if feature_source == "spatial_corners":
        return _spatial_descriptors(image, boxes)
    if feature_source not in {"sift", "reviewed_corners"}:
        raise ValueError("explicit known source feature representation required")
    points, descriptors = [], []
    sift = cv2.SIFT_create(nfeatures=500, edgeThreshold=15)
    for region, (x1, y1, x2, y2) in enumerate(boxes):
        # Build pyramids from each declared crop only; no outside image
        # pixels can become reference support or current candidate context.
        crop = image[y1:y2, x1:x2]
        if feature_source == "reviewed_corners":
            corners = cv2.goodFeaturesToTrack(crop, 100, 0.01, 5)
            if corners is None:
                continue
            # Preserve the existing corner proposal detector. A fixed-scale,
            # fixed-orientation descriptor only proposes correspondence;
            # projected NCC still verifies actual rotated/scaled appearance.
            keys = [cv2.KeyPoint(float(x), float(y), 3, 0) for x, y in corners.reshape(-1, 2)]
            keys, values = sift.compute(crop, keys)
        else:
            keys, values = sift.detectAndCompute(crop, None)
        if values is None:
            continue
        for key, descriptor in zip(keys, values, strict=True):
            x, y = key.pt
            margin = max(8, math.ceil(3 * key.size))
            if margin <= x < x2 - x1 - margin and margin <= y < y2 - y1 - margin:
                points.append((region, [x + x1, y + y1]))
                descriptors.append(descriptor)
    return points, np.asarray(descriptors, np.float32).reshape(-1, 128)


def _spatial_descriptors(image, boxes):
    """Local proposal coverage with identical 19px descriptor input contexts.

    Candidate budgets/quality/distance apply per 64px tile, not globally.
    Overlaps deduplicate physical points; they do not add independent witnesses.
    """
    points, descriptors, seen = [], [], set()
    sift = cv2.SIFT_create(nfeatures=500, edgeThreshold=15)
    for region, (x1, y1, x2, y2) in enumerate(boxes):
        for top in range(y1, y2, 32):
            for left in range(x1, x2, 32):
                tile = image[top : min(top + 64, y2), left : min(left + 64, x2)]
                if min(tile.shape) < 19:
                    continue
                corners = cv2.goodFeaturesToTrack(tile, 100, 0.01, 5)
                if corners is None:
                    continue
                for dx, dy in corners.reshape(-1, 2):
                    x, y = int(dx) + left, int(dy) + top
                    if (x, y) in seen or not (x1 + 9 <= x < x2 - 9 and y1 + 9 <= y < y2 - 9):
                        continue
                    # Exact, fully observed context, independent of tile/crop
                    # boundary; library pyramid extension is not extra support.
                    crop = image[y - 9 : y + 10, x - 9 : x + 10]
                    _, values = sift.compute(crop, [cv2.KeyPoint(9, 9, 3, 0)])
                    if values is not None:
                        seen.add((x, y))
                        points.append((region, [float(x), float(y)]))
                        descriptors.append(values[0])
    return points, np.asarray(descriptors, np.float32).reshape(-1, 128)


def _distinct_correspondences(tracks):
    """Multiple SIFT orientations at one location are one physical witness."""
    pairs, destinations, origins = {}, {}, {}
    for track in tracks:
        origin = tuple(round(v, 2) for v in track["reference_xy"])
        destination = tuple(round(v, 2) for v in track["current_xy"])
        if (
            origin in destinations and destinations[origin] != destination
            or destination in origins and origins[destination] != origin
        ):
            return None  # Never select a preferred conflicting correspondence.
        destinations[origin] = destination
        origins[destination] = origin
        pairs.setdefault((origin, destination), track)
    return list(pairs.values())


def descriptor_domain_proposal(
    reference, current, source_boxes, current_boxes, *, feature_source="sift"
):
    _validate(reference, source_boxes)
    _validate(current, current_boxes)
    before, source = _descriptors(reference, source_boxes, feature_source=feature_source)
    after, target = _descriptors(current, current_boxes, feature_source=feature_source)
    result = {
        "scope": "descriptor geometry proposal plus fixed-domain appearance; diagnostic only",
        "source_descriptors": len(source),
        "current_descriptors": len(target),
        "tracks": [],
        "model": None,
        "model_inliers": 0,
        "domains": None,
        "joint": None,
        "diagnostic_initialization_proposed": False,
        "runtime_proof_authorized": False,
        "world_mask_authorized": False,
        "qualification_created": False,
    }
    if feature_source != "sift":
        result["feature_source"] = feature_source
        result["descriptor_context"] = (
            "fixed size3/orientation0, exact19px context; per64px tile GFTT100/0.01/5 stride32"
            if feature_source == "spatial_corners"
            else "fixed size3/orientation0, inside declared crop"
        )
    if min(len(source), len(target)) < 2:
        return {**result, "reason": "descriptor_support_unavailable"}
    matcher = cv2.BFMatcher(cv2.NORM_L2)
    forward = matcher.knnMatch(source, target, k=2)
    reverse = matcher.knnMatch(target, source, k=2)

    def unique(pair):
        # Fixed proposal-stage ambiguity screen, not an NCC safety score.
        return len(pair) == 2 and pair[0].distance < 0.75 * pair[1].distance

    used = set()
    for index, pair in enumerate(forward):
        if not unique(pair):
            continue
        destination = pair[0].trainIdx
        back = reverse[destination]
        if not unique(back) or back[0].trainIdx != index or destination in used:
            continue
        used.add(destination)
        result["tracks"].append(
            {
                "region": before[index][0],
                "reference_xy": before[index][1],
                "current_xy": after[destination][1],
                "descriptor_distance": float(pair[0].distance),
            }
        )
    result["descriptor_matches"] = len(result["tracks"])
    distinct = _distinct_correspondences(result["tracks"])
    if distinct is None:
        return {**result, "reason": "ambiguous_physical_descriptor_correspondence"}
    result["tracks"] = distinct
    tracks = distinct
    if len(tracks) < 3 or len({p["region"] for p in tracks}) < 3:
        return {**result, "reason": "three_region_descriptor_support_unavailable"}
    cv2.setRNGSeed(0)
    model, support = cv2.estimateAffinePartial2D(
        np.float32([p["reference_xy"] for p in tracks]),
        np.float32([p["current_xy"] for p in tracks]),
        method=cv2.RANSAC,
        ransacReprojThreshold=2,
    )
    if model is None or not np.isfinite(model).all() or support is None:
        return {**result, "reason": "source_camera_model_unavailable"}
    result["model"] = model.tolist()
    result["model_inliers"] = int(support.sum())
    if result["model_inliers"] < 0.90 * len(tracks):
        return {**result, "reason": "source_camera_model_incoherent"}
    allowed = np.zeros(current.shape, np.float32)
    for x1, y1, x2, y2 in current_boxes:
        allowed[y1:y2, x1:x2] = 1
    verified = []
    for track, inlier in zip(tracks, support.reshape(-1), strict=True):
        x, y = np.round(track["reference_xy"]).astype(int)
        yy, xx = np.mgrid[y - 7 : y + 8, x - 7 : x + 8]
        mx = (model[0, 0] * xx + model[0, 1] * yy + model[0, 2]).astype(np.float32)
        my = (model[1, 0] * xx + model[1, 1] * yy + model[1, 2]).astype(np.float32)
        valid = cv2.remap(allowed, mx, my, cv2.INTER_LINEAR)
        score = None
        if (valid == 1.0).all():
            aligned = cv2.remap(current, mx, my, cv2.INTER_LINEAR)
            score = _ncc(reference[y - 7 : y + 8, x - 7 : x + 8], aligned)
        track["projected_patch_ncc"] = score
        track["model_inlier"] = bool(inlier)
        if inlier and score is not None and score >= 0.90:
            verified.append(track)
    result["photometric_inliers"] = len(verified)
    if len(verified) < 0.90 * len(tracks) or len({p["region"] for p in verified}) < 3:
        return {**result, "reason": "projected_patch_support_unavailable"}
    # Descriptor support cannot bypass the complete domain NCC>=0.90,
    # protected/current footprint, distributed support or ambiguity gates.
    measurements = []
    result["domains"] = domain_displacement_audit(
        reference,
        current,
        source_boxes,
        model,
        offset_sink=measurements,
        allowed_current_boxes=current_boxes,
    )
    result["joint"] = joint_domain_audit(source_boxes, model, measurements)
    result["diagnostic_initialization_proposed"] = result["joint"][
        "locally_unique_joint_appearance"
    ]
    result["reason"] = (
        "diagnostic_descriptor_domain_proposal"
        if result["diagnostic_initialization_proposed"]
        else "complete_joint_appearance_unavailable"
    )
    return result
