"""Research visual projections used only by the existing shared state owner.

This module revises its supplied state rows; it is not another state engine.
Original estimates and observation IDs remain attached. No qualification changes.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from copy import deepcopy
from typing import Any

from .evidence import digest, native_time, source_scope
from .round_visual import round_visual_candidates

VERSION = "development_practical_visual_state_v1"


def _confidence(value: Any, minimum: float = 0) -> bool:
    return bool(type(value) in (int, float) and math.isfinite(value) and minimum <= value <= 1)


def selected_agent(candidates: list[dict[str, Any]]) -> str | None:
    ranked = sorted([r for r in candidates if _confidence(r.get("score"))],
                    key=lambda r: r["score"], reverse=True)
    if not ranked or ranked[0].get("score", 0) < .65:
        return None
    if len(ranked) > 1 and ranked[0]["score"] - ranked[1]["score"] < .08:
        return None
    value = ranked[0].get("agent")
    return value if isinstance(value, str) else None


def _hp_support(rows: list[dict[str, Any]]) -> bool:
    for r in rows:
        raw = r["raw"]
        hp = raw.get("view_hp", {})
        if not isinstance(hp, dict):
            continue
        text = hp.get("display")
        if (raw.get("camera_hypothesis") == "SELF"
                and raw.get("current_HUD_component_supported") is True
                and not raw.get("owned_verb_phrase")
                and isinstance(text, str) and text.isascii() and text.isdigit()
                and 0 < int(text) <= 150 and _confidence(hp.get("confidence"), .90)):
            return True
    return False


def apply_visual_state(
    states: list[dict[str, Any]], observations: dict[str, Any],
    estimate: Callable[..., dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Use explicit cues in research estimates, retaining competing hypotheses."""
    history: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    by_sample = {f["sample"]["sample_sha256"]: f for f in states}

    def revise(frame: dict[str, Any], domain: str, value: str, evidence: list[str],
               reason: str) -> None:
        before = deepcopy(frame[domain])
        if before["value"] == value:
            return
        after = estimate(value, alternatives=[value, *before["hypotheses"]],
                         reason=reason, evidence=[*before["evidence_ids"], *evidence],
                         origin="visual_state_projection")
        after.update(rule_estimate=before, uncertainty="unqualified_visual_state_candidate")
        frame[domain] = after
        history.append({"sample": frame["sample"], "domain": domain, "before": before,
                        "after": deepcopy(after), "evidence_ids": sorted(set(evidence)),
                        "reason": reason, "qualified": False})

    for frame in states:
        rows = [observations[i] for i in frame["observation_ids"]]
        signals = {s for r in rows for s in r["signals"]}
        view = frame.get("viewed_identity", {})
        anchor = view.get("recording_player_anchor")
        if not anchor or signals & {"remote", "downed", "revival", "death"}:
            continue
        if source_scope(anchor["sample"]) != source_scope(frame["sample"]):
            continue
        if native_time(anchor["sample"]) >= native_time(frame["sample"]):
            continue
        current = selected_agent(view.get("viewed_agent_candidates", []))
        recorder = selected_agent(anchor.get("agent_candidates", []))
        relation = view.get("agent_signature_relation")
        same = relation == "COMPATIBLE" or bool(current and current == recorder)
        different = bool(current and recorder and current != recorder)
        portrait = view.get("portrait_candidate", {}).get("agent_candidates", [])
        portrait_agrees = bool(current and any(r.get("agent") == current
                                               and _confidence(r.get("score"), .50)
                                               for r in portrait))
        evidence = sorted(set(view.get("evidence_ids", []) + anchor["evidence_ids"]
                              + [r["observation_id"] for r in rows
                                 if r["raw"].get("camera_hypothesis") is not None]))
        report = view.get("report_or_log_visibility", {}).get("combat_report") == "VISIBLE"
        owned_display = any(r["context"].get("elimination_display_signature") for r in rows)
        if different and portrait_agrees and (report or "spectator" in signals):
            revise(frame, "camera", "SPECTATOR", evidence,
                   "different_viewed_agent_portrait_and_report_or_spectator")
            if owned_display and "spectator" in signals:
                revise(frame, "life", "DEAD", evidence,
                       "current_owned_display_and_visually_distinct_spectator")
        elif same and _hp_support(rows) and "spectator" not in signals:
            # Matching an agent alone never establishes owner identity.
            # Current owner-shaped HUD/HP is additional support. A new BUY can
            # resolve an old victim report; a current death/remote/down cue vetoes.
            alive = frame["life"]["value"] != "DEAD" or "buy" in signals
            if alive and (not owned_display or "buy" in signals):
                revise(frame, "camera", "SELF", evidence,
                       "recorder_signature_and_current_self_HUD_HP")
                revise(frame, "life", "ALIVE", evidence,
                       "recorder_signature_and_current_self_HUD_HP")
        view["current_view_candidate"] = frame["camera"]["value"]
        view["recorder_life_candidate"] = frame["life"]["value"]
        view["state_changed"] = any(h["sample"] == frame["sample"] for h in history[-2:])

    cues = round_visual_candidates(list(observations.values()))["candidates"]
    for cue in cues:
        cue_frame = by_sample.get(cue["sample_sha256"])
        if cue_frame is None:
            continue
        frame = cue_frame
        rows = [observations[i] for i in frame["observation_ids"]]
        signals = {s for r in rows for s in r["signals"]}
        kind = cue["kind"]
        # An observed BUY belongs to the new Round; a delayed score cue must
        # not move it into the previous ending. No second semantic clock needed.
        if kind == "end" and "buy" in signals:
            continue
        revise(frame, "round", "ACTIVE" if kind == "start" else "ENDED",
               cue["support_observation_ids"], "measured_round_visual_" + kind)
        events.append(_event("round_" + kind, frame, frame,
                             cue["support_observation_ids"]))

    # The shared owner can use a measured barrier loss as a single start cue.
    # A failed OCR scan alone is never evidence that a purchase phase ended.
    prior: dict[str, Any] | None = None
    last_dead: dict[tuple[str, ...], dict[str, Any]] = {}
    for frame in states:
        rows = [observations[i] for i in frame["observation_ids"]]
        signals = {s for r in rows for s in r["signals"]}
        scope = source_scope(frame["sample"])
        if not frame["continuity"].get("carry_allowed", False):
            prior = None
            last_dead.pop(scope, None)
        if prior and source_scope(prior["sample"]) == scope:
            previous_rows = [observations[i] for i in prior["observation_ids"]]
            before_barriers = [r for r in previous_rows if r["raw"].get(
                "screen_cues", {}).get("barrier", {}).get("present") is True]
            after_barriers = [r for r in rows if r["raw"].get(
                "screen_cues", {}).get("barrier", {}).get("not_detected") is True]
            gap = native_time(frame["sample"]) - native_time(prior["sample"])
            loss = any(_same_map_view(a, b) for a in before_barriers for b in after_barriers)
            if (0 < gap <= 2 and prior["round"]["value"] == "BUY" and loss
                    and not signals & {"buy", "result", "intermission", "remote"}
                    and not any(r["raw"].get("hud_visibility", {}).get("candidates")
                                for r in rows)):
                evidence = [r["observation_id"] for r in before_barriers + after_barriers]
                revise(frame, "round", "ACTIVE", evidence, "observed_purchase_barrier_loss")
                events.append(_event("round_start", prior, frame, evidence))
            if (frame["camera"]["value"] == "SPECTATOR"
                    and prior["camera"]["value"] != "SPECTATOR"
                    and frame["camera"]["origin"] == "visual_state_projection"):
                events.append(_event("spectator", prior, frame,
                                     frame["camera"]["evidence_ids"]))
            agents = [selected_agent(f.get("viewed_identity", {}).get(
                "viewed_agent_candidates", [])) for f in (prior, frame)]
            if (0 < gap <= 5 and all(f["camera"]["value"] == "SPECTATOR"
                                    for f in (prior, frame))
                    and all(agents) and agents[0] != agents[1]):
                events.append(_event("view_target_change", prior, frame,
                                     prior["observation_ids"] + frame["observation_ids"]))
        dead = last_dead.get(scope)
        if (dead and frame["camera"]["value"] == "SELF" and frame["life"]["value"] == "ALIVE"
                and "buy" in signals and any(frame[d]["origin"] == "visual_state_projection"
                                             for d in ("life", "camera"))):
            events.append(_event("return", dead, frame,
                                 dead["life"]["evidence_ids"] + frame["life"]["evidence_ids"]))
            last_dead.pop(scope, None)
        elif frame["life"]["value"] == "DEAD":
            last_dead[scope] = frame
        prior = frame

    ended: set[tuple[str, ...]] = set()
    for frame in states:
        rows = [observations[i] for i in frame["observation_ids"]]
        _attach_map_view(frame, rows)
        scope = source_scope(frame["sample"])
        # Each admitted Source represents one physical match. A noisy BUY
        # reading must not duplicate a persisting match-result display.
        result = [r for r in rows if r["raw"].get("screen_cues", {}).get(
            "match_result", {}).get("visible") is True]
        if result and scope not in ended:
            events.append(_event("match_end", frame, frame,
                                 [r["observation_id"] for r in result]))
            ended.add(scope)
    return history, events


def _same_map_view(a: dict[str, Any], b: dict[str, Any]) -> bool:
    first = a["raw"]["screen_cues"]["barrier"]
    second = b["raw"]["screen_cues"]["barrier"]
    x, y = first.get("map_signature", []), second.get("map_signature", [])
    return bool(first.get("map_view_supported") and second.get("map_view_supported")
                and len(x) == len(y) == 1024
                and sum(abs(u-v) for u, v in zip(x, y, strict=True)) / (255*1024) <= .15)


def _attach_map_view(frame: dict[str, Any], rows: list[dict[str, Any]]) -> None:
    """Join existing marker ranking to current view without issuing owner positions."""
    ranking = frame["map"].get("marker_ranking_hypotheses")
    if not ranking:
        return
    ranking["camera_candidate"] = frame["camera"]["value"]
    pools = [r for r in rows if r["producer_fingerprint"] == ranking["map_supplier_fingerprint"]]
    if len(pools) != 1:
        return
    pool = pools[0]
    hypotheses = []
    camera = frame["camera"]["value"]
    for rank, item in enumerate(ranking["rankings"][:5], 1):
        index = item.get("candidate_index")
        if type(index) is not int or not 0 <= index < len(pool["map_candidates"]):
            continue
        hypotheses.append({
            "rank": rank, "candidate": deepcopy(pool["map_candidates"][index]),
            "ranking": deepcopy(item), "sample": deepcopy(frame["sample"]),
            "camera_candidate": camera,
            "viewed_agent_candidates": deepcopy(frame.get("viewed_identity", {}).get(
                "viewed_agent_candidates", [])),
            "role_hypotheses": ["RECORDER_SELF", "OTHER", "UNKNOWN"]
            if camera == "SELF" and frame["life"]["value"] == "ALIVE"
            else ["SPECTATED_ACTOR", "OTHER", "UNKNOWN"] if camera == "SPECTATOR"
            else ["VIEWED_ACTOR", "OTHER", "UNKNOWN"],
            "evidence_ids": sorted(set(ranking["evidence_ids"] + [pool["observation_id"]]
                                       + frame["camera"]["evidence_ids"])),
            "reason": "current_shared_camera_and_existing_marker_ranking",
            "uncertainty": "marker_ranking_does_not_establish_actor_or_recorder_identity",
            "ownership": "UNKNOWN", "position_authority": False,
            "temporal_path_eligible": False, "qualified": False,
        })
    frame["map"]["research_view_position_hypotheses"] = hypotheses
    from .map_correspondence import associate_generic_map

    frame["map"]["research_map_correspondence_hypotheses"] = associate_generic_map(
        frame, rows, ranking, pool
    )


def _event(kind: str, low: dict[str, Any], high: dict[str, Any],
           evidence: list[str]) -> dict[str, Any]:
    result = {"kind": kind, "lower_sample": deepcopy(low["sample"]),
              "upper_sample": deepcopy(high["sample"]),
              "evidence_ids": sorted(set(evidence)), "status": "unqualified_visual_candidate",
              "internal_game_event_time": None, "qualified": False}
    result["candidate_id"] = digest(result)
    return result


def reconcile_visual_transitions(
    transitions: list[dict[str, Any]], states: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Archive stale pre-projection edges without deleting their prior evidence."""
    points = {f["sample"]["sample_sha256"]: f for f in states}
    superseded = []
    retained = []
    for event in transitions:
        domain = event.get("domain")
        upper = points.get(event["upper_sample"]["sample_sha256"])
        lower = points.get(event["lower_sample"]["sample_sha256"])
        if (domain not in {"round", "life", "camera"} or upper is None or lower is None
                or event["kind"] not in {"state_change", "spectator", "round_start", "round_end"}
                or (event["kind"] != "state_change"
                    and not any(f[domain]["origin"] == "visual_state_projection"
                                for f in (lower, upper)))):
            retained.append(event)
            continue
        before = deepcopy(event)
        if event.get("after") != upper[domain]["value"]:
            superseded.append({"rule_transition": before, "status": "superseded",
                               "reason": "upper_state_revised_by_shared_postprocessing",
                               "current_estimate": deepcopy(upper[domain]), "qualified": False})
            continue
        if lower[domain]["value"] == upper[domain]["value"]:
            superseded.append({"rule_transition": before, "status": "superseded",
                               "reason": "no_state_change_after_shared_revision",
                               "current_estimate": deepcopy(upper[domain]), "qualified": False})
            continue
        if event.get("before") != lower[domain]["value"]:
            event["rule_transition"] = before
            event["before"] = lower[domain]["value"]
            event["evidence_ids"] = sorted(set(event["evidence_ids"]
                                             + lower[domain]["evidence_ids"]))
        retained.append(event)
    transitions[:] = retained
    return superseded


def merge_visual_events(existing: list[dict[str, Any]], added: list[dict[str, Any]]) -> None:
    """A lasting result or two suppliers must not create another ending."""
    for event in added:
        if any(e["kind"] == event["kind"]
               and source_scope(e["upper_sample"]) == source_scope(event["upper_sample"])
               and (abs(native_time(e["upper_sample"]) - native_time(event["upper_sample"])) <= 1
                    or bool(set(e["evidence_ids"]) & set(event["evidence_ids"])))
               for e in existing):
            continue
        existing.append(event)
    existing.sort(key=lambda e: (source_scope(e["upper_sample"]),
                                 native_time(e["upper_sample"])))
