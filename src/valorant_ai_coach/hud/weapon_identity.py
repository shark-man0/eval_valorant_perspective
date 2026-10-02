"""Training-only, identity-specific stable masks. No geometry assets or labels."""

from __future__ import annotations

import math
from typing import Any

import cv2
import numpy as np


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

    A mask uses persistent UI edges and their stable surrounding pixels. Changing
    digits/icons are excluded using within-cluster variance, not expected values.
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
    )
    if len(crops) < 16 or any(c.shape != crops[0].shape for c in crops):
        return None
    gray = [cv2.cvtColor(c, cv2.COLOR_BGR2GRAY) if c.ndim == 3 else c for c in crops]
    height, width = gray[0].shape
    h, w = max(16, round(height * 0.30)), max(16, round(width * 0.20))
    if h >= height or w >= width:
        return None
    accepted = []
    for y in np.linspace(0, height - h, 5).astype(int):
        for x in np.linspace(0, width - w, 5).astype(int):
            patches = [g[y : y + h, x : x + w] for g in gray]
            training = patches[::2]
            edges = [cv2.Canny(p, 60, 150) > 0 for p in training]
            dilated = [cv2.dilate(e.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0 for e in edges]
            clusters = set()
            for e in edges:
                if np.count_nonzero(e) < 12:
                    continue
                members = tuple(i for i, d in enumerate(dilated) if np.mean(d[e]) >= 0.90)
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
                reference = np.median(stack, axis=0).astype(np.uint8)
                variance = stack.var(axis=0)
                persistence = np.mean(np.stack([edges[i] for i in members]), axis=0)
                fixed_edges = (persistence >= 0.90).astype(np.uint8)
                mask = (
                    (variance <= 4) & (cv2.dilate(fixed_edges, np.ones((5, 5), np.uint8)) > 0)
                ).astype(np.uint8) * 255
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
                    else "mask_contrast_insufficient"
                    if masked_score(reference, reference, mask) < 0.90
                    else None
                )
                row["structural_rejection_reason"] = rejection
                row["support_rejection_reason"] = None
                # Diagnostic-only holdout values cannot affect training ranking.
                diagnostic_scores = [masked_score(reference, p, mask) for p in patches[1::2]]
                row["holdout_accept_count"] = sum(s >= 0.90 for s in diagnostic_scores)
                row["holdout_prevalence"] = row["holdout_accept_count"] / len(diagnostic_scores)
                if (
                    lines is None
                    or len(lines) < 2
                    or not arranged
                    or not 0.015 <= density <= 0.25
                    or masked_score(reference, reference, mask) < 0.90
                ):
                    stats["structural_rejected"] += 1
                    counts = stats["rejection_counts"]
                    counts[rejection] = counts.get(rejection, 0) + 1
                else:
                    scores = [masked_score(reference, p, mask) for p in training]
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
        return None
    _, reference, bounds, mask, patches, row = max(accepted, key=lambda item: item[0])
    heldout = [masked_score(reference, p, mask) for p in patches[1::2]]
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
