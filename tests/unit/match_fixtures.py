"""Synthetic fixtures for the Match aggregation / temporal contract tests.

Everything here is derived from the repository's synthetic ``tests/cases`` Round Packages
(``match_id`` starts with ``MOCK-``) and is *not* real game footage. A Round's time axis is
shifted so several Rounds can sit on one video timeline without overlapping. The
expectations in the tests come from the existing per-case ``expected_assertions.json``
contract, never from a new subjective answer key.
"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from valorant_ai_coach.application import MockCoachAdapter, RoundAnalysis, RoundAnalyzer
from valorant_ai_coach.application.match_aggregation import RoundInput
from valorant_ai_coach.facts import FactBuilder
from valorant_ai_coach.resources import resource_path
from valorant_ai_coach.rules import DeterministicRuleEngine, RuleSelector
from valorant_ai_coach.schema_validation import SchemaValidator

CASES = Path(__file__).resolve().parents[1] / "cases"
RULES_PATH = Path(__file__).resolve().parents[2] / "config" / "valorant_evaluation_rules_v4.json"
REGISTRY_PATH = (
    Path(__file__).resolve().parents[2] / "config" / "rule_trigger_registry_v2.json"
)
MATCH = "M-SYN-001"
ROUND_SPACING_SEC = 200.0

_TIME_KEYS = frozenset({"time_sec", "start_sec", "end_sec"})


def rules_config() -> dict[str, Any]:
    return json.loads(RULES_PATH.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def registry() -> dict[str, Any]:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def make_analyzer() -> RoundAnalyzer:
    return RoundAnalyzer(
        fact_builder=FactBuilder(),
        selector=RuleSelector(resource_path("config/rule_trigger_registry_v2.json")),
        rule_engine=DeterministicRuleEngine(),
        coach=MockCoachAdapter(),
        validator=SchemaValidator(),
    )


def load_case(case_id: str) -> dict[str, Any]:
    return json.loads((CASES / case_id / "input.json").read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def expected_pairs(case_id: str) -> list[tuple[str, str]]:
    """(rule_id, label) pairs the existing per-case contract expects."""
    path = CASES / case_id / "expected_assertions.json"
    expected = json.loads(path.read_text(encoding="utf-8"))
    return sorted((e["primary_rule_id"], e["label"]) for e in expected["expected_evaluations"])


def _shift(value: Any, offset: float) -> Any:
    if isinstance(value, dict):
        return {
            key: (
                item + offset
                if key in _TIME_KEYS
                and isinstance(item, int | float)
                and not isinstance(item, bool)
                else _shift(item, offset)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_shift(item, offset) for item in value]
    return value


def case_package(
    case_id: str, *, match_id: str = MATCH, round_no: int = 1, offset: float | None = None
) -> dict[str, Any]:
    """A synthetic Round Package placed at ``round_no`` on a shared video timeline."""
    package = load_case(case_id)
    shift = (round_no - 1) * ROUND_SPACING_SEC if offset is None else offset
    package = _shift(package, shift)
    package["match_id"] = match_id
    package["round_no"] = round_no
    package["source_video"]["duration_sec"] = float(package["source_video"]["duration_sec"]) + shift
    return package  # type: ignore[no-any-return]


def lowered_confidence(package: dict[str, Any], confidence: float = 0.3) -> dict[str, Any]:
    """Same Round with every fact confidence lowered (lowering is always contract-safe)."""
    value = deepcopy(package)
    for fact in value["deterministic_facts"]:
        fact["confidence"] = min(float(fact["confidence"]), confidence)
    return value


def analyze(package: dict[str, Any]) -> RoundAnalysis:
    return make_analyzer().analyze(package)


def analysis_for(
    case_id: str, *, match_id: str = MATCH, round_no: int = 1, offset: float | None = None
) -> RoundAnalysis:
    return analyze(case_package(case_id, match_id=match_id, round_no=round_no, offset=offset))


def round_input(
    case_id: str, *, match_id: str = MATCH, round_no: int = 1, offset: float | None = None
) -> RoundInput:
    return RoundInput.from_round_analysis(
        analysis_for(case_id, match_id=match_id, round_no=round_no, offset=offset)
    )


def three_round_match() -> list[RoundInput]:
    """R1 AIM-02 good, R2 AIM-03(+MOV-02) improve, R3 PEEK-02 unscored."""
    return [
        round_input("TC-006", round_no=1),
        round_input("TC-017", round_no=2),
        round_input("TC-026", round_no=3),
    ]
