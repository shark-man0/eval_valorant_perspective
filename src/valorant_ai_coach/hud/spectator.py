"""Positive panel-structure detector; never match a background/clear image.

The ROI is supplied by the layout. A supported panel candidate must contain a
long boundary, portrait-like closed box, and aligned text components to its right.
These are UI-shape priors, not frame labels. Unrecognised UI variants stay unknown.
"""

from __future__ import annotations

from typing import Any

import cv2
import numpy as np


def portrait_frames(
    edges: np.ndarray, diagnostics: dict[str, Any]
) -> list[tuple[int, int, int, int]]:
    """Frame occupancy from fragments/line pairs; no closed convex polygon required."""
    h, w = edges.shape
    proposals: set[tuple[int, int, int, int]] = set()
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    for contour in contours:
        x, y, bw, bh = cv2.boundingRect(contour)
        proposals.add((int(x), int(y), int(bw), int(bh)))
    lines = cv2.HoughLinesP(
        edges,
        1,
        np.pi / 180,
        threshold=6,
        minLineLength=max(8, int(min(h, w) * 0.10)),
        maxLineGap=4,
    )
    vertical, horizontal = [], []
    if lines is not None:
        for x1, y1, x2, y2 in lines[:, 0]:
            if abs(x1 - x2) <= 2:
                vertical.append((int((x1 + x2) // 2), int(min(y1, y2)), int(max(y1, y2))))
            if abs(y1 - y2) <= 2:
                horizontal.append((int((y1 + y2) // 2), int(min(x1, x2)), int(max(x1, x2))))
    # Deterministic bounds keep complex world textures from exploding combinations.
    vertical = sorted(set(vertical), key=lambda v: v[2] - v[1], reverse=True)[:48]
    horizontal = sorted(set(horizontal), key=lambda v: v[2] - v[1], reverse=True)[:48]
    for i, (x, top, bottom) in enumerate(vertical):
        for other, ot, ob in vertical[i + 1 :]:
            y, end = max(top, ot), min(bottom, ob)
            if end > y:
                proposals.add((min(x, other), y, abs(x - other) + 1, end - y + 1))
    for i, (y, left, right) in enumerate(horizontal):
        for other, ol, ob in horizontal[i + 1 :]:
            x, end = max(left, ol), min(right, ob)
            if end > x:
                proposals.add((x, min(y, other), end - x + 1, abs(y - other) + 1))
    nearby = cv2.distanceTransform((edges == 0).astype(np.uint8), cv2.DIST_L2, 3) <= 1.5
    boxes = []
    best = 0.0
    geometry_count = 0
    best_sides = [0.0] * 4
    for x, y, bw, bh in sorted(proposals):
        if not (0.08 * w <= bw <= 0.35 * w and 0.15 * h <= bh <= 0.8 * h and 0.5 <= bw / bh <= 1.8):
            continue
        geometry_count += 1
        side = [
            float(nearby[y, x : x + bw].mean()),
            float(nearby[y + bh - 1, x : x + bw].mean()),
            float(nearby[y : y + bh, x].mean()),
            float(nearby[y : y + bh, x + bw - 1].mean()),
        ]
        score = float(np.mean(side))
        if score > best:
            best, best_sides = score, side
        # Three supported sides plus nonzero fourth-side evidence prevents two
        # disconnected lines/text rows from becoming a portrait box.
        if sum(s >= 0.55 for s in side) >= 3 and min(side) >= 0.25 and score >= 0.70:
            boxes.append((x, y, bw, bh))
    diagnostics.update(
        portrait_candidate_count=len(proposals),
        portrait_frame_score=best,
        portrait_supported_count=len(boxes),
        portrait_geometry_count=geometry_count,
        portrait_occupancy_rejected=geometry_count - len(boxes),
        portrait_side_scores=best_sides,
    )
    return boxes


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
        final_rejections={
            "text_alignment_insufficient": 0,
            "boundary_span_insufficient": 0,
            "relative_position_mismatch": 0,
            "component_pixels_insufficient": 0,
        },
        final_gates={
            "portrait": False,
            "text_alignment": False,
            "boundary_span": False,
            "component_pixels": False,
        },
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
    boxes = portrait_frames(edges, diag)
    diag["portrait"] = bool(boxes)
    diag["final_gates"]["portrait"] = bool(boxes)
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
            diag["final_rejections"]["text_alignment_insufficient"] += 1
            continue
        diag["portrait_textlike"] = True
        diag["final_gates"]["text_alignment"] = True
        # A boundary must span the portrait/text group and lie outside its row.
        # Mere coincident game-world edges are not a coherent panel candidate.
        boundary = np.zeros_like(gray)
        right = max(a + c for a, b, c, d in rows)
        spanned = False
        for left, by, end in horizontal:
            coverage = max(0, min(end, right) - max(left, x)) / max(1, right - x)
            outside = by < y + 2 or by > y + bh - 2
            if coverage >= 0.90 and left <= x + bw * 0.25 + 2 and outside:
                cv2.line(boundary, (left, by), (end, by), 1, 1)
                spanned = True
            elif not outside:
                diag["final_rejections"]["relative_position_mismatch"] += 1
        if not spanned:
            diag["final_rejections"]["boundary_span_insufficient"] += 1
            continue
        diag["final_gates"]["boundary_span"] = True
        labels = boundary.copy()
        box = np.zeros_like(gray)
        cv2.rectangle(box, (x, y), (x + bw - 1, y + bh - 1), 1, 2)
        labels[(box > 0) & (edges > 0)] = 2
        for a, b, c, d in rows:
            region = labels[b : b + d, a : a + c]
            region[edges[b : b + d, a : a + c] > 0] = 3
        if all(np.count_nonzero(labels == k) >= 12 for k in (1, 2, 3)):
            diag["final_gates"]["component_pixels"] = True
            diag["component_pixel_counts"] = [int(np.count_nonzero(labels == k)) for k in (1, 2, 3)]
            diag.update(all_components=True, reason="candidate")
            return labels
        diag["final_rejections"]["component_pixels_insufficient"] += 1
    return None


def component_scores(gray: np.ndarray, labels: np.ndarray) -> list[float]:
    if gray.shape != labels.shape or any(np.count_nonzero(labels == k) < 12 for k in (1, 2, 3)):
        return []
    edges = cv2.dilate(cv2.Canny(gray, 60, 150), np.ones((3, 3), np.uint8))
    return [float(np.mean(edges[labels == k] > 0)) for k in (1, 2, 3)]


def local_component_scores(gray: np.ndarray, labels: np.ndarray) -> list[float]:
    """Require recall AND local precision for each group at one shared <=2px offset.

    Only precision uses the raw edges: dilating observed edges before counting
    them would let dense texture cover almost every reference pixel. A one-pixel
    match band within a two-pixel neighbourhood penalizes extra nearby edges.
    Absence keeps its separate, conservative coverage-only checks.
    """
    if gray.shape != labels.shape or any(np.count_nonzero(labels == k) < 12 for k in (1, 2, 3)):
        return []
    best = [0.0] * 3
    h, w = gray.shape
    edges = cv2.Canny(gray, 60, 150) > 0
    padded = np.pad(edges, 2)
    covered = np.pad(cv2.dilate(edges.astype(np.uint8), np.ones((3, 3), np.uint8)), 2)
    groups = []
    for kind in (1, 2, 3):
        expected = labels == kind
        band = cv2.dilate(expected.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0
        neighbourhood = cv2.dilate(expected.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
        groups.append((expected, band, neighbourhood))
    for dy in range(-2, 3):
        for dx in range(-2, 3):
            shifted = padded[2 + dy : 2 + dy + h, 2 + dx : 2 + dx + w]
            shifted_covered = covered[2 + dy : 2 + dy + h, 2 + dx : 2 + dx + w]
            scores = []
            for expected, band, neighbourhood in groups:
                observed = shifted & neighbourhood
                recall = float(np.mean(shifted_covered[expected] > 0))
                precision = int(np.count_nonzero(observed & band)) / max(
                    1, int(np.count_nonzero(observed))
                )
                scores.append(min(recall, precision))
            if min(scores) > min(best):
                best = scores
    return best


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
        matcher="edge_recall_precision_v1",
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
    stats["final_rejection_counts"] = (
        {
            key: sum(s["final_rejections"][key] for s in samples)
            for key in samples[0]["final_rejections"]
        }
        if samples
        else {}
    )
    stats["candidate_support"] = []
    candidates = []
    clusters = set()
    for index, frame in enumerate(gray[::2]):
        labels = panel_components(frame)
        if labels is None:
            stats["structural_rejected"] += 1
            continue
        stats["candidate_count"] += 1
        members = tuple(
            i
            for i, g in enumerate(gray[::2])
            if min(local_component_scores(g, labels), default=0) >= 0.90
        )
        support = len(members)
        stats["candidate_support"].append(
            {"sample_index": index * 2, "training_support": support, "minimum_required": 3}
        )
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
    heldout = sum(min(local_component_scores(g, labels), default=0) >= 0.90 for g in gray[1::2])
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
    positive_scores = local_component_scores(gray, labels)
    result["positive_component_scores"] = positive_scores
    if min(positive_scores, default=0) >= 0.90:
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
