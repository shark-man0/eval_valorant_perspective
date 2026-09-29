from __future__ import annotations

import json
from pathlib import Path

import pytest

from valorant_ai_coach.application import MockCoachAdapter, RoundAnalyzer
from valorant_ai_coach.facts import FactBuilder
from valorant_ai_coach.resources import resource_path
from valorant_ai_coach.rules import DeterministicRuleEngine, RuleSelector
from valorant_ai_coach.schema_validation import ContractValidationError, SchemaValidator

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def analyzer() -> RoundAnalyzer:
    return RoundAnalyzer(
        fact_builder=FactBuilder(),
        selector=RuleSelector(resource_path("config/rule_trigger_registry_v2.json")),
        rule_engine=DeterministicRuleEngine(),
        coach=MockCoachAdapter(),
        validator=SchemaValidator(),
    )


def load_case(case_id: str) -> dict[str, object]:
    path = ROOT / "tests" / "cases" / case_id / "input.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_good_and_improve_can_coexist_in_one_round(analyzer: RoundAnalyzer) -> None:
    result = analyzer.analyze(load_case("TC-029"))
    assert [(item["primary_rule_id"], item["label"]) for item in result.output["evaluations"]] == [
        ("AIM-02", "good"),
        ("DEC-01", "improve"),
    ]
    assert result.deterministic_decisions["AIM-02"]["label"] == "good"


def test_normal_round_has_no_candidates_or_evaluations(analyzer: RoundAnalyzer) -> None:
    result = analyzer.analyze(load_case("TC-037"))
    assert result.candidates == ()
    assert result.output["evaluations"] == []


def test_missing_required_fact_becomes_unscored_not_excluded(
    analyzer: RoundAnalyzer,
) -> None:
    result = analyzer.analyze(load_case("TC-025"))
    assert "INFO-03" in {candidate.rule_id for candidate in result.candidates}
    evaluation = result.output["evaluations"][0]
    assert evaluation["label"] == "unscored"
    assert evaluation["display_clip"] is None
    assert evaluation["missing_information"]


@pytest.mark.parametrize(
    ("case_id", "forbidden"),
    [("TC-031", "ROLE-06"), ("TC-036", "ROLE-02")],
)
def test_role_mismatch_is_not_a_candidate(
    analyzer: RoundAnalyzer, case_id: str, forbidden: str
) -> None:
    result = analyzer.analyze(load_case(case_id))
    assert forbidden not in {candidate.rule_id for candidate in result.candidates}


def test_round_boundary_rejects_coach_that_overrides_deterministic_label() -> None:
    mock = MockCoachAdapter()

    class ConflictingCoach:
        @staticmethod
        def evaluate(*args: object, **kwargs: object) -> dict[str, object]:
            value = mock.evaluate(*args, **kwargs)  # type: ignore[arg-type]
            evaluation = value["evaluations"][0]
            evaluation["label"] = "improve"
            evaluation["improvement"] = "決定論的基準と異なる出力"
            return value

    value = RoundAnalyzer(
        fact_builder=FactBuilder(),
        selector=RuleSelector(resource_path("config/rule_trigger_registry_v2.json")),
        rule_engine=DeterministicRuleEngine(),
        coach=ConflictingCoach(),  # type: ignore[arg-type]
        validator=SchemaValidator(),
    )
    with pytest.raises(ContractValidationError, match="決定論的判定と一致"):
        value.analyze(load_case("TC-006"))
