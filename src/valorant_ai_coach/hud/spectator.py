"""Positive panel-structure detector; never match a background/clear image.

The ROI is supplied by the layout. A supported panel candidate must contain a
long boundary, portrait-like closed box, and aligned text components to its right.
These are UI-shape priors, not frame labels. Unrecognised UI variants stay unknown.
"""

from __future__ import annotations

from typing import Any

import cv2
import numpy as np


def panel_components(gray: np.ndarray) -> np.ndarray | None:
    h, w = gray.shape
    if min(h, w) < 32:
        return None
    edges = cv2.Canny(gray, 60, 150)
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    boxes = []
    for contour in contours:
        x, y, bw, bh = cv2.boundingRect(contour)
        polygon = cv2.approxPolyDP(contour, 0.02 * cv2.arcLength(contour, True), True)
        if (
            len(polygon) == 4
            and cv2.isContourConvex(polygon)
            and 0.08 * w <= bw <= 0.35 * w
            and 0.15 * h <= bh <= 0.8 * h
            and 0.5 <= bw / bh <= 1.8
            and x < 0.45 * w
        ):
            boxes.append((x, y, bw, bh))
    lines = cv2.HoughLinesP(
        edges, 1, np.pi / 180, threshold=max(12, w // 5), minLineLength=int(0.55 * w), maxLineGap=3
    )
    if not boxes or lines is None:
        return None
    boundary = np.zeros_like(gray)
    for line in lines[:, 0]:
        x1, y1, x2, y2 = map(int, line)
        if abs(y1 - y2) <= 2 and (y1 < 0.3 * h or y1 > 0.7 * h):
            cv2.line(boundary, (x1, y1), (x2, y2), 1, 1)
    if np.count_nonzero(boundary) < 0.55 * w:
        return None
    for x, y, bw, bh in sorted(boxes):
        # Text-shaped connected components, spatially aligned beside the portrait.
        _, _, stats, _ = cv2.connectedComponentsWithStats(edges, connectivity=8)
        glyphs = [
            (int(a), int(b), int(c), int(d))
            for a, b, c, d, area in stats[1:]
            if a > x + bw
            and a < 0.95 * w
            and y - 4 <= b <= y + bh
            and 2 <= c <= 0.10 * w
            and 4 <= d <= 0.35 * h
            and area >= 4
        ]
        rows = [g for g in glyphs if sum(abs(g[1] - v[1]) <= 3 for v in glyphs) >= 3]
        if len(rows) < 3:
            continue
        labels = boundary.copy()
        box = np.zeros_like(gray)
        cv2.rectangle(box, (x, y), (x + bw - 1, y + bh - 1), 1, 2)
        labels[(box > 0) & (edges > 0)] = 2
        for a, b, c, d in rows:
            region = labels[b : b + d, a : a + c]
            region[edges[b : b + d, a : a + c] > 0] = 3
        if all(np.count_nonzero(labels == k) >= 12 for k in (1, 2, 3)):
            return labels
    return None


def component_scores(gray: np.ndarray, labels: np.ndarray) -> list[float]:
    if gray.shape != labels.shape or any(np.count_nonzero(labels == k) < 12 for k in (1, 2, 3)):
        return []
    edges = cv2.dilate(cv2.Canny(gray, 60, 150), np.ones((3, 3), np.uint8))
    return [float(np.mean(edges[labels == k] > 0)) for k in (1, 2, 3)]


def generate_panel_reference(crops: list[np.ndarray], stats: dict[str, Any]) -> np.ndarray | None:
    gray = [cv2.cvtColor(c, cv2.COLOR_BGR2GRAY) if c.ndim == 3 else c for c in crops]
    stats.update(
        training_count=len(gray[::2]),
        holdout_count=len(gray[1::2]),
        candidate_count=0,
        structural_rejected=0,
        support_rejected=0,
        holdout_rejected=0,
    )
    candidates = []
    for frame in gray[::2]:
        labels = panel_components(frame)
        if labels is None:
            stats["structural_rejected"] += 1
            continue
        stats["candidate_count"] += 1
        support = sum(min(component_scores(g, labels), default=0) >= 0.90 for g in gray[::2])
        if support >= 3:
            candidates.append((support, labels))
        else:
            stats["support_rejected"] += 1
    if not candidates:
        return None
    support, labels = max(candidates, key=lambda item: item[0])
    heldout = sum(min(component_scores(g, labels), default=0) >= 0.90 for g in gray[1::2])
    stats.update(training_accept_count=support, holdout_accept_count=heldout)
    if heldout < 3 or heldout < 0.80 * support * len(gray[1::2]) / len(gray[::2]):
        stats["holdout_rejected"] += 1
        return None
    return labels


def detect_panel(crop: np.ndarray, labels: np.ndarray | None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "checked": False,
        "panel_present": None,
        "reason": "reference_unavailable",
    }
    if labels is None:
        return result
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if crop.ndim == 3 else crop
    scores = component_scores(gray, labels)
    if not scores:
        result["reason"] = "geometry_mismatch"
        return result
    if (
        float(gray.std()) < 8
        or not 12 < float(gray.mean()) < 245
        or float(cv2.Laplacian(gray, cv2.CV_64F).var()) < 10
    ):
        result["reason"] = "roi_unobservable"
        return result
    result["component_scores"] = scores
    if min(scores) >= 0.90:
        result.update(checked=True, panel_present=True, reason="panel_structure_present")
    elif max(scores) <= 0.10:
        # Each mandatory UI component was checked and strongly contradicted.
        # Partial structure, noise/occlusion or just a below-threshold match is unknown.
        result.update(checked=True, panel_present=False, reason="panel_structure_excluded")
    else:
        result["reason"] = "panel_structure_ambiguous"
    return result
