"""Match-level aggregation: collect, classify, count - never judge.

The fixtures are synthetic Round Packages (see ``match_fixtures``); expected labels come
from the existing ``tests/cases/*/expected_assertions.json`` contract.
"""

from __future__ import annotations

import itertools
import json
import math
from copy import deepcopy
from dataclasses import replace
from typing import Any

import pytest
from match_fixtures import (
    MATCH,
    analysis_for,
    case_package,
    expected_pairs,
    lowered_confidence,
    rules_config,
    three_round_match,
)
from match_fixtures import analyze as analyze_package
from match_fixtures import round_input as make_round

from valorant_ai_coach.application import RoundAnalysis
from valorant_ai_coach.application import match_aggregation as ma
from valorant_ai_coach.application.match_aggregation import (
    MatchAggregation,
    MatchAggregationError,
    MatchAggregator,
    RoundInput,
)
from valorant_ai_coach.rules.temporal_contract import TemporalPolicyTable
from valorant_ai_coach.schema_validation import ContractValidationError, SchemaValidator


def aggregate(rounds: list[Any], **kwargs: Any) -> MatchAggregation:
    return MatchAggregator().aggregate(rounds, **kwargs)


def dumped(result: MatchAggregation) -> str:
    return json.dumps(result.to_dict(), sort_keys=True, ensure_ascii=False, allow_nan=False)


class PassThroughValidator(SchemaValidator):
    """Skips the cross-field contracts so the aggregator's own defences can be exercised."""

    def validate_round_package(self, value: dict[str, Any]) -> dict[str, Any]:
        return value

    def validate_ai_output(self, value: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        return value


def with_output(entry: RoundInput, mutate: Any) -> RoundInput:
    assert entry.output is not None
    output = deepcopy(dict(entry.output))
    mutate(output)
    return replace(entry, output=output)


# --------------------------------------------------------------------- normal match


def test_three_round_match_is_collected_in_round_order_with_expected_labels() -> None:
    result = aggregate(three_round_match(), expected_round_numbers=[1, 2, 3])
    assert result.match_id == MATCH
    assert result.completeness.status == ma.COMPLETENESS_VERIFIED
    assert result.completeness.blocking_reasons == ()
    assert result.issues == ()
    assert result.completeness.rounds_included == (1, 2, 3)
    actual = [(ref.round_no, ref.primary_rule_id, ref.label) for ref in result.evaluations]
    wanted = [
        (1, *expected_pairs("TC-006")[0]),
        (2, *expected_pairs("TC-017")[0]),
        (3, *expected_pairs("TC-026")[0]),
    ]
    assert actual == wanted


def test_without_expected_round_numbers_completeness_is_unverifiable_not_complete() -> None:
    result = aggregate(three_round_match())
    assert result.completeness.status == ma.COMPLETENESS_UNVERIFIABLE
    assert result.completeness.expected_round_numbers is None


def test_accepts_round_analysis_objects_and_round_inputs_identically() -> None:
    analyses: list[RoundAnalysis] = [
        analysis_for("TC-006", round_no=1),
        analysis_for("TC-017", round_no=2),
    ]
    from_analyses = aggregate(list(analyses))
    from_inputs = aggregate([RoundInput.from_round_analysis(item) for item in analyses])
    assert dumped(from_analyses) == dumped(from_inputs)


def test_one_evaluation_is_counted_once_and_merged_rules_keep_their_identity() -> None:
    result = aggregate(three_round_match())
    assert len(result.evaluations) == 3
    primary_total = sum(sum(rule.counts.values()) for rule in result.rules)
    assert primary_total == len(result.evaluations)  # related rules never add to counts
    aim03, mov02 = result.rule("AIM-03"), result.rule("MOV-02")
    assert aim03 is not None and mov02 is not None
    assert aim03.counts == {"good": 0, "improve": 1, "unscored": 0}
    assert aim03.related_counts == {"good": 0, "improve": 0, "unscored": 0}
    # MOV-02 was merged into AIM-03 by the display aggregation: it is not lost, not doubled.
    assert mov02.counts == {"good": 0, "improve": 0, "unscored": 0}
    assert mov02.related_counts == {"good": 0, "improve": 1, "unscored": 0}
    assert mov02.related_evaluation_ids == aim03.primary_evaluation_ids
    assert mov02.rounds_as_related == (2,) and mov02.rounds_as_primary == ()


def test_good_improve_and_unscored_are_never_mixed() -> None:
    result = aggregate(three_round_match())
    assert result.rule("AIM-02").counts == {"good": 1, "improve": 0, "unscored": 0}  # type: ignore[union-attr]
    peek = result.rule("PEEK-02")
    assert peek is not None
    assert peek.counts == {"good": 0, "improve": 0, "unscored": 1}
    assert peek.unscored_reason_counts  # the reason is kept, not collapsed


def test_each_evaluation_ref_keeps_round_fact_and_event_provenance() -> None:
    entries = three_round_match()
    result = aggregate(entries)
    ref = next(item for item in result.evaluations if item.round_no == 2)
    package = entries[1].round_package
    facts = {fact["fact_id"]: fact for fact in package["deterministic_facts"]}
    event_ids = {event["event_id"] for event in package["events"]}
    assert ref.facts and ref.provenance_basis == ma.BASIS_FACTS
    for item in ref.facts:
        assert item.resolved
        assert item.confidence == facts[item.fact_id]["confidence"]
        assert item.source == facts[item.fact_id]["source"]
        assert set(item.provenance_event_ids) <= event_ids
        assert item.missing_event_ids == ()


def test_confidence_is_copied_exactly_and_never_aggregated() -> None:
    entries = three_round_match()
    result = aggregate(entries)
    supplied = {
        e["evaluation_id"]: e["confidence"]
        for entry in entries
        if entry.output
        for e in entry.output["evaluations"]
    }
    assert {ref.evaluation_id: ref.confidence for ref in result.evaluations} == supplied
    flat = json.dumps(result.to_dict())
    for forbidden in ("mean_confidence", "average_confidence", "match_confidence"):
        assert forbidden not in flat


def test_no_match_level_verdict_score_or_weight_exists_anywhere_in_the_output() -> None:
    forbidden = {
        "match_label",
        "match_verdict",
        "verdict",
        "overall",
        "overall_label",
        "score",
        "total_score",
        "weight",
        "weights",
        "summary_label",
    }

    def keys(value: Any) -> set[str]:
        if isinstance(value, dict):
            return set(value) | {key for item in value.values() for key in keys(item)}
        if isinstance(value, list):
            return {key for item in value for key in keys(item)}
        return set()

    assert not keys(aggregate(three_round_match()).to_dict()) & forbidden


def test_all_input_orderings_give_the_identical_result() -> None:
    entries = three_round_match()
    outputs = {dumped(aggregate(list(order))) for order in itertools.permutations(entries)}
    assert len(outputs) == 1


def test_inputs_are_never_modified_and_result_is_deterministic_json() -> None:
    entries = three_round_match()
    before = deepcopy([(item.round_package, item.output) for item in entries])
    first, second = aggregate(entries), aggregate(entries)
    assert [(item.round_package, item.output) for item in entries] == before
    assert dumped(first) == dumped(second)
    json.loads(dumped(first))  # allow_nan=False: no NaN/Infinity can leak out


# ----------------------------------------------------------------- identity conflicts


def test_rounds_from_different_matches_are_refused_not_merged() -> None:
    mixed = [make_round("TC-006", round_no=1), make_round("TC-017", round_no=2, match_id="M-OTHER")]
    with pytest.raises(MatchAggregationError, match="異なるmatch_id"):
        aggregate(mixed)


def test_declared_match_id_must_agree_with_the_rounds() -> None:
    with pytest.raises(MatchAggregationError, match="異なるmatch_id"):
        aggregate(three_round_match(), match_id="M-OTHER")


def test_output_must_belong_to_its_own_package() -> None:
    entry = make_round("TC-006", round_no=1)
    wrong_match = with_output(entry, lambda out: out.update(match_id="M-OTHER"))
    wrong_round = with_output(entry, lambda out: out.update(round_no=2))
    with pytest.raises(MatchAggregationError, match="match_id"):
        aggregate([wrong_match])
    with pytest.raises(MatchAggregationError, match="round_no"):
        aggregate([wrong_round])


@pytest.mark.parametrize("bad", [None, "", 0, -1, True, 1.5, "1"])
def test_round_package_without_a_valid_round_no_is_refused(bad: Any) -> None:
    entry = make_round("TC-006", round_no=1)
    package = {**entry.round_package, "round_no": bad}
    with pytest.raises(MatchAggregationError):
        aggregate([replace(entry, round_package=package, output=None)])


def test_same_round_supplied_twice_with_same_content_is_counted_once() -> None:
    entry = make_round("TC-006", round_no=1)
    result = aggregate([entry, entry, deepcopy(entry)])
    assert len(result.evaluations) == 1
    assert result.rule("AIM-02").counts["good"] == 1  # type: ignore[union-attr]
    duplicates = result.issues_with_code(ma.DUPLICATE_ROUND_INPUT_IGNORED)
    assert len(duplicates) == 2 and all(item.round_no == 1 for item in duplicates)


def test_same_round_id_with_different_content_is_refused() -> None:
    first = make_round("TC-006", round_no=1)
    other = make_round("TC-016", round_no=1)
    with pytest.raises(MatchAggregationError, match="内容の異なる"):
        aggregate([first, other])


def test_evaluation_id_reused_by_two_rounds_is_refused() -> None:
    first, second = make_round("TC-006", round_no=1), make_round("TC-016", round_no=2)
    assert first.output and second.output
    reused = first.output["evaluations"][0]["evaluation_id"]

    def set_id(out: dict[str, Any]) -> None:
        out["evaluations"][0]["evaluation_id"] = reused

    with pytest.raises(MatchAggregationError, match="複数のRound"):
        aggregate([first, with_output(second, set_id)])


def test_identity_conflicts_never_return_a_partial_result() -> None:
    mixed = [make_round("TC-006", round_no=1), make_round("TC-017", round_no=2, match_id="M-X")]
    with pytest.raises(ContractValidationError):
        aggregate(mixed)


# ---------------------------------------------------------------- incomplete material


def test_partially_observed_round_is_flagged_but_its_evaluations_stay_visible() -> None:
    entries = [make_round("TC-006", round_no=1), make_round("TC-015", round_no=2)]
    result = aggregate(entries, expected_round_numbers=[1, 2])
    assert result.completeness.status == ma.COMPLETENESS_INCOMPLETE
    assert result.completeness.rounds_timeline_not_complete == (2,)
    assert ma.ROUND_TIMELINE_PARTIAL_CODE in result.completeness.blocking_reasons
    flagged = result.issues_with_code(ma.ROUND_TIMELINE_PARTIAL_CODE)
    assert [item.round_no for item in flagged] == [2]
    assert result.rule("POS-01").counts["unscored"] == 1  # type: ignore[union-attr]


def test_zero_timeline_completeness_is_unavailable_not_a_measured_fraction() -> None:
    package = case_package("TC-006", round_no=1)
    package["observation_quality"]["timeline_completeness"] = 0.0
    result = aggregate([RoundInput.from_round_analysis(analyze_package(package))])
    assert result.rounds[0].timeline == "unavailable"
    assert result.issues_with_code(ma.ROUND_TIMELINE_UNAVAILABLE_CODE)
    assert result.completeness.status == ma.COMPLETENESS_INCOMPLETE


def test_missing_intervals_make_a_full_looking_round_partial() -> None:
    package = case_package("TC-006", round_no=1)
    package["observation_quality"]["missing_intervals"] = [{"start_sec": 10.0, "end_sec": 20.0}]
    result = aggregate([RoundInput.from_round_analysis(analyze_package(package))])
    assert result.rounds[0].timeline == "partial"


def test_round_without_an_evaluation_is_not_evaluated_and_never_scored() -> None:
    evaluated = make_round("TC-006", round_no=1)
    pending = replace(
        make_round("TC-016", round_no=2), output=None, evaluation_failure="API timeout"
    )
    result = aggregate([evaluated, pending], expected_round_numbers=[1, 2])
    assert result.completeness.status == ma.COMPLETENESS_INCOMPLETE
    assert result.completeness.rounds_not_evaluated == (2,)
    summary = result.rounds[1]
    assert summary.status == ma.ROUND_NOT_EVALUATED
    assert summary.failure == "API timeout"
    assert summary.label_counts == {"good": 0, "improve": 0, "unscored": 0}
    assert result.rule("AIM-01") is None  # nothing is invented for the missing Round
    assert [ref.round_no for ref in result.evaluations] == [1]


def test_round_number_gap_is_reported_and_never_filled_from_neighbours() -> None:
    result = aggregate([make_round("TC-006", round_no=1), make_round("TC-017", round_no=3)])
    assert result.completeness.round_number_gaps == (2,)
    assert result.completeness.status == ma.COMPLETENESS_INCOMPLETE
    assert [item.round_no for item in result.rounds] == [1, 3]  # R2 is not synthesised
    assert all(ref.round_no != 2 for ref in result.evaluations)
    assert result.rounds[0].round_window == {"start_sec": 0.0, "end_sec": 100.0}


def test_expected_round_numbers_catch_missing_and_unexpected_rounds() -> None:
    entries = [make_round("TC-006", round_no=1), make_round("TC-017", round_no=2)]
    result = aggregate(entries, expected_round_numbers=[1, 2, 3])
    assert result.completeness.expected_rounds_missing == (3,)
    assert result.completeness.status == ma.COMPLETENESS_INCOMPLETE
    extra = aggregate(entries, expected_round_numbers=[1])
    assert [item.round_no for item in extra.issues_with_code(ma.UNEXPECTED_ROUND)] == [2]
    assert extra.completeness.status == ma.COMPLETENESS_INCOMPLETE


@pytest.mark.parametrize("bad", [[0], [-1], [True], [1.5], ["1"]])
def test_expected_round_numbers_must_be_positive_integers(bad: list[Any]) -> None:
    with pytest.raises(ValueError, match="expected_round_numbers"):
        aggregate(three_round_match(), expected_round_numbers=bad)


def test_overlapping_and_reversed_round_windows_are_flagged_not_repaired() -> None:
    overlap = aggregate(
        [
            make_round("TC-006", round_no=1, offset=0.0),
            make_round("TC-017", round_no=2, offset=50.0),
        ]
    )
    assert [item.round_no for item in overlap.issues_with_code(ma.ROUND_WINDOWS_OVERLAP)] == [2]
    assert overlap.completeness.status == ma.COMPLETENESS_INCOMPLETE
    reversed_ = aggregate(
        [
            make_round("TC-006", round_no=1, offset=400.0),
            make_round("TC-017", round_no=2, offset=0.0),
        ]
    )
    conflicts = reversed_.issues_with_code(ma.ROUND_WINDOW_ORDER_CONFLICT)
    assert [item.round_no for item in conflicts] == [2]
    assert reversed_.rounds[0].round_window == {"start_sec": 400.0, "end_sec": 500.0}


# ------------------------------------------------------------- all / some unscored


def test_all_rounds_unscored_never_synthesises_good_or_improve() -> None:
    # Only deterministic-label rules (AIM-02 / AIM-03) are gated to ``unscored`` by low
    # fact confidence; hybrid rules are judged by the coach and only get a lower ceiling.
    entries = [
        RoundInput.from_round_analysis(
            analyze_package(lowered_confidence(case_package(case, round_no=n)))
        )
        for n, case in enumerate(("TC-005", "TC-006", "TC-017"), start=1)
    ]
    result = aggregate(entries, expected_round_numbers=[1, 2, 3])
    assert {ref.label for ref in result.evaluations} == {"unscored"}
    for rule in result.rules:
        assert rule.counts["good"] == rule.counts["improve"] == 0
        assert rule.related_counts["good"] == rule.related_counts["improve"] == 0
    assert all(
        item.label_counts["good"] == item.label_counts["improve"] == 0 for item in result.rounds
    )
    assert all(ref.unscored_reason_code == "low_confidence" for ref in result.evaluations)
    assert all(ref.confidence is not None and ref.confidence <= 0.5 for ref in result.evaluations)


def test_one_successful_round_among_failures_keeps_only_that_rounds_counts() -> None:
    ok = make_round("TC-006", round_no=1)
    failed = replace(make_round("TC-016", round_no=2), output=None, evaluation_failure="boom")
    result = aggregate([ok, failed])
    assert result.rule("AIM-02").counts["good"] == 1  # type: ignore[union-attr]
    assert result.rule("AIM-01") is None
    assert result.completeness.status == ma.COMPLETENESS_INCOMPLETE


def test_a_round_that_breaks_the_contract_is_quarantined_not_half_trusted() -> None:
    good, broken = make_round("TC-006", round_no=1), make_round("TC-017", round_no=2)

    def cite_unknown_fact(out: dict[str, Any]) -> None:
        out["evaluations"][0]["fact_refs"] = ["F-DOES-NOT-EXIST"]

    result = aggregate([good, with_output(broken, cite_unknown_fact)])
    assert result.rounds[1].status == ma.ROUND_EXCLUDED_INVALID
    assert result.completeness.rounds_excluded_invalid == (2,)
    assert [ref.round_no for ref in result.evaluations] == [1]
    assert result.rule("AIM-03") is None and result.rule("MOV-02") is None
    (issue,) = result.issues_with_code(ma.ROUND_CONTRACT_VIOLATION)
    assert issue.round_no == 2
    assert result.completeness.status == ma.COMPLETENESS_INCOMPLETE


def test_confidence_above_the_cited_facts_quarantines_the_round() -> None:
    entry = make_round("TC-006", round_no=1)

    def inflate(out: dict[str, Any]) -> None:
        out["evaluations"][0]["confidence"] = 1.0

    package = deepcopy(dict(entry.round_package))
    for fact in package["deterministic_facts"]:
        fact["confidence"] = min(float(fact["confidence"]), 0.6)
    result = aggregate([with_output(replace(entry, round_package=package), inflate)])
    assert result.rounds[0].status == ma.ROUND_EXCLUDED_INVALID
    assert result.evaluations == ()


def test_out_of_range_package_is_quarantined() -> None:
    entry = make_round("TC-006", round_no=1)
    package = deepcopy(dict(entry.round_package))
    package["events"][0]["time_sec"] = 9999.0
    result = aggregate([replace(entry, round_package=package)])
    assert result.rounds[0].status == ma.ROUND_EXCLUDED_INVALID


def test_output_candidate_scope_is_enforced_when_candidates_are_known() -> None:
    entry = make_round("TC-006", round_no=1)
    narrowed = replace(entry, candidate_rule_ids=frozenset({"DEC-01"}))
    result = aggregate([narrowed])
    assert result.rounds[0].status == ma.ROUND_EXCLUDED_INVALID


# ----------------------------------------------- provenance defences (lenient validator)


def test_unresolved_fact_ref_is_reported_and_never_shown_as_evidence_backed() -> None:
    entry = make_round("TC-006", round_no=1)

    def cite_unknown(out: dict[str, Any]) -> None:
        out["evaluations"][0]["fact_refs"].append("F-GHOST")

    result = MatchAggregator(validator=PassThroughValidator()).aggregate(
        [with_output(entry, cite_unknown)]
    )
    (ref,) = result.evaluations
    ghost = next(item for item in ref.facts if item.fact_id == "F-GHOST")
    assert ghost.resolved is False and ghost.confidence is None
    assert ref.provenance_basis == ma.BASIS_UNRESOLVED
    assert result.issues_with_code(ma.FACT_REF_UNRESOLVED)


def test_event_cited_by_a_fact_but_absent_from_the_package_is_reported() -> None:
    entry = make_round("TC-006", round_no=1)
    package = deepcopy(dict(entry.round_package))
    cited = next(f for f in package["deterministic_facts"] if f["provenance_event_ids"])
    cited["provenance_event_ids"].append("E-GHOST")
    ref_id = cited["fact_id"]

    def cite(out: dict[str, Any]) -> None:
        if ref_id not in out["evaluations"][0]["fact_refs"]:
            out["evaluations"][0]["fact_refs"].append(ref_id)

    result = MatchAggregator(validator=PassThroughValidator()).aggregate(
        [with_output(replace(entry, round_package=package), cite)]
    )
    (ref,) = result.evaluations
    fact = next(item for item in ref.facts if item.fact_id == ref_id)
    assert fact.missing_event_ids == ("E-GHOST",)
    assert ref.provenance_basis == ma.BASIS_UNRESOLVED


def test_default_validator_keeps_a_round_with_a_ghost_event_reference_out_of_the_counts() -> None:
    entry = make_round("TC-006", round_no=1)
    package = deepcopy(dict(entry.round_package))
    next(f for f in package["deterministic_facts"] if f["provenance_event_ids"])[
        "provenance_event_ids"
    ].append("E-GHOST")
    result = aggregate([replace(entry, round_package=package)])
    assert result.rounds[0].status == ma.ROUND_EXCLUDED_INVALID
    assert result.rules == ()


def test_evaluation_without_facts_is_evidence_only_or_none_never_fact_backed() -> None:
    entry = make_round("TC-006", round_no=1)

    def drop_facts(out: dict[str, Any]) -> None:
        out["evaluations"][0]["fact_refs"] = []

    result = MatchAggregator(validator=PassThroughValidator()).aggregate(
        [with_output(entry, drop_facts)]
    )
    (ref,) = result.evaluations
    assert ref.facts == ()
    assert ref.provenance_basis in {ma.BASIS_EVIDENCE_ONLY, ma.BASIS_NONE}
    assert ref.provenance_basis != ma.BASIS_FACTS

    def drop_all(out: dict[str, Any]) -> None:
        out["evaluations"][0]["fact_refs"] = []
        out["evaluations"][0]["evidence"] = []

    bare = MatchAggregator(validator=PassThroughValidator()).aggregate(
        [with_output(entry, drop_all)]
    )
    assert bare.evaluations[0].provenance_basis == ma.BASIS_NONE


def test_duplicate_evaluation_id_inside_a_round_never_double_counts() -> None:
    entry = make_round("TC-006", round_no=1)

    def duplicate(out: dict[str, Any]) -> None:
        out["evaluations"].append(deepcopy(out["evaluations"][0]))

    doubled = with_output(entry, duplicate)
    strict = aggregate([doubled])
    assert strict.rounds[0].status == ma.ROUND_EXCLUDED_INVALID
    assert strict.evaluations == ()
    lenient = MatchAggregator(validator=PassThroughValidator()).aggregate([doubled])
    assert lenient.rounds[0].status == ma.ROUND_EXCLUDED_INVALID
    assert lenient.issues_with_code(ma.DUPLICATE_EVALUATION_ID)
    assert lenient.evaluations == ()


# ------------------------------------------------------------------------- empty match


def test_empty_match_is_explicitly_empty_not_complete() -> None:
    result = aggregate([])
    assert result.match_id is None
    assert result.completeness.status == ma.COMPLETENESS_INCOMPLETE
    assert ma.NO_ROUNDS in result.completeness.blocking_reasons
    assert result.rounds == () and result.rules == () and result.evaluations == ()
    json.loads(dumped(result))


def test_empty_match_with_expectations_lists_every_expected_round_as_missing() -> None:
    result = aggregate([], match_id=MATCH, expected_round_numbers=[1, 2])
    assert result.match_id == MATCH
    assert result.completeness.expected_rounds_missing == (1, 2)
    assert result.completeness.status == ma.COMPLETENESS_INCOMPLETE


# ---------------------------------------------------- match context / display metadata


def test_match_level_and_whole_match_aggregated_rules_stay_distinct() -> None:
    entries = [make_round("TC-016", round_no=1), make_round("TC-006", round_no=2)]
    unverified = aggregate(entries)
    aim01, aim02 = unverified.rule("AIM-01"), unverified.rule("AIM-02")
    assert aim01 is not None and aim02 is not None
    assert aim01.level == "match" and aim02.level == "micro"
    assert aim01.needs_match_context and aim02.needs_match_context
    assert aim01.uses_whole_match_aggregation and aim02.uses_whole_match_aggregation
    assert aim01.match_context_unverified and aim02.match_context_unverified
    verified = aggregate(entries, expected_round_numbers=[1, 2])
    assert verified.rule("AIM-01").match_context_unverified is False  # type: ignore[union-attr]


def test_rule_that_needs_no_match_context_is_not_marked_unverified() -> None:
    result = aggregate([make_round("TC-001", round_no=1)])
    dec01 = result.rule("DEC-01")
    assert dec01 is not None
    assert dec01.needs_match_context is False
    assert dec01.match_context_unverified is False


def test_policy_metadata_comes_from_the_rule_config_without_conversion() -> None:
    config = {item["id"]: item for item in rules_config()["rules"]}
    result = aggregate(three_round_match())
    for rule in result.rules:
        policy = config[rule.rule_id]["aggregation_policy"]
        assert rule.display_limit == policy["max_display_exemplars_per_match"]
        assert rule.aggregate_repeated_occurrences == policy["aggregate_repeated_occurrences"]
        assert rule.summary_required_if_occurrences_at_least == policy.get(
            "summary_required_if_occurrences_at_least"
        )


def test_display_limit_reached_warns_that_counts_may_be_a_lower_bound() -> None:
    limit = TemporalPolicyTable.load().get("AIM-02").max_display_exemplars_per_match  # type: ignore[union-attr]
    entries = [make_round("TC-006", round_no=n) for n in range(1, limit + 1)]
    result = aggregate(entries)
    rule = result.rule("AIM-02")
    assert rule is not None and rule.display_limit_reached
    assert result.issues_with_code(ma.DISPLAY_LIMIT_REACHED)
    below = aggregate(entries[: limit - 1]) if limit > 1 else None
    if below is not None:
        assert below.rule("AIM-02").display_limit_reached is False  # type: ignore[union-attr]


def test_context_requirements_are_forwarded_per_round_without_new_judgement() -> None:
    entries = [make_round("TC-012", round_no=1), make_round("TC-006", round_no=2)]
    result = aggregate(entries)
    eco = result.rule("ECO-01")
    assert eco is not None
    ((round_no, context),) = eco.context_by_round
    assert round_no == 1
    assert context.needs_previous_round_context
    assert context.missing_context == ()  # TC-012 carries previous_round_context

    stripped = deepcopy(dict(entries[0].round_package))
    stripped["previous_round_context"] = None
    missing = aggregate([replace(entries[0], round_package=stripped)])
    ((_, lacking),) = missing.rule("ECO-01").context_by_round  # type: ignore[union-attr]
    assert lacking.missing_context == ("previous_round_context",)
    # the evaluation itself is untouched: the gap is surfaced, nothing is re-judged
    assert missing.evaluations[0].label == result.evaluations[0].label


def test_numeric_helpers_never_turn_null_or_non_finite_values_into_numbers() -> None:
    assert ma._number_or_none(0.0) == 0.0
    assert ma._number_or_none(0) == 0.0
    for bad in (None, True, False, "0.5", math.nan, math.inf, -math.inf, [], {}):
        assert ma._number_or_none(bad) is None
    assert ma._interval({"start_sec": 1, "end_sec": math.nan}) is None
    assert ma._interval({"start_sec": 1}) is None
    assert ma._interval({"start_sec": 1, "end_sec": 2.5}) == {"start_sec": 1.0, "end_sec": 2.5}
