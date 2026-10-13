"""Practical Mode x evaluation policy (D-1 / D-1b) x Match aggregation.

PR #11 introduced the evaluation merge policy (merged confidence = weakest member, 0.55 floor
applied to every evaluation *before* merging). PR #12 introduced Practical Mode, whose Round
Packages may carry provisional / unknown boundaries. These tests pin how the two meet:

* a Round whose boundary is not confirmed is stored and shown, but never scored, so neither
  D-1 nor D-1b can ever raise a confidence or create GOOD / IMPROVE for it;
* such a Round cannot claim full-Round confidence in its own Package;
* its presence in a job does not change how a confirmed (Strict) Round is merged or floored;
* the Match view reports the Round as incomplete instead of treating it as a full Round.

Everything is synthetic (``tests/cases``); no real footage, no real API.
"""

from __future__ import annotations

import copy
from types import SimpleNamespace
from typing import Any

import pytest
from match_fixtures import (
    MATCH,
    case_package,
    make_analyzer,
    registry,
    round_input,
    rules_config,
)
from match_fixtures import analyze as analyze_package

from valorant_ai_coach.application import RoundAnalyzer
from valorant_ai_coach.application.match_aggregation import MatchAggregator, RoundInput
from valorant_ai_coach.application.pipeline import MatchAnalysisPipeline
from valorant_ai_coach.rules import EvaluationAggregator
from valorant_ai_coach.schema_validation import ContractValidationError

UNCERTAIN_COMBINATIONS = [
    ("provisional", "provisional"),
    ("provisional", "unknown"),
    ("unknown", "provisional"),
    ("unknown", "unknown"),
]


def endpoint(status: str, kind: str, window: dict[str, float]) -> dict[str, Any]:
    if status == "unknown":
        return {"status": "unknown", "candidate": None, "formal_event_id": None}
    return {
        "status": "provisional",
        "formal_event_id": None,
        "candidate": {
            "kind": kind,
            "boundary_status": "provisional",
            "boundary_time_sec": window["start_sec"] + 1.0,
            "confirmation_time_sec": None,
            "evidence_times_sec": [window["start_sec"] + 1.0],
            "confidence": 0.9,
            "provenance": {"scope": "synthetic"},
        },
    }


def uncertain_package(
    case_id: str = "TC-006", *, start: str, end: str, round_no: int = 2
) -> dict[str, Any]:
    """A real synthetic Round Package with an uncertain Practical lifecycle.

    Its observation quality is zeroed, which is what the Package contract requires of a Round
    whose boundary is not confirmed.
    """
    package = case_package(case_id, round_no=round_no)
    window = package["round_window"]
    package["round_lifecycle"] = {
        "mode": "practical",
        "observed_round_no": None,
        "start": endpoint(start, "round_start", window),
        "end": endpoint(end, "round_end", window),
    }
    package["observation_quality"].update(
        hud_confidence=0, visual_confidence=0, timeline_completeness=0
    )
    return package


@pytest.mark.parametrize(("start", "end"), UNCERTAIN_COMBINATIONS)
def test_a_round_with_an_uncertain_boundary_gets_no_evaluation_from_the_real_analyzer(
    start: str, end: str
) -> None:
    analysis = analyze_package(uncertain_package(start=start, end=end))
    assert analysis.output["evaluations"] == []
    assert analysis.output["analysis_id"].startswith("partial-")
    assert analysis.deterministic_decisions == {} and analysis.candidates == ()


def test_the_same_synthetic_round_is_scored_when_it_carries_no_practical_lifecycle() -> None:
    """Control for the test above: only the uncertain lifecycle suppresses scoring (Strict)."""
    analysis = analyze_package(case_package("TC-006", round_no=2))
    assert [(e["primary_rule_id"], e["label"]) for e in analysis.output["evaluations"]] == [
        ("AIM-02", "good")
    ]
    assert not RoundAnalyzer.boundary_context_is_uncertain(analysis.round_package)


@pytest.mark.parametrize(
    "quality", ["hud_confidence", "visual_confidence", "timeline_completeness"]
)
def test_an_uncertain_round_cannot_claim_full_round_confidence_in_its_package(
    quality: str,
) -> None:
    package = uncertain_package(start="provisional", end="unknown")
    package["observation_quality"][quality] = 0.4
    with pytest.raises(ContractValidationError, match="full-round confidence"):
        make_analyzer().analyze(package)


def eval_item(
    evaluation_id: str, label: str, confidence: float, facts: list[str], start: float
) -> dict[str, Any]:
    scored = label != "unscored"
    return {
        "evaluation_id": evaluation_id,
        "primary_rule_id": "AIM-02",
        "related_rule_ids": [],
        "label": label,
        "confidence": confidence,
        "clip_id": f"clip-{evaluation_id}" if scored else None,
        "improvement": "x" if label == "improve" else None,
        "fact_refs": list(facts),
        "evidence_range": {"start_sec": start, "end_sec": start + 1.5},
        "display_clip": {"start_sec": start - 3, "end_sec": start + 4} if scored else None,
        "evidence": [],
        "missing_information": [],
        "unscored_reason_code": None if scored else "low_confidence",
    }


def aggregate_job(*rounds: tuple[int, list[dict[str, Any]]]) -> dict[int, list[dict[str, Any]]]:
    """The pipeline's own display aggregation (floor -> merge -> floor) for a whole job."""
    pipeline = MatchAnalysisPipeline.__new__(MatchAnalysisPipeline)
    pipeline.aggregator = EvaluationAggregator(rules_config(), registry())
    results = [
        SimpleNamespace(output={"round_no": number, "evaluations": copy.deepcopy(evaluations)})
        for number, evaluations in rounds
    ]
    return pipeline._aggregate_round_evaluations(results)


CONFIRMED_ROUND = (
    1,
    [
        eval_item("weak", "good", 0.50, ["F1"], 10.0),
        eval_item("strong", "good", 0.90, ["F2"], 11.0),
    ],
)


@pytest.mark.parametrize(
    "uncertain_first", [False, True], ids=["uncertain_last", "uncertain_first"]
)
def test_an_uncertain_round_in_the_job_does_not_change_how_a_confirmed_round_is_merged(
    uncertain_first: bool,
) -> None:
    alone = aggregate_job(CONFIRMED_ROUND)[1]
    uncertain = (2, [])  # what the analyzer returns for it
    rounds = (uncertain, CONFIRMED_ROUND) if uncertain_first else (CONFIRMED_ROUND, uncertain)
    mixed = aggregate_job(*rounds)
    assert mixed[2] == []  # stored with no evaluation, never invented
    assert mixed[1] == alone
    # D-1b outcome for the confirmed Round: weak one demoted alone, strong one kept
    assert [(e["evaluation_id"], e["label"], e["confidence"]) for e in mixed[1]] == [
        ("weak", "unscored", 0.50),
        ("strong", "good", 0.90),
    ]


def test_evaluations_are_never_merged_across_a_confirmed_and_an_uncertain_round() -> None:
    """Even a (hypothetical) scored item in the uncertain Round stays inside its own Round."""
    mixed = aggregate_job(
        CONFIRMED_ROUND, (2, [eval_item("late", "good", 0.95, ["F9"], 11.0)])
    )
    assert [e["evaluation_id"] for e in mixed[1]] == ["weak", "strong"]
    assert [e["evaluation_id"] for e in mixed[2]] == ["late"]
    assert all(e["confidence"] == 0.95 for e in mixed[2])


def test_the_match_view_marks_an_uncertain_round_incomplete_and_counts_nothing_for_it() -> None:
    confirmed = round_input("TC-006", round_no=1)
    uncertain = RoundInput.from_round_analysis(
        analyze_package(uncertain_package(start="provisional", end="unknown"))
    )
    alone = MatchAggregator().aggregate([confirmed], match_id=MATCH, expected_round_numbers=[1])
    both = MatchAggregator().aggregate(
        [confirmed, uncertain], match_id=MATCH, expected_round_numbers=[1, 2]
    )
    assert alone.completeness.status == "verified_complete"  # nothing uncertain
    completeness = both.completeness
    assert completeness.status == "incomplete"  # not verified despite 2 of 2 supplied
    assert completeness.rounds_timeline_not_complete == (2,)
    assert "round_timeline_unavailable" in completeness.blocking_reasons
    # the uncertain Round adds no evaluation and does not disturb the confirmed Round's counts
    assert [r.evaluation_count for r in both.rounds] == [1, 0]
    assert both.evaluations == alone.evaluations
    assert [(r.rule_id, r.counts, r.primary_evaluation_ids) for r in both.rules] == [
        (r.rule_id, r.counts, r.primary_evaluation_ids) for r in alone.rules
    ]


def test_an_unverified_uncertain_round_is_never_reported_as_a_verified_complete_match() -> None:
    uncertain = RoundInput.from_round_analysis(
        analyze_package(uncertain_package(start="unknown", end="unknown", round_no=1))
    )
    view = MatchAggregator().aggregate([uncertain], match_id=MATCH, expected_round_numbers=[1])
    assert view.completeness.status != "verified_complete"
    assert view.evaluations == () and view.rules == ()
