"""Offline model for panel-scale persistent separator motifs.

This module has no paths, labels, timestamps, serialization, E2E, or production
wiring. `learn_panel_separator_model` consumes training grayscale frames only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import cv2
import numpy as np

SCORE_THRESHOLD = 0.90
ORIENTATION_TOLERANCE_DEG = 20.0
PIXEL_TOLERANCE = 1
PERSISTENCE_FRACTION = 0.60
MIN_TRAIN_OBSERVATIONS = 3
MIN_SUPPORT_PIXELS = 32
MIN_GROUP_SPAN = 8
MIN_INTERGROUP_GAP = 16
MIN_SEGMENT_FRACTION = 0.50
MAX_SEGMENT_THICKNESS = 8
MAX_CONTOUR_TRACK_GAP = 3
MIN_PARALLEL_GAP = 4
MAX_PARALLEL_GAP = 32
MIN_OVERLAP_FRACTION = 0.60
MAX_CORNER_GAP = 8
REGION_GUARDBAND = 7
FEATURE_DILATION_RADIUS = 7
DERIVATIVE_GUARD = 3


@dataclass
class Segment:
    orientation: str
    bounds: tuple[int, int, int, int]
    support: np.ndarray
    length: int
    recurrence: float


@dataclass
class Group:
    kind: str
    bounds: tuple[int, int, int, int]
    support: np.ndarray
    orientation_map: np.ndarray
    segments: list[dict[str, Any]]
    recurrence: float


@dataclass
class Model:
    image_shape: tuple[int, int]
    groups: list[Group]
    training_scores: list[dict[str, Any]]
    sufficient: bool
    reason: str
    diagnostics: dict[str, Any]


def _gray(image: np.ndarray) -> np.ndarray:
    if image.ndim == 3:
        image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    if image.ndim != 2 or image.dtype != np.uint8:
        raise ValueError("expected uint8 grayscale or BGR image")
    return image


def _edges(image: np.ndarray) -> np.ndarray:
    return cv2.Canny(cv2.GaussianBlur(image, (3, 3), 0.6), 60, 140) > 0


def _dilate(mask: np.ndarray, radius: int = 1) -> np.ndarray:
    return (
        cv2.dilate(mask.astype(np.uint8), np.ones((2 * radius + 1, 2 * radius + 1), np.uint8)) > 0
    )


def _matches(
    expected: np.ndarray,
    expected_angles: np.ndarray,
    observed: np.ndarray,
    observed_angles: np.ndarray,
) -> np.ndarray:
    h, w = expected.shape
    pe = np.pad(observed, 1)
    pa = np.pad(observed_angles, 1)
    hits = np.zeros((h, w), bool)
    tol = np.deg2rad(ORIENTATION_TOLERANCE_DEG)
    for dy in range(3):
        for dx in range(3):
            oe = pe[dy : dy + h, dx : dx + w]
            oa = pa[dy : dy + h, dx : dx + w]
            d = np.abs(expected_angles - oa)
            hits |= oe & (np.minimum(d, np.pi - d) <= tol)
    return hits & expected


def _angle(image: np.ndarray) -> np.ndarray:
    sm = cv2.GaussianBlur(image, (3, 3), 0.6)
    gx = cv2.Sobel(sm, cv2.CV_64F, 1, 0)
    gy = cv2.Sobel(sm, cv2.CV_64F, 0, 1)
    return np.mod(np.arctan2(gy, gx), np.pi)


def _localized(image: np.ndarray, group: Group) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Derive features only from the 7px dilated support band, with 3px guard."""
    h, w = image.shape
    x1, y1, x2, y2 = group.bounds
    box = np.zeros((h, w), bool)
    box[y1:y2, x1:x2] = True
    allowed = _dilate(group.support, FEATURE_DILATION_RADIUS) & box
    values = image[allowed]
    if not values.size:
        return np.zeros((h, w), bool), np.zeros((h, w), float), allowed
    isolated = np.full((h, w), int(np.median(values)), np.uint8)
    isolated[allowed] = image[allowed]
    valid = (
        cv2.erode(
            allowed.astype(np.uint8),
            np.ones((2 * DERIVATIVE_GUARD + 1, 2 * DERIVATIVE_GUARD + 1), np.uint8),
        )
        > 0
    )
    return _edges(isolated) & valid, _angle(isolated), allowed


def _overlap(a0: int, a1: int, b0: int, b1: int) -> float:
    return max(0, min(a1, b1) - max(a0, b0)) / max(1, min(a1 - a0, b1 - b0))


def _relation(a: Segment, b: Segment) -> str | None:
    ax1, ay1, ax2, ay2 = a.bounds
    bx1, by1, bx2, by2 = b.bounds
    if a.orientation == b.orientation:
        if a.orientation == "h":
            gap = max(0, max(ay1, by1) - min(ay2, by2))
            overlap = _overlap(ax1, ax2, bx1, bx2)
        else:
            gap = max(0, max(ax1, bx1) - min(ax2, bx2))
            overlap = _overlap(ay1, ay2, by1, by2)
        return (
            "parallel_pair"
            if MIN_PARALLEL_GAP <= gap <= MAX_PARALLEL_GAP and overlap >= MIN_OVERLAP_FRACTION
            else None
        )
    hs, vs = (a, b) if a.orientation == "h" else (b, a)
    hx1, hy1, hx2, hy2 = hs.bounds
    vx1, vy1, vx2, vy2 = vs.bounds
    yc = (hy1 + hy2 - 1) / 2
    xc = (vx1 + vx2 - 1) / 2
    dx = min(abs(xc - hx1), abs(xc - (hx2 - 1)))
    dy = max(0.0, max(vy1 - yc, yc - (vy2 - 1)))
    return "corner" if float(np.hypot(dx, dy)) <= MAX_CORNER_GAP else None


def _panel_segments(persistent: np.ndarray, recurrence: np.ndarray) -> list[Segment]:
    h, w = persistent.shape
    rows = []
    for orient, kernel, minlen in [
        (
            "h",
            np.ones((1, int(np.ceil(MIN_SEGMENT_FRACTION * w))), np.uint8),
            int(np.ceil(MIN_SEGMENT_FRACTION * w)),
        ),
        (
            "v",
            np.ones((int(np.ceil(MIN_SEGMENT_FRACTION * h)), 1), np.uint8),
            int(np.ceil(MIN_SEGMENT_FRACTION * h)),
        ),
    ]:
        opened = cv2.morphologyEx(persistent.astype(np.uint8), cv2.MORPH_OPEN, kernel)
        n, labels, stats, _ = cv2.connectedComponentsWithStats(opened, connectivity=8)
        for label in range(1, n):
            x, y, bw, bh, _ = map(int, stats[label])
            length, thick = (bw, bh) if orient == "h" else (bh, bw)
            if length < minlen or thick > MAX_SEGMENT_THICKNESS:
                continue
            support = persistent & (labels == label)
            if int(support.sum()) < MIN_SUPPORT_PIXELS // 2:
                continue
            rows.append(
                Segment(
                    orient,
                    (x, y, x + bw, y + bh),
                    support,
                    length,
                    float(recurrence[support].mean()),
                )
            )
    # Canny outlines both sides of a bright/dark ridge. Merge only adjacent
    # contour tracks of the same physical separator (gap <=3px, >=90% overlap).
    merged = []
    used = set()
    for i, seg in enumerate(rows):
        if i in used:
            continue
        cluster = [i]
        used.add(i)
        changed = True
        while changed:
            changed = False
            for j, other in enumerate(rows):
                if j in used or other.orientation != seg.orientation:
                    continue
                for q in cluster:
                    old = rows[q]
                    x1, y1, x2, y2 = old.bounds
                    u1, v1, u2, v2 = other.bounds
                    if old.orientation == "h":
                        gap = max(0, max(y1, v1) - min(y2, v2))
                        overlap = _overlap(x1, x2, u1, u2)
                    else:
                        gap = max(0, max(x1, u1) - min(x2, u2))
                        overlap = _overlap(y1, y2, v1, v2)
                    if gap <= MAX_CONTOUR_TRACK_GAP and overlap >= 0.90:
                        cluster.append(j)
                        used.add(j)
                        changed = True
                        break
        members = [rows[k] for k in cluster]
        support = np.logical_or.reduce([x.support for x in members])
        xs = []
        ys = []
        for x in members:
            xx1, yy1, xx2, yy2 = x.bounds
            xs.extend((xx1, xx2))
            ys.extend((yy1, yy2))
        bounds = (min(xs), min(ys), max(xs), max(ys))
        merged.append(
            Segment(
                seg.orientation,
                bounds,
                support,
                max(x.length for x in members),
                float(np.mean([x.recurrence for x in members])),
            )
        )
    return merged


def _pair_group(a: Segment, b: Segment, shape: tuple[int, int]) -> Group | None:
    kind = _relation(a, b)
    if kind is None:
        return None
    h, w = shape
    support = a.support | b.support
    ys, xs = np.nonzero(support)
    if xs.size < MIN_SUPPORT_PIXELS:
        return None
    sx1, sy1, sx2, sy2 = int(xs.min()), int(ys.min()), int(xs.max() + 1), int(ys.max() + 1)
    if sx2 - sx1 < MIN_GROUP_SPAN or sy2 - sy1 < MIN_GROUP_SPAN:
        return None
    x1, y1 = max(0, sx1 - REGION_GUARDBAND), max(0, sy1 - REGION_GUARDBAND)
    x2, y2 = min(w, sx2 + REGION_GUARDBAND), min(h, sy2 + REGION_GUARDBAND)
    omap = np.full(shape, -1, np.int8)
    omap[a.support] = 1 if a.orientation == "h" else 0
    omap[b.support] = 1 if b.orientation == "h" else 0
    return Group(
        kind,
        (x1, y1, x2, y2),
        support,
        omap,
        [
            dict(
                orientation=s.orientation,
                bounds=list(s.bounds),
                length=s.length,
                recurrence=s.recurrence,
            )
            for s in (a, b)
        ],
        float((a.recurrence + b.recurrence) / 2),
    )


def _group_score(
    image: np.ndarray, group: Group, expected_angles: np.ndarray
) -> dict[str, float | int]:
    expected = group.support
    observed, angles, allowed = _localized(image, group)
    near = observed & allowed & (_dilate(expected, 2))
    recall_hits = _matches(expected, expected_angles, observed, angles)
    precision_hits = _matches(near, angles, expected, expected_angles)
    n = int(expected.sum())
    m = int(near.sum())
    recall = float(recall_hits.sum() / max(1, n))
    precision = float(precision_hits.sum() / max(1, m))
    return dict(
        expected_edges=n,
        observed_near_edges=m,
        recall=recall,
        precision=precision,
        score=min(recall, precision),
    )


def _angles(group: Group) -> np.ndarray:
    a = np.zeros(group.support.shape, float)
    a[group.orientation_map == 1] = np.pi / 2
    a[group.orientation_map == 0] = 0.0
    return a


def _full_score(image: np.ndarray, groups: list[Group]) -> dict[str, Any]:
    vals = [_group_score(image, g, _angles(g)) for g in groups]
    return dict(
        accepted=len(groups) in (2, 3, 4) and all(r["score"] >= SCORE_THRESHOLD for r in vals),
        score=min((r["score"] for r in vals), default=0.0),
        groups=vals,
    )


def _independent(a: Group, b: Group) -> bool:
    radius = int(np.ceil(MIN_INTERGROUP_GAP / 2))
    ba = _dilate(a.support, radius)
    bb = _dilate(b.support, radius)
    return not bool(np.any(ba & bb))


def learn_panel_separator_model(train_gray: np.ndarray) -> Model:
    """Learn panel-scale pair motifs from gray training frames only."""
    frames = np.stack([_gray(x) for x in train_gray])
    h, w = frames.shape[1:]
    if len(frames) < MIN_TRAIN_OBSERVATIONS:
        return Model((h, w), [], [], False, "too_few_training_frames", _params())
    perframe = np.stack([_edges(x) for x in frames])
    votes = np.stack([_dilate(e) for e in perframe]).mean(axis=0)
    required = max(MIN_TRAIN_OBSERVATIONS, int(np.ceil(PERSISTENCE_FRACTION * len(frames))))
    reference = np.median(frames, axis=0).astype(np.uint8)
    persistent = _edges(reference) & (votes >= required / len(frames))
    segments = _panel_segments(persistent, votes)
    pairs = []
    seen = set()
    for i, a in enumerate(segments):
        for b in segments[i + 1 :]:
            g = _pair_group(a, b, (h, w))
            if g is None:
                continue
            key = np.packbits(g.support).tobytes()
            if key in seen:
                continue
            seen.add(key)
            rows = [_group_score(im, g, _angles(g)) for im in frames]
            count = sum(r["score"] >= SCORE_THRESHOLD for r in rows)
            if count >= MIN_TRAIN_OBSERVATIONS and count >= 0.80 * len(frames):
                pairs.append(
                    (
                        count / len(frames),
                        float(np.median([r["score"] for r in rows])),
                        int(g.support.sum()),
                        g,
                        rows,
                    )
                )
    pairs.sort(key=lambda x: (-x[0], -x[1], -x[2], x[3].bounds))
    selected = []
    for candidate in pairs:
        g = candidate[3]
        if any(not _independent(g, old) for old in selected):
            continue
        selected.append(g)
        if len(selected) == 4:
            break
    selected_directions = {s["orientation"] for g in selected for s in g.segments}
    sufficient = len(selected) in (2, 3, 4) and selected_directions == {"h", "v"}
    train_scores = [_full_score(im, selected) for im in frames] if sufficient else []
    joint = sum(s["accepted"] for s in train_scores)
    if sufficient and (joint < MIN_TRAIN_OBSERVATIONS or joint < 0.80 * len(frames)):
        sufficient = False
        reason = "training_joint_consistency_failed"
    else:
        reason = "selected" if sufficient else "insufficient_panel_scale_pair_support"
    dg = _params()
    dg.update(
        candidate_pair_count=len(pairs),
        persistent_segment_count=len(segments),
        training_count=len(frames),
        support_learning=(
            "exact Canny edges from training median reference intersected with "
            ">=60% one-pixel recurrence; dilation used for votes only"
        ),
        selected_group_training=[
            dict(
                index=i + 1,
                accepted=sum(r["groups"][i]["score"] >= SCORE_THRESHOLD for r in train_scores),
                count=len(train_scores),
                support_pixels=int(g.support.sum()),
                kind=g.kind,
                segments=g.segments,
            )
            for i, g in enumerate(selected)
        ],
    )
    return Model((h, w), selected, train_scores, sufficient, reason, dg)


def score_holdout(model: Model, holdout_gray: np.ndarray) -> dict[str, Any]:
    frames = np.stack([_gray(x) for x in holdout_gray])
    if tuple(frames.shape[1:]) != model.image_shape or not model.sufficient:
        return dict(
            accepted=False,
            reason="model_insufficient_or_shape_mismatch",
            count=len(frames),
            scores=[],
        )
    scores = [_full_score(im, model.groups) for im in frames]
    ok = sum(r["accepted"] for r in scores)
    accepted = ok >= MIN_TRAIN_OBSERVATIONS and ok >= 0.80 * len(frames)
    groups = []
    for i, _group in enumerate(model.groups):
        vals = [r["groups"][i] for r in scores]
        count = sum(x["score"] >= SCORE_THRESHOLD for x in vals)
        groups.append(
            dict(
                group=i + 1,
                matched=count,
                count=len(vals),
                support_fraction=count / max(1, len(vals)),
                mean_recall=float(np.mean([x["recall"] for x in vals])),
                mean_precision=float(np.mean([x["precision"] for x in vals])),
            )
        )
    return dict(
        accepted=accepted,
        reason="selected" if accepted else "holdout_consistency_failed",
        matched=ok,
        count=len(frames),
        support_fraction=ok / max(1, len(frames)),
        groups=groups,
        scores=scores,
    )


def _params() -> dict[str, Any]:
    return dict(
        score_threshold=SCORE_THRESHOLD,
        orientation_tolerance_deg=ORIENTATION_TOLERANCE_DEG,
        pixel_tolerance=PIXEL_TOLERANCE,
        recurrence_fraction=PERSISTENCE_FRACTION,
        min_train_observations=MIN_TRAIN_OBSERVATIONS,
        min_panel_segment_fraction=MIN_SEGMENT_FRACTION,
        parallel_separation_px=[MIN_PARALLEL_GAP, MAX_PARALLEL_GAP],
        parallel_overlap_fraction=MIN_OVERLAP_FRACTION,
        corner_endpoint_gap_px=MAX_CORNER_GAP,
        group_support_min_pixels=MIN_SUPPORT_PIXELS,
        min_group_span_px=MIN_GROUP_SPAN,
        min_intergroup_gap_px=MIN_INTERGROUP_GAP,
        support_feature_dilation_px=FEATURE_DILATION_RADIUS,
        derivative_guard_px=DERIVATIVE_GUARD,
        region_guardband_px=REGION_GUARDBAND,
    )
