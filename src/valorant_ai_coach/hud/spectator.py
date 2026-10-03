"""Positive panel-structure detector; never match a background/clear image.

The ROI is supplied by the layout. A supported panel candidate must contain a
coherent boundary fragments, portrait-frame edges, and aligned adjacent text.
These are UI-shape priors, not frame labels. Unrecognised UI variants stay unknown.
"""

from __future__ import annotations

from typing import Any

import cv2
import numpy as np


class PanelReference(np.ndarray):
    """Measured edges and frozen, disjoint precision regions (local assets only).

    The array itself remains a legacy-compatible component label image. Regions
    include *all* source edges, not just synthetic Hough lines or glyph outlines.
    Orientation is measured, never inferred from a label or a frame identity.
    """

    regions: np.ndarray
    orientation: np.ndarray

    def __new__(
        cls, labels: np.ndarray, regions: np.ndarray, orientation: np.ndarray
    ) -> PanelReference:
        obj = np.asarray(labels, dtype=np.uint8).view(cls)
        if (
            regions.shape != obj.shape
            or orientation.shape != obj.shape
            or not set(np.unique(regions)).issubset({0, 1, 2, 3})
            or np.any((obj > 0) & (obj != regions))
            or np.any(orientation > 179)
        ):
            raise ValueError("invalid component support assets")
        obj.regions = np.asarray(regions, dtype=np.uint8).copy()
        obj.orientation = np.asarray(orientation, dtype=np.uint8).copy()
        return obj

    def __array_finalize__(self, obj: Any) -> None:
        if obj is not None:
            self.regions = getattr(obj, "regions", np.empty((0, 0), np.uint8))
            self.orientation = getattr(obj, "orientation", np.empty((0, 0), np.uint8))


def _orientation(gray: np.ndarray) -> np.ndarray:
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1)
    # Signed gradient direction, quantised to two degrees per uint8 unit.
    # Opposite sides of a bright UI line must not substitute for each other.
    return np.mod(np.rint(np.degrees(np.arctan2(gy, gx)) / 2), 180).astype(np.uint8)


def portrait_frames(
    edges: np.ndarray, diagnostics: dict[str, Any], orientation: np.ndarray | None = None
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
    # Directed side occupancy rejects coincidental world/chat rectangles.
    # Keep the Windows occupancy gates, using the canonical two-degree angles.
    vertical_nearby = horizontal_nearby = nearby
    if orientation is not None:
        angle = (orientation.astype(np.int16) * 2) % 180
        vertical_edges = (edges > 0) & (np.minimum(angle, 180 - angle) <= 22.5)
        horizontal_edges = (edges > 0) & (np.abs(angle - 90) <= 22.5)
        vertical_nearby = (
            cv2.distanceTransform((~vertical_edges).astype(np.uint8), cv2.DIST_L2, 3) <= 1.5
        )
        horizontal_nearby = (
            cv2.distanceTransform((~horizontal_edges).astype(np.uint8), cv2.DIST_L2, 3) <= 1.5
        )
    boxes = []
    best = 0.0
    geometry_count = 0
    best_sides = [0.0] * 4
    for x, y, bw, bh in sorted(proposals):
        if not (0.08 * w <= bw <= 0.35 * w and 0.15 * h <= bh <= 0.8 * h and 0.5 <= bw / bh <= 1.8):
            continue
        geometry_count += 1
        side = [
            float(horizontal_nearby[y, x : x + bw].mean()),
            float(horizontal_nearby[y + bh - 1, x : x + bw].mean()),
            float(vertical_nearby[y : y + bh, x].mean()),
            float(vertical_nearby[y : y + bh, x + bw - 1].mean()),
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
    gray: np.ndarray,
    diagnostics: dict[str, Any] | None = None,
    *,
    conservative_veto: bool = False,
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
            "boundary_orientation_incoherent": 0,
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
    boxes = portrait_frames(edges, diag, None if conservative_veto else _orientation(gray))
    diag["portrait"] = bool(boxes)
    diag["final_gates"]["portrait"] = bool(boxes)
    lines = cv2.HoughLinesP(
        edges,
        1,
        np.pi / 180,
        threshold=max(8, w // 12),
        minLineLength=max(8, int(0.10 * w)),
        maxLineGap=3,
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
        text_left = min(a for a, b, c, d in rows)
        text_top = min(b for a, b, c, d in rows)
        text_bottom = max(b + d for a, b, c, d in rows)
        if text_left - (x + bw) > bw or max(a + c for a, b, c, d in rows) - text_left > 3.5 * bw:
            diag["final_rejections"]["relative_position_mismatch"] += 1
            continue
        # Header/footer and interior text separators are valid only with bounded
        # portrait/text geometry. Merge real fragments; never fill missing edges.
        boundary = np.zeros_like(gray)
        right = max(a + c for a, b, c, d in rows)
        best_segments = []
        best_coverage = 0.0
        for by in sorted({s[1] for s in horizontal}):
            segments = [s for s in horizontal if abs(s[1] - by) <= max(2, round(0.03 * bh))]
            covered = np.zeros(w, bool)
            for left, _, end in segments:
                covered[max(x, left) : min(right, end + 1)] = True
            coverage = float(np.mean(covered[x:right]))
            diag["boundary_coverage"] = max(diag.get("boundary_coverage", 0.0), coverage)
            # A union must connect both sides of the group and retain >=90% of
            # its actual span. Unrelated distant fragments cannot bridge a panel.
            if min(s[0] for s in segments) > x + bw * 0.25 + 2:
                continue
            if coverage < 0.90:
                continue
            diag["boundary_span_candidates"] = diag.get("boundary_span_candidates", 0) + 1
            outside_text = by <= text_top - 2 or by >= text_bottom + 2
            distance = max(text_top - by, by - text_bottom, 0) / bh
            if not (outside_text and y - 0.5 * bh <= by <= y + 1.5 * bh and distance <= 1.0):
                diag["final_rejections"]["relative_position_mismatch"] += 1
                continue
            if coverage >= 0.90 and coverage > best_coverage:
                best_segments, best_coverage = segments, coverage
                diag["panel_topology"] = (
                    "group_header"
                    if by <= y + 2
                    else "group_footer"
                    if by >= y + bh - 2
                    else "text_separator"
                )
                diag["boundary_relative_y"] = float((by - y + 0.5 * bh) / (2 * bh))
        if not best_segments:
            diag["final_rejections"]["boundary_span_insufficient"] += 1
            continue
        for left, by, end in best_segments:
            cv2.line(boundary, (left, by), (end, by), 1, 1)
        diag["boundary_coverage"] = best_coverage
        diag["boundary_fragment_count"] = len(best_segments)
        diag["portrait_text_gap_ratio"] = float((text_left - x - bw) / bw)
        diag["final_gates"]["boundary_span"] = True
        # Preserve the ancestor's broader structural veto for absence. Neither
        # stricter generation guard may make absence easier to establish.
        if conservative_veto:
            legacy = boundary.copy()
            old_box = np.zeros_like(gray)
            cv2.rectangle(old_box, (x, y), (x + bw - 1, y + bh - 1), 1, 2)
            legacy[(old_box > 0) & (edges > 0)] = 2
            for a, b, c, d in rows:
                region = legacy[b : b + d, a : a + c]
                region[edges[b : b + d, a : a + c] > 0] = 3
            if all(np.count_nonzero(legacy == k) >= 12 for k in (1, 2, 3)):
                return legacy
            continue
        # Freeze support before looking at edge matches. All observed source
        # edges in these regions become expectations, so source-frame recall
        # and precision have the same denominator/representation contract.
        regions = cv2.dilate(boundary, np.ones((5, 5), np.uint8))
        box = np.zeros_like(gray)
        cv2.rectangle(box, (x, y), (x + bw - 1, y + bh - 1), 1, 5)
        regions[box > 0] = 2
        for a, b, c, d in rows:
            regions[max(0, b - 2) : min(h, b + d + 2), max(0, a - 2) : min(w, a + c + 2)] = 3
        labels = np.where(edges > 0, regions, 0).astype(np.uint8)
        orientation = _orientation(gray)
        boundary_angles = (orientation[labels == 1].astype(np.int16) * 2) % 180
        # Horizontal boundary evidence must be predominantly normal to its
        # direction, not a Hough coincidence in dense isotropic world texture.
        # +/-20 degrees accommodates rasterisation; 60% requires a clear
        # majority over isotropic noise's 40/180 ~=22% expected support.
        if not len(boundary_angles) or np.mean(np.abs(boundary_angles - 90) <= 20) < 0.60:
            diag["final_rejections"]["boundary_orientation_incoherent"] += 1
            continue
        if all(np.count_nonzero(labels == k) >= 12 for k in (1, 2, 3)):
            diag["final_gates"]["component_pixels"] = True
            diag["component_pixel_counts"] = [int(np.count_nonzero(labels == k)) for k in (1, 2, 3)]
            diag.update(all_components=True, reason="candidate")
            if diagnostics is not None:
                legacy = boundary.copy()
                old_box = np.zeros_like(gray)
                cv2.rectangle(old_box, (x, y), (x + bw - 1, y + bh - 1), 1, 2)
                legacy[(old_box > 0) & (edges > 0)] = 2
                for a, b, c, d in rows:
                    region = legacy[b : b + d, a : a + c]
                    region[edges[b : b + d, a : a + c] > 0] = 3
                diag["legacy_self_match"] = component_match_diagnostics(gray, legacy)
            return PanelReference(labels, regions, orientation)
        diag["final_rejections"]["component_pixels_insufficient"] += 1
    return None


def component_scores(gray: np.ndarray, labels: np.ndarray) -> list[float]:
    if gray.shape != labels.shape or any(np.count_nonzero(labels == k) < 12 for k in (1, 2, 3)):
        return []
    edges = cv2.dilate(cv2.Canny(gray, 60, 150), np.ones((3, 3), np.uint8))
    return [float(np.mean(edges[labels == k] > 0)) for k in (1, 2, 3)]


def local_component_scores(gray: np.ndarray, labels: np.ndarray) -> list[float]:
    return [c["score"] for c in component_match_diagnostics(gray, labels).get("components", [])]


def component_match_diagnostics(gray: np.ndarray, labels: np.ndarray) -> dict[str, Any]:
    """Require recall AND local precision for each group at one shared <=2px offset.

    V2 compares measured oriented edges inside frozen disjoint support regions.
    Only precision counts raw observed edges. Legacy label-only assets retain
    their old one-pixel band / two-pixel neighbourhood matcher, never silently
    fabricate missing regions/orientations. Absence remains coverage-only.
    """
    if gray.shape != labels.shape or any(np.count_nonzero(labels == k) < 12 for k in (1, 2, 3)):
        return {}
    best: dict[str, Any] = {}
    h, w = gray.shape
    edges = cv2.Canny(gray, 60, 150) > 0
    padded = np.pad(edges, 2)
    covered = np.pad(cv2.dilate(edges.astype(np.uint8), np.ones((3, 3), np.uint8)), 2)
    angles = np.pad(_orientation(gray), 2)
    groups = []
    coordinates = []
    for kind in (1, 2, 3):
        expected = np.asarray(labels) == kind
        band = cv2.dilate(expected.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0
        neighbourhood = (
            labels.regions == kind
            if isinstance(labels, PanelReference)
            else cv2.dilate(expected.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
        )
        groups.append((expected, band, neighbourhood))
        coordinates.append(np.nonzero(expected))
    for dy in range(-2, 3):
        for dx in range(-2, 3):
            shifted = padded[2 + dy : 2 + dy + h, 2 + dx : 2 + dx + w]
            shifted_covered = covered[2 + dy : 2 + dy + h, 2 + dx : 2 + dx + w]
            components: list[dict[str, Any]] = []
            for kind, (expected, band, neighbourhood) in enumerate(groups, 1):
                observed = shifted & neighbourhood
                if isinstance(labels, PanelReference):
                    # Bidirectional 1px / 20-degree oriented correspondence.
                    # Dense random texture must not obtain coverage merely by
                    # filling the tolerance band. No independent group shifts.
                    ey, ex = coordinates[kind - 1]
                    expected_angles = labels.orientation[ey, ex].astype(np.int16)
                    matched_expected = np.zeros(len(ey), bool)
                    matched_observed = np.zeros_like(expected)
                    shifted_angles = angles[2 + dy : 2 + dy + h, 2 + dx : 2 + dx + w]
                    for oy in (-1, 0, 1):
                        for ox in (-1, 0, 1):
                            sy, sx = ey + oy, ex + ox
                            inside = (sy >= 0) & (sy < h) & (sx >= 0) & (sx < w)
                            sy, sx = np.clip(sy, 0, h - 1), np.clip(sx, 0, w - 1)
                            delta = np.abs(
                                shifted_angles[sy, sx].astype(np.int16) - expected_angles
                            )
                            valid = (
                                inside & observed[sy, sx] & (np.minimum(delta, 180 - delta) <= 10)
                            )
                            matched_expected |= valid
                            matched_observed[sy[valid], sx[valid]] = True
                    ne, no = int(matched_expected.sum()), int(matched_observed.sum())
                else:
                    ne = int(np.count_nonzero(shifted_covered & expected))
                    no = int(np.count_nonzero(observed & band))
                expected_count, observed_count = int(expected.sum()), int(observed.sum())
                recall, precision = ne / expected_count, no / max(1, observed_count)
                components.append(
                    dict(
                        component=("boundary", "portrait", "text")[kind - 1],
                        component_id=kind,
                        expected_count=expected_count,
                        observed_count=observed_count,
                        matched_expected_count=ne,
                        matched_observed_count=no,
                        recall=recall,
                        precision=precision,
                        score=min(recall, precision),
                    )
                )
            score = min(c["score"] for c in components)
            # Prefer the smallest rigid displacement on tied scores.
            if not best or (score, -abs(dx) - abs(dy)) > (
                best["minimum_score"],
                -abs(best["dx"]) - abs(best["dy"]),
            ):
                best = dict(
                    components=components,
                    minimum_score=score,
                    dx=dx,
                    dy=dy,
                    limiting_component=min(components, key=lambda c: c["score"])["component"],
                    passed=score >= 0.90,
                )
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
        matcher="oriented_component_regions_v2",
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
        comparisons = [component_match_diagnostics(g, labels) for g in gray[::2]]
        members = tuple(i for i, result in enumerate(comparisons) if result.get("passed"))
        failed = [r.get("minimum_score", 0.0) for r in comparisons if not r.get("passed")]
        support = len(members)
        stats["candidate_support"].append(
            {
                "sample_index": index * 2,
                "training_support": support,
                "minimum_required": 3,
                "self_match": comparisons[index],
                "training_matches": [
                    {"sample_index": i * 2, **r} for i, r in enumerate(comparisons)
                ],
                "legacy_self_match": samples[index * 2].get("legacy_self_match", {}),
                "failed_support_scores": dict(
                    count=len(failed),
                    min=min(failed) if failed else None,
                    median=float(np.median(failed)) if failed else None,
                    max=max(failed) if failed else None,
                ),
            }
        )
        if support >= 3:
            if members not in clusters:
                candidates.append((support, labels, index * 2))
                clusters.add(members)
        else:
            stats["support_rejected"] += 1
    if not candidates:
        return None
    stats["cluster_count"] = len(candidates)
    support, labels, sample_index = max(candidates, key=lambda item: item[0])
    stats["selected_sample_index"] = sample_index
    holdout_matches = [
        {"sample_index": i * 2 + 1, **component_match_diagnostics(g, labels)}
        for i, g in enumerate(gray[1::2])
    ]
    stats["holdout_matches"] = holdout_matches
    heldout = sum(bool(r.get("passed")) for r in holdout_matches)
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
        if panel_components(
            gray, conservative_veto=True
        ) is not None or _displaced_component_present(gray, labels):
            result["reason"] = "panel_structure_mismatch"
            return result
        # Each mandatory UI component was checked and strongly contradicted.
        # Partial structure, noise/occlusion or just a below-threshold match is unknown.
        result.update(checked=True, panel_present=False, reason="panel_structure_excluded")
    else:
        result["reason"] = "panel_structure_ambiguous"
    return result
