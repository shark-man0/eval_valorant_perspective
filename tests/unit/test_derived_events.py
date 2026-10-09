"""DerivedEventBuilder contract tests (synthetic HUD observations)."""

from __future__ import annotations

import copy
import random
from typing import Any

import pytest

from valorant_ai_coach.events import DerivedEventBuilder, EventSourceContract
from valorant_ai_coach.events.derived import DerivedEventInputError
from valorant_ai_coach.resources import resource_path


def builder() -> DerivedEventBuilder:
    contract = EventSourceContract.load(resource_path("config/event_source_contract_v1.json"))
    return DerivedEventBuilder(contract)


def obs(
    time_sec: float,
    *,
    spike: str = "not_carried",
    ally: int = 5,
    enemy: int = 5,
    hp: int | None = 100,
    valid: bool = True,
    confidence: float = 0.9,
) -> dict[str, Any]:
    return {
        "time_sec": time_sec,
        "primary_state": "live_first_person" if valid else "spectator_first_person",
        "values": {
            "ally_alive": ally,
            "enemy_alive": enemy,
            "hp": hp if valid else None,
            "armor": 0,
            "spike_state": spike,
            "round_time_remaining_sec": 90,
            "player_specific_hud_valid": valid,
        },
        "quality": {"hud_confidence": confidence},
    }


def ids(events: list[dict[str, Any]]) -> list[str]:
    return [event["event_id"] for event in events]


# --- id stability / determinism -------------------------------------------------------------


def test_event_ids_do_not_depend_on_unrelated_earlier_observations() -> None:
    target = obs(5.0, spike="planted")
    alone = builder().build([target])
    with_noise = builder().build([obs(1.0, confidence=0.1), obs(2.0, ally=4), target])
    noise_free = [e for e in with_noise if e["time_sec"] == 5.0]
    assert ids(alone) == ids(noise_free)


def test_same_observations_in_any_order_give_identical_events() -> None:
    observations = [
        obs(float(t), ally=5 - (t % 3), spike="planted" if t > 6 else "not_carried")
        for t in range(10)
    ]
    expected = builder().build(observations)
    for seed in range(5):
        shuffled = copy.deepcopy(observations)
        random.Random(seed).shuffle(shuffled)
        assert builder().build(shuffled) == expected


def test_same_millisecond_observations_get_distinct_deterministic_ids() -> None:
    first, second = obs(5.0, ally=5), obs(5.0, ally=4)
    forward = builder().build([first, second])
    backward = builder().build([second, first])
    assert len(set(ids(forward))) == len(forward)
    assert forward == backward


def test_event_ids_are_unique_within_a_build() -> None:
    events = builder().build([obs(float(t), ally=5 - t % 4, spike="planted") for t in range(20)])
    assert len(set(ids(events))) == len(events)


# --- viewpoint scoping ----------------------------------------------------------------------


@pytest.mark.parametrize("spike", ["carried_by_player", "carried_by_ally", "not_carried"])
def test_spectator_view_player_relative_spike_state_is_not_exposed(spike: str) -> None:
    events = builder().build([obs(5.0, spike=spike, valid=False)])
    assert events  # a state_snapshot is still emitted
    assert all(e["attributes"].get("spike_state", "unknown") == "unknown" for e in events)
    assert not [e for e in events if e["type"] == "objective_state"]


@pytest.mark.parametrize("spike", ["planted", "dropped", "defusing", "resolved"])
def test_spectator_view_keeps_viewpoint_independent_spike_state(spike: str) -> None:
    events = builder().build([obs(5.0, spike=spike, valid=False)])
    assert {e["attributes"]["spike_state"] for e in events} == {spike}


def test_live_player_view_is_unchanged() -> None:
    events = builder().build([obs(5.0, spike="carried_by_player")])
    assert {e["type"] for e in events} == {"state_snapshot", "objective_state"}
    assert all(e["attributes"]["spike_state"] == "carried_by_player" for e in events)


def test_other_players_hp_changes_do_not_create_player_state_events() -> None:
    changes = [obs(1.0, valid=False), obs(2.0, valid=False), obs(3.0, valid=False)]
    changes[1]["values"]["hp"] = 40
    changes[2]["values"]["armor"] = 50
    assert len(builder().build(changes)) == 1


# --- malformed input ------------------------------------------------------------------------


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -1.0, "5", True, None])
def test_invalid_time_is_rejected_not_silently_zeroed(bad: Any) -> None:
    value = obs(5.0)
    value["time_sec"] = bad
    with pytest.raises(DerivedEventInputError):
        builder().build([value])


def test_missing_time_is_rejected() -> None:
    value = obs(5.0)
    del value["time_sec"]
    with pytest.raises(DerivedEventInputError):
        builder().build([value])


def test_observation_without_values_object_is_rejected() -> None:
    value = obs(5.0)
    value["values"] = None
    with pytest.raises(DerivedEventInputError):
        builder().build([value])


@pytest.mark.parametrize("bad", [None, float("nan"), "0.9", True, -0.5])
def test_unusable_hud_confidence_is_treated_as_no_confidence(bad: Any) -> None:
    value = obs(5.0)
    value["quality"]["hud_confidence"] = bad
    assert builder().build([value]) == []


def test_confidence_below_gate_creates_no_event_and_resets_change_detection() -> None:
    events = builder().build([obs(1.0), obs(2.0, confidence=0.5), obs(3.0)])
    assert [e["time_sec"] for e in events if e["type"] == "state_snapshot"] == [1.0, 3.0]


# --- provenance / no invention --------------------------------------------------------------


def test_derived_events_only_use_allowed_types_and_observed_times_and_confidence() -> None:
    observations = [
        obs(1.0, confidence=0.8),
        obs(2.0, ally=4, confidence=0.7),
        obs(3.0, spike="planted"),
    ]
    by_time = {o["time_sec"]: o["quality"]["hud_confidence"] for o in observations}
    events = builder().build(observations)
    assert {e["type"] for e in events} <= {"state_snapshot", "objective_state"}
    for event in events:
        assert event["time_sec"] in by_time
        assert event["confidence"] == by_time[event["time_sec"]]  # propagated unchanged
        assert event["actor"] == "system"
