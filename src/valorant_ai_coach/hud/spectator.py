"""Positive panel-structure detector; never match a background/clear image.

The ROI is supplied by the layout. A supported panel candidate must contain a
long boundary, portrait-like closed box, and aligned text components to its right.
These are UI-shape priors, not frame labels. Unrecognised UI variants stay unknown.
"""

from __future__ import annotations

from typing import Any

import cv2
import numpy as np


def panel_components(
    gray: np.ndarray, diagnostics: dict[str, Any] | None = None
) -> np.ndarray | None:
    diag = diagnostics if diagnostics is not None else {}
    diag.update(
        observable=False,
        boundary=False,
        portrait=False,
        textlike=False,
        boundary_portrait=False,
        portrait_textlike=False,
        boundary_textlike=False,
        all_components=False,
        reason="geometry_rejected",
    )
    h, w = gray.shape
    if min(h, w) < 32:
        return None
    if float(gray.std()) < 8 or not 12 < float(gray.mean()) < 245:
        diag["reason"] = "contrast_rejected"
        return None
    if float(cv2.Laplacian(gray, cv2.CV_64F).var()) < 10:
        diag["reason"] = "blur_rejected"
        return None
    diag.update(observable=True, reason="structural_rejected")
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
        ):
            boxes.append((x, y, bw, bh))
    diag["portrait"] = bool(boxes)
    lines = cv2.HoughLinesP(
        edges, 1, np.pi / 180, threshold=max(12, w // 5), minLineLength=int(0.30 * w), maxLineGap=3
    )
    boundary = np.zeros_like(gray)
    horizontal = []
    for line in [] if lines is None else lines[:, 0]:
        x1, y1, x2, y2 = map(int, line)
        if abs(y1 - y2) <= 2:
            cv2.line(boundary, (x1, y1), (x2, y2), 1, 1)
            horizontal.append((min(x1, x2), y1, max(x1, x2)))
    diag["boundary"] = bool(horizontal)
    diag["boundary_portrait"] = bool(horizontal and boxes)
    _, _, stats, _ = cv2.connectedComponentsWithStats(edges, connectivity=8)
    generic_glyphs = [
        (int(a), int(b), int(c), int(d))
        for a, b, c, d, area in stats[1:]
        if 2 <= c <= 0.10 * w and 4 <= d <= 0.35 * h and area >= 4
    ]
    diag["textlike"] = any(
        sum(abs(g[1] - v[1]) <= max(3, 0.03 * h) for v in generic_glyphs) >= 3
        for g in generic_glyphs
    )
    diag["boundary_textlike"] = bool(diag["boundary"] and diag["textlike"])
    for x, y, bw, bh in sorted(boxes):
        # Text-shaped connected components, spatially aligned beside the portrait.
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
        rows = [g for g in glyphs if sum(abs(g[1] - v[1]) <= max(3, 0.03 * h) for v in glyphs) >= 3]
        if len(rows) < 3:
            continue
        diag["portrait_textlike"] = True
        # A boundary must span the portrait/text group and lie outside its row.
        # Mere coincident game-world edges are not a coherent panel candidate.
        boundary = np.zeros_like(gray)
        right = max(a + c for a, b, c, d in rows)
        for left, by, end in horizontal:
            if left <= x + bw * 0.25 and end >= right and (by < y or by > y + bh):
                cv2.line(boundary, (left, by), (end, by), 1, 1)
        labels = boundary.copy()
        box = np.zeros_like(gray)
        cv2.rectangle(box, (x, y), (x + bw - 1, y + bh - 1), 1, 2)
        labels[(box > 0) & (edges > 0)] = 2
        for a, b, c, d in rows:
            region = labels[b : b + d, a : a + c]
            region[edges[b : b + d, a : a + c] > 0] = 3
        if all(np.count_nonzero(labels == k) >= 12 for k in (1, 2, 3)):
            diag.update(all_components=True, reason="candidate")
            return labels
    return None


def component_scores(gray: np.ndarray, labels: np.ndarray) -> list[float]:
    if gray.shape != labels.shape or any(np.count_nonzero(labels == k) < 12 for k in (1, 2, 3)):
        return []
    edges = cv2.dilate(cv2.Canny(gray, 60, 150), np.ones((3, 3), np.uint8))
    return [float(np.mean(edges[labels == k] > 0)) for k in (1, 2, 3)]


def _displaced_component_present(gray: np.ndarray, labels: np.ndarray) -> bool:
    """Search the whole ROI before treating fixed-position contradictions as absence.

    A displaced characteristic component is ambiguous evidence, not proof of
    presence. Use the same .90 edge-coverage requirement as the positive detector.
    """
    edges = (cv2.dilate(cv2.Canny(gray, 60, 150), np.ones((3, 3), np.uint8)) > 0).astype(np.float32)
    for kind in (1, 2, 3):
        ys, xs = np.nonzero(labels == kind)
        template = (labels[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1] == kind).astype(
            np.float32
        )
        coverage = cv2.matchTemplate(edges, template, cv2.TM_CCORR) / len(xs)
        if float(coverage.max()) >= 0.90:
            return True
    return False


def generate_panel_reference(crops: list[np.ndarray], stats: dict[str, Any]) -> np.ndarray | None:
    gray = [cv2.cvtColor(c, cv2.COLOR_BGR2GRAY) if c.ndim == 3 else c for c in crops]
    stats.update(
        training_count=len(gray[::2]),
        holdout_count=len(gray[1::2]),
        candidate_count=0,
        structural_rejected=0,
        support_rejected=0,
        holdout_rejected=0,
        cluster_count=0,
    )
    samples = []
    for index, frame in enumerate(gray):
        sample: dict[str, Any] = {"sample_index": index, "training": index % 2 == 0}
        panel_components(frame, sample)
        samples.append(sample)
    stats["samples"] = samples
    stats["evidence_counts"] = {
        key: sum(s.get(key) is True for s in samples)
        for key in (
            "observable",
            "boundary",
            "portrait",
            "textlike",
            "boundary_portrait",
            "portrait_textlike",
            "boundary_textlike",
            "all_components",
        )
    }
    stats["rejection_counts"] = {
        reason: sum(s["reason"] == reason for s in samples)
        for reason in (
            "geometry_rejected",
            "contrast_rejected",
            "blur_rejected",
            "structural_rejected",
        )
    }
    candidates = []
    clusters = set()
    for frame in gray[::2]:
        labels = panel_components(frame)
        if labels is None:
            stats["structural_rejected"] += 1
            continue
        stats["candidate_count"] += 1
        members = tuple(
            i
            for i, g in enumerate(gray[::2])
            if min(component_scores(g, labels), default=0) >= 0.90
        )
        support = len(members)
        if support >= 3:
            if members not in clusters:
                candidates.append((support, labels))
                clusters.add(members)
        else:
            stats["support_rejected"] += 1
    if not candidates:
        return None
    stats["cluster_count"] = len(candidates)
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
        if panel_components(gray) is not None or _displaced_component_present(gray, labels):
            result["reason"] = "panel_structure_mismatch"
            return result
        # Each mandatory UI component was checked and strongly contradicted.
        # Partial structure, noise/occlusion or just a below-threshold match is unknown.
        result.update(checked=True, panel_present=False, reason="panel_structure_excluded")
    else:
        result["reason"] = "panel_structure_ambiguous"
    return result
