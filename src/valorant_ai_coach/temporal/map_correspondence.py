"""Unqualified generic Map/Camera candidate correspondence.

Keeps the existing ranker's order and original native-source provenance.
No marker is selected as a confirmed recorder position by this bridge.
"""
from __future__ import annotations

import math
from copy import deepcopy
from typing import Any, cast

from .composite_view import VERSION as COMPOSITE_VERSION
from .evidence import digest

VERSION = "development_generic_map_camera_bridge_v1"
MAX_RANKS = 64
VETO = {"spectator", "death", "downed", "remote", "revival",
        "result", "intermission"}


def _self_supported(frame: dict[str, Any], rows: list[dict[str, Any]]) -> bool:
    camera, life = frame["camera"], frame["life"]
    ids = {r["observation_id"] for r in rows}
    signals = {s for r in rows for s in r["signals"]}
    if (
        camera["value"] != "SELF" or life["value"] != "ALIVE"
        or any(x.get("origin") not in {
            "observation_projection", "visual_state_projection"
        } for x in (camera, life))
        or any(not ids.intersection(x.get("evidence_ids", []))
               for x in (camera, life))
        or signals & VETO
        or any(r["continuity"].get("decode_ok") is False for r in rows)
        or frame.get("viewed_identity", {}).get(
            "agent_signature_relation"
        ) == "DIFFERENT"
    ):
        return False
    return "owner_hud" in signals or any(
        r["raw"].get("camera_hypothesis") == "SELF"
        and r["raw"].get("current_HUD_component_supported") is True
        and isinstance(r["raw"].get("view_hp"), dict)
        and r["raw"]["view_hp"].get("display") is not None
        for r in rows
    )


def associate_generic_map(
    frame: dict[str, Any], rows: list[dict[str, Any]],
    ranking: dict[str, Any], pool: dict[str, Any],
) -> list[dict[str, Any]]:
    """Return rank-preserving role hypotheses, or abstain on mismatched inputs."""
    sample = frame["sample"]
    if (pool.get("sample") != sample or pool.get("producer_fingerprint")
            != ranking.get("map_supplier_fingerprint")):
        return []
    ranked = ranking.get("rankings")
    if not isinstance(ranked, list) or not ranked:
        return []
    bound = [
        r for r in rows
        if r.get("sample") == sample
        and r["raw"].get("schema") == COMPOSITE_VERSION
        and r["raw"].get("marker_candidate_supplier")
        == pool["producer_fingerprint"]
        and r["raw"].get("marker_context_rankings") == ranked
        and r["observation_id"] in ranking.get("evidence_ids", [])
    ]
    if len(bound) != 1 or not isinstance(pool.get("map_candidates"), list):
        return []
    used: set[int] = set()
    for item in ranked:
        if not isinstance(item, dict):
            return []
        index, score = item.get("candidate_index"), item.get("score")
        if (type(index) is not int or not 0 <= index < len(pool["map_candidates"])
                or index in used or type(score) not in (int, float)
                or not math.isfinite(cast(float, score))):
            return []
        used.add(index)

    camera = frame["camera"]["value"]
    if _self_supported(frame, rows):
        roles = ["RECORDER_SELF", "OTHER", "UNKNOWN"]
        subject = "recorder_position_candidate"
    elif camera == "SPECTATOR":
        roles = ["SPECTATED_ACTOR", "OTHER", "UNKNOWN"]
        subject = "spectated_actor_position_candidate"
    else:
        roles = ["VIEWED_ACTOR", "OTHER", "UNKNOWN"]
        subject = "unresolved_viewed_actor_candidate"
    view = frame.get("viewed_identity", {})
    evidence = sorted(set(
        [pool["observation_id"], bound[0]["observation_id"]]
        + frame["camera"].get("evidence_ids", [])
        + frame["life"].get("evidence_ids", [])
        + view.get("evidence_ids", [])
    ))
    output: list[dict[str, Any]] = []
    for rank, item in enumerate(ranked[:MAX_RANKS], 1):
        entry = {
            "contract": VERSION, "rank": rank,
            "candidate_index": item["candidate_index"],
            "ranking": deepcopy(item),
            "candidate": deepcopy(pool["map_candidates"][item["candidate_index"]]),
            "sample": deepcopy(sample),
            "map_supplier_fingerprint": pool["producer_fingerprint"],
            "map_observation_id": pool["observation_id"],
            "map_profile_fingerprint": pool["context"].get("profile_fingerprint"),
            "ranking_observation_id": bound[0]["observation_id"],
            "role_hypotheses": roles.copy(), "position_subject": subject,
            "camera_candidate": camera, "life_candidate": frame["life"]["value"],
            "viewed_agent_candidates": deepcopy(view.get("viewed_agent_candidates", [])),
            "recorder_agent_candidates": deepcopy(
                (view.get("recording_player_anchor") or {}).get("agent_candidates", [])
            ),
            "signature_relation": view.get("agent_signature_relation", "UNKNOWN"),
            "evidence_ids": evidence, "ownership": "UNKNOWN",
            "qualified": False, "position_authority": False,
            "temporal_path_eligible": False,
            "reason": "generic_rank_with_current_common_camera",
            "uncertainty": "no_strict_marker_recorder_correspondence",
        }
        entry["hypothesis_id"] = digest(entry)
        output.append(entry)
    return output


# Existing review contract retained for application and Map projection consumers.
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
            and isinstance(score, (int, float))
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
