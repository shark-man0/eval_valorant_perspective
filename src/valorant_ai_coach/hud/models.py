from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Literal

PrimaryState = Literal[
    "live_first_person",
    "spectator_first_person",
    "remote_control_view",
    "buy_menu_open",
    "expanded_tactical_map",
    "unknown",
]
RemoteViewType = Literal[
    "none",
    "astra_astral",
    "cypher_camera",
    "sova_drone",
    "skye_trailblazer",
    "other",
    "unknown",
]
StateFlag = Literal[
    "buy_phase_banner",
    "combat_report_visible",
    "round_end_banner",
    "vision_obscured_smoke",
    "vision_obscured_flash",
    "visual_transition",
]

PRIMARY_STATES = {
    "live_first_person",
    "spectator_first_person",
    "remote_control_view",
    "buy_menu_open",
    "expanded_tactical_map",
    "unknown",
}
REMOTE_VIEW_TYPES = {
    "none",
    "astra_astral",
    "cypher_camera",
    "sova_drone",
    "skye_trailblazer",
    "other",
    "unknown",
}
STATE_FLAGS = {
    "buy_phase_banner",
    "combat_report_visible",
    "round_end_banner",
    "vision_obscured_smoke",
    "vision_obscured_flash",
    "visual_transition",
}


def empty_hud_values() -> dict[str, Any]:
    return {
        "round_time_remaining_sec": None,
        "score_ally": None,
        "score_enemy": None,
        "ally_alive": None,
        "enemy_alive": None,
        "hp": None,
        "armor": None,
        "ammo_current": None,
        "ammo_reserve": None,
        "weapon_text": None,
        "spike_state": "unknown",
        "location_text": None,
        "kill_feed_rows": [],
        "ability_slots": [],
        "combat_report_visible": False,
        "buy_phase_visible": False,
        "round_end_text": None,
        "zone_id": None,
        "player_specific_hud_valid": False,
    }


def empty_hud_quality() -> dict[str, Any]:
    return {
        "hud_confidence": 0.0,
        "visual_confidence": 0.0,
        "occluded_rois": [],
        "notes": [],
        "state_confidence": 0.0,
        "roi_confidence": {},
    }


@dataclass(frozen=True, slots=True)
class HudObservationV2:
    """Schema-shaped, non-evaluative observation for one sampled frame."""

    time_sec: float
    frame_index: int
    primary_state: PrimaryState = "unknown"
    state_flags: tuple[StateFlag, ...] = ()
    values: dict[str, Any] = field(default_factory=empty_hud_values)
    quality: dict[str, Any] = field(default_factory=empty_hud_quality)
    remote_view_type: RemoteViewType = "none"
    is_player_world_view_trustworthy: bool = False

    schema_version: Literal["2.0"] = "2.0"

    def __post_init__(self) -> None:
        if (
            isinstance(self.time_sec, bool)
            or not isinstance(self.time_sec, (int, float))
            or not math.isfinite(self.time_sec)
            or self.time_sec < 0
        ):
            raise ValueError("time_secは0以上である必要があります")
        if (
            not isinstance(self.frame_index, int)
            or isinstance(self.frame_index, bool)
            or self.frame_index < 0
        ):
            raise ValueError("frame_indexは0以上である必要があります")
        if self.primary_state not in PRIMARY_STATES:
            raise ValueError(f"primary_stateが不正です: {self.primary_state}")
        if self.remote_view_type not in REMOTE_VIEW_TYPES:
            raise ValueError(f"remote_view_typeが不正です: {self.remote_view_type}")
        if any(flag not in STATE_FLAGS for flag in self.state_flags):
            raise ValueError("state_flagsに未対応の値があります")
        if len(set(self.state_flags)) != len(self.state_flags):
            raise ValueError("state_flagsは重複できません")
        _validate_values(self.values)
        _validate_quality(self.quality)
        player_valid = bool(self.values.get("player_specific_hud_valid", False))
        if self.primary_state != "live_first_person" and player_valid:
            raise ValueError("live_first_person以外ではplayer_specific_hud_valid=falseが必要です")
        if not player_valid:
            for key in ("hp", "armor", "ammo_current", "ammo_reserve", "weapon_text"):
                if self.values.get(key) is not None:
                    raise ValueError(f"player_specific_hud_valid=falseでは{key}=nullが必要です")
            for slot in self.values["ability_slots"]:
                if slot["available"] is not None or slot["charges"] is not None:
                    raise ValueError("player_specific_hud_valid=falseではability値を確定できません")
        if self.primary_state != "remote_control_view" and self.remote_view_type != "none":
            raise ValueError("remote_control_view以外ではremote_view_type=noneが必要です")
        if self.is_player_world_view_trustworthy and self.primary_state != "live_first_person":
            raise ValueError("live_first_person以外ではworld viewを信頼できません")
        if self.is_player_world_view_trustworthy and set(self.state_flags) & {
            "vision_obscured_smoke",
            "vision_obscured_flash",
            "visual_transition",
        }:
            raise ValueError("遮蔽または遷移中はworld viewを信頼できません")

    @property
    def player_specific_hud_valid(self) -> bool:
        return bool(self.values.get("player_specific_hud_valid", False))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "2.0",
            "time_sec": float(self.time_sec),
            "frame_index": int(self.frame_index),
            "primary_state": self.primary_state,
            "state_flags": list(self.state_flags),
            "view_context": {
                "remote_view_type": self.remote_view_type,
                "is_player_world_view_trustworthy": bool(self.is_player_world_view_trustworthy),
            },
            "values": _copy_json_value(self.values),
            "quality": _copy_json_value(self.quality),
        }

    @classmethod
    def from_dict(cls, source: dict[str, Any]) -> HudObservationV2:
        allowed = {
            "schema_version",
            "time_sec",
            "frame_index",
            "primary_state",
            "state_flags",
            "view_context",
            "values",
            "quality",
        }
        if set(source) - allowed:
            raise ValueError("HUD observationにスキーマ外のfieldがあります")
        if source.get("schema_version") != "2.0":
            raise ValueError("schema_versionは2.0である必要があります")
        context = source.get("view_context")
        if not isinstance(context, dict) or set(context) != {
            "remote_view_type",
            "is_player_world_view_trustworthy",
        }:
            raise ValueError("view_contextがスキーマと一致しません")
        flags = source.get("state_flags", [])
        if not isinstance(flags, list):
            raise ValueError("state_flagsはarrayである必要があります")
        values = source.get("values")
        quality = source.get("quality")
        if not isinstance(values, dict) or not isinstance(quality, dict):
            raise ValueError("valuesとqualityはobjectである必要があります")
        world_view_trustworthy = context["is_player_world_view_trustworthy"]
        if not isinstance(world_view_trustworthy, bool):
            raise ValueError("is_player_world_view_trustworthyはbooleanである必要があります")
        return cls(
            time_sec=float(source["time_sec"]),
            frame_index=int(source["frame_index"]),
            primary_state=source["primary_state"],
            state_flags=tuple(flags),
            values=_copy_json_value(values),
            quality=_copy_json_value(quality),
            remote_view_type=context["remote_view_type"],
            is_player_world_view_trustworthy=world_view_trustworthy,
        )


def accept_hud_value(value: Any, confidence: float, *, cross_checked: bool = False) -> Any:
    """Apply HUD fact acceptance thresholds; never remap to evaluation confidence."""

    if isinstance(confidence, bool):
        raise ValueError("HUD confidenceは0〜1である必要があります")
    confidence = float(confidence)
    if not math.isfinite(confidence) or not 0 <= confidence <= 1:
        raise ValueError("HUD confidenceは0〜1である必要があります")
    if confidence < 0.65 or (confidence < 0.85 and not cross_checked):
        return None
    return value


def _validate_values(values: dict[str, Any]) -> None:
    required = {
        "round_time_remaining_sec",
        "score_ally",
        "score_enemy",
        "ally_alive",
        "enemy_alive",
        "hp",
        "armor",
        "ammo_current",
        "ammo_reserve",
        "spike_state",
        "location_text",
        "kill_feed_rows",
        "ability_slots",
    }
    allowed = required | {
        "weapon_text",
        "combat_report_visible",
        "buy_phase_visible",
        "round_end_text",
        "zone_id",
        "player_specific_hud_valid",
    }
    if required - set(values) or set(values) - allowed:
        raise ValueError("valuesがHUD Observation v2スキーマと一致しません")
    if values["spike_state"] not in {
        "not_carried",
        "carried_by_player",
        "carried_by_ally",
        "dropped",
        "planted",
        "defusing",
        "resolved",
        "unknown",
    }:
        raise ValueError("spike_stateが不正です")
    if not isinstance(values["kill_feed_rows"], list) or not isinstance(
        values["ability_slots"], list
    ):
        raise ValueError("kill_feed_rowsとability_slotsはarrayである必要があります")
    if len(values["ability_slots"]) > 4:
        raise ValueError("ability_slotsは最大4件です")
    _optional_number(values["round_time_remaining_sec"], minimum=0)
    for key in ("score_ally", "score_enemy"):
        _optional_int(values[key], minimum=0)
    for key in ("ally_alive", "enemy_alive"):
        _optional_int(values[key], minimum=0, maximum=5)
    _optional_int(values["hp"], minimum=0, maximum=100)
    _optional_int(values["armor"], minimum=0, maximum=50)
    _optional_int(values["ammo_current"], minimum=0)
    _optional_int(values["ammo_reserve"], minimum=0)
    for key in ("weapon_text", "location_text", "round_end_text", "zone_id"):
        if values.get(key) is not None and not isinstance(values[key], str):
            raise ValueError(f"{key}はstringまたはnullである必要があります")
    for key in ("combat_report_visible", "buy_phase_visible", "player_specific_hud_valid"):
        if key in values and not isinstance(values[key], bool):
            raise ValueError(f"{key}はbooleanである必要があります")
    for row in values["kill_feed_rows"]:
        if not isinstance(row, dict) or not {"raw_text", "confidence"} <= set(row):
            raise ValueError("kill_feed_rowsの各要素にはraw_textとconfidenceが必要です")
        if set(row) - {
            "raw_text",
            "killer_text",
            "victim_text",
            "confidence",
            "killer_side",
            "victim_side",
            "weapon_text",
        }:
            raise ValueError("kill_feed_rowsにスキーマ外のfieldがあります")
        if (
            isinstance(row["confidence"], bool)
            or not math.isfinite(float(row["confidence"]))
            or not 0 <= float(row["confidence"]) <= 1
        ):
            raise ValueError("kill feed confidenceは0〜1である必要があります")
        for side_key in ("killer_side", "victim_side"):
            if side_key in row and row[side_key] not in {"ally", "enemy", "unknown"}:
                raise ValueError(f"{side_key}が不正です")
    for slot in values["ability_slots"]:
        if not isinstance(slot, dict) or set(slot) != {
            "slot",
            "available",
            "charges",
            "confidence",
            "keybind_role",
            "semantic_role",
            "ability_name",
        }:
            raise ValueError("ability_slotsの要素がスキーマと一致しません")
        if slot["slot"] not in {0, 1, 2, 3}:
            raise ValueError("ability slot indexが不正です")
        if slot["available"] is not None and not isinstance(slot["available"], bool):
            raise ValueError("ability availableはbooleanまたはnullです")
        _optional_int(slot["charges"], minimum=0)
        if (
            isinstance(slot["confidence"], bool)
            or not math.isfinite(float(slot["confidence"]))
            or not 0 <= float(slot["confidence"]) <= 1
        ):
            raise ValueError("ability confidenceは0〜1である必要があります")
        if slot["keybind_role"] not in {"C", "Q", "E", "X", "unknown"}:
            raise ValueError("ability keybind_roleが不正です")
        if slot["semantic_role"] not in {
            "ability_c",
            "ability_q",
            "ability_e",
            "ultimate",
            "unknown",
        }:
            raise ValueError("ability semantic_roleが不正です")
        if slot["ability_name"] is not None and not isinstance(slot["ability_name"], str):
            raise ValueError("ability_nameはstringまたはnullである必要があります")


def _validate_quality(quality: dict[str, Any]) -> None:
    required = {
        "hud_confidence",
        "visual_confidence",
        "occluded_rois",
        "notes",
        "state_confidence",
        "roi_confidence",
    }
    if set(quality) != required:
        raise ValueError("qualityがHUD Observation v2スキーマと一致しません")
    for key in ("hud_confidence", "visual_confidence", "state_confidence"):
        if (
            isinstance(quality[key], bool)
            or not math.isfinite(float(quality[key]))
            or not 0 <= float(quality[key]) <= 1
        ):
            raise ValueError(f"{key}は0〜1である必要があります")
    if not isinstance(quality["occluded_rois"], list) or not all(
        isinstance(item, str) for item in quality["occluded_rois"]
    ):
        raise ValueError("occluded_roisはstringのarrayである必要があります")
    if not isinstance(quality["notes"], list) or not all(
        isinstance(item, str) for item in quality["notes"]
    ):
        raise ValueError("notesはstringのarrayである必要があります")
    roi_confidence = quality["roi_confidence"]
    if not isinstance(roi_confidence, dict) or any(
        isinstance(value, bool) or not math.isfinite(float(value)) or not 0 <= float(value) <= 1
        for value in roi_confidence.values()
    ):
        raise ValueError("roi_confidenceは0〜1の数値objectである必要があります")


def _optional_number(value: Any, *, minimum: float) -> None:
    if value is not None and (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value < minimum
    ):
        raise ValueError("数値が範囲外です")


def _optional_int(value: Any, *, minimum: int, maximum: int | None = None) -> None:
    if value is None:
        return
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        raise ValueError("整数が範囲外です")
    if maximum is not None and value > maximum:
        raise ValueError("整数が範囲外です")


def _copy_json_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _copy_json_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_copy_json_value(item) for item in value]
    if isinstance(value, tuple):
        return [_copy_json_value(item) for item in value]
    return value
