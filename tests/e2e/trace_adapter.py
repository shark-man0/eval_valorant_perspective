"""Loss-minimizing adapter from native HUD processing output to pack trace v1.

Ground truth is intentionally absent from this module. Round ids follow native
RoundPackage ordering: package index 1 -> sample_round_1, etc. This is only the
pack's evaluator naming convention; timestamps and round boundaries come solely
from the processor's packages and observations.
"""
from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

from valorant_ai_coach.hud.models import timer_display_evidence

# Match the HUD temporal detector's own >1s discontinuity cutoff.
MAX_SAMPLE_GAP_SEC = 1.0


def _round_id(index: int) -> str:
    return f"sample_round_{index}"


def _confidence(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _required_confidence(value: Any, context: str) -> float:
    confidence = _confidence(value)
    if confidence is None or not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
        raise ValueError(f"{context} is missing a finite confidence in [0, 1]")
    return confidence


def to_e2e_trace(result: Any) -> dict[str, list[dict[str, Any]]]:
    """Convert a HudVideoProcessingResult (or sample-shaped object) to trace v1."""
    packages = tuple(getattr(result, "round_packages", ()))
    observations = tuple(getattr(result, "observations", ()))
    visual_observations = tuple(getattr(result, "visual_observations", ()))
    trace: dict[str, list[dict[str, Any]]] = {
        "events": [], "state_intervals": [], "ownership_intervals": [],
        "snapshots": [], "visual_observations": [], "temporal_features": [],
    }

    # Native package numbering is sequential and its windows are derived by the
    # processor. The fixed label merely matches this evaluator's fixture ids.
    for package_index, package in enumerate(packages, start=1):
        rid = _round_id(package_index)
        for event in package.get("events", ()):
            row = {"round_id": rid, "type": event["type"],
                   "actor": event.get("actor", "unknown"),
                   "time_sec": float(event["time_sec"]),
                   "attributes": dict(event.get("attributes") or {})}
            row["confidence"] = _required_confidence(
                event.get("confidence"), f"event {event.get('event_id', event.get('type'))}")
            trace["events"].append(row)
        for snapshot in package.get("state_snapshots", ()):
            timestamp = float(snapshot["time_sec"])
            # Preserve native RoundPackage fields so the evaluator can catch
            # ownership contamination. Add aliases without repairing the data.
            row: dict[str, Any] = dict(snapshot)
            row["round_id"] = rid
            row["time_sec"] = timestamp
            if "hp" in snapshot and "player_hp" not in row:
                row["player_hp"] = snapshot["hp"]
            for source_name, trace_name in (("ammo_current", "ammo_mag"),
                                            ("ammo_reserve", "ammo_reserve")):
                if source_name in snapshot and trace_name not in row:
                    row[trace_name] = snapshot[source_name]
            source = next((o for o in observations
                           if float(o.get("time_sec", -1)) == timestamp), None)
            if source is None:
                raise ValueError(f"Snapshot at {timestamp} has no matching HUD confidence")
            player_location = snapshot.get("player_location") or {}
            if "zone_id" in player_location:
                row["zone_id"] = player_location["zone_id"]
            if source is not None:
                values = source.get("values") or {}
                flags = set(source.get("state_flags") or ())
                primary_state = source.get("primary_state", "unknown")
                player_hud_valid = values.get("player_specific_hud_valid") is True
                view_owner = {"live_first_person": "self",
                              "spectator_first_person": "teammate_spectated"}.get(
                                  primary_state, "unknown")
                row.update({
                    "primary_state": primary_state,
                    "buy_phase_banner": "buy_phase_banner" in flags,
                    "combat_report_visible": values.get("combat_report_visible") is True,
                    "vision_obscured_smoke": "vision_obscured_smoke" in flags,
                    "view_owner": view_owner,
                })
                if view_owner == "self" and player_hud_valid:
                    for key, value in {
                        "location_label_raw": values.get("location_text"),
                        "score_player": values.get("score_ally"),
                        "score_enemy": values.get("score_enemy"),
                        "ammo_mag": values.get("ammo_current"),
                        "ammo_reserve": values.get("ammo_reserve"),
                    }.items():
                        row.setdefault(key, value)
                    if row.get("player_hp") is None and values.get("hp") is not None:
                        row["player_hp"] = values["hp"]
                    if values.get("hp") is not None:
                        row["player_alive"] = values["hp"] > 0
                elif view_owner == "teammate_spectated":
                    row.update({"spectated_location_label_raw": values.get("location_text"),
                                "spectated_hp": values.get("hp"),
                                "spectated_ammo_mag": values.get("ammo_current"),
                                "spectated_ammo_reserve": values.get("ammo_reserve"),
                                "spectated_weapon": values.get("weapon_text")})
                remote_type = (source.get("view_context") or {}).get("remote_view_type")
                if primary_state == "remote_control_view":
                    row["remote_control_subtype"] = remote_type
                quality = source.get("quality") or {}
                for key in ("hud_confidence", "visual_confidence"):
                    row[key] = _required_confidence(
                        quality.get(key), f"HUD snapshot {key} at {timestamp}")
                # The semantic timer display is intentionally not reconstructed
                # from seconds; only source-preserved display text may be emitted.
                timer = timer_display_evidence(values)
                native_timer = timer_display_evidence(snapshot)
                if native_timer is not None:
                    if native_timer != timer:
                        raise ValueError(f"Snapshot timer source mismatch at {timestamp}")
                    row["game_timer_display"] = timer["display"]
                    row["game_timer_display_provenance"] = {
                        **timer["provenance"], "source_pts_sec": timestamp,
                    }
            trace["snapshots"].append(row)

    def containing_round(timestamp: float) -> int | None:
        # A shared context endpoint belongs to the upcoming package. Native
        # builders exclude it from the preceding observation window, while its
        # round_end event remains explicitly attached to the preceding package.
        for index, package in reversed(tuple(enumerate(packages, start=1))):
            window = package.get("round_window", {})
            if float(window.get("start_sec", 0)) <= timestamp <= float(window.get("end_sec", 0)):
                return index
        return None

    # Represent state/ownership only over adjacent observed sample timestamps.
    # No frame is synthesized and no interval is extrapolated beyond observations.
    ordered = sorted((o for o in observations if isinstance(o, Mapping)),
                     key=lambda o: float(o.get("time_sec", 0.0)))
    last_interval_by_state: dict[tuple[str, str, str, Any], dict[str, Any]] = {}
    for pos, observation in enumerate(ordered):
        t = float(observation["time_sec"])
        index = containing_round(t)
        if index is None:
            continue
        next_t = t
        if pos + 1 < len(ordered):
            candidate = float(ordered[pos + 1]["time_sec"])
            if (
                containing_round(candidate) == index
                and candidate - t <= MAX_SAMPLE_GAP_SEC
            ):
                next_t = candidate
        interval = [t, next_t]
        rid = _round_id(index)
        state = observation.get("primary_state", "unknown")
        confidence = _required_confidence(
            (observation.get("quality") or {}).get("hud_confidence"),
            f"HUD observation at {t}")
        states = [] if state == "unknown" else [("primary_state", state)]
        states.extend(("flag", flag) for flag in observation.get("state_flags", ()))
        for state_class, name in states:
            remote_type = (observation.get("view_context") or {}).get("remote_view_type")
            subtype = (
                remote_type
                if state == "remote_control_view" and state_class == "primary_state"
                else None
            )
            row = {"round_id": rid, "state": name, "subtype": subtype,
                   "interval": interval, "state_class": state_class}
            state_confidence = confidence
            if state_class == "flag" and name == "buy_phase_banner":
                phase_confidence = (
                    (observation.get("quality") or {}).get("roi_confidence") or {}
                ).get("center_phase_banner_semantic_text")
                if phase_confidence is not None:
                    state_confidence = _required_confidence(
                        phase_confidence, f"source-backed phase confidence at {t}"
                    )
                    if state_confidence < 0.90:
                        raise ValueError("source-backed phase confidence must be >= .90")
            row["confidence"] = state_confidence
            # Merge only touching samples with the identical detector state.
            # This preserves observed episode edges and never spans unknown samples.
            key = (rid, state_class, name, subtype)
            previous = last_interval_by_state.get(key)
            if (interval[1] > interval[0] and previous is not None
                    and previous["interval"][1] == interval[0]):
                previous["interval"][1] = interval[1]
                previous["confidence"] = min(previous["confidence"], state_confidence)
            elif interval[1] > interval[0]:
                trace["state_intervals"].append(row)
                last_interval_by_state[key] = row
        # Keep unknown explicitly unknown; only named primary states with direct
        # ownership semantics are translated. Dead UI is not inferred from nulls.
        owner = {"live_first_person": "self",
                 "spectator_first_person": "teammate_spectated"}.get(state, "unknown")
        row = {"round_id": rid, "owner": owner, "interval": interval}
        if confidence is not None:
            row["confidence"] = confidence
        trace["ownership_intervals"].append(row)

    for visual in visual_observations:
        timestamp = float(visual["time_sec"])
        index = containing_round(timestamp)
        if index is None:
            continue
        weapon = visual.get("weapon_action") or {}
        score = weapon.get("muzzle_flash_score")
        if (
            isinstance(score, (int, float))
            and not isinstance(score, bool)
            and not math.isfinite(float(score))
        ):
            raise ValueError(f"visual muzzle_flash_score at {timestamp} is not finite")
        if not isinstance(score, (int, float)) or isinstance(score, bool) or score < 0.5:
            continue
        eligibility = visual.get("analysis_eligibility") or {}
        # The source analyzer's mechanics attribution gate is authoritative.
        actor = "player" if eligibility.get("player_mechanics") else "unknown"
        row = {"round_id": _round_id(index), "observation": "muzzle_flash",
               "actor": actor, "time_sec": timestamp}
        row["confidence"] = _required_confidence(
            weapon.get("confidence"), f"visual weapon observation at {timestamp}")
        trace["visual_observations"].append(row)

    # Only event types with explicit direction here become temporal features;
    # durations on other event types are unsupported and are not guessed.
    for event in trace["events"]:
        direction = {
            "status_effect": "forward",
            "info_peek": "forward",
            "hold_angle": "forward",
        }.get(event["type"])
        duration = event["attributes"].get("duration_sec")
        if (
            direction is None
            or isinstance(duration, bool)
            or not isinstance(duration, (int, float))
        ):
            continue
        if not math.isfinite(float(duration)) or duration < 0:
            raise ValueError(f"event {event['type']} has invalid duration_sec")
        event_time = float(event["time_sec"])
        interval = (
            [event_time, event_time + float(duration)]
            if direction == "forward"
            else [event_time - float(duration), event_time]
        )
        trace["temporal_features"].append({
            "feature": f"{event['type']}.duration_sec",
            "interval": interval,
            "value": float(duration), "confidence": event["confidence"],
        })

    return trace
