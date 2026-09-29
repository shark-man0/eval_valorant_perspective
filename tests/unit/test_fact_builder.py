from __future__ import annotations

import json
from pathlib import Path

from valorant_ai_coach.facts import FactBuilder

ROOT = Path(__file__).resolve().parents[2]


def load_case(case_id: str) -> dict:
    path = ROOT / "tests" / "cases" / case_id / "input.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_builder_derives_missing_snapshot_and_event_facts_without_conclusions() -> None:
    package = load_case("TC-006")
    package["deterministic_facts"] = []
    facts = FactBuilder().build(package)
    values = {(fact.key, fact.value) for fact in facts}
    assert ("side", "attack") in values
    assert ("player_role", "controller") in values
    assert ("numbers_state", "even") in values
    assert ("preaim_lead_sec", 0.7) in values
    valid_sources = {"hud", "visual", "event_normalization", "derived_code", "config", "audio"}
    assert all(fact.source in valid_sources for fact in facts)
    serialized = json.dumps([fact.to_dict() for fact in facts], ensure_ascii=False).lower()
    assert all(term not in serialized for term in ("good", "bad", "improve", "unscored"))


def test_enrich_preserves_input_and_does_not_duplicate_existing_facts() -> None:
    package = load_case("TC-003")
    original_count = len(package["deterministic_facts"])
    enriched = FactBuilder().enrich(package)
    assert len(package["deterministic_facts"]) == original_count
    identities = [
        (fact["key"], json.dumps(fact["value"], sort_keys=True), fact.get("time_sec"))
        for fact in enriched["deterministic_facts"]
    ]
    assert len(identities) == len(set(identities))


def test_unknown_spatial_values_are_not_invented() -> None:
    package = load_case("TC-038")
    package["deterministic_facts"] = []
    facts = FactBuilder().build(package)
    keys = {fact.key for fact in facts}
    assert "spatial_context_available" not in keys
    assert "cover_available" not in keys
    assert "escape_route_available" not in keys
    assert "line_of_sight_state" not in keys


def test_generated_ids_do_not_collide_and_observable_context_is_derived() -> None:
    package = load_case("TC-029")
    package["deterministic_facts"] = [
        {
            "fact_id": "FB0001",
            "key": "custom_observation",
            "value": True,
            "time_sec": None,
            "time_range": None,
            "confidence": 1.0,
            "source": "config",
            "provenance_event_ids": [],
        }
    ]
    facts = FactBuilder().build(package)
    assert all(fact.fact_id != "FB0001" for fact in facts)
    values = {(fact.key, fact.value) for fact in facts}
    assert ("first_death_by_player", True) in values
    assert ("clutch_state", False) in values


def test_builder_emits_ultimate_without_agent_metadata() -> None:
    package = load_case("TC-029")
    package["events"].append(
        {
            "event_id": "E-ULT",
            "time_sec": 20.0,
            "type": "ability_state",
            "actor": "player",
            "attributes": {
                "slot": 3,
                "keybind_role": "X",
                "semantic_role": "ultimate",
                "ability_name": None,
                "available": True,
                "charges_remaining": None,
            },
            "confidence": 0.93,
        }
    )

    facts = FactBuilder().build(package)

    ultimate = next(fact for fact in facts if fact.key == "ultimate_available")
    assert ultimate.value is True
    assert ultimate.confidence == 0.93
    assert ultimate.provenance_event_ids == ("E-ULT",)
