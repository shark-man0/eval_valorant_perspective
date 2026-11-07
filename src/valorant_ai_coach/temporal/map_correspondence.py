"""Review exact-current Map correspondences without assigning a marker owner."""

from __future__ import annotations

import math
from typing import Any


def _footprint(candidate: dict[str, Any]) -> tuple[float, float, float, float] | None:
    evidence = candidate.get("appearance_evidence")
    if not isinstance(evidence, dict):
        return None
    center, size = evidence.get("center_roi_px"), evidence.get("size_roi_px")
    if (
        not isinstance(center, list)
        or not isinstance(size, list)
        or len(center) != 2
        or len(size) != 2
        or any(type(x) not in (int, float) or not math.isfinite(x) for x in center + size)
        or any(x <= 0 for x in size)
    ):
        return None
    return center[0], center[1], center[0] + size[0], center[1] + size[1]


def _overlap(a: dict[str, Any], b: dict[str, Any]) -> float | None:
    left, right = _footprint(a), _footprint(b)
    if left is None or right is None:
        return None
    x = max(0.0, min(left[2], right[2]) - max(left[0], right[0]))
    y = max(0.0, min(left[3], right[3]) - max(left[1], right[1]))
    intersection = x * y
    area = (left[2] - left[0]) * (left[3] - left[1])
    other_area = (right[2] - right[0]) * (right[3] - right[1])
    return intersection / (area + other_area - intersection)


def independent_ui_ranking(
    pool: list[dict[str, Any]],
    highlighted_index: int,
    competitor_indices: list[int],
    ui_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """Rank archived UI rim evidence separately from NCC appearance similarity.

    This diagnostic does not identify a player. Missing or malformed UI scores
    leave a family unranked instead of silently treating them as zero.
    """
    indices = [highlighted_index, *competitor_indices]
    scores: dict[int, float] = {}
    for row in ui_rows:
        index, score = row.get("candidate_index"), row.get("score")
        if (
            type(index) is int
            and index in indices
            and index not in scores
            and type(score) in (int, float)
            and math.isfinite(score)
        ):
            scores[index] = float(score)
    ranking = (
        sorted(indices, key=lambda index: (-scores[index], index))
        if len(scores) == len(indices)
        else []
    )
    competitors = []
    for index in competitor_indices:
        overlap = _overlap(pool[highlighted_index], pool[index])
        competitors.append(
            {
                "candidate_index": index,
                "footprint_iou": overlap,
                "footprints_disjoint": overlap == 0.0 if overlap is not None else None,
                "ui_score": scores.get(index),
            }
        )
    return {
        "highlighted_index": highlighted_index,
        "ui_score_method": "archived_map_ui_rim_score",
        "ui_ranked_indices": ranking,
        "highlight_ui_score": scores.get(highlighted_index),
        "highlight_over_best_competitor_margin": (
            scores[highlighted_index] - max(scores[i] for i in competitor_indices)
            if competitor_indices and len(scores) == len(indices)
            else None
        ),
        "competitors": competitors,
        "ranking_is_owner_evidence": False,
    }


def correspondence_review(
    pool: list[dict[str, Any]],
    current: list[dict[str, Any]],
    provisional: list[dict[str, Any]],
    view_ids: list[str],
    ui_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Describe what a native Map sample supports and what proof is missing.

    Indices refer only to the unchanged native candidate pool. An associated
    current-view marker is still unowned; neither association nor a highlight
    can establish recorder identity or a geometric Zone.
    """
    associated = [i for i, candidate in enumerate(pool) if candidate in current]
    highlighted = [
        i
        for i, candidate in enumerate(pool)
        if any(h.get("candidate") == candidate for h in provisional)
    ]
    same_appearance_competitors: dict[str, list[int]] = {}
    for index in highlighted:
        evidence = pool[index].get("appearance_evidence", {})
        family = evidence.get("reference_fingerprint") if isinstance(evidence, dict) else None
        if not isinstance(family, str) or not family:
            same_appearance_competitors[str(index)] = []
            continue
        same_appearance_competitors[str(index)] = [
            other
            for other, candidate in enumerate(pool)
            if other != index
            and isinstance(candidate.get("appearance_evidence"), dict)
            and candidate["appearance_evidence"].get("reference_fingerprint") == family
        ]
    independent_rankings = (
        {
            str(index): independent_ui_ranking(
                pool, index, same_appearance_competitors[str(index)], ui_rows
            )
            for index in highlighted
        }
        if ui_rows is not None
        else {}
    )
    if not pool:
        status = "NO_MARKER_CANDIDATE"
    elif highlighted:
        status = "PROVISIONAL_HIGHLIGHT_WITH_WEAK_VIEW"
    elif associated and view_ids:
        status = "CURRENT_VIEW_ASSOCIATED_CANDIDATES"
    else:
        status = "UNASSIGNED_MARKER_CANDIDATES"
    return {
        "contract": "development_map_correspondence_review_v2",
        "status": status,
        "native_marker_candidate_count": len(pool),
        "current_view_associated_indices": associated,
        "provisional_highlight_indices": highlighted,
        "same_appearance_competitor_indices": same_appearance_competitors,
        "independent_ui_rankings": independent_rankings,
        "provisional_highlight_ambiguous": any(same_appearance_competitors.values()),
        "current_view_evidence_count": len(view_ids),
        "strict_recorder_marker_count": 0,
        "missing_for_strict_correspondence": [
            "globally_calibrated_map_geometry",
            "verified_recorder_identity_at_current_native_sample",
            "verified_spectator_or_remote_exclusion",
            "independent_marker_to_recorder_correspondence",
        ]
        if pool
        else [],
        "ownership": "UNKNOWN",
        "position_authority": False,
        "temporal_path_eligible": False,
    }
