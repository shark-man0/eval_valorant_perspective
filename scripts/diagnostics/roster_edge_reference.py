"""Training-only stable portrait edges for diagnostic masked location NCC.

This is not a liveness detector. No missing-match, count or temporal inference
is supplied. All three source crops must support a reference before probing.
"""

from __future__ import annotations

import math

import cv2
import numpy as np

METHOD = "roster_portrait_stable_edge_ncc_location_v2"


def masked_locations(reference, mask, search):
    """Weighted zero-mean NCC at each placement; constants remain undefined."""
    if (reference.ndim != 2 or search.ndim != 2 or mask.shape != reference.shape
            or not set(np.unique(mask)).issubset({0, 255})
            or min(reference.shape) < 1 or any(a > b for a, b in
                                              zip(reference.shape, search.shape, strict=True))):
        raise ValueError("valid in-bounds gray portrait and binary mask required")
    weights = (mask > 0).astype(np.float32)
    population = int(weights.sum())
    if population < 128:
        raise ValueError("insufficient independent portrait edge support")
    template = reference.astype(np.float32)
    mean = float((template * weights).sum()) / population
    centered = (template - mean) * weights
    energy = float(np.square(centered).sum())
    if math.sqrt(energy / population) < 5:
        raise ValueError("insufficient portrait reference contrast")
    image = search.astype(np.float32)
    total = cv2.matchTemplate(image, weights, cv2.TM_CCORR)
    total2 = cv2.matchTemplate(np.square(image), weights, cv2.TM_CCORR)
    numerator = cv2.matchTemplate(image, centered, cv2.TM_CCORR)
    variance = np.maximum(0, total2 - np.square(total) / population)
    denominator = np.sqrt(variance * energy)
    scores = np.full(numerator.shape, np.nan, np.float32)
    valid = variance / population >= 25  # Same minimum local gray std=5.
    np.divide(numerator, denominator, out=scores, where=valid)
    return np.clip(scores, -1, 1)


def locate_edges(reference, mask, search):
    scores = masked_locations(reference, mask, search)
    if not np.isfinite(scores).any():
        return {"similarity": None, "offset_xy": None, "reason": "search_contrast_insufficient"}
    y, x = np.unravel_index(np.nanargmax(scores), scores.shape)
    return {"similarity": float(scores[y, x]), "offset_xy": [int(x), int(y)],
            "reason": "measured"}


def build_reference(crops):
    """Retain edges present within one pixel in every frozen training crop.

    Fixed Canny 60/120 and 3x3 spatial tolerance are fitted to no probe frame.
    Dilated support retains edge contrast neighbourhoods, not geometry anchors.
    A reference failing original .90 training NCC is not available for probing.
    """
    if len(crops) < 3 or any(c.shape != crops[0].shape or c.ndim != 2 for c in crops):
        raise ValueError("three same-size source portrait crops required")
    kernel = np.ones((3, 3), np.uint8)
    edges = [cv2.Canny(c, 60, 120) for c in crops]
    stable = edges[0] > 0
    for edge in edges[1:]:
        stable &= cv2.dilate(edge, kernel) > 0
    mask = cv2.dilate(stable.astype(np.uint8) * 255, kernel)
    reference = crops[0].copy()
    similarities = [locate_edges(reference, mask, c)["similarity"] for c in crops]
    return reference, mask, {
        "available": all(s is not None and s >= .90 for s in similarities),
        "edge_count": int(np.count_nonzero(edges[0])),
        "stable_edge_count": int(np.count_nonzero(stable)),
        "mask_population": int(np.count_nonzero(mask)),
        "training_similarity": similarities,
    }
