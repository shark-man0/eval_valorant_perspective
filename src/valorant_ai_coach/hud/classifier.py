from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, cast

from .models import PrimaryState, RemoteViewType, StateFlag


@dataclass(frozen=True, slots=True)
class StateClassification:
    primary_state: PrimaryState
    state_flags: tuple[StateFlag, ...]
    remote_view_type: RemoteViewType
    player_specific_hud_valid: bool
    is_player_world_view_trustworthy: bool
    confidence: float
    flag_confidence: dict[str, float]
    sensitive_visual_readers_suspended: bool = False


class HudStateClassifier:
    """Rule-based state interpreter; a positive ROI alone is never a state."""

    _REMOTE_SIGNALS: dict[str, RemoteViewType] = {
        "cypher_camera_template": "cypher_camera",
        "sova_drone_template": "sova_drone",
        "skye_trailblazer_template": "skye_trailblazer",
        "other_remote_view_template": "other",
    }

    def classify(self, signals: Mapping[str, Any]) -> StateClassification:
        flags: list[StateFlag] = []
        flag_confidence: dict[str, float] = {}
        confidence = 0.0

        def add_flag(name: StateFlag, value: bool, score: float = 0.9) -> None:
            if value and score >= 0.65:
                flags.append(name)
                flag_confidence[name] = min(1.0, max(0.0, score))

        combat_visible = bool(signals.get("combat_report_visible"))
        add_flag(
            "combat_report_visible",
            combat_visible,
            _confidence(signals, "combat_report_confidence"),
        )

        # Buy and round-end banners share a region; sequence evidence is required.
        shared_banner = bool(signals.get("shared_banner"))
        score_changed = bool(signals.get("score_changed"))
        score_change_sec = signals.get("score_changed_within_sec")
        recent_score_change = _within(score_change_sec, 3.0)
        next_state = signals.get("next_stable_state")
        buy_context = next_state == "live_first_person" or bool(signals.get("pre_round_context"))
        round_end_context = (
            recent_score_change
            or next_state == "buy_phase"
            or (bool(signals.get("timer_stopped")) and combat_visible)
        )
        buy_banner = shared_banner and not score_changed and not recent_score_change and buy_context
        round_banner = shared_banner and round_end_context and not buy_banner
        add_flag("buy_phase_banner", buy_banner, _confidence(signals, "banner_confidence"))
        add_flag("round_end_banner", round_banner, _confidence(signals, "banner_confidence"))

        # A flash requires a short temporal excursion; smoke requires persistent,
        # spatially uniform obstruction and stable HUD anchors.
        flash = all(
            bool(signals.get(key))
            for key in (
                "abrupt_luminance_spike",
                "scene_detail_collapse",
                "rapid_decay",
                "hud_anchors_stable",
            )
        )
        smoke_candidate = (
            bool(signals.get("low_edge_density"))
            and bool(signals.get("low_spatial_entropy"))
            and bool(signals.get("broad_color_uniformity"))
            and bool(signals.get("hud_anchors_stable"))
            and not flash
        )
        smoke_supported = not signals.get("smoke_ambiguous", False) or (
            signals.get("smoke_template_confirmed") is True
            and _confidence(signals, "smoke_template_confirmed_confidence", fallback=0.0) >= 0.85
        )
        smoke = smoke_candidate and smoke_supported
        add_flag("vision_obscured_flash", flash, _confidence(signals, "flash_confidence"))
        add_flag("vision_obscured_smoke", smoke, _confidence(signals, "smoke_confidence"))

        map_partial = bool(signals.get("partial_expanded_map"))
        map_transition = bool(signals.get("map_transition")) or (
            map_partial and _within(signals.get("transition_duration_sec"), 0.25)
        )
        add_flag("visual_transition", map_transition, _confidence(signals, "transition_confidence"))

        buy_menu = bool(signals.get("buy_menu_grid_present")) and bool(
            signals.get("buy_menu_close_anchor_present")
        )
        expanded_map = bool(signals.get("expanded_map_stable")) or (
            bool(signals.get("expanded_map_present")) and not map_transition
        )
        spectator = bool(signals.get("spectated_player_panel")) and (
            signals.get("self_hud_identity_trustworthy") is False
            or bool(signals.get("recent_player_death_candidate"))
        )

        remote_type: RemoteViewType = "none"
        astra_features = all(
            bool(signals.get(key))
            for key in ("astral_geometry", "purple_palette", "astra_hand_interface")
        )
        remote_evidence = bool(signals.get("remote_control_candidate")) or astra_features
        if astra_features:
            remote_type = "astra_astral"
        else:
            for signal, subtype in self._REMOTE_SIGNALS.items():
                if bool(signals.get(signal)):
                    remote_evidence = True
                    remote_type = subtype
                    break
            hinted_type = signals.get("remote_view_type")
            if remote_evidence and remote_type == "none":
                remote_type = (
                    cast(RemoteViewType, hinted_type)
                    if hinted_type
                    in {
                        "astra_astral",
                        "cypher_camera",
                        "sova_drone",
                        "skye_trailblazer",
                        "other",
                        "unknown",
                    }
                    else "unknown"
                )
        remote = remote_evidence
        heuristic_remote_only = (
            astra_features
            and bool(signals.get("remote_texture_candidate"))
            and not bool(signals.get("remote_control_candidate"))
            and not any(bool(signals.get(key)) for key in self._REMOTE_SIGNALS)
        )

        candidates = [buy_menu, expanded_map, spectator, remote]
        conflicting_modes = sum(candidates) > 1
        primary_state: PrimaryState
        if map_transition:
            primary_state = "unknown"
            confidence = _confidence(signals, "transition_confidence", fallback=0.7)
            # A transient map frame does not establish the stable map state.
        elif conflicting_modes:
            primary_state = "unknown"
            confidence = min(_confidence(signals, "state_confidence", fallback=0.45), 0.6)
        elif buy_menu:
            primary_state = "buy_menu_open"
            confidence = _confidence(signals, "buy_menu_confidence", fallback=0.88)
        elif expanded_map:
            primary_state = "expanded_tactical_map"
            confidence = _confidence(signals, "map_confidence", fallback=0.88)
        elif spectator:
            primary_state = "spectator_first_person"
            confidence = _confidence(signals, "spectator_confidence", fallback=0.9)
        elif heuristic_remote_only:
            # Color, circles and edge density are texture candidates, not a
            # confirmed control interface. Keep them in mode conflicts and live
            # exclusion, but do not promote a sole candidate to Remote or live.
            primary_state = "unknown"
            confidence = min(_confidence(signals, "state_confidence", fallback=0.45), 0.45)
        elif remote:
            primary_state = "remote_control_view"
            confidence = _confidence(signals, "remote_confidence", fallback=0.88)
        elif bool(signals.get("live_first_person")):
            primary_state = "live_first_person"
            confidence = _confidence(signals, "state_confidence", fallback=0.88)
        else:
            primary_state = "unknown"
            confidence = _confidence(signals, "state_confidence", fallback=0.0)

        player_hud_valid = primary_state == "live_first_person"
        world_trustworthy = (
            player_hud_valid
            and not (smoke_candidate and not smoke_supported)
            and not any(
                flag in flags
                for flag in (
                    "vision_obscured_smoke",
                    "vision_obscured_flash",
                    "visual_transition",
                )
            )
        )
        return StateClassification(
            primary_state=primary_state,
            state_flags=tuple(flags),
            remote_view_type=remote_type if primary_state == "remote_control_view" else "none",
            player_specific_hud_valid=player_hud_valid,
            is_player_world_view_trustworthy=world_trustworthy,
            confidence=confidence,
            flag_confidence=flag_confidence,
            sensitive_visual_readers_suspended=map_transition,
        )


def _within(value: Any, bound: float) -> bool:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return False
    return 0 <= parsed <= bound


def _confidence(signals: Mapping[str, Any], key: str, fallback: float = 0.9) -> float:
    try:
        value = float(signals.get(key, fallback))
    except (TypeError, ValueError):
        return 0.0
    return min(1.0, max(0.0, value))
