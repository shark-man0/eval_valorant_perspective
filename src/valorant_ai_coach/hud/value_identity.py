"""Role-bounded, value-invariant current-frame HUD scaffold evidence.

Configured support areas exclude text BEFORE contrast normalization and edge
extraction. Every spatial support group must pass .90 in both directions.
"""

from __future__ import annotations

from typing import Any

import cv2
import numpy as np

from .weapon_identity import oriented_matches, similarity_distribution, structural_layout

MATCHER = "value_invariant_edges_v1"


def support_regions(
    shape: tuple[int, int], spec: dict[str, Any], neighbor_bounds: list[list[float]]
) -> np.ndarray:
    h, w = shape
    intended = spec["intended_bounds"]
    areas = spec["support_bounds"]
    if not 2 <= len(areas) <= 4:
        raise ValueError("identity requires two to four separate scaffold groups")
    for box in [intended, *areas, *spec.get("dynamic_bounds", []), *neighbor_bounds]:
        if len(box) != 4 or not all(np.isfinite(v) for v in box):
            raise ValueError("invalid structure bounds")
        if not (0 <= box[0] < box[2] <= 1 and 0 <= box[1] < box[3] <= 1):
            raise ValueError("invalid structure bounds")
    regions = np.zeros(shape, np.uint8)
    for index, box in enumerate(areas, 1):
        if not (
            intended[0] <= box[0] < box[2] <= intended[2]
            and intended[1] <= box[1] < box[3] <= intended[3]
        ):
            raise ValueError("support outside intended role")
        x1, y1, x2, y2 = [round(v * (w if j % 2 == 0 else h)) for j, v in enumerate(box)]
        if min(x2 - x1, y2 - y1) < 8 or np.any(regions[y1:y2, x1:x2]):
            raise ValueError("invalid or overlapping scaffold groups")
        regions[y1:y2, x1:x2] = index
    for box in [*spec.get("dynamic_bounds", []), *neighbor_bounds]:
        x1, y1, x2, y2 = [round(v * (w if j % 2 == 0 else h)) for j, v in enumerate(box)]
        regions[y1:y2, x1:x2] = 0
    if set(np.unique(regions)) != set(range(len(areas) + 1)):
        raise ValueError("scaffold group obscured by excluded content")
    return regions


def isolated_features(image: np.ndarray, regions: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    edges = np.zeros(gray.shape, bool)
    angles = np.zeros(gray.shape, float)
    if gray.shape != regions.shape:
        return edges, angles
    for group in range(1, int(regions.max()) + 1):
        selected = regions == group
        values = gray[selected]
        if not values.size or float(values.std()) < 5:
            continue
        # HUD scaffold is a narrow bright ridge. Suppress broad background
        # shading before derivatives; neither dynamic digits nor another group
        # participate in this filtering or its normalization.
        isolated = np.full(gray.shape, float(np.median(values)), dtype=np.uint8)
        isolated[selected] = gray[selected]
        ridges = cv2.morphologyEx(isolated, cv2.MORPH_TOPHAT, np.ones((7, 7), np.uint8))
        ridge_values = ridges[selected]
        low, high = np.percentile(ridge_values, [5, 95])
        if high - low < 8:
            low, high = float(ridge_values.min()), float(ridge_values.max())
        if high - low < 8:
            continue
        normalized = np.clip((ridges.astype(float) - low) * 255 / (high - low), 0, 255).astype(
            np.uint8
        )
        # Three-pixel guard rejects derivative artifacts at configured boundaries.
        # It does not expand the existing one-pixel matching displacement.
        # Binarize narrow ridges within this support group, so the gradient
        # orientation describes the HUD contour rather than background shading.
        threshold, _ = cv2.threshold(
            normalized[selected].reshape(-1, 1), 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU
        )
        normalized = np.where(selected & (normalized > threshold), 255, 0).astype(np.uint8)
        valid = cv2.erode(selected.astype(np.uint8), np.ones((7, 7), np.uint8)) > 0
        current = (normalized > 0) & valid
        count, components, statistics, _ = cv2.connectedComponentsWithStats(
            current.astype(np.uint8), connectivity=8
        )
        keep = np.zeros(count, bool)
        keep[1:] = statistics[1:, cv2.CC_STAT_AREA] >= 8
        current = keep[components]
        normalized = current.astype(np.uint8) * 255
        # Compare the bright ridge itself, not two unstable anti-aliased contours.
        # Local structure-tensor orientation describes its unsigned normal; this
        # remains defined inside narrow strokes and is stable under compression.
        blurred = cv2.GaussianBlur(normalized, (3, 3), 0.6)
        gx = cv2.Sobel(blurred, cv2.CV_64F, 1, 0)
        gy = cv2.Sobel(blurred, cv2.CV_64F, 0, 1)
        xx = cv2.GaussianBlur(gx * gx, (5, 5), 1)
        yy = cv2.GaussianBlur(gy * gy, (5, 5), 1)
        xy = cv2.GaussianBlur(gx * gy, (5, 5), 1)
        # Fit the normal of each straight connected ridge, avoiding noisy
        # per-pixel gradients at anti-aliased line ends. Curved/branched groups
        # retain their local tensor orientation.
        fitted = np.mod(0.5 * np.arctan2(2 * xy, xx - yy), np.pi)
        for component in range(1, count):
            cy, cx = np.nonzero((components == component) & current)
            if len(cx) < 8:
                continue
            covariance = np.cov(np.stack((cx, cy)))
            eigenvalues, eigenvectors = np.linalg.eigh(covariance)
            if eigenvalues[1] < 4 * max(eigenvalues[0], 0.1):
                continue
            tangent = eigenvectors[:, 1]
            normal = float(np.mod(np.arctan2(tangent[1], tangent[0]) + np.pi / 2, np.pi))
            fitted[cy, cx] = normal
        edges |= current
        angles[current] = fitted[current]
    return edges, angles


def feature_score(
    reference: tuple[np.ndarray, np.ndarray],
    observed: tuple[np.ndarray, np.ndarray],
    mask: np.ndarray,
    regions: np.ndarray,
) -> float:
    expected_edges, expected_angles = reference
    edges, angles = observed
    scores = []
    for group in range(1, int(regions.max()) + 1):
        expected = expected_edges & (mask > 0) & (regions == group)
        if np.count_nonzero(expected) < 32:
            return 0.0
        near = (
            edges
            & (regions == group)
            & (cv2.dilate(expected.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0)
        )
        if not near.any():
            return 0.0
        recall = np.count_nonzero(
            oriented_matches(expected, expected_angles, edges, angles)
        ) / np.count_nonzero(expected)
        precision = np.count_nonzero(
            oriented_matches(near, angles, expected, expected_angles)
        ) / np.count_nonzero(near)
        scores.append(min(recall, precision))
    return float(min(scores)) if len(scores) >= 2 else 0.0


def value_invariant_score(
    reference: np.ndarray, image: np.ndarray, mask: np.ndarray, regions: np.ndarray
) -> float:
    if (
        reference.shape[:2] != image.shape[:2]
        or mask.shape != regions.shape
        or mask.shape != reference.shape[:2]
    ):
        return 0.0
    return feature_score(
        isolated_features(reference, regions), isolated_features(image, regions), mask, regions
    )


def scaffold_reference(
    crops: list[np.ndarray],
    spec: dict[str, Any],
    stats: dict[str, Any],
    neighbor_bounds: list[list[float]],
) -> tuple[np.ndarray, list[float], np.ndarray, np.ndarray] | None:
    stats.update(
        matcher=MATCHER,
        proposal_source="configured_role_scaffold",
        candidate_count=0,
        structural_rejected=0,
        support_rejected=0,
        holdout_rejected=0,
        training_count=len(crops[::2]),
        holdout_count=len(crops[1::2]),
    )
    if len(crops) < 16 or any(c.shape != crops[0].shape for c in crops):
        return None
    h, w = crops[0].shape[:2]
    try:
        regions = support_regions((h, w), spec, neighbor_bounds)
    except (KeyError, ValueError, TypeError):
        stats["reason"] = "role_geometry_invalid"
        return None
    ys, xs = np.nonzero(regions)
    x1, y1, x2, y2 = int(xs.min()), int(ys.min()), int(xs.max() + 1), int(ys.max() + 1)
    bounds = [x1 / w, y1 / h, x2 / w, y2 / h]
    regions = regions[y1:y2, x1:x2]
    gray = [cv2.cvtColor(c, cv2.COLOR_BGR2GRAY) if c.ndim == 3 else c for c in crops]
    patches = [c[y1:y2, x1:x2] for c in gray]
    training = patches[::2]
    features = [isolated_features(p, regions) for p in training]
    candidates = []
    seen = set()
    for seed_index, (seed_edges, seed_angles) in enumerate(features):
        # A seed cannot promote a unique world edge to HUD evidence. Candidate
        # edges need the same minimum three independent TRAINING observations.
        recurrence = np.sum(
            np.stack([oriented_matches(seed_edges, seed_angles, *f) for f in features]), axis=0
        )
        seed_edges = seed_edges & (recurrence >= 3)
        if any(
            np.count_nonzero(seed_edges & (regions == g)) < 32
            for g in range(1, int(regions.max()) + 1)
        ):
            stats["structural_rejected"] += 1
            continue
        members = tuple(
            i
            for i, f in enumerate(features)
            if feature_score(
                (seed_edges, seed_angles), f, seed_edges.astype(np.uint8) * 255, regions
            )
            >= 0.90
        )
        if len(members) < 3:
            stats["support_rejected"] += 1
            continue
        key = (seed_index, members)
        if key in seen:
            continue
        seen.add(key)
        persistence = np.mean(
            np.stack([oriented_matches(seed_edges, seed_angles, *features[i]) for i in members]),
            axis=0,
        )
        mask = ((persistence >= 0.90) & seed_edges).astype(np.uint8) * 255
        reference = training[seed_index].copy()
        reference[regions == 0] = 0  # Saved asset never contains numeric glyphs.
        ref_features = isolated_features(reference, regions)
        lines = cv2.HoughLinesP(mask, 1, np.pi / 180, threshold=8, minLineLength=8, maxLineGap=2)
        arrangement = structural_layout(mask > 0, ref_features[1], lines)
        arrangement["structural_gates"].update(
            edge_density=0.015 <= float(np.count_nonzero(mask) / mask.size) <= 0.25,
            edge_support=feature_score(ref_features, ref_features, mask, regions) >= 0.90,
        )
        stats["candidate_count"] += 1
        if (
            not arrangement["structural_gates"]["line_support"]
            or not 0.015 <= float(np.count_nonzero(mask) / mask.size) <= 0.25
            or not arrangement["structural_gates"]["arrangement"]
            or feature_score(ref_features, ref_features, mask, regions) < 0.90
        ):
            stats["structural_rejected"] += 1
            continue
        scores = [feature_score(ref_features, f, mask, regions) for f in features]
        support = sum(v >= 0.90 for v in scores)
        if support < 3 or sum(scores[i] >= 0.90 for i in members) < 0.80 * len(members):
            stats["support_rejected"] += 1
            continue
        row = dict(
            roi_bounds=bounds,
            dimensions=[int(reference.shape[1]), int(reference.shape[0])],
            edge_count=int(np.count_nonzero(ref_features[0])),
            orientation_consistency=float(persistence[mask > 0].mean()),
            training_cluster_size=len(members),
            intended_bounds=spec["intended_bounds"],
            support_bounds=spec["support_bounds"],
            dynamic_bounds=spec.get("dynamic_bounds", []),
            distance_from_intended_region=0.0,
            neighbor_overlap_ratio=0.0,
            proposal_source="configured_role_scaffold",
            mask_population=int(np.count_nonzero(mask)),
            group_mask_population=[
                int(np.count_nonzero(mask[regions == g])) for g in range(1, int(regions.max()) + 1)
            ],
            training_accept_count=support,
            training_similarity=similarity_distribution(scores),
            **arrangement,
        )
        candidates.append(
            (
                support,
                float(np.median([v for v in scores if v >= 0.90])),
                reference,
                mask,
                ref_features,
                row,
            )
        )
    if not candidates:
        stats["reason"] = "scaffold_evidence_insufficient"
        return None
    # Freeze the selection using TRAINING only; holdout is evaluated once.
    _, _, reference, mask, ref_features, row = max(candidates, key=lambda item: item[:2])
    heldout = [
        feature_score(ref_features, isolated_features(p, regions), mask, regions)
        for p in patches[1::2]
    ]
    support = sum(v >= 0.90 for v in heldout)
    row.update(holdout_accept_count=support, holdout_similarity=similarity_distribution(heldout))
    stats.update(
        training_accept_count=row["training_accept_count"],
        holdout_accept_count=support,
        selected_candidate=row,
    )
    expected = row["training_accept_count"] * len(heldout) / len(training)
    if support < 3 or support < 0.80 * expected:
        stats["holdout_rejected"] += 1
        stats["reason"] = "holdout_rejected"
        return None
    stats["reason"] = "selected"
    return reference, bounds, mask, regions
