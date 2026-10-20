"""A scoped episode cannot prove elimination ordering across the round."""
from copy import deepcopy

import pytest

from tests.unit.test_fact_builder import load_case
from valorant_ai_coach.facts import FactBuilder


@pytest.mark.parametrize("earlier_kill", [False, True])
def test_self_death_only_retains_death_without_elimination_order(earlier_kill):
    package = load_case("TC-029")
    death = next(e for e in package["events"] if e["type"] == "player_death")
    death["attributes"]["evidence_provenance"] = {"elimination_coverage": "self_death_only"}
    package["events"] = [death]
    if earlier_kill:
        package["events"].insert(0, {
            "event_id": "earlier-kill", "type": "kill", "actor": "player",
            "time_sec": death["time_sec"] - 1, "confidence": .9, "attributes": {},
        })
    package["deterministic_facts"] = []
    before = deepcopy(package)
    facts = FactBuilder().build(package)
    died = next(f for f in facts if f.key == "player_died")
    assert died.value is True and died.confidence == death["confidence"]
    assert died.time_sec == death["time_sec"]
    assert died.provenance_event_ids == (death["event_id"],)
    assert not any(f.key == "first_death_by_player" for f in facts)
    assert package == before


@pytest.mark.parametrize("proof", [None, {}, "self_death_only", {"other": "self_death_only"}])
def test_unscoped_legacy_events_keep_existing_fact_contract(proof):
    package = load_case("TC-029")
    death = next(e for e in package["events"] if e["type"] == "player_death")
    death["attributes"]["evidence_provenance"] = proof
    package["events"] = [death]
    package["deterministic_facts"] = []
    first = next(f for f in FactBuilder().build(package) if f.key == "first_death_by_player")
    assert first.value is True
    assert first.confidence == min(death["confidence"], .9)
