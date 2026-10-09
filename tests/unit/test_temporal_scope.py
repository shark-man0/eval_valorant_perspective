"""Analysis-scope ("what the AI looks at") contract tests.

Synthetic fixtures derived from TC-006; they test the scope contract only.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from threading import Event
from typing import Any

import pytest

from valorant_ai_coach.application import RoundAnalyzer
from valorant_ai_coach.facts import FactBuilder
from valorant_ai_coach.models import RuleCandidate
from valorant_ai_coach.resources import resource_path
from valorant_ai_coach.rules import DeterministicRuleEngine, RuleSelector, TemporalScopeResolver
from valorant_ai_coach.rules.temporal_scope import (
    AnalysisScope,
    scope_round_package,
    validate_output_scope,
)
from valorant_ai_coach.schema_validation import ContractValidationError, SchemaValidator

CASES = Path(__file__).resolve().parents[1] / "cases"


def base_package() -> dict[str, Any]:
    package = json.loads((CASES / "TC-006" / "input.json").read_text(encoding="utf-8"))
    package["events"].append(
        {
            "event_id": "FAR-1",
            "time_sec": 80.0,
            "type": "peek",
            "actor": "player",
            "attributes": {},
            "confidence": 0.9,
        }
    )
    package["frames"] = [
        {"time_sec": 30.0, "path": "near.jpg", "purpose": "hud_evidence"},
        {"time_sec": 80.0, "path": "far.jpg", "purpose": "hud_evidence"},
    ]
    return package


def candidate(rule_id: str, level: str, matched: tuple[str, ...] = ()) -> RuleCandidate:
    return RuleCandidate(rule_id, "important", level, "deterministic", matched_event_types=matched)


def test_micro_rule_window_is_built_around_every_trigger_event() -> None:
    scope = TemporalScopeResolver().resolve(
        candidate("AIM-02", "micro", ("preaim_started", "peek")), base_package()
    )
    assert not scope.whole_round
    # preaim_started@30 and peek@30.7 overlap; peek@80 is a separate pivot only if matched.
    assert scope.windows[0] == (24.0, 34.7)
    assert scope.windows[-1] == (74.0, 84.0)  # FAR-1 is also a "peek"


def test_window_is_clamped_to_the_round_window() -> None:
    package = base_package()
    package["round_window"] = {"start_sec": 28.0, "end_sec": 31.0}
    package["events"] = [e for e in package["events"] if e["time_sec"] <= 31]
    pivot = candidate("AIM-02", "micro", ("preaim_started",))
    scope = TemporalScopeResolver().resolve(pivot, package)
    assert scope.windows == ((28.0, 31.0),)


@pytest.mark.parametrize(
    ("rule_id", "level"),
    [("AIM-01", "match"), ("PEEK-01", "round"), ("POS-04", "phase"), ("ECO-01", "cross_round")],
)
def test_round_phase_match_and_cross_round_levels_use_the_whole_round(
    rule_id: str, level: str
) -> None:
    scope = TemporalScopeResolver().resolve(candidate(rule_id, level, ("peek",)), base_package())
    assert scope.whole_round and scope.windows == ()


def test_windowed_rule_without_a_pivot_event_falls_back_to_the_whole_round() -> None:
    scope = TemporalScopeResolver().resolve(candidate("AIM-02", "micro", ()), base_package())
    assert scope.whole_round


@pytest.mark.parametrize("rule_id", ["ECO-01", "ECO-02", "ADV-07"])
def test_cross_round_rule_reports_missing_previous_round_context(rule_id: str) -> None:
    package = base_package()
    package["previous_round_context"] = None
    scope = TemporalScopeResolver().resolve(candidate(rule_id, "cross_round"), package)
    assert scope.missing_context == ("previous_round_context",)
    package["previous_round_context"] = {
        "round_no": 4,
        "result": "loss",
        "economy": {"player_credits_end": 900, "next_round_team_buy": "full_buy"},
    }
    resolved = TemporalScopeResolver().resolve(candidate(rule_id, "cross_round"), package)
    assert resolved.missing_context == ()


def test_scope_is_deterministic_for_the_same_input() -> None:
    resolver = TemporalScopeResolver()
    first = resolver.resolve(candidate("AIM-02", "micro", ("peek",)), base_package())
    second = resolver.resolve(candidate("AIM-02", "micro", ("peek",)), base_package())
    assert first == second


def narrow(package: dict[str, Any]) -> AnalysisScope:
    return AnalysisScope("AIM-02", "micro", ((24.0, 34.7),), whole_round=False)


def test_scoped_package_drops_outside_observations_and_adds_nothing() -> None:
    package = FactBuilder().enrich(base_package())
    scoped, kept = scope_round_package(package, [narrow(package)])
    assert kept == [0]
    assert [f["path"] for f in scoped["frames"]] == ["near.jpg"]
    assert all(24.0 <= e["time_sec"] <= 34.7 for e in scoped["events"])
    assert "FAR-1" not in {e["event_id"] for e in scoped["events"]}
    for key in ("events", "state_snapshots", "deterministic_facts", "frames"):
        original = {json.dumps(item, sort_keys=True) for item in package[key]}
        assert {json.dumps(item, sort_keys=True) for item in scoped[key]} <= original
    SchemaValidator().validate_round_package(scoped)  # provenance still resolves


def test_scoped_package_keeps_facts_a_decision_depends_on() -> None:
    package = FactBuilder().enrich(base_package())
    far_fact = {
        "fact_id": "FAR-F",
        "key": "x",
        "value": 1,
        "time_sec": 80.0,
        "time_range": None,
        "confidence": 0.9,
        "source": "derived_code",
        "provenance_event_ids": [],
    }
    package["deterministic_facts"].append(far_fact)
    dropped, _ = scope_round_package(package, [narrow(package)])
    assert "FAR-F" not in {f["fact_id"] for f in dropped["deterministic_facts"]}
    kept, _ = scope_round_package(package, [narrow(package)], keep_fact_ids={"FAR-F"})
    assert "FAR-F" in {f["fact_id"] for f in kept["deterministic_facts"]}


def test_any_whole_round_scope_disables_narrowing() -> None:
    package = FactBuilder().enrich(base_package())
    whole = AnalysisScope("PEEK-01", "round")
    scoped, kept = scope_round_package(package, [narrow(package), whole])
    assert kept == [0, 1]
    assert scoped["events"] == package["events"]


def evaluation(
    label: str, start: float | None, end: float | None, primary: str = "AIM-02"
) -> dict[str, Any]:
    return {
        "evaluation_id": "e1",
        "primary_rule_id": primary,
        "related_rule_ids": [],
        "label": label,
        "evidence_range": None if start is None else {"start_sec": start, "end_sec": end},
    }


def test_scored_evidence_outside_the_analysis_window_is_rejected() -> None:
    scopes = {"AIM-02": narrow({})}
    validate_output_scope({"evaluations": [evaluation("good", 29.0, 31.0)]}, scopes)
    with pytest.raises(ContractValidationError, match="分析範囲外"):
        validate_output_scope({"evaluations": [evaluation("good", 79.0, 81.0)]}, scopes)
    with pytest.raises(ContractValidationError, match="分析範囲外"):
        validate_output_scope({"evaluations": [evaluation("improve", 33.0, 36.0)]}, scopes)


def test_unscored_evaluation_is_not_range_checked() -> None:
    unscored = {"evaluations": [evaluation("unscored", None, None)]}
    validate_output_scope(unscored, {"AIM-02": narrow({})})


def test_scored_evaluation_without_required_context_is_rejected() -> None:
    missing = ("previous_round_context",)
    scopes = {"ECO-01": AnalysisScope("ECO-01", "cross_round", missing_context=missing)}
    with pytest.raises(ContractValidationError, match="採点"):
        validate_output_scope({"evaluations": [evaluation("good", 1.0, 2.0, "ECO-01")]}, scopes)
    validate_output_scope({"evaluations": [evaluation("unscored", None, None, "ECO-01")]}, scopes)


# --- RoundAnalyzer integration -------------------------------------------------------------


class RecordingCoach:
    def __init__(self, evaluations: list[dict[str, Any]] | None = None) -> None:
        self.calls: list[dict[str, Any]] = []
        self.evaluations = evaluations or []

    def evaluate(
        self,
        round_package: dict[str, Any],
        candidate_rule_ids: list[str],
        *,
        frame_paths: list[Path] | None = None,
        deterministic_decisions: dict[str, dict[str, Any]] | None = None,
        analysis_scopes: dict[str, dict[str, Any]] | None = None,
        cancel_event: Event | None = None,
    ) -> dict[str, Any]:
        self.calls.append(
            {
                "package": copy.deepcopy(round_package),
                "candidates": list(candidate_rule_ids),
                "frame_paths": frame_paths,
                "scopes": analysis_scopes,
            }
        )
        return {
            "schema_version": "3.0",
            "analysis_id": "a",
            "match_id": round_package["match_id"],
            "round_no": round_package["round_no"],
            "evaluations": self.evaluations,
        }


def analyzer(coach: RecordingCoach) -> RoundAnalyzer:
    return RoundAnalyzer(
        fact_builder=FactBuilder(),
        selector=RuleSelector(resource_path("config/rule_trigger_registry_v2.json")),
        rule_engine=DeterministicRuleEngine(),
        coach=coach,  # type: ignore[arg-type]
        validator=SchemaValidator(),
    )


class NarrowEverythingResolver(TemporalScopeResolver):
    """Pin every candidate to the AIM-02 window so scoping is exercised deterministically."""

    def resolve(self, candidate: RuleCandidate, package: dict[str, Any]) -> AnalysisScope:  # type: ignore[override]
        return AnalysisScope(candidate.rule_id, "micro", ((24.0, 34.7),), whole_round=False)


def test_analyzer_gives_the_coach_a_scoped_package_and_matching_frames() -> None:
    coach = RecordingCoach()
    runner = RoundAnalyzer(
        fact_builder=FactBuilder(),
        selector=RuleSelector(resource_path("config/rule_trigger_registry_v2.json")),
        rule_engine=DeterministicRuleEngine(),
        coach=coach,  # type: ignore[arg-type]
        validator=SchemaValidator(),
        scope_resolver=NarrowEverythingResolver({}),
    )
    # The recording coach returns no evaluations, so the authority check rejects the
    # output afterwards; what matters here is what the coach was given.
    with pytest.raises(ContractValidationError, match="決定論的評価が出力から欠落"):
        runner.analyze(base_package())
    call = coach.calls[0]
    assert [Path(p).name for p in call["frame_paths"]] == ["near.jpg"]
    assert "FAR-1" not in {e["event_id"] for e in call["package"]["events"]}
    assert [f["path"] for f in call["package"]["frames"]] == ["near.jpg"]
    assert call["scopes"] and set(call["scopes"]) == set(call["candidates"])
    assert all(item["scope"] == "event_windows" for item in call["scopes"].values())


def test_real_coach_prompt_carries_the_analysis_scopes() -> None:
    from types import SimpleNamespace

    from valorant_ai_coach.ai import OpenAICoach
    from valorant_ai_coach.rules import MockEvaluator

    package = FactBuilder().enrich(json.loads((CASES / "TC-006" / "input.json").read_text("utf-8")))
    reply = json.dumps(MockEvaluator().evaluate(package, ["AIM-02"]), ensure_ascii=False)
    calls: list[dict[str, Any]] = []

    class Responses:
        def create(self, **kwargs: Any) -> Any:
            calls.append(kwargs)
            return SimpleNamespace(status="completed", output_text=reply)

    rules_file = resource_path("config/valorant_evaluation_rules_v4.json")
    rules = json.loads(rules_file.read_text("utf-8"))
    coach = OpenAICoach(
        api_key="k",
        model="m",
        rules_by_id={rule["id"]: rule for rule in rules["rules"]},
        validator=SchemaValidator(),
        client=SimpleNamespace(responses=Responses()),
        max_repair_attempts=0,
        retry_delays=(),
    )
    scopes = {"AIM-02": AnalysisScope("AIM-02", "micro", ((24.0, 34.7),), False).to_prompt()}
    coach.evaluate(package, ["AIM-02"], analysis_scopes=scopes)
    prompt = json.loads(calls[0]["input"][0]["content"][0]["text"])
    assert prompt["analysis_scopes"] == scopes


def test_analysis_scopes_are_exposed_on_the_result_for_mock_coach() -> None:
    from valorant_ai_coach.application import MockCoachAdapter

    result = RoundAnalyzer(
        fact_builder=FactBuilder(),
        selector=RuleSelector(resource_path("config/rule_trigger_registry_v2.json")),
        rule_engine=DeterministicRuleEngine(),
        coach=MockCoachAdapter(),
        validator=SchemaValidator(),
    ).analyze(json.loads((CASES / "TC-006" / "input.json").read_text(encoding="utf-8")))
    assert set(result.analysis_scopes) == {c.rule_id for c in result.candidates}
    assert result.analysis_scopes["AIM-02"].level == "micro"
