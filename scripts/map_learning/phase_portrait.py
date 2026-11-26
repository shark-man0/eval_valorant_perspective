"""Rescore the incumbent portrait CNN at observed sub-stride marker centers."""

from __future__ import annotations

import math
from itertools import product

import cv2
import numpy as np

from valorant_ai_coach.temporal.map_direct_recorder import _rim_evidence
from valorant_ai_coach.temporal.map_marker_geometry import measure_marker_geometry

OFFSETS = sorted(product(range(-2, 3), repeat=2), key=lambda p: (math.hypot(*p), p))


def phase_portraits(image, roi, peaks, score_batch, public_scores, target):
    """Locate a warm outline and keep the existing portrait confidence requirement."""
    left, top, right, bottom = roi
    scale = image.shape[1] / 1920
    crop = image[top:bottom, left:right]
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    extent = math.ceil(11 * scale)
    half = max(2, round(8 * scale))
    phase_samples, patches = [], []
    seen = set()
    for peak in peaks:
        peak_center = tuple(peak.center)
        if peak.warm_sectors < 5 or peak.chromatic_rivals > 5:
            continue
        for dx, dy in OFFSETS:
            x = peak_center[0] + round(dx * scale)
            y = peak_center[1] + round(dy * scale)
            if (x, y) in seen:
                continue
            seen.add((x, y))
            if not (extent <= x < right - left - extent and extent <= y < bottom - top - extent):
                continue
            warm, pairs, rivals = _rim_evidence(hsv, x, y, scale)
            if warm < 10 or pairs < 3 or rivals > 2:
                continue
            patch = crop[y - half : y + half + 1, x - half : x + half + 1]
            phase_samples.append(((x + left, y + top), peak_center, (warm, pairs, rivals)))
            patches.append(cv2.resize(patch, (17, 17), interpolation=cv2.INTER_AREA))
    if not patches:
        return []
    results = []
    probability = np.asarray(score_batch(np.stack(patches)))
    if probability.shape != (len(patches),) or not np.isfinite(probability).all():
        raise ValueError("Expected one finite incumbent score per candidate crop")
    order = np.argsort(-probability, kind="stable")
    for i in order:
        confidence = float(probability[i])
        if confidence < 0.80:
            break
        center, peak, shape = phase_samples[i]
        if any(math.dist(center, c) <= 4 * scale for c, _ in results):
            continue
        if (center[0] - left, center[1] - top) == peak:
            continue
        values = public_scores(image, center)
        if values is None or values[target] < 0.73:
            continue
        margin = float(values[target] - np.delete(values, target).max())
        if margin < 0.055:
            continue
        (outline,) = measure_marker_geometry(image, [{"center_frame_px": center}])
        if (
            outline is None
            or outline.palette != "WARM"
            or math.dist(outline.center, center) > 2 * scale
        ):
            continue
        results.append(
            (
                center,
                {
                    "proposal": "incumbent_cnn_phase_search",
                    "initial_peak_roi_px": peak,
                    "current_public_portrait": True,
                    "public_agent_score": float(values[target]),
                    "public_agent_margin": margin,
                    "incumbent_portrait_score_at_measured_center": confidence,
                    "rim_sectors_pairs_rivals": shape,
                    "outline_center_frame_px": outline.center,
                    "outline_support": outline.support,
                },
            )
        )
    return results
