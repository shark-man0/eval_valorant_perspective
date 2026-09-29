from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from valorant_ai_coach.resources import resource_path

_REMOTE_POLICY = json.loads(
    resource_path("config/visual_v2/config/remote_view_detection_policy_v1.json").read_text()
)

_PRECEDENCE_STATES = {
    "spectator_first_person": "spectator_first_person",
    "buy_menu_open": "buy_menu_open",
    "expanded_tactical_map": "expanded_tactical_map",
}
_AGENT_TYPES = {
    "astra_astral",
    "cypher_camera",
    "sova_drone",
    "skye_trailblazer",
    "other",
}
_SIGNAL_ALIASES = {
    "player_hud_missing": ("player_hud_missing", "normal_weapon_hud_missing"),
    "ability_control_active": ("ability_control_active", "remote_ability_active"),
    "remote_overlay": ("remote_overlay", "remote_reticle_or_overlay"),
    "hands_weapon_absent_sustained": (
        "hands_weapon_absent_sustained",
        "normal_hands_weapon_absent_sustained",
    ),
}


def classify_remote_view(
    hud: Any,
    appearance_signals: Mapping[str, Any] | None = None,
    *,
    agent_template_type: str | None = None,
) -> dict[str, Any]:
    """Classify view attribution conservatively using Visual v2 precedence.

    `appearance_signals` may contain booleans or confidence floats for four
    independent evidence groups: `player_hud_missing`, `ability_control_active`,
    `remote_overlay`, and `hands_weapon_absent_sustained`. Missing OCR values
    are deliberately not evidence of a missing HUD. An explicit structural
    validity signal is required.

    The result is an internal decision record, not a strict VisualObservation.
    Cross-agent fallback requires two distinct groups and is capped at 0.78;
    a single group returns `unknown` so the caller can suppress mechanics.
    """

    primary_state = _read(hud, "primary_state", "unknown")
    flags = set(_read(hud, "state_flags", ()) or ())
    values = _read(hud, "values", {})
    if not isinstance(values, Mapping):
        values = {}

    # Preserve higher-priority classifications before attempting remote fallback.
    if primary_state in _PRECEDENCE_STATES:
        return _decision(primary_state, "none", _state_confidence(hud), [], "hud_precedence")
    if "buy_phase_banner" in flags or values.get("buy_phase_visible") is True:
        return _decision("buy_menu_open", "none", _state_confidence(hud), [], "buy_menu_signal")
    if _read(hud, "expanded_tactical_map", False) is True:
        return _decision(
            "expanded_tactical_map", "none", _state_confidence(hud), [], "tactical_map_signal"
        )

    if agent_template_type in _AGENT_TYPES:
        confidence = _number(_read(hud, "agent_template_confidence", 0.9), 0.9)
        return _decision(
            "remote_control_view",
            agent_template_type,
            confidence,
            ["agent_specific_template"],
            "agent_specific_template",
        )

    remote_type = _read(hud, "view_context", {}).get("remote_view_type", "unknown")
    if primary_state == "remote_control_view":
        return _decision(
            "remote_control_view",
            remote_type,
            _state_confidence(hud),
            ["hud_remote_state"],
            "hud_remote_state",
        )

    signals = dict(appearance_signals or {})
    # Explicit supplementary HUD fields are allowed, but absence of ammo OCR is
    # not. A caller may set `normal_weapon_hud_missing` only after structural checks.
    for name in ("remote_signals", "visual_remote_signals"):
        extra = _read(hud, name, None)
        if isinstance(extra, Mapping):
            signals.update(extra)
    if isinstance(values.get("remote_signals"), Mapping):
        signals.update(values["remote_signals"])

    accepted: list[tuple[str, float]] = []
    for group, aliases in _SIGNAL_ALIASES.items():
        raw = next((signals[key] for key in aliases if key in signals), None)
        signal_confidence = _signal_confidence(raw)
        if signal_confidence is not None:
            accepted.append((group, signal_confidence))

    if len(accepted) >= 2:
        base = sum(score for _, score in accepted) / len(accepted)
        confidence = min(
            _REMOTE_POLICY["cross_agent_remote_fallback"]["confidence_cap_without_agent_template"],
            base + min(0.08, 0.025 * (len(accepted) - 1)),
        )
        return _decision(
            "remote_control_view",
            "unknown",
            confidence,
            [name for name, _ in accepted],
            "cross_agent_fallback",
        )
    if accepted:
        name, score = accepted[0]
        return _decision("unknown", "unknown", min(0.39, score * 0.5), [name], "single_signal")

    if primary_state == "live_first_person":
        return _decision("live_first_person", "none", _state_confidence(hud), [], "hud_state")
    return _decision("unknown", "unknown", 0.0, [], "insufficient_evidence")


def _decision(
    state: str,
    subtype: str,
    confidence: float,
    signals: list[str],
    source: str,
) -> dict[str, Any]:
    return {
        "primary_state": state,
        "remote_view_type": subtype,
        "confidence": max(0.0, min(1.0, confidence)),
        "signals": signals,
        "source": source,
        "player_mechanics_eligible": state == "live_first_person",
    }


def _signal_confidence(value: Any) -> float | None:
    if isinstance(value, Mapping):
        present = value.get("present", value.get("value", False))
        if present is not True:
            return None
        return max(0.0, min(1.0, _number(value.get("confidence", 0.6), 0.6)))
    if value is True:
        return 0.6
    if (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and 0.0 < float(value) <= 1.0
    ):
        return float(value)
    return None


def _state_confidence(hud: Any) -> float:
    quality = _read(hud, "quality", {})
    if isinstance(quality, Mapping):
        return _number(quality.get("state_confidence", quality.get("hud_confidence", 0.0)))
    return 0.0


def _number(value: Any, default: float = 0.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError, OverflowError):
        return default
    return parsed if 0.0 <= parsed <= 1.0 else default


def _read(source: Any, name: str, default: Any) -> Any:
    if isinstance(source, Mapping):
        return source.get(name, default)
    return getattr(source, name, default)
