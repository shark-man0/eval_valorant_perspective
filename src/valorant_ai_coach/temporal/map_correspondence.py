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
    if not pool:
        status = "NO_MARKER_CANDIDATE"
    elif highlighted:
        status = "PROVISIONAL_HIGHLIGHT_WITH_WEAK_VIEW"
    elif associated and view_ids:
        status = "CURRENT_VIEW_ASSOCIATED_CANDIDATES"
    else:
        status = "UNASSIGNED_MARKER_CANDIDATES"
    return {
        "contract": "development_map_correspondence_review_v1",
        "status": status,
        "native_marker_candidate_count": len(pool),
        "current_view_associated_indices": associated,
        "provisional_highlight_indices": highlighted,
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
