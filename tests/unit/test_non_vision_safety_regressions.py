"""Confidence / provenance / aggregation safety regressions (non-vision pipeline).

Everything is synthetic: fixtures are derived from ``tests/cases`` Round Packages or are
hand-written dictionaries. Nothing here is real footage and nothing is a new quality
judgement; the expectations come from contracts that already exist
(``SchemaValidator.validate_ai_output``, the deterministic 0.90 gate, the aggregation
policy of the rules JSON).

Layout
  1. confidence  - the cap, boundaries, 0.0 vs null, non-finite, malformed types
  2. provenance  - fact / event / match / round ownership
  3. aggregation - EvaluationAggregator + same-basis UNSCORED merging, property checks
  4. match view  - the Task A aggregator keeps the same guarantees
  5. snapshot    - audit of the known snapshot-fact issues (reproduction, not redefinition)

Tests named ``test_known_limitation_*`` / ``test_known_consequence_*`` pin *current* behaviour
so a later, approved change has to flip them knowingly. D-1 (a merged evaluation exceeding the
weakest fact it cites) was approved and fixed; its regression tests are ordinary passing tests.
"""

from __future__ import annotations

import copy
import itertools
import math
import random
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from match_fixtures import (
    analysis_for,
    registry,
    round_input,
    rules_config,
)
from test_match_aggregation import with_output
from test_snapshot_source_confidence import build, hud_observation

from valorant_ai_coach.application.match_aggregation import (
    LABELS,
    ROUND_EXCLUDED_INVALID,
    ROUND_INCLUDED,
    MatchAggregator,
)
from valorant_ai_coach.facts import FactBuilder
from valorant_ai_coach.rules import DeterministicRuleEngine, EvaluationAggregator
from valorant_ai_coach.schema_validation import ContractValidationError, SchemaValidator

VALIDATOR = SchemaValidator()


def case_pair(case_id: str = "TC-006", round_no: int = 1) -> tuple[dict[str, Any], dict[str, Any]]:
    analysis = analysis_for(case_id, round_no=round_no)
    return copy.deepcopy(dict(analysis.round_package)), copy.deepcopy(dict(analysis.output))


def validate(output: dict[str, Any], package: dict[str, Any]) -> None:
    VALIDATOR.validate_ai_output(copy.deepcopy(output), round_package=copy.deepcopy(package))


def fact_confidence(package: dict[str, Any], fact_id: str) -> float:
    return next(
        float(f["confidence"]) for f in package["deterministic_facts"] if f["fact_id"] == fact_id
    )


# =============================================================================== 1. confidence


def test_the_cap_is_the_weakest_cited_fact_regardless_of_citation_order() -> None:
    package, output = case_pair()
    strong, weak = "F008", "F007"  # 0.98 and 0.90
    assert fact_confidence(package, strong) > fact_confidence(package, weak)
    for refs in ([strong, weak], [weak, strong]):
        accepted = copy.deepcopy(output)
        accepted["evaluations"][0]["fact_refs"] = refs
        accepted["evaluations"][0]["confidence"] = fact_confidence(package, weak)
        validate(accepted, package)
        rejected = copy.deepcopy(accepted)
        rejected["evaluations"][0]["confidence"] = fact_confidence(package, strong)
        with pytest.raises(ContractValidationError, match="最小confidence"):
            validate(rejected, package)


def test_confidence_exactly_at_the_cap_passes_and_a_visible_excess_does_not() -> None:
    package, output = case_pair()
    cap = fact_confidence(package, output["evaluations"][0]["fact_refs"][0])
    at_cap = copy.deepcopy(output)
    at_cap["evaluations"][0]["confidence"] = cap
    validate(at_cap, package)
    float_noise = copy.deepcopy(output)
    float_noise["evaluations"][0]["confidence"] = cap + 1e-10
    validate(float_noise, package)  # the existing 1e-9 slack is for float noise only
    over = copy.deepcopy(output)
    over["evaluations"][0]["confidence"] = cap + 1e-6
    with pytest.raises(ContractValidationError, match="最小confidence"):
        validate(over, package)


def test_zero_confidence_is_a_real_value_but_null_or_missing_is_not() -> None:
    package, output = case_pair()
    zero = copy.deepcopy(output)
    zero["evaluations"][0]["confidence"] = 0.0
    validate(zero, package)  # 0.0 is "measured as no confidence", it is not "undefined"
    null = copy.deepcopy(output)
    null["evaluations"][0]["confidence"] = None
    with pytest.raises(ContractValidationError):
        validate(null, package)
    missing = copy.deepcopy(output)
    del missing["evaluations"][0]["confidence"]
    with pytest.raises(ContractValidationError):
        validate(missing, package)


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf])
@pytest.mark.parametrize(
    "where",
    ["confidence", "evidence_range.start_sec", "display_clip.end_sec", "evidence.time_sec"],
)
def test_non_finite_numbers_are_rejected_wherever_they_appear_in_an_evaluation(
    where: str, bad: float
) -> None:
    package, output = case_pair()
    evaluation = output["evaluations"][0]
    if where == "confidence":
        evaluation["confidence"] = bad
    elif where == "evidence.time_sec":
        evaluation["evidence"][0]["time_sec"] = bad
    else:
        field, key = where.split(".")
        evaluation[field][key] = bad
    with pytest.raises(ContractValidationError):
        validate(output, package)


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf])
def test_non_finite_fact_confidence_cannot_enter_through_the_round_package(bad: float) -> None:
    package, _ = case_pair()
    package["deterministic_facts"][0]["confidence"] = bad
    with pytest.raises(ContractValidationError):
        VALIDATOR.validate_round_package(package)


def engine_decision(confidence: Any, *, present: bool = True) -> Any:
    fact: dict[str, Any] = {
        "fact_id": "F1",
        "key": "preaim_lead_sec",
        "value": 0.7,
        "provenance_event_ids": [],
    }
    if present:
        fact["confidence"] = confidence
    return DeterministicRuleEngine().evaluate("AIM-02", [fact], [])


@pytest.mark.parametrize(
    "undefined",
    [None, True, False, "0.95", "1", "nan", [0.99], {"v": 0.99}, math.nan, math.inf, -math.inf],
)
def test_an_undefined_or_malformed_fact_confidence_never_reaches_the_deterministic_gate(
    undefined: Any,
) -> None:
    decision = engine_decision(undefined)
    assert decision is not None
    assert decision.label == "unscored" and decision.unscored_reason_code == "low_confidence"
    assert decision.confidence <= 0.5


def test_a_fact_without_any_confidence_never_reaches_the_deterministic_gate() -> None:
    decision = engine_decision(None, present=False)
    assert decision is not None and decision.label == "unscored"


@pytest.mark.parametrize(
    ("confidence", "label"), [(0.0, "unscored"), (0.8999, "unscored"), (0.9, "good"), (1, "good")]
)
def test_the_deterministic_gate_edges_use_real_numbers_only(confidence: Any, label: str) -> None:
    decision = engine_decision(confidence)
    assert decision is not None and decision.label == label


def test_zero_and_null_confidence_stay_distinguishable_in_the_match_view() -> None:
    entry = round_input("TC-006", round_no=1)
    zero = with_output(entry, lambda out: out["evaluations"][0].update(confidence=0.0))
    result = MatchAggregator().aggregate([zero])
    assert result.evaluations[0].confidence == 0.0  # not None, not dropped, not raised


def test_an_evaluation_with_image_evidence_and_no_fact_refs_is_not_rejected() -> None:
    package, output = case_pair()
    evaluation = output["evaluations"][0]
    evaluation["fact_refs"] = []
    evaluation["confidence"] = 0.97  # no cited fact: nothing to cap against (existing contract)
    validate(output, package)
    entry = round_input("TC-006", round_no=1)

    def frame_only(out: dict[str, Any]) -> None:
        out["evaluations"][0]["fact_refs"] = []
        out["evaluations"][0]["confidence"] = 0.97

    result = MatchAggregator().aggregate([with_output(entry, frame_only)])
    assert result.rounds[0].status == ROUND_INCLUDED
    assert result.evaluations[0].provenance_basis == "evidence_only"
    assert result.evaluations[0].facts == ()


# =============================================================================== 2. provenance


def test_a_fact_id_that_only_exists_in_another_round_is_rejected() -> None:
    first_package, first_output = case_pair("TC-006", 1)
    second_package, _ = case_pair("TC-017", 2)
    foreign = copy.deepcopy(second_package["deterministic_facts"][0])
    foreign["fact_id"] = "F900"
    second_package["deterministic_facts"].append(foreign)
    first_output["evaluations"][0]["fact_refs"] = ["F900"]
    with pytest.raises(ContractValidationError, match="未知のfact_id"):
        validate(first_output, first_package)


@pytest.mark.parametrize("ghost", ["f008", " F008", "F008 ", "F0008", ""])
def test_fact_references_must_match_exactly_not_loosely(ghost: str) -> None:
    package, output = case_pair()
    output["evaluations"][0]["fact_refs"] = [ghost]
    with pytest.raises(ContractValidationError):
        validate(output, package)


def test_duplicate_fact_references_are_rejected_not_double_counted() -> None:
    package, output = case_pair()
    ref = output["evaluations"][0]["fact_refs"][0]
    output["evaluations"][0]["fact_refs"] = [ref, ref]
    with pytest.raises(ContractValidationError):
        validate(output, package)


def test_a_fact_citing_an_event_of_another_round_is_rejected() -> None:
    package, _ = case_pair("TC-006", 1)
    other, _ = case_pair("TC-017", 2)
    foreign_event = next(e["event_id"] for e in other["events"] if e["event_id"] not in
                         {x["event_id"] for x in package["events"]})
    cited = next(f for f in package["deterministic_facts"] if f["provenance_event_ids"])
    cited["provenance_event_ids"].append(foreign_event)
    with pytest.raises(ContractValidationError):
        VALIDATOR.validate_round_package(package)


def test_facts_of_different_matches_cannot_be_mixed_in_one_match_view() -> None:
    mine = round_input("TC-006", round_no=1)
    other = round_input("TC-017", round_no=2, match_id="M-OTHER-MATCH")
    from valorant_ai_coach.application.match_aggregation import MatchAggregationError

    with pytest.raises(MatchAggregationError, match="異なるmatch_id"):
        MatchAggregator().aggregate([mine, other])


def test_an_evaluation_citing_a_fact_that_only_the_neighbouring_round_has_is_quarantined() -> None:
    first, second = round_input("TC-006", round_no=1), round_input("TC-017", round_no=2)
    package = copy.deepcopy(dict(first.round_package))
    foreign = copy.deepcopy(package["deterministic_facts"][0])
    foreign["fact_id"] = "F901"
    package["deterministic_facts"].append(foreign)

    def cite(out: dict[str, Any]) -> None:
        out["evaluations"][0]["fact_refs"] = ["F901"]  # exists in R1's package, not in R2's

    result = MatchAggregator().aggregate(
        [replace(first, round_package=package), with_output(second, cite)]
    )
    assert result.rounds[0].status == ROUND_INCLUDED
    assert result.rounds[1].status == ROUND_EXCLUDED_INVALID
    assert [ref.round_no for ref in result.evaluations] == [1]


def test_rule_identity_survives_merging_in_the_display_aggregator() -> None:
    aggregator = display_aggregator()
    merged = aggregator.aggregate(
        [
            ev("a", "AIM-03", "improve", 10.0, 0.9, ["F1"]),
            ev("b", "MOV-02", "improve", 10.2, 0.9, ["F1"]),
            ev("c", "MOV-01", "improve", 10.4, 0.9, ["F1"]),
        ]
    )
    assert len(merged) == 1
    assert {merged[0]["primary_rule_id"], *merged[0]["related_rule_ids"]} == {
        "AIM-03",
        "MOV-02",
        "MOV-01",
    }


# ============================================================================== 3. aggregation


def display_aggregator() -> EvaluationAggregator:
    return EvaluationAggregator(rules_config(), registry())


def ev(
    evaluation_id: str,
    rule: str,
    label: str,
    start: float,
    confidence: float,
    facts: list[str],
    reason: str | None = None,
    *,
    scope: int = 1,
    related: tuple[str, ...] = (),
) -> dict[str, Any]:
    scored = label != "unscored"
    return {
        "evaluation_id": evaluation_id,
        "primary_rule_id": rule,
        "related_rule_ids": list(related),
        "label": label,
        "confidence": confidence,
        "fact_refs": list(facts),
        "evidence_range": {"start_sec": start, "end_sec": start + 1.5},
        "display_clip": {"start_sec": start - 3, "end_sec": start + 4} if scored else None,
        "evidence": [],
        "missing_information": [],
        "unscored_reason_code": reason,
        "_aggregation_scope": scope,
    }


def unscored(evaluation_id: str, rule: str, start: float, facts: list[str], reason: str) -> Any:
    return ev(evaluation_id, rule, "unscored", start, 0.3, facts, reason)


@pytest.mark.parametrize(
    ("second", "merged"),
    [
        (dict(rule="MOV-02", facts=["F1"], reason="low_confidence"), True),
        (dict(rule="MOV-01", facts=["F1"], reason="low_confidence"), True),
        (dict(rule="MOV-02", facts=["F1"], reason="occluded"), False),  # different cause
        (dict(rule="MOV-02", facts=["F2"], reason="low_confidence"), False),  # different basis
        (dict(rule="MOV-02", facts=["F1", "F2"], reason="low_confidence"), False),  # superset
        (dict(rule="DEC-01", facts=["F1"], reason="low_confidence"), False),  # other group
        (dict(rule="AIM-02", facts=["F1"], reason="low_confidence"), False),  # not in a group
    ],
)
def test_unscored_items_merge_only_when_reason_and_fact_basis_are_identical(
    second: dict[str, Any], merged: bool
) -> None:
    first = unscored("a", "AIM-03", 10.0, ["F1"], "low_confidence")
    other = unscored("b", second["rule"], 60.0, second["facts"], second["reason"])
    result = display_aggregator().aggregate([first, other])
    assert (len(result) == 1) is merged
    assert {item["label"] for item in result} == {"unscored"}


def test_unscored_without_fact_refs_is_never_merged_even_with_the_same_reason() -> None:
    result = display_aggregator().aggregate(
        [
            unscored("a", "AIM-03", 10.0, [], "low_confidence"),
            unscored("b", "MOV-02", 60.0, [], "low_confidence"),
        ]
    )
    assert len(result) == 2


def test_fact_ref_order_does_not_change_whether_unscored_items_are_the_same_basis() -> None:
    result = display_aggregator().aggregate(
        [
            unscored("a", "AIM-03", 10.0, ["F1", "F2"], "low_confidence"),
            unscored("b", "MOV-02", 60.0, ["F2", "F1"], "low_confidence"),
        ]
    )
    assert len(result) == 1 and result[0]["related_rule_ids"] == ["MOV-02"]


def test_unscored_never_absorbs_or_becomes_a_scored_evaluation_on_the_same_basis() -> None:
    result = display_aggregator().aggregate(
        [
            ev("a", "AIM-03", "improve", 10.0, 0.9, ["F1"]),
            unscored("b", "MOV-02", 10.0, ["F1"], "low_confidence"),
            ev("c", "MOV-01", "good", 10.0, 0.9, ["F1"]),
        ]
    )
    assert sorted(item["label"] for item in result) == ["good", "improve", "unscored"]
    by_id = {item["evaluation_id"]: item for item in result}
    assert by_id["b"]["label"] == "unscored" and by_id["b"]["primary_rule_id"] == "MOV-02"


def random_evaluations(seed: int, size: int = 6, *, ties: bool = False) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    rules = ["AIM-02", "AIM-03", "MOV-01", "MOV-02", "DEC-01", "DEC-02", "INFO-03", "ECO-02"]
    reasons = ["low_confidence", "occluded"]
    used: set[tuple[float, float]] = set()
    items: list[dict[str, Any]] = []
    for index in range(size):
        label = rng.choice(["good", "improve", "unscored"])
        # the contract caps an unscored evaluation at 0.5
        levels = [0.3, 0.5] if label == "unscored" else [0.5, 0.7, 0.85, 0.9, 0.95]
        while True:
            start = float(rng.choice(range(0, 120, 3)))
            confidence = rng.choice(levels)
            if ties or (start, confidence) not in used:
                used.add((start, confidence))
                break
        facts = sorted(rng.sample(["F1", "F2", "F3"], rng.randint(1, 2)))
        items.append(
            ev(
                f"E{index}",
                rng.choice(rules),
                label,
                start,
                confidence,
                facts,
                rng.choice(reasons) if label == "unscored" else None,
                scope=rng.choice([1, 2]),
            )
        )
    return items


SEEDS = range(60)


@pytest.mark.parametrize("seed", SEEDS)
def test_aggregation_never_invents_labels_ids_rules_or_confidence(seed: int) -> None:
    items = random_evaluations(seed)
    by_id = {item["evaluation_id"]: item for item in items}
    rule_ids = {item["primary_rule_id"] for item in items}
    result = display_aggregator().aggregate([copy.deepcopy(item) for item in items])
    fact_caps: dict[str, float] = {}
    for item in items:
        for ref in item["fact_refs"]:
            fact_caps[ref] = max(fact_caps.get(ref, 0.0), float(item["confidence"]))
    assert len(result) <= len(items)
    for kept in result:
        origin = by_id[kept["evaluation_id"]]
        assert kept["label"] == origin["label"]  # no GOOD/IMPROVE/UNSCORED crossing
        # a merged item takes the weakest member's confidence: never raised above the id it keeps
        assert kept["confidence"] <= origin["confidence"]
        # the contract in miniature: no cited fact may be weaker than the evaluation citing it.
        # A fact's cap is the strongest confidence any input evaluation placed on it (so every
        # input is valid), and a merged item that cites the union must still sit under all caps.
        assert kept["confidence"] <= min(fact_caps[ref] for ref in kept["fact_refs"])
        assert kept["primary_rule_id"] == origin["primary_rule_id"]
        assert set(kept["related_rule_ids"]) <= rule_ids - {kept["primary_rule_id"]}
        assert kept["_aggregation_scope"] == origin["_aggregation_scope"]
    for label in LABELS:
        assert sum(k["label"] == label for k in result) <= sum(i["label"] == label for i in items)
    assert not any(
        k["label"] in {"good", "improve"} and by_id[k["evaluation_id"]]["label"] == "unscored"
        for k in result
    )


@pytest.mark.parametrize("seed", SEEDS)
def test_aggregation_counts_do_not_depend_on_input_order(seed: int) -> None:
    items = random_evaluations(seed, size=5)  # distinct (time, confidence): no exact ties
    outcomes = set()
    for order in itertools.permutations(items):
        result = display_aggregator().aggregate([copy.deepcopy(item) for item in order])
        outcomes.add(
            tuple(
                sorted(
                    (k["evaluation_id"], k["primary_rule_id"], tuple(k["related_rule_ids"]))
                    for k in result
                )
            )
        )
    assert len(outcomes) == 1


@pytest.mark.parametrize("seed", SEEDS)
def test_aggregation_is_idempotent(seed: int) -> None:
    aggregator = display_aggregator()
    once = aggregator.aggregate(random_evaluations(seed))
    twice = aggregator.aggregate(copy.deepcopy(once))

    def members(items: list[dict[str, Any]]) -> list[tuple[str, tuple[str, ...]]]:
        # a merge replaces an item in place, so only the *membership* is compared, not the order
        return sorted((k["evaluation_id"], tuple(k["related_rule_ids"])) for k in items)

    assert members(once) == members(twice)


def test_every_input_rule_stays_visible_while_no_display_limit_is_hit() -> None:
    limits = {r["id"]: r["aggregation_policy"]["max_display_exemplars_per_match"]
              for r in rules_config()["rules"]}
    checked = 0
    for seed in SEEDS:
        items = random_evaluations(seed)
        per_rule: dict[str, int] = {}
        for item in items:
            per_rule[item["primary_rule_id"]] = per_rule.get(item["primary_rule_id"], 0) + 1
        if any(count > limits[rule] for rule, count in per_rule.items()):
            continue
        result = display_aggregator().aggregate(copy.deepcopy(items))
        visible = {k["primary_rule_id"] for k in result} | {
            r for k in result for r in k["related_rule_ids"]
        }
        assert {i["primary_rule_id"] for i in items} <= visible
        checked += 1
    assert checked > 20  # the property was exercised, not skipped


def test_good_and_improve_in_the_same_scene_are_both_kept() -> None:
    result = display_aggregator().aggregate(
        [
            ev("a", "AIM-03", "good", 10.0, 0.9, ["F1"]),
            ev("b", "AIM-03", "improve", 10.5, 0.9, ["F2"]),
        ]
    )
    assert sorted(item["label"] for item in result) == ["good", "improve"]


def test_known_limitation_display_limit_counts_per_rule_so_early_good_can_hide_improve() -> None:
    """Characterisation: ``max_display_exemplars_per_match`` is per rule, not per label.

    Three early GOOD evaluations fill AIM-02's budget (3), so a later IMPROVE of the same
    rule is dropped from the aggregated result. No label is mixed or invented, but the
    stored result under-represents IMPROVE. Changing this is a behaviour decision.
    """
    items = [
        ev("g1", "AIM-02", "good", 100.0, 0.9, ["F1"]),
        ev("g2", "AIM-02", "good", 300.0, 0.9, ["F2"]),
        ev("g3", "AIM-02", "good", 500.0, 0.9, ["F3"]),
        ev("i1", "AIM-02", "improve", 700.0, 0.95, ["F4"]),
    ]
    result = display_aggregator().aggregate(items)
    assert [item["evaluation_id"] for item in result] == ["g1", "g2", "g3"]


def test_known_limitation_an_exact_time_and_confidence_tie_keeps_the_first_supplied_id() -> None:
    """Characterisation: the count is order independent, the surviving id is not (ties only)."""
    a = ev("a", "AIM-02", "good", 10.0, 0.9, ["F1"])
    b = ev("b", "AIM-02", "good", 10.0, 0.9, ["F2"])
    forward = display_aggregator().aggregate([copy.deepcopy(a), copy.deepcopy(b)])
    backward = display_aggregator().aggregate([copy.deepcopy(b), copy.deepcopy(a)])
    assert len(forward) == len(backward) == 1
    assert {forward[0]["evaluation_id"], backward[0]["evaluation_id"]} == {"a", "b"}


# D-1 (approved): a merged evaluation cites the union of its members' facts, so it may not claim
# more confidence than its weakest member (each member is already capped by its own facts).
MERGE_PATHS: dict[str, tuple[str, list[tuple[str, str, float, list[str]]]]] = {
    # case, then (evaluation_id, rule, confidence, fact_refs) per member
    "same_rule": ("TC-006", [("a", "AIM-02", 0.98, ["F008"]), ("b", "AIM-02", 0.90, ["F007"])]),
    "dedup_group": ("TC-017", [("a", "AIM-03", 0.98, ["F010"]), ("b", "MOV-02", 0.90, ["F007"])]),
}


def schema_valid_member(
    template: dict[str, Any], evaluation_id: str, rule: str, confidence: float, facts: list[str]
) -> dict[str, Any]:
    """A real, schema-complete evaluation (copied from a case) with only identity/basis changed."""
    item = copy.deepcopy(template)
    item.update(
        evaluation_id=evaluation_id,
        clip_id=f"clip-{evaluation_id}",
        primary_rule_id=rule,
        related_rule_ids=[],
        confidence=confidence,
        fact_refs=list(facts),
        _aggregation_scope=1,
    )
    return item


def merge_inputs(path: str) -> list[dict[str, Any]]:
    """The same members as minimal dictionaries, for order / identity checks."""
    gap = 3.0 if path == "same_rule" else 0.2  # same-rule dedup window vs same-scene overlap
    return [
        ev(eid, rule, "good" if path == "same_rule" else "improve", 10.0 + gap * index, conf, facts)
        for index, (eid, rule, conf, facts) in enumerate(MERGE_PATHS[path][1])
    ]


@pytest.mark.parametrize("flip", [False, True], ids=["as_listed", "reversed"])
@pytest.mark.parametrize("path", ["same_rule", "dedup_group"])
def test_merged_evaluation_keeps_the_confidence_cap_of_every_fact_it_cites(
    path: str, flip: bool
) -> None:
    """Regression for D-1, through the real contract validator (the one the pipeline re-runs)."""
    case, members = MERGE_PATHS[path]
    package, output = case_pair(case, 1)
    template = output["evaluations"][0]
    items = [schema_valid_member(template, *member) for member in members]
    merged = display_aggregator().aggregate(items[::-1] if flip else items)
    assert len(merged) == 1
    cited = {fact_id for member in members for fact_id in member[3]}
    assert set(merged[0]["fact_refs"]) == cited  # references are kept (union) ...
    assert merged[0]["confidence"] <= min(fact_confidence(package, f) for f in cited)  # ... capped
    for item in merged:
        item.pop("_aggregation_scope")
    validate({**output, "evaluations": merged}, package)


def test_the_unfixed_merge_really_fails_the_validator_for_the_cap_reason() -> None:
    """Guard for the test above: its inputs are schema-complete, so only the cap can reject it."""
    package, output = case_pair("TC-006", 1)
    template = output["evaluations"][0]
    item = schema_valid_member(template, "a", "AIM-02", 0.98, ["F008", "F007"])
    item.pop("_aggregation_scope")
    with pytest.raises(ContractValidationError, match="最小confidence"):
        validate({**output, "evaluations": [item]}, package)  # the pre-fix merge result


@pytest.mark.parametrize("path", ["same_rule", "dedup_group"])
@pytest.mark.parametrize("low_first", [False, True], ids=["high_first", "low_first"])
@pytest.mark.parametrize("flip", [False, True], ids=["as_listed", "reversed"])
def test_merged_confidence_is_the_weakest_member_in_every_time_and_input_order(
    path: str, low_first: bool, flip: bool
) -> None:
    items = merge_inputs(path)
    cited = sorted({fact_id for item in items for fact_id in item["fact_refs"]})
    if low_first:  # the weaker member also comes first in time
        items = [{**items[0], "confidence": 0.90}, {**items[1], "confidence": 0.98}]
    expected_rules = {item["primary_rule_id"] for item in items}
    merged = display_aggregator().aggregate(items[::-1] if flip else items)
    assert len(merged) == 1
    result = merged[0]
    assert result["confidence"] == 0.90  # the weakest member, whichever one was the representative
    assert sorted(result["fact_refs"]) == cited  # references kept
    assert {result["primary_rule_id"], *result["related_rule_ids"]} == expected_rules  # identity
    assert result["label"] == items[0]["label"]  # meaning unchanged


@pytest.mark.parametrize("order", list(itertools.permutations(range(3))))
def test_a_three_member_group_takes_the_weakest_of_all_three(order: tuple[int, ...]) -> None:
    members = [
        ev("a", "AIM-03", "improve", 10.0, 0.98, ["F1"]),
        ev("b", "MOV-02", "improve", 10.2, 0.90, ["F2"]),
        ev("c", "MOV-01", "improve", 10.4, 0.70, ["F3"]),
    ]
    merged = display_aggregator().aggregate([copy.deepcopy(members[i]) for i in order])
    assert len(merged) == 1
    assert merged[0]["confidence"] == 0.70
    assert sorted(merged[0]["fact_refs"]) == ["F1", "F2", "F3"]
    assert {merged[0]["primary_rule_id"], *merged[0]["related_rule_ids"]} == {
        "AIM-03",
        "MOV-02",
        "MOV-01",
    }


@pytest.mark.parametrize("order", list(itertools.permutations(range(3))))
@pytest.mark.parametrize(
    "confidences",
    [(0.98, 0.90, 0.95), (0.90, 0.98, 0.95), (0.95, 0.90, 0.98), (0.90, 0.95, 0.98)],
    ids=lambda values: "-".join(f"{value:.2f}" for value in values),
)
def test_same_rule_merge_keeps_the_strongest_member_as_representative_and_the_weakest_confidence(
    confidences: tuple[float, float, float], order: tuple[int, ...]
) -> None:
    """D-1 lowers the *confidence*; it must not change *which* evaluation represents the group.

    The representative (its id, clip and evidence window) is still the strongest member, as before
    the fix. The lowered confidence of an already merged item must not be used when comparing it
    with the next member, otherwise a middle member would replace the strongest one.
    """
    members = [
        ev(name, "AIM-02", "improve", 10.0 + index, confidence, [f"F{index + 1}"])
        for index, (name, confidence) in enumerate(zip("abc", confidences, strict=True))
    ]
    merged = display_aggregator().aggregate([copy.deepcopy(members[i]) for i in order])
    assert len(merged) == 1
    strongest = max(members, key=lambda member: member["confidence"])
    assert merged[0]["evaluation_id"] == strongest["evaluation_id"]
    assert merged[0]["confidence"] == min(confidences)
    assert sorted(merged[0]["fact_refs"]) == ["F1", "F2", "F3"]
    assert merged[0]["primary_rule_id"] == "AIM-02" and merged[0]["related_rule_ids"] == []


def test_merging_members_of_equal_confidence_changes_nothing_about_confidence() -> None:
    merged = display_aggregator().aggregate(
        [
            ev("a", "AIM-03", "improve", 10.0, 0.9, ["F1"]),
            ev("b", "MOV-02", "improve", 10.2, 0.9, ["F2"]),
        ]
    )
    assert len(merged) == 1 and merged[0]["confidence"] == 0.9


def test_a_merged_unscored_item_is_still_unscored_and_not_more_confident_than_its_members() -> None:
    merged = display_aggregator().aggregate(
        [
            ev("a", "AIM-03", "unscored", 10.0, 0.5, ["F1"], "low_confidence"),
            ev("b", "MOV-02", "unscored", 60.0, 0.3, ["F1"], "low_confidence"),
        ]
    )
    assert len(merged) == 1
    assert merged[0]["label"] == "unscored"
    assert merged[0]["unscored_reason_code"] == "low_confidence"
    assert merged[0]["confidence"] == 0.3 and merged[0]["fact_refs"] == ["F1"]


def test_known_consequence_a_weak_member_can_demote_a_merged_good_to_unscored() -> None:
    """Characterisation of the approved D-1 behaviour together with the pipeline's 0.55 floor.

    Before, the merged item kept the *higher* confidence, so a 0.50 good merged with a 0.90 good
    stayed a good. Now the merged item is 0.50 and the pipeline's existing floor demotes it to
    ``unscored`` (``low_confidence``). No new label logic exists: only the existing floor acts on
    the now-honest confidence.
    """
    from valorant_ai_coach.application.pipeline import MatchAnalysisPipeline

    merged = display_aggregator().aggregate(
        [
            ev("a", "AIM-02", "good", 10.0, 0.50, ["F1"]),
            ev("b", "AIM-02", "good", 13.0, 0.90, ["F2"]),
        ]
    )
    assert len(merged) == 1 and merged[0]["confidence"] == 0.50
    enforced = MatchAnalysisPipeline._enforce_confidence_policy(merged[0])
    assert enforced["label"] == "unscored" and enforced["unscored_reason_code"] == "low_confidence"
    assert sorted(enforced["fact_refs"]) == ["F1", "F2"]  # the basis is not lost


# ================================================================================ 4. match view


def synthetic_rounds(seed: int) -> list[Any]:
    rng = random.Random(seed)
    cases = ["TC-005", "TC-006", "TC-017", "TC-026", "TC-029", "TC-016", "TC-012", "TC-018"]
    chosen = rng.sample(cases, 4)
    return [round_input(case, round_no=number) for number, case in enumerate(chosen, start=1)]


@pytest.mark.parametrize("seed", range(8))
def test_match_view_counts_equal_the_supplied_evaluations_and_never_cross_labels(
    seed: int,
) -> None:
    entries = synthetic_rounds(seed)
    supplied = [
        (e["evaluation_id"], e["primary_rule_id"], e["label"], e["confidence"])
        for entry in entries
        if entry.output
        for e in entry.output["evaluations"]
    ]
    result = MatchAggregator().aggregate(entries)
    assert sorted(
        (r.evaluation_id, r.primary_rule_id, r.label, r.confidence) for r in result.evaluations
    ) == sorted(supplied)
    for label in LABELS:
        assert sum(sum(rule.counts[label] for rule in [r]) for r in result.rules) == sum(
            item[2] == label for item in supplied
        )
    shuffled = list(reversed(entries))
    assert MatchAggregator().aggregate(shuffled).to_dict() == result.to_dict()


def test_match_view_identity_survives_even_when_the_display_aggregator_merged_rules() -> None:
    entries = [round_input("TC-017", round_no=1)]  # AIM-03 with MOV-02 merged in
    result = MatchAggregator().aggregate(entries)
    mov = result.rule("MOV-02")
    assert mov is not None and sum(mov.related_counts.values()) == 1
    assert sum(mov.counts.values()) == 0  # not double counted as a primary


# ============================================================================== 5. snapshot audit


def test_legacy_package_without_source_confidence_is_conservative_not_high(tmp_path: Path) -> None:
    result = build(tmp_path, [hud_observation(1.0, 0.99, timer=0.99)])
    legacy = copy.deepcopy(result)
    for snapshot in legacy["state_snapshots"]:
        snapshot.pop("source_confidence", None)
    stamps = {s["time_sec"] for s in legacy["state_snapshots"]}
    derived = [
        f
        for f in FactBuilder().enrich(legacy)["deterministic_facts"]
        if f["key"] == "numbers_state" and f.get("time_sec") in stamps
    ]
    assert derived and all(f["confidence"] == 0.0 for f in derived)


def test_known_limitation_thinning_keeps_the_first_reading_of_an_unchanged_state(
    tmp_path: Path,
) -> None:
    """Characterisation: a later, higher-confidence reading of the same state is dropped.

    Conservative only: the kept snapshot's confidence is that of the observation it came from
    (never raised), but the better reading cannot lift the fact over the 0.90 gate.
    """
    low_first = build(
        tmp_path, [hud_observation(1.0, 0.70, timer=0.70), hud_observation(1.5, 0.99, timer=0.99)]
    )
    assert [s["source_confidence"]["ally_alive"] for s in low_first["state_snapshots"]] == [0.70]
    high_first = build(
        tmp_path, [hud_observation(1.0, 0.99, timer=0.99), hud_observation(1.5, 0.70, timer=0.70)]
    )
    assert [s["source_confidence"]["ally_alive"] for s in high_first["state_snapshots"]] == [0.99]


def test_known_limitation_hp_fact_uses_its_own_value_score_and_snapshot_hp_has_no_source(
    tmp_path: Path,
) -> None:
    """Characterisation of the HP / armor provenance split.

    * the HP *fact* takes ``roi_confidence.hp_value`` (kept only if >= 0.90), so it can be
      higher than the observation's ``hud_confidence``;
    * the snapshot's ``hp`` / ``armor`` carry no ``source_confidence`` entry and armor has
      no fact at all.
    """
    observation = hud_observation(1.0, 0.65, timer=0.65)
    observation["quality"]["roi_confidence"]["hp_value"] = 0.95
    result = build(tmp_path, [observation])
    hp_facts = [f for f in result["deterministic_facts"] if f["key"] == "hp"]
    assert [f["confidence"] for f in hp_facts] == [0.95]
    assert result["state_snapshots"][0]["source_confidence"].keys().isdisjoint({"hp", "armor"})
    assert not [f for f in result["deterministic_facts"] if f["key"] == "armor"]
    below_gate = hud_observation(1.0, 0.99, timer=0.99)
    below_gate["quality"]["roi_confidence"]["hp_value"] = 0.89
    assert not [f for f in build(tmp_path, [below_gate])["deterministic_facts"] if f["key"] == "hp"]


def zone_package(tmp_path: Path) -> dict[str, Any]:
    from shapely.geometry import Polygon

    from valorant_ai_coach.events import EventSourceContract
    from valorant_ai_coach.hud.models import (
        HudObservationV2,
        empty_hud_quality,
        empty_hud_values,
    )
    from valorant_ai_coach.maps.registry import MapRegistry
    from valorant_ai_coach.maps.resolver import ZoneResolver
    from valorant_ai_coach.resources import resource_path
    from valorant_ai_coach.rounds import RoundPackageBuilder
    from valorant_ai_coach.video import VideoMetadata

    definition = MapRegistry().load("summit")
    resolver = ZoneResolver(definition)
    resolutions: list[dict[str, Any]] = []
    for zone_id in ("summit_a_approach", "summit_a_site", "summit_a_site"):
        point = Polygon(definition.zone_index[zone_id]["polygon_norm"]).representative_point()
        for _ in range(9):
            index = len(resolutions)
            resolutions.append(
                resolver.resolve(
                    time_sec=index * 0.2,
                    frame_index=index,
                    point=(point.x, point.y),
                    marker_confidence=0.95,
                    calibration={"status": "ok", "confidence": 0.95, "diagnostics": []},
                    label=None,
                    label_confidence=0,
                )
            )
    hud = []
    for index, item in enumerate(resolutions):
        values, quality = empty_hud_values(), empty_hud_quality()
        values["player_specific_hud_valid"] = True
        quality.update(hud_confidence=0.99, visual_confidence=0.99)
        hud.append(
            HudObservationV2(
                time_sec=item["time_sec"],
                frame_index=index,
                primary_state="live_first_person",
                values=values,
                quality=quality,
                is_player_world_view_trustworthy=True,
            ).to_dict()
        )
    end = resolutions[-1]["time_sec"]
    contract = EventSourceContract.load(resource_path("config/event_source_contract_v1.json"))
    return RoundPackageBuilder(contract=contract, validator=SchemaValidator()).build(
        match_id="zone-audit",
        video_metadata=VideoMetadata(
            tmp_path / "z.mp4", end + 1, 1920, 1080, 30, "h264", None, False, 0
        ),
        hud_observations=hud,
        hud_events=[],
        zone_resolutions=resolutions,
        map_name="summit",
    )[0]


def test_known_limitation_zone_fact_is_capped_by_the_package_aggregate_never_raised(
    tmp_path: Path,
) -> None:
    """Characterisation: the package aggregate only ever *lowers* the zone fact.

    The snapshot records the resolver's own ``zone_confidence`` (0.90) but the zone fact the
    builder emits is ``min(zone_confidence, package visual_confidence)``. With no visual
    observations the aggregate is 0.0, so a 0.90 resolution becomes a 0.0 fact. Safe
    direction; whether the aggregate should cap at all is a provenance decision.
    """
    package = zone_package(tmp_path)
    zones = [s for s in package["state_snapshots"] if s["player_location"]["zone_id"]]
    assert zones
    source = {s["source_confidence"]["player_location"] for s in zones}
    assert source == {0.9}
    aggregate = package["observation_quality"]["visual_confidence"]
    facts = [
        f for f in FactBuilder().enrich(package)["deterministic_facts"] if f["key"] == "zone_id"
    ]
    assert facts
    for fact in facts:
        assert fact["confidence"] <= max(source) + 1e-9  # never above the resolver's own value
        assert fact["confidence"] == pytest.approx(min(max(source), aggregate))
    assert aggregate < max(source)  # the situation in which the limitation shows
