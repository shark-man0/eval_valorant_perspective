"""Review exact-current Map correspondences without assigning a marker owner."""

from __future__ import annotations

from typing import Any


def correspondence_review(
    pool: list[dict[str, Any]],
    current: list[dict[str, Any]],
    provisional: list[dict[str, Any]],
    view_ids: list[str],
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
