"""Bounded, training-only local edge group proposals inside the configured ROI."""

from __future__ import annotations

from collections import Counter
from typing import Any

import cv2
import numpy as np


def candidate_windows(edges: list[np.ndarray], stats: dict[str, Any]) -> list[dict[str, Any]]:
    height, width = edges[0].shape
    observed: Counter[tuple[int, int, int, int]] = Counter()
    sources: dict[tuple[int, int, int, int], str] = {}
    rejected: Counter[str] = Counter()
    step = max(2, round(min(height, width) * 0.01))
    for image in edges:
        _, _, components, centers = cv2.connectedComponentsWithStats(
            image.astype(np.uint8), connectivity=8
        )
        groups = []
        for c, center in zip(components[1:], centers[1:], strict=True):
            x, y, w, h, area = map(int, c)
            if area < 8:
                continue
            if w >= 0.75 * width or h >= 0.75 * height:
                rejected["spanning_component"] += 1
                continue
            groups.append((x, y, x + w, y + h, center))
        groups = sorted(groups, key=lambda g: (g[2] - g[0]) * (g[3] - g[1]), reverse=True)[:32]
        boxes = [(g[:4], "localized_component") for g in groups]
        for i, group in enumerate(groups):
            neighbours = sorted(
                (other for j, other in enumerate(groups) if j != i),
                key=lambda g: float(np.linalg.norm(g[4] - group[4])),
            )[:3]
            for other in neighbours:
                boxes.append(
                    (
                        (
                            min(group[0], other[0]),
                            min(group[1], other[1]),
                            max(group[2], other[2]),
                            max(group[3], other[3]),
                        ),
                        "component_group",
                    )
                )
        seen = set()
        for (x1, y1, x2, y2), source in boxes:
            bw, bh = x2 - x1, y2 - y1
            # Reject stripes before padding can make them appear two-dimensional.
            if min(bw, bh) < 6 or max(bw, bh) / min(bw, bh) > 6:
                rejected["one_dimensional"] += 1
                continue
            if bw >= 0.75 * width or bh >= 0.9 * height:
                rejected["group_extent_invalid"] += 1
                continue
            px, py = max(3, round(bw * 0.15)), max(3, round(bh * 0.15))
            left, top = max(0, (x1 - px) // step * step), max(0, (y1 - py) // step * step)
            right = min(width, max(left + 16, (x2 + px + step - 1) // step * step))
            bottom = min(height, max(top + 16, (y2 + py + step - 1) // step * step))
            if right - left < 16 or bottom - top < 16:
                rejected["group_extent_invalid"] += 1
                continue
            key = (left, top, right, bottom)
            if key not in seen:
                observed[key] += 1
                sources[key] = source
                seen.add(key)
    # Rank by recurrence on training only. No frame labels or holdout are inputs.
    ranked = sorted(observed, key=lambda b: (-observed[b], b))
    stats["proposal_rejection_counts"] = dict(rejected)
    stats["proposal_budget_omitted"] = max(0, len(ranked) - 16)
    windows: list[dict[str, Any]] = [
        dict(pixel_bounds=b, proposal_source=sources[b], proposal_training_frames=observed[b])
        for b in ranked[:16]
    ]
    # Keep the original proposals for backwards-compatible coverage. They still
    # face the existing 2D arrangement, density and support gates.
    h, w = max(16, round(height * 0.30)), max(16, round(width * 0.20))
    if h < height and w < width:
        windows.extend(
            dict(
                pixel_bounds=(int(x), int(y), int(x + w), int(y + h)), proposal_source="legacy_grid"
            )
            for y in np.linspace(0, height - h, 5).astype(int)
            for x in np.linspace(0, width - w, 5).astype(int)
        )
    stats["proposal_count"] = len(windows)
    stats["proposals"] = [
        dict(
            proposal_source=row["proposal_source"],
            proposal_training_frames=row.get("proposal_training_frames"),
            roi_bounds=[b[0] / width, b[1] / height, b[2] / width, b[3] / height],
            dimensions=[b[2] - b[0], b[3] - b[1]],
        )
        for row in windows
        for b in [row["pixel_bounds"]]
    ]
    return windows
