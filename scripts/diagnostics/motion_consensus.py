"""Out-of-region motion diagnostics, not a semantic background classifier.

A held-out region is not used to estimate the motion tested against its tracks.
High residual can also mean parallax/model mismatch. Low residual never proves
world background, content-time continuity, or player ownership.
"""

from __future__ import annotations

import cv2
import numpy as np


def measure_region_consensus(tracks):
    points_before = np.array([t["previous"] for t in tracks], dtype=float).reshape(-1, 2)
    points_after = np.array([t["current"] for t in tracks], dtype=float).reshape(-1, 2)
    regions = np.array([t["region"] for t in tracks])
    if (
        not np.isfinite(points_before).all()
        or not np.isfinite(points_after).all()
        or any(type(t["region"]) is not int or not 0 <= t["region"] < 6 for t in tracks)
    ):
        raise ValueError("finite source correspondences and six known regions required")
    result = []
    for region in range(6):
        test = regions == region
        train = ~test
        supporting_regions = sorted(set(regions[train].tolist()))
        model, mask = None, None
        if train.sum() >= 3 and len(supporting_regions) >= 2:
            cv2.setRNGSeed(0)
            model, mask = cv2.estimateAffinePartial2D(
                points_before[train].astype(np.float32),
                points_after[train].astype(np.float32),
                method=cv2.RANSAC,
                ransacReprojThreshold=2,
            )
        residuals = np.array([], dtype=float)
        if model is not None and test.any():
            predicted = points_before[test] @ model[:, :2].T + model[:, 2]
            residuals = np.linalg.norm(predicted - points_after[test], axis=1)
        result.append(
            {
                "region": region,
                "tested_tracks": int(test.sum()),
                "model_training_regions": supporting_regions,
                "model_training_tracks": int(train.sum()),
                "model_training_inliers": 0 if mask is None else int(mask.sum()),
                "out_of_region_affine": None if model is None else model.tolist(),
                "median_residual_px": None if not len(residuals) else float(np.median(residuals)),
                "p90_residual_px": None
                if not len(residuals)
                else float(np.quantile(residuals, 0.9)),
                "consistent_at_existing_2px": int((residuals <= 2).sum()),
                "unqualified": True,
            }
        )
    return result
