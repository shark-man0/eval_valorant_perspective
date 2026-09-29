"""Visual confidence policy and explicit projections into the strict v3 model."""

from __future__ import annotations

import json
import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from valorant_ai_coach.resources import resource_path

_POLICY = json.loads(
    resource_path("config/visual_v2/config/visual_confidence_policy_v1.json").read_text()
)
CONFIDENCE_POLICY: dict[str, dict[str, float | int]] = _POLICY["tiers"]
SEMANTIC_ONLY_PREAIM_MAX_CONFIDENCE = _POLICY["semantic_only_rules"][
    "preaim_moving_case_max_confidence"
]
_SEMANTIC = json.loads(
    resource_path("config/visual_v2/config/visual_semantic_inference_policy_v2.json").read_text()
)
SEMANTIC_FACT_ACCEPT_MIN = _SEMANTIC["confidence_policy"]["semantic_fact_accept"]
SEMANTIC_FACT_REVIEW_MIN = _SEMANTIC["confidence_policy"]["semantic_fact_review"]
SEMANTIC_CALL_BUDGET_PER_MATCH = _SEMANTIC["invocation_policy"]["max_calls_per_match"]


@dataclass(frozen=True, slots=True)
class ConfidenceDecision:
    status: str
    confidence: float
    independent_source_count: int
    reason: str | None = None


def _source_family(source: str) -> str:
    """Collapse aliases and correlated measurements before counting evidence."""
    normalized = source.strip().lower().replace("-", "_").replace(" ", "_")
    families = {
        "ammo_delta": "hud_ammo",
        "ammo_current": "hud_ammo",
        "hud_ammo": "hud_ammo",
        "weapon_visual_cue": "weapon_visual_cue",
        "recoil_score": "weapon_visual_cue",
        "visual_recoil": "weapon_visual_cue",
        "muzzle_flash_score": "weapon_visual_cue",
        "muzzle_flash": "weapon_visual_cue",
        "local_optical_flow": "global_optical_flow",
        "global_optical_flow": "global_optical_flow",
        "weapon_bob": "weapon_bob",
        "minimap_track": "minimap_track",
        "minimap_displacement": "minimap_track",
        "location_change": "location_change",
        "static_map_registry": "static_map_registry",
        "static_peek_registry": "static_peek_registry",
        "semantic_adapter": "semantic_adapter",
        "semantic_sequence": "semantic_adapter",
        "cast_animation": "cast_animation",
        "ability_charge_delta": "ability_charge_delta",
        "cover_transition": "cover_transition",
        "line_of_sight_transition": "line_of_sight_transition",
        "entity_tracker": "entity_tracker",
        "minimap_marker": "minimap_marker",
    }
    return families.get(normalized, normalized)


def independent_source_count(sources: Iterable[str]) -> int:
    return len({_source_family(source) for source in sources if source.strip()})


def evaluate_visual_confidence(
    tier: str,
    confidence: float,
    evidence_sources: Iterable[str],
    *,
    semantic_confirmation: str = "not_needed",
    semantic_required: bool = False,
    semantic_only_preaim: bool = False,
    retain_low_confidence_candidate: bool = False,
) -> ConfidenceDecision:
    """Apply visual tiers independently from HUD and AI-coach confidence."""
    tier_key = tier.upper()
    policy = CONFIDENCE_POLICY.get(tier_key)
    if policy is None:
        raise ValueError(f"Unknown visual confidence tier: {tier}")
    score = float(confidence)
    score = min(1.0, max(0.0, score)) if math.isfinite(score) else 0.0
    if semantic_only_preaim:
        score = min(score, SEMANTIC_ONLY_PREAIM_MAX_CONFIDENCE)
    source_count = independent_source_count(evidence_sources)

    if semantic_confirmation == "rejected":
        return ConfidenceDecision("suppressed", score, source_count, "semantic_rejected")
    if semantic_required and semantic_confirmation != "confirmed":
        return ConfidenceDecision(
            "candidate", score, source_count, "semantic_confirmation_required"
        )

    if score >= float(policy["direct_confirm_min"]):
        return ConfidenceDecision("confirmed", score, source_count)
    if score >= float(policy["cross_checked_confirm_min"]) and source_count >= int(
        policy["cross_checked_min_independent_sources"]
    ):
        return ConfidenceDecision("confirmed", score, source_count)
    if score >= float(policy["below_candidate_min"]) or retain_low_confidence_candidate:
        return ConfidenceDecision("candidate", score, source_count)
    return ConfidenceDecision("suppressed", score, source_count, "below_candidate_threshold")


def semantic_fact(
    evidence: Mapping[str, Any], field_name: str, *, required_confirmation: bool = False
) -> tuple[Any | None, float, str]:
    """Read a bounded semantic fact only when its confidence and confirmation allow it."""
    value = evidence.get(field_name)
    if value is None:
        return None, 0.0, "unavailable"
    try:
        confidence = float(evidence.get(f"{field_name}_confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0
    confirmation_values = evidence.get("semantic_confirmed", ())
    if isinstance(confirmation_values, str):
        confirmation_values = (confirmation_values,)
    confirmed = field_name in confirmation_values
    if confidence < SEMANTIC_FACT_REVIEW_MIN:
        return None, confidence, "unavailable"
    if required_confirmation and not confirmed:
        return None, confidence, "required"
    if confidence < SEMANTIC_FACT_ACCEPT_MIN:
        return None, confidence, "unavailable"
    return value, confidence, "confirmed" if confirmed else "unavailable"


# Candidate-only fields are intentionally excluded. This is an explicit v3
# event attribute contract; intermediate metadata never travels with an Event.
_V3_EVENT_TYPES = frozenset(
    {
        "enemy_spotted",
        "enemy_lost",
        "engagement_start",
        "engagement_end",
        "shot",
        "movement_state",
        "preaim_started",
        "peek",
        "info_peek",
        "position_change",
        "position_hold",
        "rotation_started",
        "rotation_completed",
        "utility_used",
        "ally_entry_start",
        "ally_enter_site",
        "enemy_reengage",
        "hold_angle",
        "site_state",
        "utility_effect_observed",
        "spike_pickup",
        "spike_dropped",
        "spike_defuse_started",
        "spike_defused",
        "weapon_pickup",
    }
)

_V3_EVENT_ATTRIBUTES: dict[str, frozenset[str]] = {
    "enemy_spotted": frozenset({"source", "zone_id", "world_bbox"}),
    "enemy_lost": frozenset({"source", "last_zone_id"}),
    "engagement_start": frozenset({"visible_enemy_count", "weapon"}),
    "engagement_end": frozenset({"reason"}),
    "shot": frozenset({"moving", "speed_class", "distance_class", "fire_mode", "first_shot"}),
    "movement_state": frozenset({"state", "speed_class"}),
    "preaim_started": frozenset({"lead_sec", "reference_mode", "alignment_error_norm"}),
    "peek": frozenset({"peek_style", "exposed_directions", "target_known", "distance_class"}),
    "info_peek": frozenset({"new_information_observed", "shot_fired", "duration_sec"}),
    "position_change": frozenset({"from", "to"}),
    "position_hold": frozenset({"duration_sec", "zone_id"}),
    "rotation_started": frozenset(
        {"from", "to", "known_enemy_info_count", "delay_since_enemy_info_sec"}
    ),
    "rotation_completed": frozenset({"from", "to", "duration_sec"}),
    "utility_used": frozenset({"ability_name", "purpose_observed", "slot"}),
    "ally_entry_start": frozenset({"site", "ally_count"}),
    "ally_enter_site": frozenset({"site", "ally_count"}),
    "enemy_reengage": frozenset({"gap_sec", "zone_id"}),
    "hold_angle": frozenset({"duration_sec", "weapon", "view_target_zone_id"}),
    "site_state": frozenset(
        {"visible_enemy_count", "active_crossfire", "incoming_damage_risk_observed"}
    ),
    "utility_effect_observed": frozenset(
        {"ability_name", "affected_side", "affected_count", "duration_sec"}
    ),
    "spike_pickup": frozenset(),
    "spike_dropped": frozenset(),
    "spike_defuse_started": frozenset(),
    "spike_defused": frozenset(),
    "weapon_pickup": frozenset(),
}

_V3_SPATIAL_KEYS = (
    "cover_available",
    "escape_route_available",
    "line_of_sight_state",
    "exposed_directions_count",
    "view_target_zone_id",
)


def project_spatial_context(spatial: Mapping[str, Any] | None) -> dict[str, Any]:
    """Project only the five v3 StateSnapshot spatial-context fields."""
    source = spatial if isinstance(spatial, Mapping) else {}
    result = {key: source.get(key) for key in _V3_SPATIAL_KEYS}
    if result["line_of_sight_state"] not in {
        "confirmed_clear",
        "confirmed_blocked",
        "unknown",
    }:
        result["line_of_sight_state"] = "unknown"
    count = result["exposed_directions_count"]
    exposure_source = source.get("exposed_directions_source")
    try:
        if count is not None and (int(count) < 0 or exposure_source != "static_peek_registry"):
            result["exposed_directions_count"] = None
        elif count is not None:
            result["exposed_directions_count"] = int(count)
    except (TypeError, ValueError):
        result["exposed_directions_count"] = None
    return result


def project_candidate_to_v3_event(
    candidate: Any, *, event_id: str | None = None
) -> dict[str, Any] | None:
    """Project a confirmed candidate to exactly the strict v3 Event top-level shape.

    Candidate metadata (evidence, producer, status, and suppression reason) is
    deliberately not copied. Unconfirmed/suppressed candidates remain in the
    intermediate timeline and cannot silently become package facts.
    """
    if isinstance(candidate, Mapping):
        data = candidate
    elif hasattr(candidate, "to_dict"):
        data = candidate.to_dict()
    else:
        return None
    if data.get("status") != "confirmed":
        return None
    event_type = data.get("type")
    if event_type not in _V3_EVENT_TYPES:
        return None
    attributes = data.get("attributes")
    if not isinstance(attributes, Mapping):
        attributes = {}
    try:
        time_sec = float(data.get("start_sec", data.get("time_sec")))
        confidence = min(1.0, max(0.0, float(data.get("confidence", 0.0))))
    except (TypeError, ValueError):
        return None
    if not math_is_finite_nonnegative(time_sec):
        return None
    identifier = event_id or str(data.get("candidate_id", ""))
    if not identifier:
        return None
    actor = data.get("actor", "unknown")
    if actor not in {"player", "ally", "enemy", "team", "system", "unknown"}:
        actor = "unknown"
    allowed = _V3_EVENT_ATTRIBUTES[event_type]
    return {
        "event_id": identifier,
        "time_sec": time_sec,
        "type": event_type,
        "actor": actor,
        "attributes": {key: attributes[key] for key in allowed if key in attributes},
        "confidence": confidence,
    }


def math_is_finite_nonnegative(value: float) -> bool:
    # Kept local so policy/projection remains importable without detector code.
    import math

    return math.isfinite(value) and value >= 0.0
