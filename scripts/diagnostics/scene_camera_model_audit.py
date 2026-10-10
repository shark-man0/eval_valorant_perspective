"""Shadow source-camera model residuals on one fixed correspondence population.

No image, clock, phase, PTS, expected value or event enters this interface.
Fits are diagnostic: neither consensus nor a more flexible fit qualifies a
world correspondence, scene continuity, HUD geometry or runtime boundary.
"""

from __future__ import annotations

import cv2
import numpy as np


def _summary(matrix, mask, source, target, regions, tolerance):
    if matrix is None or mask is None or not np.isfinite(matrix).all():
        return {"available": False, "descriptive_geometric_quorum": False}
    homogeneous = np.column_stack([source, np.ones(len(source))])
    transform = np.vstack([matrix, [0, 0, 1]]) if matrix.shape == (2, 3) else matrix
    projected = homogeneous @ transform.T
    if np.linalg.matrix_rank(transform) < 3 or (np.abs(projected[:, 2]) < 1e-8).any():
        return {"available": False, "descriptive_geometric_quorum": False}
    predicted = projected[:, :2] / projected[:, 2, None]
    residuals = np.linalg.norm(predicted - target, axis=1)
    if not np.isfinite(residuals).all():
        return {"available": False, "descriptive_geometric_quorum": False}
    within = residuals <= tolerance
    supported_regions = sorted(set(regions[within].tolist()))
    # Report both actual final-model residual support and the estimator's mask;
    # RANSAC masks are not silently assumed equal after model refinement.
    regional = []
    for region in sorted(set(regions.tolist())):
        local = residuals[regions == region]
        regional.append(
            {
                "region": region,
                "points": len(local),
                "median_residual_px": float(np.median(local)),
                "maximum_residual_px": float(local.max()),
                "within_floor": int((local <= tolerance).sum()),
            }
        )
    full_rank = (
        np.linalg.matrix_rank(source - source.mean(axis=0)) == 2
        and np.linalg.matrix_rank(target - target.mean(axis=0)) == 2
    )
    return {
        "available": True,
        "matrix": matrix.tolist(),
        "ransac_inliers": int(mask.sum()),
        "final_residual_inliers": int(within.sum()),
        "supported_seed_regions": supported_regions,
        "regions": regional,
        "full_rank_correspondences": bool(full_rank),
        "descriptive_geometric_quorum": bool(
            full_rank and within.sum() >= 0.90 * len(source) and len(supported_regions) >= 3
        ),
        "runtime_proof_authorized": False,
    }


def audit_world_models(cloud, *, scale=1):
    if type(scale) is not int or scale not in {1, 3}:
        raise ValueError("canonical or native scale required")
    source = np.float32(cloud["seed_points"])
    target = np.float32(cloud["current_points"])
    regions = np.asarray(cloud["regions"])
    if (
        source.ndim != 2
        or source.shape[1:] != (2,)
        or source.shape != target.shape
        or len(source) < 3
        or regions.shape != (len(source),)
        or not np.isfinite(source).all()
        or not np.isfinite(target).all()
        or not np.issubdtype(regions.dtype, np.integer)
        or (regions < 0).any()
    ):
        raise ValueError("finite paired points and seed-region IDs required")
    tolerance = 2 * scale
    cv2.setRNGSeed(0)
    similarity, similar_mask = cv2.estimateAffinePartial2D(
        source, target, method=cv2.RANSAC, ransacReprojThreshold=tolerance
    )
    original = cloud.get("original_partial_affine")
    if original is not None and not np.array_equal(similarity, np.asarray(original)):
        raise ValueError("original similarity fit not exactly reproduced")
    original_mask = cloud.get("original_inliers")
    if original_mask is not None and (
        similar_mask is None or not np.array_equal(similar_mask.ravel(), np.asarray(original_mask))
    ):
        raise ValueError("original similarity mask not exactly reproduced")
    cv2.setRNGSeed(0)
    affine, affine_mask = cv2.estimateAffine2D(
        source, target, method=cv2.RANSAC, ransacReprojThreshold=tolerance
    )
    cv2.setRNGSeed(0)
    homography, homography_mask = (
        cv2.findHomography(source, target, cv2.RANSAC, tolerance)
        if len(source) >= 4
        else (None, None)
    )
    return {
        "scope": "Shadow fits only; same immutable candidate correspondences",
        "points": len(source),
        "canonical_residual_floor_px": 2,
        "pixel_residual_floor": tolerance,
        "similarity": _summary(similarity, similar_mask, source, target, regions, tolerance),
        "affine": _summary(affine, affine_mask, source, target, regions, tolerance),
        "homography": _summary(homography, homography_mask, source, target, regions, tolerance),
        "runtime_proof_authorized": False,
    }
