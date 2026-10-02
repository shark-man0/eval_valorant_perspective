"""Current-frame identity evidence, deliberately independent of geometry anchors."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

STRUCTURES = ("hp_hud_structure", "ability_bar_structure", "weapon_ammo_structure")


@dataclass(frozen=True)
class IdentityEvidence:
    live: bool
    positive_count: int
    reason: str


def live_identity(signals: Mapping[str, Any], *, geometry_valid: bool) -> IdentityEvidence:
    def confirmed(key: str) -> bool:
        score = signals.get(key + "_confidence")
        return (
            signals.get(key) is True
            and isinstance(score, (int, float))
            and not isinstance(score, bool)
            and math.isfinite(score)
            and 0.90 <= score <= 1
        )

    count = sum(confirmed(key) for key in STRUCTURES)
    if not geometry_valid:
        return IdentityEvidence(False, count, "geometry_invalid")
    # Unchecked absence is not negative evidence. The current frame must have
    # been measured by a configured spectator detector, not just lack its flag.
    if (
        signals.get("spectator_panel_absent") is not True
        or signals.get("spectator_detector_checked") is not True
        or signals.get("spectator_panel_present") is not False
    ):
        return IdentityEvidence(False, count, "spectator_exclusion_unverified")
    blockers = (
        "spectated_player_panel",
        "self_hud_identity_lost",
        "recent_player_death_candidate",
        "remote_control_candidate",
        "cypher_camera_template",
        "sova_drone_template",
        "skye_trailblazer_template",
        "other_remote_view_template",
        "special_reticle_present",
        "expanded_map_present",
        "expanded_map_stable",
        "map_transition",
        "combat_report_visible",
    )
    if (
        any(signals.get(key) for key in blockers)
        or (signals.get("buy_menu_grid_present") and signals.get("buy_menu_close_anchor_present"))
        or signals.get("self_hud_identity_trustworthy") is False
        or all(
            signals.get(key)
            for key in ("astral_geometry", "purple_palette", "astra_hand_interface")
        )
    ):
        return IdentityEvidence(False, count, "competing_view_evidence")
    if count < len(STRUCTURES):
        return IdentityEvidence(False, count, "structure_evidence_insufficient")
    return IdentityEvidence(True, count, "independent_hud_structures")
