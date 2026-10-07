from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from threading import Event
from typing import Any, Protocol

from valorant_ai_coach.facts import FactBuilder
from valorant_ai_coach.models import RuleCandidate
from valorant_ai_coach.rules import DeterministicRuleEngine, MockEvaluator, RuleSelector
from valorant_ai_coach.rules.temporal_scope import (
    AnalysisScope,
    TemporalScopeResolver,
    scope_round_package,
    validate_output_scope,
)
from valorant_ai_coach.schema_validation import ContractValidationError, SchemaValidator


class RoundCoach(Protocol):
    def evaluate(
        self,
        round_package: dict[str, Any],
        candidate_rule_ids: list[str],
        *,
        frame_paths: list[Path] | None = None,
        deterministic_decisions: dict[str, dict[str, Any]] | None = None,
        analysis_scopes: dict[str, dict[str, Any]] | None = None,
        cancel_event: Event | None = None,
    ) -> dict[str, Any]: ...


class MockCoachAdapter:
    """Give the deterministic demo evaluator the same boundary as the API coach."""

    def __init__(self, evaluator: MockEvaluator | None = None) -> None:
        self.evaluator = evaluator or MockEvaluator()

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
        del frame_paths, deterministic_decisions, analysis_scopes
        if cancel_event is not None and cancel_event.is_set():
            raise InterruptedError("AI評価がキャンセルされました")
        return self.evaluator.evaluate(round_package, candidate_rule_ids)


@dataclass(frozen=True, slots=True)
class RoundAnalysis:
    round_package: dict[str, Any]
    candidates: tuple[RuleCandidate, ...]
    deterministic_decisions: dict[str, dict[str, Any]]
    output: dict[str, Any]
    analysis_scopes: dict[str, AnalysisScope] = field(default_factory=dict)


class RoundAnalyzer:
    """Canonical Fact Builder -> selector -> Rule Engine -> coach flow."""

    def __init__(
        self,
        *,
        fact_builder: FactBuilder,
        selector: RuleSelector,
        rule_engine: DeterministicRuleEngine,
        coach: RoundCoach,
        validator: SchemaValidator,
        scope_resolver: TemporalScopeResolver | None = None,
    ) -> None:
        self.scope_resolver = scope_resolver or TemporalScopeResolver()
        self.fact_builder = fact_builder
        self.selector = selector
        self.rule_engine = rule_engine
        self.coach = coach
        self.validator = validator

    def analyze(
        self, round_package: dict[str, Any], *, cancel_event: Event | None = None
    ) -> RoundAnalysis:
        self.validator.validate_round_package(round_package)
        enriched = self.fact_builder.enrich(round_package)
        self.validator.validate_round_package(enriched)
        candidates = self.selector.select(enriched)
        candidate_ids = [candidate.rule_id for candidate in candidates]
        decisions: dict[str, dict[str, Any]] = {}
        for candidate in candidates:
            decision = self.rule_engine.evaluate(
                candidate.rule_id,
                enriched["deterministic_facts"],
                enriched["events"],
            )
            if decision is not None:
                serialized = asdict(decision)
                serialized["fact_refs"] = list(decision.fact_refs)
                serialized["missing_information"] = list(decision.missing_information)
                decisions[candidate.rule_id] = serialized
        scopes = {
            candidate.rule_id: self.scope_resolver.resolve(candidate, enriched)
            for candidate in candidates
        }
        bound_fact_ids = {
            str(ref) for decision in decisions.values() for ref in decision.get("fact_refs", [])
        }
        scoped_package, kept_frames = scope_round_package(
            enriched, list(scopes.values()), keep_fact_ids=bound_fact_ids
        )
        all_frame_paths = [Path(frame["path"]) for frame in enriched["frames"]]
        frame_paths = [all_frame_paths[index] for index in kept_frames]
        output = self.coach.evaluate(
            scoped_package,
            candidate_ids,
            frame_paths=frame_paths,
            deterministic_decisions=decisions,
            analysis_scopes={rule_id: scope.to_prompt() for rule_id, scope in scopes.items()},
            cancel_event=cancel_event,
        )
        self.validator.validate_ai_output(
            output,
            round_package=enriched,
            candidate_rule_ids=set(candidate_ids),
        )
        self._validate_deterministic_authority(output, decisions)
        validate_output_scope(output, scopes)
        return RoundAnalysis(enriched, tuple(candidates), decisions, output, scopes)

    @staticmethod
    def _validate_deterministic_authority(
        output: dict[str, Any], decisions: dict[str, dict[str, Any]]
    ) -> None:
        for rule_id, decision in decisions.items():
            evaluation = next(
                (
                    item
                    for item in output["evaluations"]
                    if item["primary_rule_id"] == rule_id
                    or rule_id in item.get("related_rule_ids", [])
                ),
                None,
            )
            if evaluation is None:
                raise ContractValidationError(
                    f"決定論的評価が出力から欠落しています: {rule_id}"
                )
            if evaluation["label"] != decision["label"]:
                raise ContractValidationError(
                    f"{rule_id} のlabelが決定論的判定と一致しません"
                )
            expected = set(decision.get("fact_refs", []))
            if not expected.issubset(evaluation["fact_refs"]):
                raise ContractValidationError(
                    f"{rule_id} の決定論的fact_refsが出力にありません"
                )
