"""Organise per-Round evaluation results into one Match-level, evidence-preserving view.

Scope guard (read before extending)
-----------------------------------
This module *collects, classifies and counts*. It deliberately produces **no** Match-level
GOOD/IMPROVE verdict, no overall score, no weights and no aggregated confidence: the
rules contain human criteria that a repetition count cannot decide, and those meanings
are not defined. Per-evaluation confidence is copied through exactly as supplied.

What it does guarantee
----------------------
* Identity conflicts raise ``MatchAggregationError`` and never produce a partial
  result: Round Packages from different matches, one Round supplied twice with
  different content, an evaluation id reused across Rounds, or a package/output pair
  that disagrees about its own match / round.
* Content defects quarantine only that Round. A Round whose package or output breaks the
  existing contracts (``SchemaValidator``) is excluded from every count and reported;
  it is never half-trusted.
* Nothing is filled in. Missing, unevaluated or partially observed Rounds, gaps in the
  round numbers and Rounds that cannot be placed on the timeline are reported as
  issues. Neighbouring Rounds are never used to guess a boundary or a result.
* *Availability* is separated from *completeness*. Having Rounds is not the same as
  having the Match: ``verified_complete`` is only possible when the caller supplies
  ``expected_round_numbers``; otherwise the best possible status is ``unverifiable``.
* Counts are of the evaluation records as supplied. They are not distinct game events,
  and an input that already went through the display aggregator may have been reduced
  (``display_limit_reached`` marks that risk).
* The result is a pure function of its inputs: independent of input order, JSON-safe,
  and the inputs are never modified.
"""

from __future__ import annotations

import json
import math
from collections import Counter
from collections.abc import Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from valorant_ai_coach.models import RuleCandidate
from valorant_ai_coach.rules.temporal_contract import (
    ROUND_TIMELINE_COMPLETE,
    ContextAssessment,
    TemporalPolicyTable,
    assess_context,
    round_timeline_status,
)
from valorant_ai_coach.rules.temporal_scope import AnalysisScope, TemporalScopeResolver
from valorant_ai_coach.schema_validation import ContractValidationError, SchemaValidator

from .round_analyzer import RoundAnalysis

SCHEMA_VERSION = "match_aggregation.v1"
COUNTING_BASIS = "evaluation_records_as_supplied"
LABELS: tuple[str, ...] = ("good", "improve", "unscored")

ROUND_INCLUDED = "included"
ROUND_NOT_EVALUATED = "not_evaluated"
ROUND_EXCLUDED_INVALID = "excluded_invalid"

COMPLETENESS_VERIFIED = "verified_complete"
COMPLETENESS_INCOMPLETE = "incomplete"
COMPLETENESS_UNVERIFIABLE = "unverifiable"

BASIS_FACTS = "facts"
BASIS_EVIDENCE_ONLY = "evidence_only"
BASIS_NONE = "none"
BASIS_UNRESOLVED = "unresolved"
UNSPECIFIED_REASON = "unspecified"
_BASES: tuple[str, ...] = (BASIS_FACTS, BASIS_EVIDENCE_ONLY, BASIS_NONE, BASIS_UNRESOLVED)

# Issue codes
NO_ROUNDS = "no_rounds"
DUPLICATE_ROUND_INPUT_IGNORED = "duplicate_round_input_ignored"
ROUND_NOT_EVALUATED_CODE = "round_not_evaluated"
ROUND_CONTRACT_VIOLATION = "round_contract_violation"
DUPLICATE_EVALUATION_ID = "duplicate_evaluation_id"
ROUND_NUMBER_GAP = "round_number_gap"
EXPECTED_ROUND_MISSING = "expected_round_missing"
UNEXPECTED_ROUND = "unexpected_round"
ROUND_WINDOW_ORDER_CONFLICT = "round_window_order_conflict"
ROUND_WINDOWS_OVERLAP = "round_windows_overlap"
ROUND_TIMELINE_PARTIAL_CODE = "round_timeline_partial"
ROUND_TIMELINE_UNAVAILABLE_CODE = "round_timeline_unavailable"
ROUND_TIMELINE_UNKNOWN_CODE = "round_timeline_unknown"
UNKNOWN_RULE_ID = "unknown_rule_id"
FACT_REF_UNRESOLVED = "fact_ref_unresolved"
DISPLAY_LIMIT_REACHED = "display_limit_reached"

# Issues that mean "this Match view cannot be called complete".
COMPLETENESS_BLOCKING: frozenset[str] = frozenset(
    {
        NO_ROUNDS,
        ROUND_NOT_EVALUATED_CODE,
        ROUND_CONTRACT_VIOLATION,
        DUPLICATE_EVALUATION_ID,
        ROUND_NUMBER_GAP,
        EXPECTED_ROUND_MISSING,
        UNEXPECTED_ROUND,
        ROUND_WINDOW_ORDER_CONFLICT,
        ROUND_WINDOWS_OVERLAP,
        ROUND_TIMELINE_PARTIAL_CODE,
        ROUND_TIMELINE_UNAVAILABLE_CODE,
        ROUND_TIMELINE_UNKNOWN_CODE,
    }
)

_TIMELINE_ISSUE = {
    "partial": ROUND_TIMELINE_PARTIAL_CODE,
    "unavailable": ROUND_TIMELINE_UNAVAILABLE_CODE,
    "unknown": ROUND_TIMELINE_UNKNOWN_CODE,
}


class MatchAggregationError(ContractValidationError):
    """An identity conflict that makes a Match-level view meaningless."""


# --------------------------------------------------------------------------- inputs


@dataclass(frozen=True, slots=True)
class RoundInput:
    """One Round: its package, its evaluation output (if any) and how it was scoped."""

    round_package: Mapping[str, Any]
    output: Mapping[str, Any] | None = None
    analysis_scopes: Mapping[str, AnalysisScope] = field(default_factory=dict)
    candidates: tuple[RuleCandidate, ...] = ()
    candidate_rule_ids: frozenset[str] | None = None
    evaluation_failure: str | None = None

    @classmethod
    def from_round_analysis(cls, analysis: RoundAnalysis) -> RoundInput:
        return cls(
            round_package=analysis.round_package,
            output=analysis.output,
            analysis_scopes=analysis.analysis_scopes,
            candidates=analysis.candidates,
            candidate_rule_ids=frozenset(candidate.rule_id for candidate in analysis.candidates),
        )


# -------------------------------------------------------------------------- results


@dataclass(frozen=True, slots=True)
class AggregationIssue:
    code: str
    detail: str
    round_no: int | None = None
    rule_id: str | None = None
    evaluation_id: str | None = None

    def sort_key(self) -> tuple[int, str, str, str, str]:
        return (
            -1 if self.round_no is None else self.round_no,
            self.code,
            self.rule_id or "",
            self.evaluation_id or "",
            self.detail,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "round_no": self.round_no,
            "rule_id": self.rule_id,
            "evaluation_id": self.evaluation_id,
            "detail": self.detail,
        }


@dataclass(frozen=True, slots=True)
class FactRefProvenance:
    """What one cited fact is, according to the Round Package that owns the evaluation."""

    fact_id: str
    resolved: bool
    key: str | None = None
    confidence: float | None = None
    source: str | None = None
    provenance_event_ids: tuple[str, ...] = ()
    missing_event_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class EvaluationRef:
    """A reference back to one supplied evaluation and the evidence behind it."""

    evaluation_id: str
    round_no: int
    primary_rule_id: str
    related_rule_ids: tuple[str, ...]
    label: str
    decision_source: str | None
    confidence: float | None
    unscored_reason_code: str | None
    evidence_range: dict[str, float] | None
    display_clip: dict[str, float] | None
    evidence_count: int
    provenance_basis: str
    facts: tuple[FactRefProvenance, ...]

    def sort_key(self) -> tuple[int, float, str]:
        start = (self.evidence_range or {}).get("start_sec")
        return (self.round_no, math.inf if start is None else float(start), self.evaluation_id)

    def to_dict(self) -> dict[str, Any]:
        return {
            "evaluation_id": self.evaluation_id,
            "round_no": self.round_no,
            "primary_rule_id": self.primary_rule_id,
            "related_rule_ids": list(self.related_rule_ids),
            "label": self.label,
            "decision_source": self.decision_source,
            "confidence": self.confidence,
            "unscored_reason_code": self.unscored_reason_code,
            "evidence_range": None if self.evidence_range is None else dict(self.evidence_range),
            "display_clip": None if self.display_clip is None else dict(self.display_clip),
            "evidence_count": self.evidence_count,
            "provenance_basis": self.provenance_basis,
            "facts": [
                {
                    "fact_id": item.fact_id,
                    "resolved": item.resolved,
                    "key": item.key,
                    "confidence": item.confidence,
                    "source": item.source,
                    "provenance_event_ids": list(item.provenance_event_ids),
                    "missing_event_ids": list(item.missing_event_ids),
                }
                for item in self.facts
            ],
        }


@dataclass(frozen=True, slots=True)
class RoundSummary:
    round_no: int
    status: str
    round_window: dict[str, float] | None
    timeline: str | None
    timeline_completeness: float | None
    evaluation_count: int
    label_counts: dict[str, int]
    failure: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "round_no": self.round_no,
            "status": self.status,
            "round_window": None if self.round_window is None else dict(self.round_window),
            "timeline": self.timeline,
            "timeline_completeness": self.timeline_completeness,
            "evaluation_count": self.evaluation_count,
            "label_counts": dict(self.label_counts),
            "failure": self.failure,
        }


@dataclass(frozen=True, slots=True)
class RuleAggregate:
    """Everything supplied about one rule, kept apart by label and by role.

    ``counts`` are evaluations where the rule is the *primary* rule. ``related_counts``
    are evaluations that merged this rule in as a related rule; they are never added
    to ``counts``, so one evaluation is never counted twice, yet the rule's identity is
    not lost when the display aggregator folded it into another rule.
    """

    rule_id: str
    known_rule: bool
    level: str | None
    uses_whole_match_aggregation: bool | None
    needs_match_context: bool | None
    match_context_unverified: bool | None
    counts: dict[str, int]
    related_counts: dict[str, int]
    primary_evaluation_ids: tuple[str, ...]
    related_evaluation_ids: tuple[str, ...]
    rounds_as_primary: tuple[int, ...]
    rounds_as_related: tuple[int, ...]
    unscored_reason_counts: dict[str, int]
    evidence_basis_counts: dict[str, int]
    display_limit: int | None
    display_limit_reached: bool
    aggregate_repeated_occurrences: bool | None
    summary_required_if_occurrences_at_least: int | None
    context_by_round: tuple[tuple[int, ContextAssessment], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "known_rule": self.known_rule,
            "level": self.level,
            "uses_whole_match_aggregation": self.uses_whole_match_aggregation,
            "needs_match_context": self.needs_match_context,
            "match_context_unverified": self.match_context_unverified,
            "counts": dict(self.counts),
            "related_counts": dict(self.related_counts),
            "primary_evaluation_ids": list(self.primary_evaluation_ids),
            "related_evaluation_ids": list(self.related_evaluation_ids),
            "rounds_as_primary": list(self.rounds_as_primary),
            "rounds_as_related": list(self.rounds_as_related),
            "unscored_reason_counts": dict(self.unscored_reason_counts),
            "evidence_basis_counts": dict(self.evidence_basis_counts),
            "display_limit": self.display_limit,
            "display_limit_reached": self.display_limit_reached,
            "aggregate_repeated_occurrences": self.aggregate_repeated_occurrences,
            "summary_required_if_occurrences_at_least": (
                self.summary_required_if_occurrences_at_least
            ),
            "context_by_round": [
                {"round_no": round_no, **assessment.to_dict()}
                for round_no, assessment in self.context_by_round
            ],
        }


@dataclass(frozen=True, slots=True)
class MatchCompleteness:
    status: str
    expected_round_numbers: tuple[int, ...] | None
    rounds_supplied: tuple[int, ...]
    rounds_included: tuple[int, ...]
    rounds_not_evaluated: tuple[int, ...]
    rounds_excluded_invalid: tuple[int, ...]
    rounds_timeline_not_complete: tuple[int, ...]
    round_number_gaps: tuple[int, ...]
    expected_rounds_missing: tuple[int, ...]
    blocking_reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "expected_round_numbers": (
                None
                if self.expected_round_numbers is None
                else list(self.expected_round_numbers)
            ),
            "rounds_supplied": list(self.rounds_supplied),
            "rounds_included": list(self.rounds_included),
            "rounds_not_evaluated": list(self.rounds_not_evaluated),
            "rounds_excluded_invalid": list(self.rounds_excluded_invalid),
            "rounds_timeline_not_complete": list(self.rounds_timeline_not_complete),
            "round_number_gaps": list(self.round_number_gaps),
            "expected_rounds_missing": list(self.expected_rounds_missing),
            "blocking_reasons": list(self.blocking_reasons),
        }


@dataclass(frozen=True, slots=True)
class MatchAggregation:
    match_id: str | None
    completeness: MatchCompleteness
    rounds: tuple[RoundSummary, ...]
    rules: tuple[RuleAggregate, ...]
    evaluations: tuple[EvaluationRef, ...]
    issues: tuple[AggregationIssue, ...]
    schema_version: str = SCHEMA_VERSION
    counting_basis: str = COUNTING_BASIS

    def rule(self, rule_id: str) -> RuleAggregate | None:
        return next((item for item in self.rules if item.rule_id == rule_id), None)

    def issues_with_code(self, code: str) -> tuple[AggregationIssue, ...]:
        return tuple(item for item in self.issues if item.code == code)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "counting_basis": self.counting_basis,
            "match_id": self.match_id,
            "completeness": self.completeness.to_dict(),
            "rounds": [item.to_dict() for item in self.rounds],
            "rules": [item.to_dict() for item in self.rules],
            "evaluations": [item.to_dict() for item in self.evaluations],
            "issues": [item.to_dict() for item in self.issues],
        }


# ------------------------------------------------------------------------ aggregator


def _number_or_none(value: Any) -> float | None:
    """A finite real number, or ``None``. ``None`` is never coerced to 0.0 or 1.0."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _interval(value: Any) -> dict[str, float] | None:
    if not isinstance(value, Mapping):
        return None
    start, end = _number_or_none(value.get("start_sec")), _number_or_none(value.get("end_sec"))
    if start is None or end is None:
        return None
    return {"start_sec": start, "end_sec": end}


def _fingerprint(entry: RoundInput) -> str:
    return json.dumps(
        [entry.round_package, entry.output, entry.evaluation_failure],
        sort_keys=True,
        ensure_ascii=False,
        default=str,
    )


def _empty_counts() -> dict[str, int]:
    return {label: 0 for label in LABELS}


class MatchAggregator:
    """Build a :class:`MatchAggregation` from per-Round results (no I/O, no API)."""

    def __init__(
        self,
        rule_config: Mapping[str, Any] | None = None,
        *,
        validator: SchemaValidator | None = None,
    ) -> None:
        self.policies = (
            TemporalPolicyTable.load()
            if rule_config is None
            else TemporalPolicyTable.from_config(rule_config)
        )
        rules = (rule_config or {}).get("rules")
        self.resolver = (
            TemporalScopeResolver()
            if rules is None
            else TemporalScopeResolver({str(rule["id"]): rule for rule in rules})
        )
        self.validator = validator or SchemaValidator()

    # -- public ---------------------------------------------------------------------

    def aggregate(
        self,
        rounds: Iterable[RoundInput | RoundAnalysis],
        *,
        match_id: str | None = None,
        expected_round_numbers: Collection[int] | None = None,
    ) -> MatchAggregation:
        expected = self._expected(expected_round_numbers)
        entries = [
            item if isinstance(item, RoundInput) else RoundInput.from_round_analysis(item)
            for item in rounds
        ]
        issues: list[AggregationIssue] = []
        unique = self._unique_rounds(entries, issues)
        resolved_match = self._match_id(unique, match_id)
        self._reject_reused_evaluation_ids(unique)

        summaries: list[RoundSummary] = []
        refs: list[EvaluationRef] = []
        contexts: dict[tuple[str, int], ContextAssessment] = {}
        window_by_round: dict[int, dict[str, float]] = {}
        for round_no in sorted(unique):
            summary, round_refs, round_contexts = self._process_round(
                round_no, unique[round_no], issues
            )
            summaries.append(summary)
            refs.extend(round_refs)
            contexts.update({(rule_id, round_no): item for rule_id, item in round_contexts})
            if summary.round_window is not None:
                window_by_round[round_no] = summary.round_window

        if not unique:
            issues.append(AggregationIssue(NO_ROUNDS, "Roundが1件も渡されていません"))
        self._check_round_numbers(sorted(unique), expected, issues)
        self._check_windows(window_by_round, issues)
        refs.sort(key=lambda item: item.sort_key())
        # Every completeness-blocking issue exists by now; the per-rule step below only
        # adds informational ones, so the status can be fixed first and handed down.
        completeness = self._completeness(summaries, expected, issues)
        rules = self._rule_aggregates(refs, contexts, issues, completeness.status)
        issues.sort(key=lambda item: item.sort_key())
        return MatchAggregation(
            match_id=resolved_match,
            completeness=completeness,
            rounds=tuple(summaries),
            rules=rules,
            evaluations=tuple(refs),
            issues=tuple(issues),
        )

    # -- input handling -------------------------------------------------------------

    @staticmethod
    def _expected(values: Collection[int] | None) -> tuple[int, ...] | None:
        if values is None:
            return None
        numbers = list(values)
        if any(isinstance(item, bool) or not isinstance(item, int) or item < 1 for item in numbers):
            raise ValueError("expected_round_numbersは1以上の整数だけを指定できます")
        return tuple(sorted(set(numbers)))

    @staticmethod
    def _identity(entry: RoundInput) -> tuple[str, int]:
        package = entry.round_package
        match_id, round_no = package.get("match_id"), package.get("round_no")
        if (
            not isinstance(match_id, str)
            or not match_id
            or isinstance(round_no, bool)
            or not isinstance(round_no, int)
            or round_no < 1
        ):
            raise MatchAggregationError(
                "round_packageにmatch_id(文字列)とround_no(1以上の整数)が必要です"
            )
        output = entry.output
        if output is not None:
            if output.get("match_id") != match_id:
                raise MatchAggregationError(
                    f"R{round_no}: 評価出力のmatch_idがround_packageと一致しません"
                )
            if output.get("round_no") != round_no:
                raise MatchAggregationError(
                    f"R{round_no}: 評価出力のround_noがround_packageと一致しません"
                )
        return match_id, round_no

    def _unique_rounds(
        self, entries: Sequence[RoundInput], issues: list[AggregationIssue]
    ) -> dict[int, RoundInput]:
        unique: dict[int, RoundInput] = {}
        for entry in entries:
            _, round_no = self._identity(entry)
            existing = unique.get(round_no)
            if existing is None:
                unique[round_no] = entry
            elif _fingerprint(existing) == _fingerprint(entry):
                issues.append(
                    AggregationIssue(
                        DUPLICATE_ROUND_INPUT_IGNORED,
                        "同一内容のRoundが重複して渡されたため、2件目以降は集計していません",
                        round_no=round_no,
                    )
                )
            else:
                raise MatchAggregationError(
                    f"R{round_no}: 同じround_noに内容の異なる入力が渡されました"
                )
        return unique

    def _match_id(self, unique: Mapping[int, RoundInput], declared: str | None) -> str | None:
        found = {str(entry.round_package["match_id"]) for entry in unique.values()}
        if declared is not None:
            found |= {declared}
        if len(found) > 1:
            raise MatchAggregationError(f"異なるmatch_idが混在しています: {sorted(found)}")
        return next(iter(found), None)

    @staticmethod
    def _reject_reused_evaluation_ids(unique: Mapping[int, RoundInput]) -> None:
        owner: dict[str, int] = {}
        for round_no in sorted(unique):
            output = unique[round_no].output
            evaluations = output.get("evaluations") if output is not None else None
            if not isinstance(evaluations, list):
                continue
            for evaluation_id in {
                str(item["evaluation_id"])
                for item in evaluations
                if isinstance(item, Mapping) and "evaluation_id" in item
            }:
                if owner.setdefault(evaluation_id, round_no) != round_no:
                    raise MatchAggregationError(
                        f"evaluation_id {evaluation_id} が複数のRound"
                        f"(R{owner[evaluation_id]}, R{round_no})で使われています"
                    )

    # -- one round ------------------------------------------------------------------

    def _process_round(
        self, round_no: int, entry: RoundInput, issues: list[AggregationIssue]
    ) -> tuple[RoundSummary, list[EvaluationRef], list[tuple[str, ContextAssessment]]]:
        package = entry.round_package
        try:
            self.validator.validate_round_package(dict(package))
        except ContractValidationError as exc:
            return self._excluded(round_no, str(exc), issues), [], []

        window = _interval(package.get("round_window"))
        timeline = round_timeline_status(package)
        quality = package.get("observation_quality")
        completeness = (
            _number_or_none(quality.get("timeline_completeness"))
            if isinstance(quality, Mapping)
            else None
        )
        if timeline != ROUND_TIMELINE_COMPLETE:
            issues.append(
                AggregationIssue(
                    _TIMELINE_ISSUE[timeline],
                    f"Round全体の時間軸を完全には観測できていません ({timeline})",
                    round_no=round_no,
                )
            )

        if entry.output is None:
            reason = entry.evaluation_failure or "評価結果がありません"
            issues.append(AggregationIssue(ROUND_NOT_EVALUATED_CODE, reason, round_no=round_no))
            return (
                RoundSummary(
                    round_no,
                    ROUND_NOT_EVALUATED,
                    window,
                    timeline,
                    completeness,
                    0,
                    _empty_counts(),
                    failure=reason,
                ),
                [],
                [],
            )

        output = dict(entry.output)
        candidate_ids = self._candidate_ids(entry)
        try:
            self.validator.validate_ai_output(
                output,
                round_package=dict(package),
                candidate_rule_ids=None if candidate_ids is None else set(candidate_ids),
            )
        except ContractValidationError as exc:
            return self._excluded(round_no, str(exc), issues, window=window), [], []
        duplicate = self._duplicate_ids_in(output)
        if duplicate:
            return (
                self._excluded(
                    round_no,
                    f"evaluation_idが重複しています: {sorted(duplicate)}",
                    issues,
                    window=window,
                    code=DUPLICATE_EVALUATION_ID,
                ),
                [],
                [],
            )

        facts = {
            str(fact["fact_id"]): fact
            for fact in package.get("deterministic_facts", [])
            if isinstance(fact, Mapping) and "fact_id" in fact
        }
        event_ids = {
            str(event["event_id"])
            for event in package.get("events", [])
            if isinstance(event, Mapping) and "event_id" in event
        }
        refs: list[EvaluationRef] = []
        contexts: dict[str, ContextAssessment] = {}
        label_counts = _empty_counts()
        for evaluation in output.get("evaluations", []):
            ref = self._evaluation_ref(round_no, evaluation, facts, event_ids, issues)
            refs.append(ref)
            if ref.label in label_counts:
                label_counts[ref.label] += 1
            for rule_id in (ref.primary_rule_id, *ref.related_rule_ids):
                assessment = self._assess(rule_id, entry, package, issues, round_no, ref)
                if assessment is not None:
                    contexts.setdefault(rule_id, assessment)
        summary = RoundSummary(
            round_no,
            ROUND_INCLUDED,
            window,
            timeline,
            completeness,
            len(refs),
            label_counts,
        )
        return summary, refs, sorted(contexts.items())

    @staticmethod
    def _candidate_ids(entry: RoundInput) -> frozenset[str] | None:
        if entry.candidate_rule_ids is not None:
            return entry.candidate_rule_ids
        if entry.candidates:
            return frozenset(candidate.rule_id for candidate in entry.candidates)
        return None

    @staticmethod
    def _duplicate_ids_in(output: Mapping[str, Any]) -> set[str]:
        counts = Counter(
            str(item.get("evaluation_id"))
            for item in output.get("evaluations", [])
            if isinstance(item, Mapping)
        )
        return {key for key, count in counts.items() if count > 1}

    @staticmethod
    def _excluded(
        round_no: int,
        detail: str,
        issues: list[AggregationIssue],
        *,
        window: dict[str, float] | None = None,
        code: str = ROUND_CONTRACT_VIOLATION,
    ) -> RoundSummary:
        issues.append(AggregationIssue(code, detail, round_no=round_no))
        return RoundSummary(
            round_no, ROUND_EXCLUDED_INVALID, window, None, None, 0, _empty_counts(), failure=detail
        )

    def _evaluation_ref(
        self,
        round_no: int,
        evaluation: Mapping[str, Any],
        facts: Mapping[str, Mapping[str, Any]],
        event_ids: set[str],
        issues: list[AggregationIssue],
    ) -> EvaluationRef:
        evaluation_id = str(evaluation["evaluation_id"])
        fact_ids = sorted({str(item) for item in evaluation.get("fact_refs", [])})
        details: list[FactRefProvenance] = []
        for fact_id in fact_ids:
            fact = facts.get(fact_id)
            if fact is None:
                details.append(FactRefProvenance(fact_id, False))
                issues.append(
                    AggregationIssue(
                        FACT_REF_UNRESOLVED,
                        f"fact_id {fact_id} がRound Packageにありません",
                        round_no=round_no,
                        evaluation_id=evaluation_id,
                    )
                )
                continue
            cited = sorted({str(item) for item in fact.get("provenance_event_ids", [])})
            missing = tuple(item for item in cited if item not in event_ids)
            for event_id in missing:
                issues.append(
                    AggregationIssue(
                        FACT_REF_UNRESOLVED,
                        f"{fact_id} が参照するevent_id {event_id} がRound Packageにありません",
                        round_no=round_no,
                        evaluation_id=evaluation_id,
                    )
                )
            details.append(
                FactRefProvenance(
                    fact_id,
                    True,
                    key=str(fact.get("key")),
                    confidence=_number_or_none(fact.get("confidence")),
                    source=None if fact.get("source") is None else str(fact["source"]),
                    provenance_event_ids=tuple(cited),
                    missing_event_ids=missing,
                )
            )
        evidence = evaluation.get("evidence")
        evidence_count = len(evidence) if isinstance(evidence, list) else 0
        if details:
            resolved = all(item.resolved and not item.missing_event_ids for item in details)
            basis = BASIS_FACTS if resolved else BASIS_UNRESOLVED
        else:
            basis = BASIS_EVIDENCE_ONLY if evidence_count else BASIS_NONE
        decision_source = evaluation.get("decision_source")
        reason = evaluation.get("unscored_reason_code")
        return EvaluationRef(
            evaluation_id=evaluation_id,
            round_no=round_no,
            primary_rule_id=str(evaluation["primary_rule_id"]),
            related_rule_ids=tuple(
                sorted({str(item) for item in evaluation.get("related_rule_ids", [])})
            ),
            label=str(evaluation["label"]),
            decision_source=None if decision_source is None else str(decision_source),
            confidence=_number_or_none(evaluation.get("confidence")),
            unscored_reason_code=None if reason is None else str(reason),
            evidence_range=_interval(evaluation.get("evidence_range")),
            display_clip=_interval(evaluation.get("display_clip")),
            evidence_count=evidence_count,
            provenance_basis=basis,
            facts=tuple(details),
        )

    def _assess(
        self,
        rule_id: str,
        entry: RoundInput,
        package: Mapping[str, Any],
        issues: list[AggregationIssue],
        round_no: int,
        ref: EvaluationRef,
    ) -> ContextAssessment | None:
        policy = self.policies.get(rule_id)
        if policy is None:
            issues.append(
                AggregationIssue(
                    UNKNOWN_RULE_ID,
                    f"{rule_id} はルール設定にありません",
                    round_no=round_no,
                    rule_id=rule_id,
                    evaluation_id=ref.evaluation_id,
                )
            )
            return None
        scope = entry.analysis_scopes.get(rule_id)
        if scope is None:
            candidate = next((item for item in entry.candidates if item.rule_id == rule_id), None)
            if candidate is not None:
                scope = self.resolver.resolve(candidate, package)
        return assess_context(policy, package, scope)

    # -- cross-round checks ---------------------------------------------------------

    @staticmethod
    def _check_round_numbers(
        supplied: Sequence[int], expected: tuple[int, ...] | None, issues: list[AggregationIssue]
    ) -> None:
        if supplied:
            present = set(supplied)
            for number in range(min(supplied) + 1, max(supplied)):
                if number not in present:
                    issues.append(
                        AggregationIssue(
                            ROUND_NUMBER_GAP,
                            f"R{number} が渡されたRoundの間で欠けています",
                            round_no=number,
                        )
                    )
        if expected is None:
            return
        present = set(supplied)
        for number in expected:
            if number not in present:
                issues.append(
                    AggregationIssue(
                        EXPECTED_ROUND_MISSING,
                        f"期待されたR{number}が渡されていません",
                        round_no=number,
                    )
                )
        for number in sorted(present - set(expected)):
            issues.append(
                AggregationIssue(
                    UNEXPECTED_ROUND,
                    f"R{number} は期待されたRound番号に含まれていません",
                    round_no=number,
                )
            )

    @staticmethod
    def _check_windows(
        windows: Mapping[int, Mapping[str, float]], issues: list[AggregationIssue]
    ) -> None:
        ordered = sorted(windows)
        for earlier, later in zip(ordered, ordered[1:], strict=False):
            first, second = windows[earlier], windows[later]
            if second["start_sec"] < first["start_sec"]:
                issues.append(
                    AggregationIssue(
                        ROUND_WINDOW_ORDER_CONFLICT,
                        f"R{later} の開始(={second['start_sec']})が"
                        f"R{earlier} の開始(={first['start_sec']})より前です",
                        round_no=later,
                    )
                )
            elif first["end_sec"] > second["start_sec"]:
                issues.append(
                    AggregationIssue(
                        ROUND_WINDOWS_OVERLAP,
                        f"R{earlier} の終了(={first['end_sec']})が"
                        f"R{later} の開始(={second['start_sec']})より後です",
                        round_no=later,
                    )
                )

    # -- per-rule view --------------------------------------------------------------

    def _rule_aggregates(
        self,
        refs: Sequence[EvaluationRef],
        contexts: Mapping[tuple[str, int], ContextAssessment],
        issues: list[AggregationIssue],
        completeness_status: str,
    ) -> tuple[RuleAggregate, ...]:
        rule_ids = sorted(
            {ref.primary_rule_id for ref in refs}
            | {related for ref in refs for related in ref.related_rule_ids}
        )
        result: list[RuleAggregate] = []
        for rule_id in rule_ids:
            primary = [ref for ref in refs if ref.primary_rule_id == rule_id]
            related = [ref for ref in refs if rule_id in ref.related_rule_ids]
            counts, related_counts = _empty_counts(), _empty_counts()
            for ref in primary:
                if ref.label in counts:
                    counts[ref.label] += 1
            for ref in related:
                if ref.label in related_counts:
                    related_counts[ref.label] += 1
            reasons = Counter(
                ref.unscored_reason_code or UNSPECIFIED_REASON
                for ref in primary
                if ref.label == "unscored"
            )
            bases = Counter(ref.provenance_basis for ref in primary)
            policy = self.policies.get(rule_id)
            limit = None if policy is None else policy.max_display_exemplars_per_match
            reached = limit is not None and len(primary) >= limit
            if reached:
                issues.append(
                    AggregationIssue(
                        DISPLAY_LIMIT_REACHED,
                        f"{rule_id} の件数が表示上限({limit})に達しています。入力が表示用の"
                        "集約を経ている場合、実際の発生数はこれより多い可能性があります",
                        rule_id=rule_id,
                    )
                )
            rounds_with_context = sorted({ref.round_no for ref in (*primary, *related)})
            result.append(
                RuleAggregate(
                    rule_id=rule_id,
                    known_rule=policy is not None,
                    level=None if policy is None else policy.level,
                    uses_whole_match_aggregation=(
                        None if policy is None else policy.uses_whole_match_aggregation
                    ),
                    needs_match_context=None if policy is None else policy.needs_match_context,
                    # Having Rounds is not having the Match: a rule that needs match-wide
                    # context stays unverified until the caller proves completeness.
                    match_context_unverified=(
                        None
                        if policy is None
                        else policy.needs_match_context
                        and completeness_status != COMPLETENESS_VERIFIED
                    ),
                    counts=counts,
                    related_counts=related_counts,
                    primary_evaluation_ids=tuple(ref.evaluation_id for ref in primary),
                    related_evaluation_ids=tuple(ref.evaluation_id for ref in related),
                    rounds_as_primary=tuple(sorted({ref.round_no for ref in primary})),
                    rounds_as_related=tuple(sorted({ref.round_no for ref in related})),
                    unscored_reason_counts=dict(sorted(reasons.items())),
                    evidence_basis_counts={basis: bases.get(basis, 0) for basis in _BASES},
                    display_limit=limit,
                    display_limit_reached=reached,
                    aggregate_repeated_occurrences=(
                        None if policy is None else policy.aggregate_repeated_occurrences
                    ),
                    summary_required_if_occurrences_at_least=(
                        None
                        if policy is None
                        else policy.summary_required_if_occurrences_at_least
                    ),
                    context_by_round=tuple(
                        (round_no, contexts[(rule_id, round_no)])
                        for round_no in rounds_with_context
                        if (rule_id, round_no) in contexts
                    ),
                )
            )
        return tuple(result)

    # -- completeness ---------------------------------------------------------------

    @staticmethod
    def _completeness(
        summaries: Sequence[RoundSummary],
        expected: tuple[int, ...] | None,
        issues: Sequence[AggregationIssue],
    ) -> MatchCompleteness:
        def with_status(status: str) -> list[int]:
            return sorted(item.round_no for item in summaries if item.status == status)

        included = with_status(ROUND_INCLUDED)
        not_complete = sorted(
            item.round_no
            for item in summaries
            if item.status == ROUND_INCLUDED and item.timeline != ROUND_TIMELINE_COMPLETE
        )
        blocking = sorted({item.code for item in issues if item.code in COMPLETENESS_BLOCKING})
        gaps = sorted(
            item.round_no
            for item in issues
            if item.code == ROUND_NUMBER_GAP and item.round_no is not None
        )
        missing = sorted(
            item.round_no
            for item in issues
            if item.code == EXPECTED_ROUND_MISSING and item.round_no is not None
        )
        if blocking:
            status = COMPLETENESS_INCOMPLETE
        elif expected is None:
            status = COMPLETENESS_UNVERIFIABLE
        else:
            status = COMPLETENESS_VERIFIED
        return MatchCompleteness(
            status=status,
            expected_round_numbers=expected,
            rounds_supplied=tuple(sorted(item.round_no for item in summaries)),
            rounds_included=tuple(included),
            rounds_not_evaluated=tuple(with_status(ROUND_NOT_EVALUATED)),
            rounds_excluded_invalid=tuple(with_status(ROUND_EXCLUDED_INVALID)),
            rounds_timeline_not_complete=tuple(not_complete),
            round_number_gaps=tuple(gaps),
            expected_rounds_missing=tuple(missing),
            blocking_reasons=tuple(blocking),
        )
