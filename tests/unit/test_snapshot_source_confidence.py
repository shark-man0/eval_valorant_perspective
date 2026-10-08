"""Snapshot-derived facts take their confidence from the source observation.

Synthetic fixtures: they test the confidence-provenance contract, not Vision output.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import math
from pathlib import Path
from typing import Any

import pytest

from valorant_ai_coach.events import EventSourceContract
from valorant_ai_coach.facts import FactBuilder
from valorant_ai_coach.resources import resource_path
from valorant_ai_coach.rounds import RoundPackageBuilder
from valorant_ai_coach.rules import DeterministicRuleEngine
from valorant_ai_coach.schema_validation import ContractValidationError, SchemaValidator
from valorant_ai_coach.video import VideoMetadata
from valorant_ai_coach.visual.models import VisualObservation

ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT_KEYS = {
    "numbers_state",
    "clutch_state",
    "weapon",
    "spike_carried_by_player",
    "spike_planted",
    "round_time_remaining_sec",
    "utility_available_count",
    "spatial_context_available",
    "cover_available",
    "escape_route_available",
    "exposed_directions_count",
}
FIELDS = (
    "ally_alive",
    "enemy_alive",
    "weapon",
    "spike_state",
    "round_time_remaining_sec",
    "utility_available_count",
    "spatial_context",
)


def snapshot(source: dict[str, Any] | None) -> dict[str, Any]:
    value: dict[str, Any] = {
        "time_sec": 10.0,
        "ally_alive": 4,
        "enemy_alive": 5,
        "hp": 100,
        "armor": 50,
        "weapon": "Vandal",
        "spike_state": "carried_by_player",
        "round_time_remaining_sec": 80.0,
        "utility_available_count": 2,
        "player_location": {"zone_id": None, "zone_name": None},
        "known_enemy_locations": [],
        "spatial_context": {
            "cover_available": True,
            "escape_route_available": False,
            "line_of_sight_state": "unknown",
            "exposed_directions_count": 3,
            "view_target_zone_id": None,
        },
    }
    if source is not None:
        value["source_confidence"] = source
    return value


def package(source: dict[str, Any] | None, *, aggregate: float = 0.99) -> dict[str, Any]:
    case = json.loads((ROOT / "tests" / "cases" / "TC-006" / "input.json").read_text("utf-8"))
    case["events"] = []
    case["deterministic_facts"] = []
    case["state_snapshots"] = [snapshot(source)]
    case["observation_quality"]["hud_confidence"] = aggregate
    case["observation_quality"]["visual_confidence"] = aggregate
    SchemaValidator().validate_round_package(case)
    return case


def uniform(confidence: float) -> dict[str, Any]:
    return {field: confidence for field in FIELDS}


def snapshot_facts(
    source: dict[str, Any] | None, *, aggregate: float = 0.99
) -> list[dict[str, Any]]:
    enriched = FactBuilder().enrich(package(source, aggregate=aggregate))
    return [f for f in enriched["deterministic_facts"] if f["key"] in SNAPSHOT_KEYS]


# --- the four required regressions ---------------------------------------------------------


@pytest.mark.parametrize("source", [0.0, 0.30, 0.65])
def test_source_065_or_lower_never_yields_a_fact_at_the_gate(source: float) -> None:
    facts = snapshot_facts(uniform(source), aggregate=0.99)
    assert facts
    assert all(f["confidence"] == pytest.approx(source) for f in facts)
    assert all(f["confidence"] < 0.90 for f in facts)


def test_source_089_does_not_pass_the_deterministic_gate() -> None:
    enriched = FactBuilder().enrich(package(uniform(0.89), aggregate=0.99))
    decision = DeterministicRuleEngine().evaluate(
        "PEEK-04", enriched["deterministic_facts"], enriched["events"]
    )
    assert decision is not None
    assert decision.label == "unscored"
    assert decision.unscored_reason_code == "low_confidence"


def test_source_095_passes_the_gate_when_other_conditions_hold() -> None:
    enriched = FactBuilder().enrich(package(uniform(0.95), aggregate=0.30))
    decision = DeterministicRuleEngine().evaluate(
        "PEEK-04", enriched["deterministic_facts"], enriched["events"]
    )
    assert decision is not None
    assert decision.label == "improve"
    assert decision.decision_source == "deterministic"
    assert decision.confidence == pytest.approx(0.95)


@pytest.mark.parametrize(("source", "aggregate"), [(0.65, 0.99), (0.95, 0.30), (0.89, 1.0)])
def test_package_aggregate_never_overrides_the_source_confidence(
    source: float, aggregate: float
) -> None:
    facts = snapshot_facts(uniform(source), aggregate=aggregate)
    assert all(f["confidence"] == pytest.approx(source) for f in facts)


# --- missing / malformed source confidence -------------------------------------------------


def test_snapshot_without_source_confidence_gets_no_confidence_not_the_aggregate() -> None:
    facts = snapshot_facts(None, aggregate=0.99)
    assert facts and all(f["confidence"] == 0.0 for f in facts)
    enriched = FactBuilder().enrich(package(None, aggregate=0.99))
    decision = DeterministicRuleEngine().evaluate(
        "PEEK-04", enriched["deterministic_facts"], enriched["events"]
    )
    assert decision is not None and decision.label == "unscored"


def test_a_field_missing_from_source_confidence_has_no_confidence() -> None:
    source = uniform(0.95)
    del source["spike_state"]
    by_key = {f["key"]: f["confidence"] for f in snapshot_facts(source)}
    assert by_key["spike_carried_by_player"] == 0.0
    assert by_key["spike_planted"] == 0.0
    assert by_key["weapon"] == pytest.approx(0.95)


def test_fields_keep_their_own_confidence_and_combined_facts_use_the_minimum() -> None:
    source = {**uniform(0.95), "enemy_alive": 0.70, "weapon": 0.91}
    by_key = {f["key"]: f["confidence"] for f in snapshot_facts(source)}
    assert by_key["numbers_state"] == pytest.approx(0.70)
    assert by_key["clutch_state"] == pytest.approx(0.70)
    assert by_key["weapon"] == pytest.approx(0.91)
    assert by_key["utility_available_count"] == pytest.approx(0.95)


@pytest.mark.parametrize("bad", [True, "0.95", None, math.nan, -0.1, 1.5, math.inf])
def test_unusable_source_confidence_value_counts_as_zero_in_fact_builder(bad: Any) -> None:
    # Bypasses schema validation on purpose: the builder must be safe on its own.
    value = package(uniform(0.95))
    value["state_snapshots"][0]["source_confidence"]["weapon"] = bad
    weapon = [
        f for f in FactBuilder().enrich(value)["deterministic_facts"] if f["key"] == "weapon"
    ]
    assert weapon and weapon[0]["confidence"] == 0.0


@pytest.mark.parametrize(
    "bad",
    [
        {"weapon": 1.5},
        {"weapon": -0.1},
        {"weapon": True},
        {"weapon": "0.9"},
        {"unknown_field": 0.5},
    ],
)
def test_schema_rejects_malformed_source_confidence(bad: dict[str, Any]) -> None:
    value = package(uniform(0.95))
    value["state_snapshots"][0]["source_confidence"] = bad
    with pytest.raises(ContractValidationError):
        SchemaValidator().validate_round_package(value)


def test_legacy_snapshot_without_the_field_still_validates() -> None:
    SchemaValidator().validate_round_package(package(None))


# --- production path: RoundPackageBuilder ---------------------------------------------------


def hud_observation(
    time_sec: float, confidence: float, *, timer: float | None = None, ally: int = 5
) -> dict[str, Any]:
    roi = {} if timer is None else {"round_timer_value": timer}
    return {
        "schema_version": "2.0",
        "time_sec": time_sec,
        "frame_index": round(time_sec * 60),
        "primary_state": "live_first_person",
        "state_flags": [],
        "view_context": {"remote_view_type": "none", "is_player_world_view_trustworthy": True},
        "values": {
            "round_time_remaining_sec": max(0.0, 100.0 - time_sec),
            "score_ally": 1,
            "score_enemy": 2,
            "ally_alive": ally,
            "enemy_alive": 5,
            "hp": 100,
            "armor": 50,
            "ammo_current": 25,
            "ammo_reserve": 50,
            "weapon_text": None,
            "spike_state": "not_carried",
            "location_text": None,
            "kill_feed_rows": [],
            "ability_slots": [],
            "combat_report_visible": False,
            "buy_phase_visible": False,
            "round_end_text": None,
            "zone_id": None,
            "player_specific_hud_valid": True,
        },
        "quality": {
            "hud_confidence": confidence,
            "visual_confidence": 0.0,
            "occluded_rois": [],
            "notes": [],
            "state_confidence": confidence,
            "roi_confidence": roi,
        },
    }


def build(
    tmp_path: Path,
    observations: list[dict[str, Any]],
    visuals: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    end = observations[-1]["time_sec"] + 1
    contract = EventSourceContract.load(resource_path("config/event_source_contract_v1.json"))
    builder = RoundPackageBuilder(contract=contract, validator=SchemaValidator())
    events = [
        {
            "event_id": kind,
            "type": kind,
            "time_sec": t,
            "actor": "system",
            "attributes": {},
            "confidence": 0.99,
        }
        for kind, t in (("round_start", 0.0), ("round_end", end - 0.5))
    ]
    return builder.build(
        match_id="m",
        video_metadata=VideoMetadata(
            tmp_path / "m.mp4", end, 1920, 1080, 60, "h264", None, False, 0
        ),
        hud_observations=observations,
        hud_events=events,
        visual_observations=visuals or [],
    )[0]


def test_builder_records_each_snapshots_own_observation_confidence(tmp_path: Path) -> None:
    confidences = [0.70, 0.99, 0.65, 0.93, 0.80]
    observations = [
        hud_observation(1.0 + i, c, timer=c, ally=5 - i) for i, c in enumerate(confidences)
    ]
    result = build(tmp_path, observations)
    by_time = {o["time_sec"]: o["quality"]["hud_confidence"] for o in observations}
    assert len({s["source_confidence"]["ally_alive"] for s in result["state_snapshots"]}) > 1
    for snap in result["state_snapshots"]:
        origin = by_time[snap["time_sec"]]
        assert snap["source_confidence"]["ally_alive"] == pytest.approx(origin)
        assert snap["source_confidence"]["enemy_alive"] == pytest.approx(origin)
        assert snap["source_confidence"]["round_time_remaining_sec"] == pytest.approx(origin)
    for fact in FactBuilder().enrich(result)["deterministic_facts"]:
        if fact["key"] in SNAPSHOT_KEYS and fact.get("time_sec") in by_time:
            assert fact["confidence"] <= by_time[fact["time_sec"]] + 1e-9


def test_round_timer_confidence_comes_only_from_the_reserved_value_score(
    tmp_path: Path,
) -> None:
    result = build(tmp_path, [hud_observation(1.0, 0.95), hud_observation(2.0, 0.95, ally=4)])
    for snap in result["state_snapshots"]:
        assert snap["source_confidence"]["round_time_remaining_sec"] == 0.0
        assert snap["source_confidence"]["ally_alive"] == pytest.approx(0.95)
    higher = build(tmp_path, [hud_observation(1.0, 0.70, timer=0.97)])
    assert higher["state_snapshots"][0]["source_confidence"]["round_time_remaining_sec"] == 0.97
    assert higher["state_snapshots"][0]["source_confidence"]["ally_alive"] == pytest.approx(0.70)


def spatial_visual(time_sec: float, spatial_conf: float, visual_conf: float) -> dict[str, Any]:
    raw = VisualObservation.from_mapping(
        {
            "time_sec": time_sec,
            "hud_primary_state": "live_first_person",
            "analysis_eligibility": {"player_mechanics": True},
            "spatial": {
                "cover_available": True,
                "escape_route_available": False,
                "exposed_directions_count": 3,
                "exposed_directions_source": "static_peek_registry",
                "confidence": spatial_conf,
            },
            "quality": {"visual_confidence": visual_conf, "occluded": False},
        }
    ).to_dict()
    return copy.deepcopy(raw)


@pytest.mark.parametrize(
    ("spatial_conf", "visual_conf", "expected"), [(0.95, 0.90, 0.90), (0.90, 0.99, 0.90)]
)
def test_spatial_source_confidence_is_the_minimum_of_its_two_visual_sources(
    tmp_path: Path, spatial_conf: float, visual_conf: float, expected: float
) -> None:
    observations = [hud_observation(1.0 + i * 0.25, 0.99) for i in range(5)]
    result = build(tmp_path, observations, [spatial_visual(2.0, spatial_conf, visual_conf)])
    merged = [s for s in result["state_snapshots"] if "spatial_context" in s["source_confidence"]]
    assert merged
    assert all(s["source_confidence"]["spatial_context"] == pytest.approx(expected) for s in merged)
    facts = FactBuilder().enrich(result)["deterministic_facts"]
    exposed = [f for f in facts if f["key"] == "exposed_directions_count"]
    assert exposed and all(f["confidence"] == pytest.approx(expected) for f in exposed)


def test_low_visual_source_blocks_the_deterministic_peek_gate_end_to_end(tmp_path: Path) -> None:
    observations = [hud_observation(1.0 + i * 0.25, 0.99) for i in range(5)]
    result = build(tmp_path, observations, [spatial_visual(2.0, 0.95, 0.88)])
    enriched = FactBuilder().enrich(result)
    decision = DeterministicRuleEngine().evaluate(
        "PEEK-04", enriched["deterministic_facts"], enriched["events"]
    )
    assert decision is not None and decision.label == "unscored"


# --- the measured property, on the production path -----------------------------------------


def test_measurement_population_has_no_overstated_snapshot_fact() -> None:
    path = ROOT / "scripts" / "measure_snapshot_fact_confidence.py"
    spec = importlib.util.spec_from_file_location("measure_snapshot_fact_confidence", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    import random

    contract = EventSourceContract.load(resource_path("config/event_source_contract_v1.json"))
    builder = RoundPackageBuilder(contract=contract, validator=SchemaValidator())
    for draw in module.SCENARIOS.values():
        for seed in range(2):
            result = module.measure_package(builder, random.Random(seed), draw)
            assert result["facts"] > 0
            assert result["over"] == 0
            assert result["under"] == 0
            assert result["raised"] == 0
