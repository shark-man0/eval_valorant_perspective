"""Downstream (non-vision) contract tests.

All inputs here are synthetic fixtures that exercise the Round Package -> Fact ->
Rule -> Coach seams. They are NOT production outputs and must never be used to
tune or backfill Vision behaviour.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from valorant_ai_coach.application import MockCoachAdapter, RoundAnalyzer
from valorant_ai_coach.facts import FactBuilder
from valorant_ai_coach.resources import resource_path
from valorant_ai_coach.rounds import RoundPackageBuilder
from valorant_ai_coach.rules import DeterministicRuleEngine, RuleSelector
from valorant_ai_coach.schema_validation import SchemaValidator

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


# --- One fact driving several deterministic rules (MOV-02 / AIM-03) -----------------------

CASES = Path(__file__).resolve().parents[1] / "cases"


def make_analyzer() -> RoundAnalyzer:
    return RoundAnalyzer(
        fact_builder=FactBuilder(),
        selector=RuleSelector(resource_path("config/rule_trigger_registry_v2.json")),
        rule_engine=DeterministicRuleEngine(),
        coach=MockCoachAdapter(),
        validator=SchemaValidator(),
    )


def load_case(case_id: str) -> dict[str, Any]:
    return json.loads((CASES / case_id / "input.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize(("case_id", "label"), [("TC-005", "good"), ("TC-017", "improve")])
def test_shared_fact_rules_are_both_represented_in_one_merged_evaluation(
    case_id: str, label: str
) -> None:
    result = make_analyzer().analyze(load_case(case_id))
    assert set(result.deterministic_decisions) == {"MOV-02", "AIM-03"}
    (evaluation,) = result.output["evaluations"]
    assert evaluation["primary_rule_id"] == "AIM-03"  # dedup_groups.movement_shooting order
    assert evaluation["related_rule_ids"] == ["MOV-02"]
    assert evaluation["label"] == label
    assert evaluation["decision_source"] == "deterministic"
    assert evaluation["display_clip"] is not None


@pytest.mark.parametrize("path", sorted(CASES.glob("TC-*/input.json")), ids=lambda p: p.parent.name)
def test_every_fixture_case_passes_round_analyzer_with_mock_coach(path: Path) -> None:
    expected = json.loads(path.with_name("expected_assertions.json").read_text(encoding="utf-8"))
    result = make_analyzer().analyze(json.loads(path.read_text(encoding="utf-8")))
    actual = sorted((e["primary_rule_id"], e["label"]) for e in result.output["evaluations"])
    wanted = sorted((e["primary_rule_id"], e["label"]) for e in expected["expected_evaluations"])
    assert actual == wanted


# --- Low confidence must surface as an explicit `unscored`, never as silence --------------

LOW_CONFIDENCE_RULES = (
    ("AIM-02", "preaim_lead_sec", 0.7),
    ("AIM-03", "first_shot_stationary", False),
    ("MOV-02", "first_shot_stationary", True),
    ("PEEK-04", "exposed_directions_count", 3),
)


def _fact(key: str, value: object, confidence: float, fact_id: str = "F1") -> dict[str, Any]:
    return {
        "fact_id": fact_id,
        "key": key,
        "value": value,
        "confidence": confidence,
        "source": "derived_code",
    }


@pytest.mark.parametrize(("rule_id", "key", "value"), LOW_CONFIDENCE_RULES)
def test_engine_low_confidence_fact_is_explicit_unscored_with_provenance(
    rule_id: str, key: str, value: object
) -> None:
    decision = DeterministicRuleEngine().evaluate(rule_id, [_fact(key, value, 0.4)], [])
    assert decision is not None
    assert decision.label == "unscored"
    assert decision.unscored_reason_code == "low_confidence"
    assert decision.fact_refs == ("F1",)
    assert decision.missing_information
    assert decision.confidence <= 0.5


@pytest.mark.parametrize(("rule_id", "key", "value"), LOW_CONFIDENCE_RULES)
def test_engine_does_not_invent_unscored_when_fact_is_absent(
    rule_id: str, key: str, value: object
) -> None:
    assert DeterministicRuleEngine().evaluate(rule_id, [], []) is None


def test_engine_confident_fact_wins_over_low_confidence_sibling() -> None:
    facts = [_fact("preaim_lead_sec", 0.7, 0.98, "F1"), _fact("preaim_lead_sec", 0.1, 0.2, "F2")]
    decision = DeterministicRuleEngine().evaluate("AIM-02", facts, [])
    assert decision is not None and decision.label == "good"
    assert decision.fact_refs == ("F1",)


def test_smoke_exception_stays_not_evaluated_even_when_confidence_is_low() -> None:
    fact = {**_fact("first_shot_stationary", True, 0.4), "provenance_event_ids": ["shot-1"]}
    shot = {"event_id": "shot-1", "type": "shot", "attributes": {"purpose": "smoke penetration"}}
    assert DeterministicRuleEngine().evaluate("MOV-02", [fact], [shot]) is None


def test_round_analysis_low_confidence_facts_yield_unscored_evaluations() -> None:
    package = load_case("TC-006")
    for item in package["deterministic_facts"]:
        item["confidence"] = 0.3
    result = make_analyzer().analyze(package)
    by_rule = {e["primary_rule_id"]: e for e in result.output["evaluations"]}
    evaluation = by_rule["AIM-02"]
    assert evaluation["label"] == "unscored"
    assert evaluation["unscored_reason_code"] == "low_confidence"
    assert evaluation["missing_information"]
    assert evaluation["display_clip"] is None and evaluation["clip_id"] is None
    assert evaluation["improvement"] is None
    assert evaluation["confidence"] <= 0.5
    assert evaluation["fact_refs"]  # provenance is preserved
    assert result.deterministic_decisions["AIM-02"]["label"] == "unscored"


def test_round_analysis_fact_confidence_is_not_raised_by_the_pipeline() -> None:
    package = load_case("TC-006")
    result = make_analyzer().analyze(package)
    before = {f["fact_id"]: f["confidence"] for f in package["deterministic_facts"]}
    after = {f["fact_id"]: f["confidence"] for f in result.round_package["deterministic_facts"]}
    refs = result.deterministic_decisions["AIM-02"]["fact_refs"]
    assert refs
    for ref in refs:
        assert after[ref] == before[ref]


# --- Config / code agreement for the confidence policy -------------------------------------


def _rules_config() -> dict[str, Any]:
    path = Path(__file__).resolve().parents[2] / "config" / "valorant_evaluation_rules_v4.json"
    return json.loads(path.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def test_config_confidence_thresholds_match_the_values_hardcoded_in_code() -> None:
    policy = _rules_config()["confidence_policy"]
    assert policy["display_review_min"] == 0.55
    assert policy["display_normal_min"] == 0.75


@pytest.mark.parametrize(
    ("confidence", "expected"),
    [(0.549, "unscored"), (0.55, "improve"), (0.9, "improve")],
)
def test_pipeline_demotes_scored_labels_below_review_minimum(
    confidence: float, expected: str
) -> None:
    from valorant_ai_coach.application.pipeline import MatchAnalysisPipeline

    evaluation = {
        "label": "improve",
        "confidence": confidence,
        "clip_id": "c1",
        "display_clip": {"clip_id": "c1"},
        "improvement": "x",
        "missing_information": [],
    }
    result = MatchAnalysisPipeline._enforce_confidence_policy(evaluation)
    assert result["label"] == expected
    if expected == "unscored":
        assert result["unscored_reason_code"] == "low_confidence"
        assert result["clip_id"] is None and result["improvement"] is None
        assert result["missing_information"]
    assert evaluation["label"] == "improve"  # input is not mutated
