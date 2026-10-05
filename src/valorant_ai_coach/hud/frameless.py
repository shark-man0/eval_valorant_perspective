"""Frameless image-slot proposals constrained by a side separator and two text rows.

No face, OCR identity, state label, or temporal oracle is used. A proposal is not
a supported reference: the caller still requires independent training/holdout.
"""

from typing import Any

import cv2
import numpy as np


def frameless_regions(
    gray: np.ndarray, edges: np.ndarray, orientation: np.ndarray, diag: dict[str, Any]
) -> tuple[np.ndarray, np.ndarray] | None:
    h, w = gray.shape
    unsigned = (orientation.astype(np.int16) * 2) % 180
    raw = cv2.HoughLinesP(
        edges,
        1,
        np.pi / 180,
        threshold=max(8, h // 20),
        minLineLength=max(16, round(0.15 * h)),
        maxLineGap=2,
    )
    separators = sorted(
        {
            (int(round((x1 + x2) / 2)), int(min(y1, y2)), int(abs(y1 - y2) + 1))
            for x1, y1, x2, y2 in ([] if raw is None else raw.reshape(-1, 4))
            if abs(x1 - x2) <= 1
        }
    )
    _, _, components, _ = cv2.connectedComponentsWithStats(edges)
    rejected: dict[str, int] = {}
    diag["frameless_rejections"] = rejected
    attempts: list[dict[str, Any]] = []
    diag["frameless_candidates"] = attempts

    def reject(reason: str) -> None:
        rejected[reason] = rejected.get(reason, 0) + 1

    for x, y, ph in separators:
        if not (
            0.15 * h <= ph <= 0.40 * h and 0.02 * w <= x <= 0.65 * w and y > 1 and y + ph < h - 1
        ):
            reject("separator_geometry")
            continue
        # Hough may select either side of the same antialiased 1px ruler.
        # Recover its measured intensity ridge, so source supports share a slot.
        start = max(0, x - 2)
        x = start + int(np.argmax(np.median(gray[y : y + ph, start : x + 3], axis=0)))
        strip = edges[y : y + ph, max(0, x - 2) : x + 3] > 0
        normal = unsigned[y : y + ph, max(0, x - 2) : x + 3]
        coherence = np.any(strip & (np.minimum(normal, 180 - normal) <= 20), axis=1).mean()
        brightness = np.any(gray[y : y + ph, max(0, x - 1) : x + 2] >= 120, axis=1).mean()
        if coherence < 0.90 or brightness < 0.80:
            reject("separator_evidence")
            continue
        glyphs = [
            (int(a), int(b), int(c), int(d))
            for a, b, c, d, area in components[1:]
            if x + 0.95 * ph <= a <= x + 4.0 * ph
            and y + 0.20 * ph <= b <= y + 0.95 * ph
            and 2 <= c <= 0.40 * ph
            and 0.10 * ph <= d <= 0.35 * ph
            and area >= 6
            and np.quantile(gray[b : b + d, a : a + c], 0.85) >= 180
        ]
        rows: list[tuple[int, int, int, int, list[tuple[int, int, int, int]]]] = []
        for top in sorted({b for a, b, c, d in glyphs}):
            glyph_row = [g for g in glyphs if abs(g[1] - top) <= 0.07 * ph]
            glyph_row.sort()
            # A row must be a compact run of at least three glyphs, not distant texture.
            runs: list[list[tuple[int, int, int, int]]] = []
            for g in glyph_row:
                if not runs or g[0] - max(a + c for a, b, c, d in runs[-1]) > 0.30 * ph:
                    runs.append([g])
                else:
                    runs[-1].append(g)
            for group in runs:
                if len(group) >= 3:
                    left = min(g[0] for g in group)
                    right = max(g[0] + g[2] for g in group)
                    bottom = max(g[1] + g[3] for g in group)
                    if 0.95 * ph <= left - x <= 1.45 * ph and 0.50 * ph <= right - left <= 2.5 * ph:
                        rows.append((left, top, right, bottom, group))
        pairs = [
            (a, b)
            for a in rows
            for b in rows
            if 0.25 * ph <= a[1] - y <= 0.60 * ph
            and 0.65 * ph <= b[1] - y <= 0.95 * ph
            and b[1] - a[3] >= 0.05 * ph
            and abs(a[0] - b[0]) <= 0.25 * ph
            and b[3] <= y + ph + 2
        ]
        if not pairs:
            reject("two_text_rows_missing")
            continue
        for first, second in pairs:
            pw = round(0.90 * ph)
            left = x + 3
            right = left + pw
            if right >= min(first[0], second[0]) - 0.08 * ph or right >= w:
                reject("portrait_text_geometry")
                continue
            slot = edges[y : y + ph, left:right]
            count = int(np.count_nonzero(slot))
            density = count / (pw * ph)
            _, group_labels, group_stats, _ = cv2.connectedComponentsWithStats(slot)
            groups = [
                i
                for i, (a, b, c, d, area) in enumerate(group_stats)
                if i > 0
                and area >= max(6, 0.002 * pw * ph)
                and 2 <= c <= 0.90 * pw
                and 2 <= d <= 0.90 * ph
            ]
            mask = np.isin(group_labels, groups).astype(np.uint8)
            ys, xs = np.nonzero(mask)
            populated_rows = sum(
                np.count_nonzero(part) >= max(3, 0.01 * pw * ph)
                for part in np.array_split(mask, 4, axis=0)
            )
            populated_columns = sum(
                np.count_nonzero(part) >= max(3, 0.01 * pw * ph)
                for part in np.array_split(mask, 4, axis=1)
            )
            histogram = np.histogram(
                orientation[y : y + ph, left:right][mask > 0], bins=np.linspace(0, 180, 9)
            )[0]
            distribution = histogram / max(1, histogram.sum())
            detail = dict(
                portrait_mode="frameless",
                portrait_search_region=[left / w, y / h, right / w, (y + ph) / h],
                portrait_region_dimensions=[pw, ph],
                portrait_edge_count=count,
                portrait_localized_component_count=len(groups),
                portrait_x_spread=float(np.ptp(xs) / pw) if len(xs) else 0.0,
                portrait_y_spread=float(np.ptp(ys) / ph) if len(ys) else 0.0,
                portrait_occupied_rows=int(populated_rows),
                portrait_occupied_columns=int(populated_columns),
                portrait_orientation_distribution=distribution.tolist(),
                portrait_relative_to_text=float((first[0] - right) / ph),
                portrait_relative_to_boundary=float(3 / ph),
                portrait_candidate_rejection_reason=None,
            )
            # Detailed examples are bounded; aggregate every rejection above.
            if len(attempts) < 64:
                attempts.append(detail)
            else:
                diag["frameless_omitted_candidates"] = (
                    diag.get("frameless_omitted_candidates", 0) + 1
                )
            reason = None
            if not 0.08 <= density <= 0.35:
                reason = "portrait_edge_density"
            elif len(groups) < 3:
                reason = "portrait_localized_groups"
            elif min(detail["portrait_x_spread"], detail["portrait_y_spread"]) < 0.65:
                reason = "portrait_spread"
            elif min(populated_rows, populated_columns) < 3:
                reason = "portrait_occupancy"
            elif sum(distribution >= 0.05) < 4 or max(distribution, default=1) > 0.50:
                reason = "portrait_orientation"
            if reason:
                detail["portrait_candidate_rejection_reason"] = reason
                reject(reason)
                continue
            regions = np.zeros_like(gray)
            regions[y : y + ph, max(0, x - 2) : x + 3] = 1
            regions[y : y + ph, left:right] = cv2.dilate(mask, np.ones((5, 5), np.uint8)) * 2
            for text_row in (first, second):
                for a, b, c, d in text_row[4]:
                    regions[
                        max(0, b - 2) : min(h, b + d + 2), max(0, a - 2) : min(w, a + c + 2)
                    ] = 3
            labels = np.where(edges > 0, regions, 0).astype(np.uint8)
            if any(np.count_nonzero(labels == k) < 12 for k in (1, 2, 3)):
                reject("component_pixels_insufficient")
                continue
            detail["portrait_support_region_population"] = int(np.count_nonzero(regions == 2))
            diag.update(detail)
            diag.update(
                portrait=True,
                boundary=True,
                textlike=True,
                boundary_portrait=True,
                portrait_textlike=True,
                boundary_textlike=True,
                all_components=True,
                reason="candidate",
                panel_topology="portrait_side_separator",
                component_pixel_counts=[int(np.count_nonzero(labels == k)) for k in (1, 2, 3)],
            )
            diag["final_gates"] = {
                k: True for k in ("portrait", "text_alignment", "boundary_span", "component_pixels")
            }
            return labels, regions
    return None
