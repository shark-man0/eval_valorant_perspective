"""Recover scope safety without importing an experimental event producer."""
import json
from types import SimpleNamespace

from tests.e2e.trace_adapter import to_e2e_trace
from tests.unit.test_fact_builder import load_case
from valorant_ai_coach.facts import FactBuilder
from valorant_ai_coach.schema_validation import SchemaValidator
from valorant_ai_coach.storage.repository import SQLiteRepository


def test_scoped_event_survives_trace_and_sqlite_without_inferred_first_death(tmp_path):
    package = load_case("TC-029")
    death = next(e for e in package["events"] if e["type"] == "player_death")
    death["attributes"]["evidence_provenance"] = {"elimination_coverage": "self_death_only"}
    package["events"] = [death]
    # This integration isolates the event path; no synthetic HUD ownership is added.
    package["state_snapshots"] = []
    package["deterministic_facts"] = []
    enriched = FactBuilder().enrich(package)
    SchemaValidator().validate_round_package(enriched)
    assert not any(f["key"] == "first_death_by_player" for f in enriched["deterministic_facts"])
    trace = to_e2e_trace(SimpleNamespace(round_packages=[enriched]))
    event = next(e for e in trace["events"] if e["type"] == "player_death")
    for field in ("type", "time_sec", "actor", "confidence", "attributes"):
        assert event[field] == death[field]
    store = SQLiteRepository(tmp_path / "safety.sqlite")
    store.save_round_package(enriched)
    saved = store.get_round_package(package["match_id"], package["round_no"])
    assert json.loads(json.dumps(saved)) == json.loads(json.dumps(enriched))
    assert FactBuilder().enrich(saved)["deterministic_facts"] == enriched["deterministic_facts"]
