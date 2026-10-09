from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from statistics import median
from typing import Any

from .global_lifecycle import GlobalLifecycleQualification, GlobalRoundLifecycle
from .round_lifecycle import (
    RoundLifecycle,
    is_discontinuous,
    preparation_confidence,
    score_is_continuous,
)


@dataclass(frozen=True, slots=True)
class KillSideAssignment:
    row_added: bool
    victim_side: str
    killer_side: str


def resolve_kill_sides(
    *,
    kill_feed_row_added: bool,
    ally_alive_before: int | None,
    ally_alive_after: int | None,
    enemy_alive_before: int | None,
    enemy_alive_after: int | None,
    killfeed_color_agrees: bool = False,
    normal_kill_confirmed: bool | None = None,
) -> KillSideAssignment:
    """Resolve sides only for a newly added row and a unique one-player drop."""

    if not kill_feed_row_added:
        return KillSideAssignment(False, "unknown", "unknown")
    ally_drop = _drop(ally_alive_before, ally_alive_after)
    enemy_drop = _drop(enemy_alive_before, enemy_alive_after)
    if ally_drop and enemy_alive_before is not None and enemy_alive_before == enemy_alive_after:
        victim = "ally"
    elif enemy_drop and ally_alive_before is not None and ally_alive_before == ally_alive_after:
        victim = "enemy"
    else:
        victim = "unknown"
    normal = killfeed_color_agrees if normal_kill_confirmed is None else normal_kill_confirmed
    if victim == "unknown" or not killfeed_color_agrees or not normal:
        killer = "unknown"
    else:
        killer = "enemy" if victim == "ally" else "ally"
    return KillSideAssignment(True, victim, killer)


def aggregate_observation_quality(
    frame_hud_confidences: Sequence[float],
    valid_timeline_fraction: float,
    *,
    frame_visual_confidences: Sequence[float] = (),
    visual_timeline_fraction: float = 0.0,
    missing_intervals: Sequence[Mapping[str, float]] = (),
) -> dict[str, Any]:
    """Aggregate the HUD/visual observation layer, independently of evaluation."""

    hud_fraction = _fraction(valid_timeline_fraction, "valid_timeline_fraction")
    visual_fraction = _fraction(visual_timeline_fraction, "visual_timeline_fraction")
    hud = _confidence_median(frame_hud_confidences) * hud_fraction
    visual = _confidence_median(frame_visual_confidences) * visual_fraction
    normalized_missing: list[dict[str, float]] = []
    for item in missing_intervals:
        start_sec = float(item["start_sec"])
        end_sec = float(item["end_sec"])
        if not math.isfinite(start_sec) or not math.isfinite(end_sec) or end_sec < start_sec:
            raise ValueError("missing intervalは有限でstart_sec<=end_secである必要があります")
        if end_sec - start_sec >= 1.0:
            normalized_missing.append({"start_sec": start_sec, "end_sec": end_sec})
    return {
        "hud_confidence": round(hud, 4),
        "visual_confidence": round(visual, 4),
        "timeline_completeness": hud_fraction,
        "missing_intervals": normalized_missing,
    }


class HudDirectEventBuilder:
    """Emit only direct HUD facts whose source evidence meets the HUD contract."""

    def build(
        self,
        observations: Sequence[dict[str, Any]],
        *,
        evidence_by_frame: Mapping[int, Mapping[str, Any]] | None = None,
        lifecycle_sink: Callable[[dict[str, Any]], None] | None = None,
        global_qualification: GlobalLifecycleQualification | None = None,
    ) -> tuple[dict[str, Any], ...]:
        from .timeline import join_hud_timeline

        events: list[dict[str, Any]] = []
        ordered = sorted(observations, key=lambda item: float(item.get("time_sec", 0.0)))
        joined_evidence = join_hud_timeline(ordered, evidence_by_frame or {})
        previous: dict[str, Any] | None = None
        previous_evidence: Mapping[str, Any] = {}
        death_latched = False
        active_status: dict[str, Any] | None = None
        status_contiguous = True
        lifecycle = RoundLifecycle()
        global_lifecycle = (
            GlobalRoundLifecycle(global_qualification) if global_qualification is not None else None
        )
        for index, observation in enumerate(ordered):
            values = observation.get("values", {})
            values = values if isinstance(values, dict) else {}
            frame_index = observation.get("frame_index", index)
            evidence = joined_evidence.get(frame_index, {})
            timestamp = max(0.0, float(observation.get("time_sec", 0.0)))
            confidence = _hud_confidence(observation)
            if is_discontinuous(previous, observation, evidence):
                previous = None
                previous_evidence = {}
                death_latched = False
                active_status = None
                status_contiguous = True
                lifecycle.reset()
                if global_lifecycle is not None:
                    global_lifecycle.reset()
            if evidence.get("player_revived_confirmed") is True:
                death_latched = False
            is_start = (
                previous is not None
                and _round_start_confirmed(previous, observation, evidence)
                and min(confidence, preparation_confidence(previous)) >= 0.65
            )
            is_end = evidence.get("round_end_joined") is True or (
                previous is not None and _round_end_confirmed(previous, observation, evidence)
            )
            decisions = (
                global_lifecycle.advance(observation, evidence)
                if global_lifecycle is not None
                else lifecycle.advance(
                    previous, observation, evidence,
                    start_candidate=is_start, end_candidate=is_end,
                )
            )
            for boundary in decisions:
                if boundary.kind == "round_start":
                    death_latched = False
                    active_status = None
                    status_contiguous = True
                events.append(
                    _event(
                        boundary.kind,
                        boundary.time_sec,
                        "system",
                        boundary.attributes,
                        boundary.confidence,
                        cross_checked=True,
                    )
                )

            if lifecycle_sink is not None:
                lifecycle_sink(
                    {
                        "frame_index": frame_index,
                        "time_sec": timestamp,
                        "state": global_lifecycle.state if global_lifecycle else lifecycle.state,
                        "boundary_scope": "global_system" if global_lifecycle else "legacy_hud",
                        "global_transition_reason": (
                            global_lifecycle.diagnostic_reason if global_lifecycle else None
                        ),
                        "hud_confidence": confidence,
                        "preparation_confidence": preparation_confidence(observation),
                        "start_candidate": is_start,
                        "end_candidate": is_end,
                    }
                )

            if previous is not None:
                prior_values = previous.get("values", {})
                prior_values = prior_values if isinstance(prior_values, dict) else {}
                prior_confidence = _hud_confidence(previous)
                event_confidence = min(confidence, prior_confidence)

                if _buy_phase_confirmed(observation, evidence) and not _buy_phase_confirmed(
                    previous, previous_evidence
                ):
                    events.append(
                        _event("buy_phase", timestamp, "team", {}, confidence, cross_checked=True)
                    )

                prior_spike = prior_values.get("spike_state")
                spike = values.get("spike_state")
                if (
                    spike == "planted"
                    and prior_spike != "planted"
                    and bool(evidence.get("plant_timer_visible"))
                ):
                    events.append(
                        _event(
                            "spike_planted",
                            timestamp,
                            "team",
                            {"site": _optional_nonempty_string(evidence.get("site"))},
                            min(
                                event_confidence,
                                _evidence_confidence(evidence, "plant_timer_confidence"),
                            ),
                            cross_checked=True,
                        )
                    )

            current_player_hud_valid = _player_hud_is_valid(observation, values)
            previous_player_hud_valid = previous is not None and _player_hud_is_valid(
                previous, previous.get("values", {})
            )
            if current_player_hud_valid:
                before_slots = (
                    previous.get("values", {}).get("ability_slots", [])
                    if previous is not None and previous_player_hud_valid
                    else []
                )
                before_confidence = (
                    _hud_confidence(previous)
                    if previous is not None and previous_player_hud_valid
                    else 1.0
                )
                ability_confidence = min(confidence, before_confidence)
                for slot_event in _ability_state_changes(
                    before_slots,
                    values.get("ability_slots", []),
                    timestamp,
                    ability_confidence,
                    initial_cross_checked=_ability_slots_cross_checked(evidence),
                ):
                    events.append(slot_event)

            pre_round = (
                observation.get("primary_state") == "buy_menu_open"
                or "buy_phase_banner" in observation.get("state_flags", ())
                or values.get("buy_phase_visible") is True
            )
            # A combat report can remain open after respawn; it is not a new death.
            death_event = (
                None
                if pre_round or is_start
                else _player_death_event(timestamp, confidence, values, evidence)
            )
            if death_event is not None and not death_latched and _event_acceptable(death_event):
                events.append(death_event)
                death_latched = True
            status_event = (
                _status_event(timestamp, confidence, evidence) if current_player_hud_valid else None
            )
            if status_event is not None and not _event_acceptable(status_event):
                status_event = None
            status_key = (
                None
                if status_event is None
                else (
                    status_event["attributes"]["effect_type"],
                    status_event["attributes"]["affected_side"],
                    status_event["attributes"]["source_side"],
                )
            )
            active_key = (
                None
                if active_status is None
                else (
                    active_status["attributes"]["effect_type"],
                    active_status["attributes"]["affected_side"],
                    active_status["attributes"]["source_side"],
                )
            )
            clear_observed = (
                status_event is None
                and current_player_hud_valid
                and confidence >= 0.65
                and bool(
                    observation.get("view_context", {}).get("is_player_world_view_trustworthy")
                )
            )
            if active_status is not None and (
                (status_event is None and not clear_observed)
                or (previous is not None and timestamp - float(previous["time_sec"]) > 1.0)
            ):
                status_contiguous = False
            if status_key != active_key and (status_event is not None or clear_observed):
                if active_status is not None and status_contiguous:
                    active_status["attributes"]["duration_sec"] = max(
                        0, timestamp - active_status["time_sec"]
                    )
                active_status = status_event
                status_contiguous = True
                if status_event is not None:
                    events.append(status_event)

            rows = values.get("kill_feed_rows", [])
            for row_index, row in enumerate(rows if isinstance(rows, list) else []):
                if not isinstance(row, dict) or not _kill_row_added(
                    evidence, row, row_index, len(rows)
                ):
                    continue
                pair = evidence.get("kill_roster_pairs", {}).get(row_index, {})
                sides = resolve_kill_sides(
                    kill_feed_row_added=True,
                    ally_alive_before=_optional_int(pair.get("ally_before")),
                    ally_alive_after=_optional_int(pair.get("ally_after")),
                    enemy_alive_before=_optional_int(pair.get("enemy_before")),
                    enemy_alive_after=_optional_int(pair.get("enemy_after")),
                    killfeed_color_agrees=(
                        row.get("color_agrees") is True
                        or _row_evidence_true(evidence, "killfeed_color_agrees", row_index)
                    ),
                    normal_kill_confirmed=_row_evidence_value(
                        row, evidence, "normal_kill_confirmed", row_index
                    ),
                )
                row_confidence = _bounded_confidence(row.get("confidence", 0.0))
                attributes: dict[str, Any] = {
                    "killer_side": sides.killer_side,
                    "victim_side": sides.victim_side,
                    "weapon": _optional_nonempty_string(row.get("weapon_text")),
                }
                events.append(
                    _event(
                        "kill",
                        timestamp,
                        "unknown",
                        attributes,
                        min(confidence, row_confidence, float(pair.get("confidence", 1.0))),
                        event_id=f"HUD-KILL-{index:05d}-{row_index:02d}",
                        cross_checked=sides.victim_side != "unknown",
                    )
                )
            previous = observation
            previous_evidence = evidence

        allowed = {
            "round_start",
            "round_end",
            "kill",
            "player_death",
            "spike_planted",
            "ability_state",
            "buy_phase",
            "status_effect",
        }
        accepted: list[dict[str, Any]] = []
        for event in events:
            confidence = float(event.pop("_candidate_confidence", event.get("confidence", 0.0)))
            cross_checked = bool(event.pop("_cross_checked", False))
            if confidence < 0.65 or (confidence < 0.85 and not cross_checked):
                continue
            event["confidence"] = confidence
            accepted.append(event)
        accepted.sort(key=lambda event: float(event["time_sec"]))
        _ensure_unique_event_ids(accepted)
        if any(event["type"] not in allowed for event in accepted):
            raise AssertionError("HUD emitted an event outside the HUD contract")
        return tuple(accepted)


def _event_acceptable(event: Mapping[str, Any]) -> bool:
    confidence = float(event.get("confidence", 0.0))
    return confidence >= 0.85 or (confidence >= 0.65 and event.get("_cross_checked") is True)


def _round_end_confirmed(
    previous: Mapping[str, Any], current: Mapping[str, Any], evidence: Mapping[str, Any]
) -> bool:
    if evidence.get("round_end_joined") is True:
        return True
    previous_values = previous.get("values", {})
    current_values = current.get("values", {})
    prior_flags = set(previous.get("state_flags", ()))
    flags = set(current.get("state_flags", ()))
    score_changed = any(
        isinstance(previous_values.get(key), int)
        and not isinstance(previous_values.get(key), bool)
        and isinstance(current_values.get(key), int)
        and not isinstance(current_values.get(key), bool)
        and previous_values[key] != current_values[key]
        for key in ("score_ally", "score_enemy")
    )
    banner = "round_end_banner" in flags or "round_end_banner" in prior_flags
    return banner and (
        (score_changed and "round_end_joined" not in evidence)
        or bool(evidence.get("timer_stopped_or_disappeared"))
    )


def _round_start_confirmed(
    previous: Mapping[str, Any], current: Mapping[str, Any], evidence: Mapping[str, Any]
) -> bool:
    prior_values = previous.get("values", {})
    values = current.get("values", {})
    prior_flags = set(previous.get("state_flags", ()))
    flags = set(current.get("state_flags", ()))
    buy_to_live = (
        previous.get("primary_state") == "buy_menu_open"
        and current.get("primary_state") == "live_first_person"
    )
    buy_banner_to_live = (
        "buy_phase_banner" in prior_flags and current.get("primary_state") == "live_first_person"
    )
    timer_reset = (
        _is_finite_number(prior_values.get("round_time_remaining_sec"))
        and _is_finite_number(values.get("round_time_remaining_sec"))
        and values["round_time_remaining_sec"] > prior_values["round_time_remaining_sec"] + 3
    )
    return (
        (buy_to_live or buy_banner_to_live) and "buy_phase_banner" not in flags
        and timer_reset and score_is_continuous(previous, current)
    )


def _buy_phase_confirmed(observation: Mapping[str, Any], evidence: Mapping[str, Any]) -> bool:
    values = observation.get("values", {})
    return bool(values.get("buy_phase_visible")) and bool(
        evidence.get("score_stable") and evidence.get("pre_round_timer_context")
    )


def _player_death_event(
    timestamp: float,
    confidence: float,
    values: Mapping[str, Any],
    evidence: Mapping[str, Any],
) -> dict[str, Any] | None:
    source_a = bool(values.get("combat_report_visible"))
    source_b = bool(
        evidence.get("spectator_transition")
        or evidence.get("self_hud_identity_lost")
        or evidence.get("roster_self_dead")
    )
    if not source_a or not source_b:
        return None
    return _event(
        "player_death",
        timestamp,
        "player",
        {"cause_known": evidence.get("cause_known") is True},
        min(confidence, _evidence_confidence(evidence, "death_source_confidence")),
        cross_checked=True,
    )


def _status_event(
    timestamp: float, confidence: float, evidence: Mapping[str, Any]
) -> dict[str, Any] | None:
    status = evidence.get("confirmed_status_effect")
    if not isinstance(status, str) or not status.strip():
        return None
    source_side = _event_side(evidence.get("status_source_side", evidence.get("status_source")))
    affected_side = _event_side(evidence.get("affected_side"))
    duration = evidence.get("status_duration_sec")
    return _event(
        "status_effect",
        timestamp,
        "player",
        {
            "effect_type": status.strip(),
            "source_side": source_side,
            "affected_side": affected_side,
            "duration_sec": duration
            if isinstance(duration, (int, float)) and _is_finite_number(duration) and duration >= 0
            else None,
        },
        min(confidence, _evidence_confidence(evidence, "status_confidence")),
        cross_checked=bool(evidence.get("status_cross_checked")),
    )


def _ability_state_changes(
    before: Any,
    after: Any,
    timestamp: float,
    confidence: float,
    *,
    initial_cross_checked: bool = False,
) -> list[dict[str, Any]]:
    if not isinstance(before, list) or not isinstance(after, list):
        return []
    prior = {
        item["slot"]: item
        for item in before
        if isinstance(item, dict) and type(item.get("slot")) is int and item["slot"] in range(4)
    }
    current = {
        item["slot"]: item
        for item in after
        if isinstance(item, dict) and type(item.get("slot")) is int and item["slot"] in range(4)
    }
    events: list[dict[str, Any]] = []
    for slot in sorted(current):
        old = prior.get(slot)
        new = current[slot]
        if not _ability_slot_observable(new):
            continue
        changed = old is None or (old.get("available"), old.get("charges")) != (
            new.get("available"),
            new.get("charges"),
        )
        if not changed:
            continue
        slot_confidences = [confidence, _bounded_confidence(new.get("confidence", 0.0))]
        if old is not None:
            slot_confidences.append(_bounded_confidence(old.get("confidence", 0.0)))
        slot_confidence = min(slot_confidences)
        if slot_confidence < 0.65:
            continue
        events.append(
            _event(
                "ability_state",
                timestamp,
                "player",
                {
                    "slot": slot,
                    "ability_name": new.get("ability_name"),
                    "available": new.get("available"),
                    "charges_remaining": new.get("charges"),
                    "semantic_role": new.get("semantic_role", "unknown"),
                },
                slot_confidence,
                event_id=f"HUD-ABILITY_STATE-{timestamp:.3f}-{slot}",
                cross_checked=old is not None or initial_cross_checked,
            )
        )
    return events


def _event(
    event_type: str,
    timestamp: float,
    actor: str,
    attributes: dict[str, Any],
    confidence: float,
    *,
    event_id: str | None = None,
    cross_checked: bool = False,
) -> dict[str, Any]:
    return {
        "time_sec": max(0.0, float(timestamp)),
        "type": event_type,
        "actor": actor,
        "attributes": attributes,
        "event_id": event_id or f"HUD-{event_type.upper()}-{timestamp:.3f}",
        "confidence": _bounded_confidence(confidence),
        "_candidate_confidence": _bounded_confidence(confidence),
        "_cross_checked": cross_checked,
    }


def _drop(before: int | None, after: int | None) -> bool:
    return before is not None and after is not None and before - after == 1


def _player_hud_is_valid(observation: Mapping[str, Any], values: Any) -> bool:
    return (
        observation.get("primary_state") == "live_first_person"
        and isinstance(values, Mapping)
        and values.get("player_specific_hud_valid") is True
    )


def _ability_slots_cross_checked(evidence: Mapping[str, Any]) -> bool:
    return (
        evidence.get("ability_slots_cross_checked") is True
        or evidence.get("ability_state_cross_checked") is True
    )


def _ability_slot_observable(slot: Mapping[str, Any]) -> bool:
    available = slot.get("available")
    charges = slot.get("charges")
    return isinstance(available, bool) or (
        isinstance(charges, int) and not isinstance(charges, bool) and charges >= 0
    )


def _kill_row_added(
    evidence: Mapping[str, Any], row: Mapping[str, Any], row_index: int, row_count: int
) -> bool:
    if row.get("row_added") is True:
        return True
    added_rows = evidence.get("kill_feed_added_rows")
    if isinstance(added_rows, (list, tuple)):
        return row_index in added_rows
    changed_rows = evidence.get("kill_feed_changed_rows")
    if isinstance(changed_rows, (list, tuple)):
        return row_index in changed_rows
    return evidence.get("kill_feed_row_added") is True and (row_count == 1 or row_index == 0)


def _row_evidence_value(
    row: Mapping[str, Any], evidence: Mapping[str, Any], key: str, row_index: int
) -> Any:
    if key in row:
        return row[key]
    value = evidence.get(key)
    if isinstance(value, (list, tuple)):
        return value[row_index] if row_index < len(value) else None
    if isinstance(value, Mapping):
        return value.get(row_index, value.get(str(row_index)))
    return value


def _row_evidence_true(evidence: Mapping[str, Any], key: str, row_index: int) -> bool:
    value = evidence.get(key)
    if isinstance(value, (list, tuple)):
        return row_index < len(value) and value[row_index] is True
    if isinstance(value, Mapping):
        return value.get(row_index, value.get(str(row_index))) is True
    return value is True


def _event_side(value: Any) -> str:
    return value if value in {"player", "ally", "enemy", "unknown"} else "unknown"


def _optional_nonempty_string(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _is_finite_number(value: Any) -> bool:
    return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)


def _ensure_unique_event_ids(events: list[dict[str, Any]]) -> None:
    seen: set[str] = set()
    for event in events:
        base_id = str(event["event_id"])
        candidate = base_id
        suffix = 2
        while candidate in seen:
            candidate = f"{base_id}-{suffix:02d}"
            suffix += 1
        event["event_id"] = candidate
        seen.add(candidate)


def _optional_int(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _hud_confidence(observation: Mapping[str, Any]) -> float:
    quality = observation.get("quality", {})
    return (
        _bounded_confidence(quality.get("hud_confidence", 0.0))
        if isinstance(quality, dict)
        else 0.0
    )


def _evidence_confidence(evidence: Mapping[str, Any], key: str) -> float:
    return _bounded_confidence(evidence.get(key, 0.85))


def _bounded_confidence(value: Any) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return 0.0
    return min(1.0, max(0.0, parsed))


def _confidence_median(values: Sequence[float]) -> float:
    normalized = [_fraction(value, "confidence") for value in values]
    return median(normalized) if normalized else 0.0


def _fraction(value: float, label: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{label}は0〜1である必要があります")
    parsed = float(value)
    if not math.isfinite(parsed) or not 0 <= parsed <= 1:
        raise ValueError(f"{label}は0〜1である必要があります")
    return parsed
