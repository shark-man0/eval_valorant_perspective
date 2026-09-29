"""Typed, conservative intermediate records for the Visual Analyzer v2 core."""

from __future__ import annotations

import copy
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _object_defaults(defaults: Mapping[str, Any], value: Any) -> dict[str, Any]:
    """Merge only schema-known keys, so a caller cannot leak ad-hoc data to v2."""
    source = _mapping(value)
    return {
        key: copy.deepcopy(source[key]) if key in source else copy.deepcopy(default)
        for key, default in defaults.items()
    }


_ELIGIBILITY_DEFAULTS: dict[str, Any] = {
    "player_mechanics": False,
    "world_semantics": False,
    "reason_codes": ["unknown_state"],
}
_MOTION_DEFAULTS: dict[str, Any] = {
    "state": "unknown",
    "map_displacement_norm_per_sec": None,
    "camera_motion_score": None,
    "stationary_confidence": 0.0,
    "evidence_sources": [],
}
_AIMING_DEFAULTS: dict[str, Any] = {
    "crosshair_x_norm": 0.5,
    "crosshair_y_norm": 0.5,
    "crosshair_stable": None,
    "visible_enemy_head_refs": [],
    "primary_target_ref": None,
    "head_alignment_error_norm": None,
    "reference_mode": "none",
    "confidence": 0.0,
}
_WEAPON_DEFAULTS: dict[str, Any] = {
    "weapon_text": None,
    "ammo_current": None,
    "ammo_delta": None,
    "muzzle_flash_score": None,
    "recoil_score": None,
    "shot_candidate": False,
    "first_shot_candidate": False,
    "confidence": 0.0,
    "burst_active": False,
    "burst_start_candidate": False,
}
_ENTITIES_DEFAULTS: dict[str, Any] = {"visible_enemies": [], "visible_allies": []}
_SPATIAL_DEFAULTS: dict[str, Any] = {
    "cover_available": None,
    "escape_route_available": None,
    "line_of_sight_state": "unknown",
    "exposed_directions_count": None,
    "view_target_zone_id": None,
    "cover_edge_score": None,
    "confidence": 0.0,
    "exposed_directions_source": "none",
}
_MINIMAP_DEFAULTS: dict[str, Any] = {
    "self_x_norm": None,
    "self_y_norm": None,
    "zone_id": None,
    "zone_name": None,
    "ally_markers": [],
    "enemy_markers": [],
    "track_confidence": 0.0,
}
_UTILITY_DEFAULTS: dict[str, Any] = {
    "cast_candidate": False,
    "slot": None,
    "ability_name": None,
    "world_effect_candidate": None,
    "affected_side": "unknown",
    "confidence": 0.0,
}
_QUALITY_DEFAULTS: dict[str, Any] = {
    "visual_confidence": 0.0,
    "occluded": False,
    "blur_score": None,
    "notes": [],
}


@dataclass(frozen=True, slots=True)
class VisualObservation:
    """Schema-shaped observation at one frame on the original video clock.

    ``from_mapping`` fills missing values with a valid but unknown/low-confidence
    v2 record. The mappings are intentionally kept as nested v2 objects so
    pixel runtimes can add observations without depending on this core's
    detector implementations.
    """

    time_sec: float = 0.0
    frame_index: int = 0
    hud_primary_state: str = "unknown"
    analysis_eligibility: Mapping[str, Any] = field(
        default_factory=lambda: copy.deepcopy(_ELIGIBILITY_DEFAULTS)
    )
    motion: Mapping[str, Any] = field(default_factory=lambda: copy.deepcopy(_MOTION_DEFAULTS))
    aiming: Mapping[str, Any] = field(default_factory=lambda: copy.deepcopy(_AIMING_DEFAULTS))
    weapon_action: Mapping[str, Any] = field(
        default_factory=lambda: copy.deepcopy(_WEAPON_DEFAULTS)
    )
    entities: Mapping[str, Any] = field(default_factory=lambda: copy.deepcopy(_ENTITIES_DEFAULTS))
    spatial: Mapping[str, Any] = field(default_factory=lambda: copy.deepcopy(_SPATIAL_DEFAULTS))
    minimap: Mapping[str, Any] = field(default_factory=lambda: copy.deepcopy(_MINIMAP_DEFAULTS))
    utility: Mapping[str, Any] = field(default_factory=lambda: copy.deepcopy(_UTILITY_DEFAULTS))
    quality: Mapping[str, Any] = field(default_factory=lambda: copy.deepcopy(_QUALITY_DEFAULTS))

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> VisualObservation:
        """Create a conservative observation from a mapping or partial runtime record."""
        raw = _mapping(value)
        time_value = raw.get("time_sec", 0.0)
        try:
            time_sec = float(time_value)
        except (TypeError, ValueError):
            time_sec = 0.0
        if not math.isfinite(time_sec) or time_sec < 0:
            time_sec = 0.0
        try:
            frame_index = max(0, int(raw.get("frame_index", 0)))
        except (TypeError, ValueError):
            frame_index = 0
        state = raw.get("hud_primary_state", "unknown")
        allowed_states = {
            "live_first_person",
            "spectator_first_person",
            "buy_menu_open",
            "remote_control_view",
            "expanded_tactical_map",
            "unknown",
        }
        if state not in allowed_states:
            state = "unknown"

        entities_source = _mapping(raw.get("entities"))
        entities: dict[str, Any] = {}
        for key in ("visible_enemies", "visible_allies"):
            detections = entities_source.get(key, [])
            clean: list[dict[str, Any]] = []
            if isinstance(detections, Sequence) and not isinstance(detections, (str, bytes)):
                for item in detections:
                    entity = _mapping(item)
                    clean.append(
                        {
                            field_name: copy.deepcopy(entity[field_name])
                            for field_name in (
                                "detection_id",
                                "bbox_norm",
                                "head_point_norm",
                                "outline_side",
                                "confidence",
                            )
                            if field_name in entity
                        }
                    )
            entities[key] = clean

        def clean_markers(name: str) -> list[dict[str, Any]]:
            values = _mapping(raw.get("minimap")).get(name, [])
            if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
                return []
            return [
                {
                    field_name: copy.deepcopy(_mapping(item)[field_name])
                    for field_name in ("x_norm", "y_norm", "side", "confidence")
                    if field_name in _mapping(item)
                }
                for item in values
            ]

        minimap = _object_defaults(_MINIMAP_DEFAULTS, raw.get("minimap"))
        minimap["ally_markers"] = clean_markers("ally_markers")
        minimap["enemy_markers"] = clean_markers("enemy_markers")

        return cls(
            time_sec=time_sec,
            frame_index=frame_index,
            hud_primary_state=state,
            analysis_eligibility=_object_defaults(
                _ELIGIBILITY_DEFAULTS, raw.get("analysis_eligibility")
            ),
            motion=_object_defaults(_MOTION_DEFAULTS, raw.get("motion")),
            aiming=_object_defaults(_AIMING_DEFAULTS, raw.get("aiming")),
            weapon_action=_object_defaults(_WEAPON_DEFAULTS, raw.get("weapon_action")),
            entities=entities,
            spatial=_object_defaults(_SPATIAL_DEFAULTS, raw.get("spatial")),
            minimap=minimap,
            utility=_object_defaults(_UTILITY_DEFAULTS, raw.get("utility")),
            quality=_object_defaults(_QUALITY_DEFAULTS, raw.get("quality")),
        )

    def to_dict(self) -> dict[str, Any]:
        """Return exactly the Visual Observation v2 top-level schema fields."""
        return {
            "schema_version": "2.0",
            "time_sec": self.time_sec,
            "frame_index": self.frame_index,
            "hud_primary_state": self.hud_primary_state,
            "analysis_eligibility": copy.deepcopy(dict(self.analysis_eligibility)),
            "motion": copy.deepcopy(dict(self.motion)),
            "aiming": copy.deepcopy(dict(self.aiming)),
            "weapon_action": copy.deepcopy(dict(self.weapon_action)),
            "entities": copy.deepcopy(dict(self.entities)),
            "spatial": copy.deepcopy(dict(self.spatial)),
            "minimap": copy.deepcopy(dict(self.minimap)),
            "utility": copy.deepcopy(dict(self.utility)),
            "quality": copy.deepcopy(dict(self.quality)),
        }


@dataclass(frozen=True, slots=True)
class EvidencePoint:
    """One observed signal attached to an event candidate."""

    time_sec: float
    frame_ref: str
    signal: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "time_sec": self.time_sec,
            "frame_ref": self.frame_ref,
            "signal": self.signal,
        }


@dataclass(frozen=True, slots=True)
class EventCandidate:
    """Evidence-backed intermediate event, before explicit v3 projection."""

    candidate_id: str
    type: str
    actor: str
    start_sec: float
    end_sec: float
    attributes: Mapping[str, Any]
    confidence: float
    producer_component: str
    evidence: tuple[EvidencePoint, ...]
    semantic_confirmation: str = "not_needed"
    status: str = "candidate"
    suppression_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        result = {
            "candidate_id": self.candidate_id,
            "type": self.type,
            "actor": self.actor,
            "start_sec": self.start_sec,
            "end_sec": self.end_sec,
            "attributes": copy.deepcopy(dict(self.attributes)),
            "confidence": self.confidence,
            "producer_component": self.producer_component,
            "evidence": [point.to_dict() for point in self.evidence],
            "semantic_confirmation": self.semantic_confirmation,
            "status": self.status,
        }
        if self.suppression_reason is not None:
            result["suppression_reason"] = self.suppression_reason
        return result
