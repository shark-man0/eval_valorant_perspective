"""Unqualified generic Map/Camera candidate correspondence.

Keeps the existing ranker's order and original native-source provenance.
No marker is selected as a confirmed recorder position by this bridge.
"""
from __future__ import annotations

import math
from copy import deepcopy
from typing import Any

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
                or not math.isfinite(score)):
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
