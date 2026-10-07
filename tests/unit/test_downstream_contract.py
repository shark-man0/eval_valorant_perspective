"""Downstream (non-vision) contract tests.

All inputs here are synthetic fixtures that exercise the Round Package -> Fact ->
Rule -> Coach seams. They are NOT production outputs and must never be used to
tune or backfill Vision behaviour.
"""

from __future__ import annotations

from typing import Any

import pytest

from valorant_ai_coach.facts import FactBuilder
from valorant_ai_coach.rounds import RoundPackageBuilder

PLAYER_RELATIVE_SPIKE_STATES = ("carried_by_player", "carried_by_ally", "not_carried")
WORLD_SPIKE_STATES = ("dropped", "planted", "defusing", "resolved")


def observation(time_sec: float, *, spike_state: str = "unknown") -> dict[str, Any]:
    """Synthetic live-first-person HUD observation (Round Package v2 intermediate)."""
    return {
        "schema_version": "2.0",
        "time_sec": time_sec,
        "frame_index": round(time_sec * 60),
        "primary_state": "live_first_person",
        "state_flags": [],
        "view_context": {"remote_view_type": "none", "is_player_world_view_trustworthy": True},
        "values": {
            "round_time_remaining_sec": max(0, 100 - time_sec),
            "ally_alive": 5,
            "enemy_alive": 5,
            "hp": 100,
            "armor": 50,
            "ammo_current": 25,
            "ammo_reserve": 50,
            "weapon_text": None,
            "spike_state": spike_state,
            "ability_slots": [],
            "player_specific_hud_valid": True,
        },
        "quality": {
            "hud_confidence": 0.9,
            "visual_confidence": 0.0,
            "occluded_rois": [],
            "notes": [],
            "state_confidence": 0.9,
            "roi_confidence": {},
        },
    }


def spectator_observation(spike_state: str) -> dict[str, Any]:
    value = observation(5.0, spike_state=spike_state)
    value["primary_state"] = "spectator_first_person"
    value["view_context"]["is_player_world_view_trustworthy"] = False  # type: ignore[index]
    values = value["values"]
    assert isinstance(values, dict)
    values.update(
        player_specific_hud_valid=False,
        hp=None,
        armor=None,
        ammo_current=None,
        ammo_reserve=None,
    )
    return value


def snapshots_of(obs: dict[str, Any]) -> list[dict[str, Any]]:
    # _state_snapshots does not use instance state; avoid constructing full builder deps.
    builder = RoundPackageBuilder.__new__(RoundPackageBuilder)
    return builder._state_snapshots([obs])


def facts_for(snapshots: list[dict[str, Any]]) -> dict[str, list[Any]]:
    package = {
        "state_snapshots": snapshots,
        "events": [],
        "round_meta": {},
        "observation_quality": {"hud_confidence": 0.9, "visual_confidence": 0.0},
    }
    result: dict[str, list[Any]] = {}
    for fact in FactBuilder().enrich(package)["deterministic_facts"]:
        result.setdefault(fact["key"], []).append(fact["value"])
    return result


@pytest.mark.parametrize("spike_state", PLAYER_RELATIVE_SPIKE_STATES)
def test_spectator_view_player_relative_spike_state_does_not_become_player_fact(
    spike_state: str,
) -> None:
    snapshots = snapshots_of(spectator_observation(spike_state))
    assert snapshots[0]["spike_state"] == "unknown"
    facts = facts_for(snapshots)
    assert "spike_carried_by_player" not in facts
    assert "spike_planted" not in facts


@pytest.mark.parametrize("spike_state", WORLD_SPIKE_STATES)
def test_spectator_view_keeps_viewpoint_independent_world_spike_state(spike_state: str) -> None:
    snapshots = snapshots_of(spectator_observation(spike_state))
    assert snapshots[0]["spike_state"] == spike_state


@pytest.mark.parametrize("spike_state", ("carried_by_player", "not_carried"))
def test_live_player_view_spike_state_is_unchanged(spike_state: str) -> None:
    snapshots = snapshots_of(observation(5.0, spike_state=spike_state))
    assert snapshots[0]["spike_state"] == spike_state
    assert facts_for(snapshots)["spike_carried_by_player"] == [spike_state == "carried_by_player"]


def test_spectator_view_masks_player_specific_values() -> None:
    snapshot = snapshots_of(spectator_observation("unknown"))[0]
    assert snapshot["hp"] is None
    assert snapshot["armor"] is None
    assert snapshot["weapon"] is None
    assert snapshot["utility_available_count"] is None
