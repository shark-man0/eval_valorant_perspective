"""Current-pixel Map role hypotheses; never an owner, state or path authority."""

from __future__ import annotations

import math
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from typing import Any

from .evidence import digest

CONTRACT = "development_provisional_map_roles_v1"


def rule_sha256() -> str:
    return sha256(Path(__file__).read_bytes()).hexdigest()


_BARRIERS = {
    "spectator", "remote", "death", "downed", "revival", "ability_return",
    "recorder_elimination_display", "hud_not_detected", "result", "intermission",
}
_PIXEL_KEYS = (
    "source_id", "source_sha256", "native_pts_tick", "native_time_base",
    "native_pixel_sha256", "frame_size_px",
)


def _current_self_view(row: dict[str, Any]) -> bool:
    raw = row["raw"]
    hp = raw.get("view_hp")
    if not isinstance(hp, dict):
        return False
    display, confidence = hp.get("display"), hp.get("confidence")
    return (
        row["context"].get("unqualified_view_model") is True
        and "owner_hud" in row["signals"]
        and raw.get("camera_hypothesis") == "SELF"
        and raw.get("current_HUD_component_supported") is True
        and raw.get("owner_hypothesis_exclusions") == []
        and raw.get("owned_verb_phrase") is None
        and isinstance(display, str) and display.isascii() and display.isdigit()
        and 1 <= int(display) <= 150
        and isinstance(confidence, (int, float)) and not isinstance(confidence, bool)
        and math.isfinite(confidence) and .90 <= confidence <= 1
    )


def _highlight(row: dict[str, Any]) -> int | None:
    packet = row["raw"]
    if (
        packet.get("schema") != "map_consumer_provisional_v1"
        or packet.get("qualification") != "development_only"
        or packet.get("ownership") != "UNKNOWN"
        or packet.get("formal_outputs") != 0
        or packet.get("observation_sha256")
        != digest({k: v for k, v in packet.items() if k != "observation_sha256"})
    ):
        return None
    pool, ui = packet.get("pool", {}), packet.get("ui", {})
    if not isinstance(pool, dict) or not isinstance(ui, dict):
        return None
    if (
        pool.get("sample") != row["sample"]
        or pool.get("candidates") != row["map_candidates"]
        or not isinstance(pool.get("pool_sha256"), str)
        or ui.get("sample_sha256") != row["sample"]["sample_sha256"]
        or ui.get("pool_sha256") != pool["pool_sha256"]
        or ui.get("status") != "highlighted_marker_candidate"
        or ui.get("qualification") != "development_only"
        or ui.get("ownership") != "UNKNOWN" or ui.get("formal_outputs") != 0
    ):
        return None
    rows = ui.get("rows")
    if not isinstance(rows, list) or not rows:
        return None
    indices = []
    for item in rows:
        if not isinstance(item, dict):
            return None
        index, score = item.get("candidate_index"), item.get("score")
        if (type(index) is not int or not 0 <= index < len(row["map_candidates"])
                or not isinstance(score, (int, float)) or isinstance(score, bool)
                or not math.isfinite(score)):
            return None
        indices.append(index)
    if len(set(indices)) != len(indices):
        return None
    ranked = sorted(rows, key=lambda item: (-item["score"], item["candidate_index"]))
    if len(ranked) > 1 and ranked[0]["score"] == ranked[1]["score"]:
        return None
    selected = ui.get("selected_index")
    if type(selected) is not int or selected != ranked[0]["candidate_index"]:
        return None
    return selected


def provisional_map_roles(
    frame: dict[str, Any], rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Associate a measured highlight only with a current weak SELF hypothesis.

    Carried/reconciled state alone is insufficient. All original supplier
    samples must match the current Source/native PTS/pixels/dimensions; epochs
    may differ only through the engine's existing exact-pixel fusion. A report,
    contrary signal, failed decode or unresolved current state blocks this
    proposal. No Source/agent reference or historical initial index is read.
    """
    if (
        any(frame[d]["value"] != v or frame[d]["origin"] != "observation_projection"
            or frame[d]["reason"] != "current_observation"
            for d, v in (("life", "ALIVE"), ("camera", "SELF")))
        or set(frame["round"]["hypotheses"]) & {"ENDED", "INTERMISSION"}
        or any(set(r["signals"]) & _BARRIERS for r in rows)
        or any(r["continuity"].get("decode_ok") is False for r in rows)
        or any(any(r["sample"][k] != frame["sample"][k] for k in _PIXEL_KEYS) for r in rows)
    ):
        return []
    views = [r for r in rows if _current_self_view(r)
             and all(r["observation_id"] in frame[d]["evidence_ids"] for d in ("life", "camera"))]
    if not views:
        return []
    hypotheses = []
    for row in rows:
        selected = _highlight(row)
        if selected is None:
            continue
        hypothesis = {
            "contract": CONTRACT,
            "candidate": deepcopy(row["map_candidates"][selected]),
            "sample": deepcopy(row["sample"]),
            "Map_observation_id": row["observation_id"],
            "view_evidence_ids": sorted(v["observation_id"] for v in views),
            "candidate_role": "RECORDER_SELF",
            "role_hypotheses": ["RECORDER_SELF", "VIEWED_PLAYER", "OTHER", "UNKNOWN"],
            "uncertainty": "weak_self_view_and_highlight_do_not_prove_recorder_identity",
            "reason": "current_shared_SELF_and_supplier_highlight",
            "confidence": None,
            "ownership": "UNKNOWN", "qualified": False,
            "position_authority": False, "temporal_path_eligible": False,
        }
        hypothesis["hypothesis_id"] = digest(hypothesis)
        hypotheses.append(hypothesis)
    return hypotheses
