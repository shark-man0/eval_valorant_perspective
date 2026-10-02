"""Training-only, identity-specific stable masks. No geometry assets or labels."""

from __future__ import annotations

import math
from typing import Any

import cv2
import numpy as np


def edge_features(image: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Local contrast normalization, then edge location and unsigned orientation."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    if gray.size == 0 or float(gray.std()) < 5:
        return np.zeros(gray.shape, bool), np.zeros(gray.shape, float)
    low, high = np.percentile(gray, [5, 95])
    if high - low < 8:
        low, high = float(gray.min()), float(gray.max())
    if high - low < 8:
        return np.zeros(gray.shape, bool), np.zeros(gray.shape, float)
    normalized = np.clip((gray.astype(float) - low) * 255 / (high - low), 0, 255).astype(np.uint8)
    normalized = cv2.GaussianBlur(normalized, (3, 3), 0.6)
    edges = cv2.Canny(normalized, 60, 150) > 0
    gx = cv2.Sobel(normalized, cv2.CV_64F, 1, 0)
    gy = cv2.Sobel(normalized, cv2.CV_64F, 0, 1)
    return edges, np.mod(np.arctan2(gy, gx), np.pi)


def oriented_matches(
    expected: np.ndarray, angles: np.ndarray, observed: np.ndarray, observed_angles: np.ndarray
) -> np.ndarray:
    """At most one-pixel displacement and 20-degree unsigned orientation error."""
    matches = np.zeros(expected.shape, bool)
    h, w = expected.shape
    padded_edges = np.pad(observed, 1)
    padded_angles = np.pad(observed_angles, 1)
    for dy in range(3):
        for dx in range(3):
            difference = np.abs(angles - padded_angles[dy : dy + h, dx : dx + w])
            aligned = np.minimum(difference, np.pi - difference) <= np.deg2rad(20)
            matches |= padded_edges[dy : dy + h, dx : dx + w] & aligned
    return np.asarray(matches & expected, dtype=bool)


def structural_score(reference: np.ndarray, image: np.ndarray, mask: np.ndarray) -> float:
    """Minimum oriented recall/precision, not pixel NCC or AI confidence.

    Precision is evaluated in the frame neighbourhood; changing content outside
    that neighbourhood cannot erase a frame, but clutter near it is not ignored.
    .90 requires >=90% agreement in BOTH directions. No global sliding search.
    """
    if image.shape[:2] != reference.shape[:2] or mask.shape != reference.shape[:2]:
        return 0.0
    ref_edges, ref_angles = edge_features(reference)
    edges, angles = edge_features(image)
    expected = ref_edges & (mask > 0)
    if np.count_nonzero(expected) < 32:
        return 0.0
    observed = edges & (cv2.dilate(expected.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0)
    if not observed.any():
        return 0.0
    recall = np.count_nonzero(
        oriented_matches(expected, ref_angles, edges, angles)
    ) / np.count_nonzero(expected)
    precision = np.count_nonzero(
        oriented_matches(observed, angles, expected, ref_angles)
    ) / np.count_nonzero(observed)
    return float(min(recall, precision))


def similarity_distribution(scores: list[float]) -> dict[str, Any]:
    return dict(
        count=len(scores),
        min=float(min(scores)),
        median=float(np.median(scores)),
        max=float(max(scores)),
    )


def frame_edges(edges: np.ndarray) -> np.ndarray:
    """Long line scaffold excludes short digit/icon strokes from seed clustering."""
    lines = cv2.HoughLinesP(
        edges.astype(np.uint8) * 255,
        1,
        np.pi / 180,
        threshold=8,
        minLineLength=max(8, min(edges.shape) // 3),
        maxLineGap=2,
    )
    scaffold = np.zeros(edges.shape, np.uint8)
    if lines is not None:
        for x1, y1, x2, y2 in lines[:, 0]:
            cv2.line(scaffold, (int(x1), int(y1)), (int(x2), int(y2)), 1, 3)
    return edges & (scaffold > 0)


def masked_score(reference: np.ndarray, image: np.ndarray, mask: np.ndarray) -> float:
    """Fixed-position masked NCC; undefined or insufficient contrasts are unknown."""
    if image.ndim == 3:
        image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    if image.shape != reference.shape or mask.shape != reference.shape:
        return 0.0
    selected = mask > 0
    if np.count_nonzero(selected) < 32:
        return 0.0
    a, b = reference[selected].astype(float), image[selected].astype(float)
    if min(float(a.std()), float(b.std())) < 5:
        return 0.0
    a -= a.mean()
    b -= b.mean()
    value = float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
    return max(0.0, min(1.0, value)) if math.isfinite(value) else 0.0


def weapon_reference(
    crops: list[np.ndarray], stats: dict[str, Any]
) -> tuple[np.ndarray, list[float], np.ndarray] | None:
    """Mine structural clusters, freeze a candidate on training, test holdout once.

    A mask uses persistent oriented UI edges, not stable pixel intensities.
    A supported structure is not itself a live label: all runtime gates still apply.
    """
    stats.update(
        candidate_count=0,
        structural_rejected=0,
        support_rejected=0,
        holdout_rejected=0,
        training_count=len(crops[::2]),
        holdout_count=len(crops[1::2]),
        candidates=[],
        omitted_candidate_count=0,
        rejection_counts={},
        matcher="oriented_edges_v1",
    )
    if len(crops) < 16 or any(c.shape != crops[0].shape for c in crops):
        return None
    gray = [cv2.cvtColor(c, cv2.COLOR_BGR2GRAY) if c.ndim == 3 else c for c in crops]
    height, width = gray[0].shape
    h, w = max(16, round(height * 0.30)), max(16, round(width * 0.20))
    if h >= height or w >= width:
        return None
    accepted = []
    best_diagnostic: dict[str, Any] | None = None
    for y in np.linspace(0, height - h, 5).astype(int):
        for x in np.linspace(0, width - w, 5).astype(int):
            patches = [g[y : y + h, x : x + w] for g in gray]
            training = patches[::2]
            features = [edge_features(p) for p in training]
            clusters = set()
            for all_edges, angle in features:
                e = frame_edges(all_edges)
                if np.count_nonzero(e) < 12:
                    continue
                members = tuple(
                    i
                    for i, (observed, orientation) in enumerate(features)
                    if np.count_nonzero(oriented_matches(e, angle, observed, orientation))
                    / np.count_nonzero(e)
                    >= 0.90
                )
                if len(members) >= 3:
                    clusters.add(members)
                else:
                    stats["support_rejected"] += 1
                    counts = stats["rejection_counts"]
                    counts["seed_support_insufficient"] = (
                        counts.get("seed_support_insufficient", 0) + 1
                    )
            for members in sorted(clusters):
                stack = np.stack([training[i] for i in members]).astype(float)
                reference = training[members[0]].copy()
                variance = stack.var(axis=0)
                ref_edges, ref_angles = edge_features(reference)
                scaffold = frame_edges(ref_edges)
                persistence = np.mean(
                    np.stack(
                        [oriented_matches(scaffold, ref_angles, *features[i]) for i in members]
                    ),
                    axis=0,
                )
                fixed_edges = ((persistence >= 0.90) & ref_edges).astype(np.uint8)
                mask = fixed_edges * 255
                bounds = [
                    float(x / width),
                    float(y / height),
                    float((x + w) / width),
                    float((y + h) / height),
                ]
                row: dict[str, Any] = dict(
                    training_cluster_size=len(members),
                    roi_bounds=bounds,
                    dimensions=[w, h],
                    temporal_variance=float(variance.mean() / 65025),
                    edge_persistence=float(persistence[fixed_edges > 0].mean())
                    if fixed_edges.any()
                    else 0.0,
                    stable_pixel_ratio=float(np.mean(variance <= 4)),
                    dynamic_pixel_ratio=float(np.mean(variance > 4)),
                    mask_pixel_ratio=float(np.mean(mask > 0)),
                    edge_count=int(np.count_nonzero(ref_edges)),
                    mask_population=int(np.count_nonzero(mask)),
                    stable_edge_ratio=float(np.count_nonzero(mask))
                    / max(1, int(np.count_nonzero(ref_edges))),
                    orientation_consistency=float(np.mean(persistence[mask > 0]))
                    if mask.any()
                    else 0.0,
                    reason="structural_rejected",
                )
                stats["candidate_count"] += 1
                lines = cv2.HoughLinesP(
                    fixed_edges * 255,
                    1,
                    np.pi / 180,
                    threshold=8,
                    minLineLength=max(8, min(h, w) // 3),
                    maxLineGap=2,
                )
                density = float(np.mean(fixed_edges > 0))
                directions = (
                    []
                    if lines is None
                    else [
                        np.array([x2 - x1, y2 - y1], dtype=float) for x1, y1, x2, y2 in lines[:, 0]
                    ]
                )
                arranged = any(
                    abs(a[0] * b[1] - a[1] * b[0]) / (np.linalg.norm(a) * np.linalg.norm(b)) >= 0.25
                    for i, a in enumerate(directions)
                    for b in directions[i + 1 :]
                )
                rejection = (
                    "fixed_edges_insufficient"
                    if lines is None or len(lines) < 2
                    else "edge_arrangement_invalid"
                    if not arranged
                    else "edge_density_invalid"
                    if not 0.015 <= density <= 0.25
                    else "edge_support_insufficient"
                    if structural_score(reference, reference, mask) < 0.90
                    else None
                )
                row["structural_rejection_reason"] = rejection
                row["support_rejection_reason"] = None
                # Diagnostic-only holdout values cannot affect training ranking.
                diagnostic_scores = [structural_score(reference, p, mask) for p in patches[1::2]]
                row["holdout_similarity"] = similarity_distribution(diagnostic_scores)
                scores = [structural_score(reference, p, mask) for p in training]
                row["training_similarity"] = similarity_distribution(scores)
                row["training_accept_count"] = sum(s >= 0.90 for s in scores)
                if best_diagnostic is None or (
                    row["training_accept_count"],
                    row["mask_population"],
                ) > (best_diagnostic["training_accept_count"], best_diagnostic["mask_population"]):
                    best_diagnostic = row
                row["holdout_accept_count"] = sum(s >= 0.90 for s in diagnostic_scores)
                row["holdout_prevalence"] = row["holdout_accept_count"] / len(diagnostic_scores)
                if (
                    lines is None
                    or len(lines) < 2
                    or not arranged
                    or not 0.015 <= density <= 0.25
                    or structural_score(reference, reference, mask) < 0.90
                ):
                    stats["structural_rejected"] += 1
                    counts = stats["rejection_counts"]
                    counts[rejection] = counts.get(rejection, 0) + 1
                else:
                    support = sum(s >= 0.90 for s in scores)
                    row["training_accept_count"] = support
                    if support < 3 or sum(scores[i] >= 0.90 for i in members) < 0.80 * len(members):
                        stats["support_rejected"] += 1
                        row["reason"] = "support_rejected"
                        row["support_rejection_reason"] = "training_support_insufficient"
                        counts = stats["rejection_counts"]
                        counts["training_support_insufficient"] = (
                            counts.get("training_support_insufficient", 0) + 1
                        )
                    else:
                        row["reason"] = "training_candidate"
                        accepted.append(
                            (
                                support + float(np.median([s for s in scores if s >= 0.90])),
                                reference,
                                bounds,
                                mask,
                                patches,
                                row,
                            )
                        )
                if len(stats["candidates"]) < 64:
                    stats["candidates"].append(row)
                else:
                    stats["omitted_candidate_count"] += 1
    stats["cluster_count"] = stats["candidate_count"]
    if not accepted:
        if best_diagnostic is not None:
            stats["selected_candidate"] = dict(best_diagnostic)
        return None
    _, reference, bounds, mask, patches, row = max(accepted, key=lambda item: item[0])
    heldout = [structural_score(reference, p, mask) for p in patches[1::2]]
    support = sum(s >= 0.90 for s in heldout)
    expected = row["training_accept_count"] * len(heldout) / len(patches[::2])
    row.update(holdout_accept_count=support, holdout_prevalence=support / len(heldout))
    stats.update(
        training_accept_count=row["training_accept_count"],
        holdout_accept_count=support,
        selected_candidate=dict(row),
    )
    if support < 3 or support < 0.80 * expected:
        stats["holdout_rejected"] += 1
        row["reason"] = "holdout_rejected"
        stats["selected_candidate"]["reason"] = "holdout_rejected"
        return None
    row["reason"] = "selected"
    stats["selected_candidate"]["reason"] = "selected"
    stats["holdout_median"] = float(np.median([s for s in heldout if s >= 0.90]))
    return reference, bounds, mask
