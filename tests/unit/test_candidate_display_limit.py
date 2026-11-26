"""Candidates are all judged and stored; only the GUI shows the first ones per Round."""

from __future__ import annotations

from threading import Event
from typing import Any

import pytest

from valorant_ai_coach.application.round_analyzer import COACH_RULES_PER_CALL, RoundAnalyzer
from valorant_ai_coach.schema_validation import ContractValidationError
from valorant_ai_coach.ui.contracts import EvaluationView
from valorant_ai_coach.ui.view_model import limit_per_round


class RecordingCoach:
    def __init__(self, evaluations=None, fail_on_call: int | None = None, cancel=None) -> None:
        self.calls: list[tuple[list[str], set[str], set[str]]] = []
        self.evaluations = evaluations
        self.fail_on_call = fail_on_call
        self.cancel = cancel

    def evaluate(self, package: dict[str, Any], candidate_rule_ids: list[str], **kwargs: Any):
        self.calls.append(
            (
                list(candidate_rule_ids),
                set(kwargs["deterministic_decisions"]),
                set(kwargs["analysis_scopes"]),
            )
        )
        if self.fail_on_call == len(self.calls):
            raise RuntimeError("API error")
        if self.cancel is not None:
            self.cancel.set()
        evaluations = (
            self.evaluations(candidate_rule_ids)
            if self.evaluations is not None
            else [{"primary_rule_id": rule_id} for rule_id in candidate_rule_ids]
        )
        return {
            "schema_version": "3.0",
            "analysis_id": f"a-{len(self.calls)}",
            "match_id": "M",
            "round_no": 1,
            "evaluations": evaluations,
        }


def _analyzer(coach: RecordingCoach) -> RoundAnalyzer:
    analyzer = RoundAnalyzer.__new__(RoundAnalyzer)
    analyzer.coach = coach
    return analyzer


def _run(analyzer: RoundAnalyzer, ids: list[str], cancel: Event | None = None):
    return analyzer._evaluate_in_batches(
        {}, ids, frame_paths=[], deterministic_decisions={},
        analysis_scopes={}, cancel_event=cancel,
    )


def test_more_than_twelve_candidates_are_judged_in_batches_in_ranked_order() -> None:
    coach = RecordingCoach()
    analyzer = _analyzer(coach)
    ids = [f"R-{n:02d}" for n in range(30)]
    output, calls = analyzer._evaluate_in_batches(
        {},
        ids,
        frame_paths=[],
        deterministic_decisions={"R-00": {}, "R-13": {}},
        analysis_scopes={rule_id: {} for rule_id in ids},
        cancel_event=None,
    )
    assert [len(call[0]) for call in coach.calls] == [12, 12, 6]
    assert all(len(call[0]) <= COACH_RULES_PER_CALL for call in coach.calls)
    # Each call carries only its own rules' decisions and scopes.
    assert coach.calls[0][1] == {"R-00"} and coach.calls[1][1] == {"R-13"}
    assert coach.calls[2][2] == set(ids[24:])
    assert [item["primary_rule_id"] for item in output["evaluations"]] == ids
    assert output["analysis_id"] == "a-1"
    assert [call["uncovered_rule_ids"] for call in calls] == [[], [], []]


IDS = [f"R-{n:02d}" for n in range(30)]


def test_a_failed_later_call_fails_the_round_with_no_partial_output() -> None:
    coach = RecordingCoach(fail_on_call=2)
    with pytest.raises(RuntimeError, match="API error"):
        _run(_analyzer(coach), IDS)
    assert len(coach.calls) == 2  # the third call is never made


def test_a_cancel_between_calls_stops_before_the_next_call() -> None:
    cancel = Event()
    coach = RecordingCoach(cancel=cancel)
    with pytest.raises(InterruptedError):
        _run(_analyzer(coach), IDS, cancel)
    assert len(coach.calls) == 1


def test_an_evaluation_naming_a_rule_of_another_call_is_refused() -> None:
    def leaky(batch: list[str]) -> list[dict[str, Any]]:
        return [{"primary_rule_id": batch[0], "related_rule_ids": ["R-29"]}]

    with pytest.raises(ContractValidationError, match="その回の候補でない"):
        _run(_analyzer(RecordingCoach(evaluations=leaky)), IDS)


def test_the_same_rule_from_two_calls_is_refused() -> None:
    analyzer = _analyzer(RecordingCoach(evaluations=lambda batch: [{"primary_rule_id": batch[0]}]))
    # Distinct primaries per call are fine ...
    output, _ = _run(analyzer, IDS)
    assert [e["primary_rule_id"] for e in output["evaluations"]] == ["R-00", "R-12", "R-24"]
    # ... but a primary repeated in a later call is not (a coach ignoring its batch).
    analyzer.coach = RecordingCoach(evaluations=lambda batch: [{"primary_rule_id": "R-00"}])
    with pytest.raises(ContractValidationError):
        _run(analyzer, IDS)


def test_a_candidate_no_evaluation_names_is_reported_not_filled() -> None:
    def partial(batch: list[str]) -> list[dict[str, Any]]:
        return [{"primary_rule_id": rule_id} for rule_id in batch[1:]]

    output, calls = _run(_analyzer(RecordingCoach(evaluations=partial)), IDS)
    assert [call["uncovered_rule_ids"] for call in calls] == [["R-00"], ["R-12"], ["R-24"]]
    assert {e["primary_rule_id"] for e in output["evaluations"]}.isdisjoint(
        {"R-00", "R-12", "R-24"}
    )


def _view(rule_id: str, label: str, round_no: int | None) -> EvaluationView:
    return EvaluationView(
        evaluation_id=rule_id, label=label, title=rule_id, rule_id=rule_id,
        related_rule_ids=(), situation="", evidence=(), missing_information=(),
        reason="", improvement=None, confidence=0.8, category="Other",
        round_no=round_no, requires_round_context=False, decision_source="llm",
        clip_path=None, needs_review=False, unscored_reason_code=None,
    )


def test_gui_shows_scored_first_up_to_the_limit_per_round_and_counts_the_rest() -> None:
    round_one = [_view(f"U{n}", "unscored", 1) for n in range(10)]
    round_one += [_view(f"G{n}", "good", 1) for n in range(5)]
    round_two = [_view("I0", "improve", 2)]
    match = [_view("MATCH", "improve", None)]
    stored = round_one + round_two + match
    shown, hidden = limit_per_round(stored, 12)
    ids = [item.rule_id for item in shown]
    assert {f"G{n}" for n in range(5)} <= set(ids)  # scored ones are never pushed out
    assert sum(1 for item in shown if item.round_no == 1) == 12
    assert hidden == {1: 3}
    assert "I0" in ids and "MATCH" in ids
    # Stored order is kept among what is shown.
    assert ids == [item.rule_id for item in stored if item.rule_id in set(ids)]
