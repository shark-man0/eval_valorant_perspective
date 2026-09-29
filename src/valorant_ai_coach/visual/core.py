"""Temporal factual detectors. No evaluation rules or coaching enter this module."""

from __future__ import annotations

import json
import math
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from valorant_ai_coach.maps.registry import MapDefinition, MapRegistry
from valorant_ai_coach.resources import resource_path
from valorant_ai_coach.schema_validation import SchemaValidator

from .map_consumer import MapEventConsumer
from .models import EventCandidate, EvidencePoint, VisualObservation
from .policy import evaluate_visual_confidence, project_candidate_to_v3_event, semantic_fact

__all__ = ["VisualEventEngine", "project_candidate_to_v3_event"]


def _score(value: Any) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
        return 0.0
    return min(1.0, max(0.0, float(value)))


def shot_movement(observation: Mapping[str, Any], proof: Mapping[str, Any]) -> tuple[str, float]:
    """Micro evidence takes priority; macro minimap cannot determine a shot label."""
    if (
        not observation["analysis_eligibility"]["world_semantics"]
        or observation["quality"]["occluded"]
        or proof.get("camera_rotation_rejected") is False
    ):
        return "unknown", 0.0
    if proof.get("micro_sample_interval_sec", 0.05) > 0.1:
        return "unknown", 0.0
    state = proof.get("micro_motion_state", "unknown")
    confidence = _score(proof.get("micro_motion_confidence"))
    flow = _score(proof.get("local_optical_flow_translation_confidence"))
    bob = _score(proof.get("weapon_bob_moving_confidence"))
    if flow >= 0.85 and bob >= 0.85:
        return "moving", min(flow, bob)
    if (
        state in {"stationary", "moving"}
        and confidence >= 0.85
        and proof.get("camera_rotation_rejected")
    ):
        return str(state), confidence
    motion = observation["motion"]
    if (
        motion["state"] == "stationary"
        and motion["stationary_confidence"] >= 0.85
        and "global_optical_flow" in motion["evidence_sources"]
    ):
        return "stationary", float(motion["stationary_confidence"])
    return "unknown", 0.0


class VisualEventEngine:
    def __init__(
        self,
        config_dir: Path | str | None = None,
        *,
        map_definition: MapDefinition | None = None,
    ) -> None:
        root = (
            Path(config_dir)
            if config_dir
            else resource_path(
                "config/visual_v2/config/visual_event_detection_contract_v2.json"
            ).parent
        )
        self.contract = json.loads((root / "visual_event_detection_contract_v2.json").read_text())
        self.map_definition = map_definition
        self.map_runtime = MapRegistry().runtime
        self.validator = SchemaValidator()
        self.enriched_observations: tuple[dict[str, Any], ...] = ()

    def process(
        self,
        observations: Iterable[VisualObservation | Mapping[str, Any]],
        evidence_by_frame: Mapping[int, Mapping[str, Any]] | None = None,
    ) -> tuple[EventCandidate, ...]:
        samples = sorted(
            (
                item.to_dict()
                if isinstance(item, VisualObservation)
                else VisualObservation.from_mapping(item).to_dict()
                for item in observations
            ),
            key=lambda item: item["time_sec"],
        )
        evidence_by_frame = evidence_by_frame or {}
        output: list[EventCandidate] = []
        previous: dict[str, Any] | None = None
        last_fire = -math.inf
        enemy_last = -math.inf
        enemy_present = False
        map_enemy_present = False
        map_enemy_last = -math.inf
        engagement = False
        engagement_end: float | None = None
        primary: str | None = None
        known_enemy_ids: set[str] = set()
        last_motion = "unknown"
        hold_start: float | None = None
        angle_emitted = False
        alignment_start: float | None = None
        alignment_confidence = 0.0
        last_peek = -math.inf
        peek_open: dict[str, Any] | None = None
        map_consumer = MapEventConsumer(self.map_definition, self.map_runtime)
        last_utility = -math.inf
        last_site = -math.inf
        last_effect: str | None = None

        def emit(
            kind: str,
            attrs: dict[str, Any],
            confidence: float,
            sources: list[str],
            *,
            actor: str = "player",
            start: float | None = None,
            semantic: str = "not_needed",
            semantic_required: bool = False,
            moving_preaim: bool = False,
        ) -> EventCandidate:
            rule = self.contract["events"][kind]
            decision = evaluate_visual_confidence(
                rule["tier"],
                confidence,
                sources,
                semantic_confirmation=semantic,
                semantic_required=semantic_required,
                semantic_only_preaim=moving_preaim,
                retain_low_confidence_candidate=moving_preaim,
            )
            candidate = EventCandidate(
                f"VC-{len(output):06d}",
                kind,
                actor,
                t if start is None else start,
                t,
                attrs,
                decision.confidence,
                rule["producer_component"],
                tuple(
                    EvidencePoint(t, str(proof.get("frame_ref", "")), signal)
                    for signal in sources or ["insufficient_evidence"]
                ),
                semantic,
                decision.status,
                decision.reason,
            )
            output.append(candidate)
            return candidate

        for obs in samples:
            t = float(obs["time_sec"])
            proof = evidence_by_frame.get(obs["frame_index"], {})
            safe = (
                obs["hud_primary_state"] == "live_first_person"
                and obs["analysis_eligibility"]["player_mechanics"]
            )
            gap = previous is not None and t - previous["time_sec"] > 0.5
            if not safe or gap:
                previous = None
                last_fire = enemy_last = -math.inf
                enemy_present = engagement = False
                engagement_end = None
                map_enemy_present = False
                map_enemy_last = -math.inf
                primary = None
                known_enemy_ids.clear()
                hold_start = alignment_start = None
                alignment_confidence = 0.0
                last_peek = last_utility = last_site = -math.inf
                angle_emitted = False
                last_motion = "unknown"
                peek_open = None
                map_consumer.reset()
                last_effect = None
                if not safe:
                    previous = None
                    continue
            action, motion, aiming, spatial, minimap = (
                obs["weapon_action"],
                obs["motion"],
                obs["aiming"],
                obs["spatial"],
                obs["minimap"],
            )
            world = (
                obs["analysis_eligibility"]["world_semantics"] and not obs["quality"]["occluded"]
            )
            map_conf = _score(minimap["track_confidence"])
            resolution = proof.get("zone_resolution", {})
            if resolution:
                self.validator.validate_zone_resolution(dict(resolution))
                if resolution["calibration_status"] != "ok":
                    motion["map_displacement_norm_per_sec"] = None
            zone_ok = (
                self.map_definition is not None
                and resolution.get("map_id") == self.map_definition.map_id
                and resolution.get("geometry_version") == self.map_definition.geometry_version
                and resolution.get("resolution_scope") == "exact_zone"
                and resolution.get("calibration_status") == "ok"
                and resolution.get("zone_confidence", 0)
                >= self.map_runtime["fusion_thresholds"]["named_zone_min"]
            )
            minimap["zone_id"] = resolution.get("zone_id") if zone_ok else None
            minimap["zone_name"] = minimap["zone_id"]
            exposure = proof.get("static_peek_exposure") if zone_ok else None
            spatial["exposed_directions_count"] = exposure
            spatial["exposed_directions_source"] = (
                "static_peek_registry" if exposure is not None else "none"
            )
            if exposure is not None:
                spatial["confidence"] = max(
                    spatial["confidence"], min(map_conf, resolution["zone_confidence"])
                )
            for field in ("cover_available", "escape_route_available"):
                value, confidence, _ = semantic_fact(proof, field)
                if value is not None and world:
                    spatial[field] = value
                    spatial["confidence"] = (
                        min(spatial["confidence"], confidence)
                        if spatial["confidence"]
                        else confidence
                    )

            micro_state, micro_conf = shot_movement(obs, proof)
            displacement = motion["map_displacement_norm_per_sec"]
            macro_state, macro_conf = "unknown", 0.0
            if displacement is not None and map_conf >= 0.85:
                macro_state = "moving" if displacement > 0.005 else "stationary"
                macro_conf = map_conf
            elif micro_state != "unknown" and world:
                macro_state, macro_conf = micro_state, micro_conf
            elif (
                world
                and motion["state"] == "stationary"
                and motion["stationary_confidence"] >= 0.85
            ):
                macro_state, macro_conf = "stationary", motion["stationary_confidence"]
            # Macro observations never overwrite the separate shot-time state.
            motion["state"] = macro_state
            if macro_state != "unknown" and macro_state != last_motion:
                emit(
                    "movement_state",
                    {"state": macro_state, "speed_class": "unknown"},
                    macro_conf,
                    ["minimap_track"] if map_conf >= 0.85 else ["global_optical_flow"],
                )
                last_motion = macro_state

            delta = action["ammo_delta"]
            cue = max(_score(action["recoil_score"]), _score(action["muzzle_flash_score"]))
            switched = proof.get("weapon_changed") is True or bool(
                previous
                and previous["weapon_action"]["weapon_text"]
                and action["weapon_text"]
                and previous["weapon_action"]["weapon_text"] != action["weapon_text"]
            )
            reload = proof.get("reload_detected") is True or (delta is not None and delta > 0)
            if switched or reload:
                last_fire = -math.inf
            fired = (
                not switched and not reload and ((delta is not None and delta < 0) or cue >= 0.5)
            )
            burst_start = fired and t - last_fire > 0.3
            action.update(
                shot_candidate=fired,
                burst_start_candidate=burst_start,
                first_shot_candidate=burst_start,
                burst_active=fired or t - last_fire <= 0.3,
            )
            if fired:
                if burst_start:
                    sources = ["ammo_delta"] if delta is not None and delta < 0 else []
                    sources += ["weapon_visual_cue"] if cue >= 0.5 else []
                    confidence = max(_score(action["confidence"]), cue)
                    # Unknown weapon state cannot exclude a switch/purchase based on ammo alone.
                    if not action["weapon_text"]:
                        confidence = min(confidence, 0.64)
                    # v3 has one event confidence, not per-attribute confidence.
                    # Never promote movement evidence using ammo confidence.
                    if micro_state != "unknown":
                        confidence = min(confidence, micro_conf)
                    emit(
                        "shot",
                        {
                            "moving": micro_state == "moving" if micro_state != "unknown" else None,
                            "speed_class": "unknown",
                            "distance_class": "unknown",
                            "fire_mode": "unknown",
                            "first_shot": True,
                        },
                        confidence,
                        sources,
                    )
                last_fire = t
                if peek_open:
                    peek_open["shot_fired"] = True

            enemies = (
                [item for item in obs["entities"]["visible_enemies"] if item["confidence"] >= 0.88]
                if world
                else []
            )
            refs = {item["detection_id"]: item for item in enemies}
            newly_seen = set(refs) - known_enemy_ids
            known_enemy_ids.update(refs)
            map_enemies = [item for item in minimap["enemy_markers"] if item["confidence"] >= 0.9]
            if map_enemies:
                if not map_enemy_present and not enemies:
                    emit(
                        "enemy_spotted",
                        {
                            "source": "minimap",
                            "zone_id": None,
                            "world_bbox": None,
                        },
                        min(item["confidence"] for item in map_enemies),
                        ["minimap_track"],
                    )
                map_enemy_present = True
                map_enemy_last = t
            elif map_enemy_present and map_conf >= 0.9 and t - map_enemy_last >= 0.5:
                emit(
                    "enemy_lost",
                    {"source": "minimap", "last_zone_id": None},
                    map_conf,
                    ["minimap_track"],
                )
                map_enemy_present = False
            previous_primary = primary
            # Reconsider the observed aim contact on every frame; a surviving
            # tracker ID does not prove that the player is still targeting it.
            heads = [item for item in enemies if item["head_point_norm"] is not None]
            distances = sorted(
                (
                    math.dist(
                        item["head_point_norm"],
                        (aiming["crosshair_x_norm"], aiming["crosshair_y_norm"]),
                    ),
                    item["detection_id"],
                )
                for item in heads
            )
            primary = (
                distances[0][1]
                if distances and (len(distances) == 1 or distances[1][0] - distances[0][0] > 0.005)
                else None
            )
            aiming["primary_target_ref"] = primary
            aiming["visible_enemy_head_refs"] = [
                item["detection_id"] for item in enemies if item["head_point_norm"] is not None
            ]
            aiming["head_alignment_error_norm"] = (
                math.dist(
                    refs[primary]["head_point_norm"],
                    (aiming["crosshair_x_norm"], aiming["crosshair_y_norm"]),
                )
                if primary and refs[primary]["head_point_norm"] is not None
                else None
            )
            if primary:
                aiming["reference_mode"] = "visible_enemy_head"
            elif aiming["reference_mode"] == "visible_enemy_head":
                aiming["reference_mode"] = "none"
            if previous_primary is not None and previous_primary != primary:
                alignment_start = None
            appeared = bool(enemies) and not enemy_present
            if enemies:
                if not enemy_present:
                    emit(
                        "enemy_spotted",
                        {
                            "source": "world_view",
                            "zone_id": minimap["zone_id"],
                            "world_bbox": enemies[0]["bbox_norm"],
                        },
                        min(item["confidence"] for item in enemies),
                        ["entity_tracker"],
                    )
                enemy_present = True
                enemy_last = t
                if peek_open and newly_seen:
                    peek_open["new_information_observed"] = True
                if not engagement and (
                    fired
                    or (
                        aiming["head_alignment_error_norm"] is not None
                        and aiming["head_alignment_error_norm"] < 0.03
                    )
                ):
                    emit(
                        "engagement_start",
                        {"visible_enemy_count": len(enemies), "weapon": action["weapon_text"]},
                        min(item["confidence"] for item in enemies),
                        ["entity_tracker", "weapon_visual_cue"],
                    )
                    if engagement_end is not None and t - engagement_end <= 3:
                        emit(
                            "enemy_reengage",
                            {"gap_sec": t - engagement_end, "zone_id": minimap["zone_id"]},
                            0.88,
                            ["entity_tracker"],
                        )
                    engagement = True
            elif world and t - enemy_last >= 0.5 and enemy_present:
                emit(
                    "enemy_lost",
                    {"source": "world_view", "last_zone_id": minimap["zone_id"]},
                    0.88,
                    ["entity_tracker"],
                )
                enemy_present = False
            if engagement and world and not enemies and t - max(enemy_last, last_fire) >= 1:
                emit("engagement_end", {"reason": "observed_combat_gap"}, 0.88, ["entity_tracker"])
                engagement = False
                engagement_end = t

            reference = aiming["reference_mode"] in {
                "visible_enemy_head",
                "static_corner_reference",
            }
            aligned = (
                world
                and micro_state == "stationary"
                and reference
                and aiming["crosshair_stable"] is True
                and aiming["confidence"] >= 0.9
                and (
                    (not enemies and aiming["reference_mode"] == "static_corner_reference")
                    or (
                        primary is not None
                        and aiming["head_alignment_error_norm"] is not None
                        and aiming["head_alignment_error_norm"] <= 0.03
                    )
                )
            )
            dense = previous is not None and 0 < t - previous["time_sec"] <= 0.1
            if aligned and (dense or previous is None):
                reference_confidence = min(
                    aiming["confidence"],
                    micro_conf,
                    refs[primary]["confidence"] if primary else 1.0,
                )
                alignment_confidence = (
                    reference_confidence
                    if alignment_start is None
                    else min(alignment_confidence, reference_confidence)
                )
                alignment_start = t if alignment_start is None else alignment_start
            else:
                alignment_start = None
            cover_score = _score(proof.get("cover_transition_confidence"))
            reveal_score = _score(proof.get("revealed_region_confidence"))
            peek_signal = (
                proof.get("cover_transition") is True and proof.get("new_line_of_sight") is True
            )
            if peek_signal and world and micro_state == "moving" and t - last_peek >= 0.5:
                confidence = min(cover_score, reveal_score, micro_conf)
                candidate = emit(
                    "peek",
                    {
                        "peek_style": "unknown",
                        "exposed_directions": spatial["exposed_directions_count"],
                        "target_known": None,
                        "distance_class": "unknown",
                    },
                    confidence,
                    ["cover_transition", "global_optical_flow"],
                )
                last_peek = t
                if candidate.status == "confirmed":
                    peek_open = {
                        "start": t,
                        "shot_fired": fired,
                        "new_information_observed": bool(newly_seen),
                        "confidence": confidence,
                    }
                if alignment_start is not None:
                    emit(
                        "preaim_started",
                        {
                            "lead_sec": t - alignment_start,
                            "reference_mode": aiming["reference_mode"],
                            "alignment_error_norm": aiming["head_alignment_error_norm"],
                        },
                        alignment_confidence,
                        ["global_optical_flow", "entity_tracker"],
                        start=alignment_start,
                    )
            # Measure the observed lead at enemy exposure, not an arbitrary earlier frame.
            if (
                aligned
                and appeared
                and alignment_start is not None
                and t - alignment_start >= 0.1
                and not any(
                    item.type == "preaim_started" and item.start_sec == alignment_start
                    for item in output
                )
            ):
                emit(
                    "preaim_started",
                    {
                        "lead_sec": t - alignment_start,
                        "reference_mode": aiming["reference_mode"],
                        "alignment_error_norm": aiming["head_alignment_error_norm"],
                    },
                    alignment_confidence,
                    ["global_optical_flow", "entity_tracker"],
                    start=alignment_start,
                )
            if (
                world
                and micro_state == "moving"
                and (
                    proof.get("semantic_alignment_confidence")
                    or (appeared and aiming["confidence"] >= 0.7)
                )
            ):
                emit(
                    "preaim_started",
                    {
                        "lead_sec": None,
                        "reference_mode": "semantic_corner_headline",
                        "alignment_error_norm": None,
                    },
                    _score(proof.get("semantic_alignment_confidence", 0.69)),
                    ["semantic_adapter"],
                    semantic="required",
                    moving_preaim=True,
                )
            if peek_open and t - peek_open["start"] > 2:
                peek_open = None
            returned, return_conf, confirmed = semantic_fact(
                proof, "returned_to_cover", required_confirmation=True
            )
            brief, brief_conf, brief_status = semantic_fact(
                proof, "brief_exposure_without_visible_combat", required_confirmation=True
            )
            new_info, _, _ = semantic_fact(
                proof, "new_information_observed", required_confirmation=True
            )
            if peek_open and new_info is False:
                # A later frame must not erase a confirmed contradiction seen
                # anywhere in this peek's evidence window.
                peek_open["information_rejected"] = True
            if peek_open and (returned is True or proof.get("returned_to_cover_cv") is True):
                if (
                    peek_open["new_information_observed"]
                    and not peek_open.get("information_rejected", False)
                    and not peek_open["shot_fired"]
                ):
                    emit(
                        "info_peek",
                        {
                            "new_information_observed": True,
                            "shot_fired": False,
                            "duration_sec": t - peek_open["start"],
                        },
                        min(return_conf or 0.75, brief_conf or 0.75, peek_open["confidence"]),
                        ["cover_transition", "semantic_adapter"],
                        semantic=confirmed
                        if returned is True and brief is True and brief_status == "confirmed"
                        else "required",
                        semantic_required=True,
                        start=peek_open["start"],
                    )
                peek_open = None

            if macro_state == "stationary":
                hold_start = t if hold_start is None else hold_start
                duration = t - hold_start
                if (
                    duration >= 3
                    and not angle_emitted
                    and world
                    and aiming["crosshair_stable"] is True
                    and proof.get("weapon_ready")
                ):
                    emit(
                        "hold_angle",
                        {
                            "duration_sec": duration,
                            "weapon": action["weapon_text"],
                            "view_target_zone_id": spatial["view_target_zone_id"],
                        },
                        min(macro_conf, aiming["confidence"]),
                        ["minimap_track", "global_optical_flow"],
                        start=hold_start,
                    )
                    angle_emitted = True
            else:
                hold_start = None
                angle_emitted = False
            if resolution:
                for mapped in map_consumer.consume(
                    resolution,
                    proof.get("ally_zone_resolutions", ()),
                    stationary=macro_state == "stationary",
                ):
                    emit(
                        mapped["type"],
                        mapped["attributes"],
                        mapped["confidence"],
                        ["minimap_track", "static_map_registry"],
                        actor=mapped["actor"],
                        start=mapped["start_sec"],
                    )
            utility = obs["utility"]
            charge_drop = (
                proof.get("ability_charge_delta") is not None and proof["ability_charge_delta"] < 0
            )
            cast = _score(proof.get("cast_animation_score"))
            if charge_drop and cast >= 0.65 and t - last_utility > 0.5:
                slot = utility["slot"] or proof.get("slot_index")
                if slot in {"C", "Q", "E", "X"}:
                    emit(
                        "utility_used",
                        {
                            "slot": slot,
                            "ability_name": utility["ability_name"],
                            "purpose_observed": None,
                        },
                        min(cast, _score(proof.get("hud_confidence", utility["confidence"]))),
                        ["ability_charge_delta", "cast_animation"],
                    )
                    last_utility = t
            if world and enemies and t - last_site >= 3:
                crossfire, cc, _ = semantic_fact(
                    proof, "active_crossfire", required_confirmation=True
                )
                risk, rc, _ = semantic_fact(
                    proof, "incoming_damage_risk_observed", required_confirmation=True
                )
                emit(
                    "site_state",
                    {
                        "visible_enemy_count": len(enemies),
                        "active_crossfire": crossfire,
                        "incoming_damage_risk_observed": risk,
                    },
                    min(item["confidence"] for item in enemies),
                    ["entity_tracker"],
                )
                last_site = t
            side, side_conf, side_status = semantic_fact(
                proof, "affected_side", required_confirmation=True
            )
            effect = utility["world_effect_candidate"]
            if world and effect and effect != last_effect:
                known_side = side in {"ally", "enemy", "both", "self"}
                emit(
                    "utility_effect_observed",
                    {
                        "ability_name": utility["ability_name"],
                        "affected_side": side if known_side else "unknown",
                        "affected_count": None,
                        "duration_sec": None,
                    },
                    min(side_conf, utility["confidence"]) if known_side else utility["confidence"],
                    ["semantic_adapter"],
                    semantic=side_status if known_side else "required",
                    semantic_required=True,
                )
            last_effect = effect
            previous = obs
        self.enriched_observations = tuple(samples)
        return tuple(output)
