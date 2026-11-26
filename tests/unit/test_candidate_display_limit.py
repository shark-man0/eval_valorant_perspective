"""Candidates are all judged and stored; only the GUI shows the first ones per Round."""

from __future__ import annotations

from typing import Any

from valorant_ai_coach.application.round_analyzer import COACH_RULES_PER_CALL, RoundAnalyzer
from valorant_ai_coach.ui.contracts import EvaluationView
from valorant_ai_coach.ui.view_model import limit_per_round


class RecordingCoach:
    def __init__(self) -> None:
        self.calls: list[tuple[list[str], set[str], set[str]]] = []

    def evaluate(self, package: dict[str, Any], candidate_rule_ids: list[str], **kwargs: Any):
        self.calls.append(
            (
                list(candidate_rule_ids),
                set(kwargs["deterministic_decisions"]),
                set(kwargs["analysis_scopes"]),
            )
        )
        return {
            "schema_version": "3.0",
            "analysis_id": f"a-{len(self.calls)}",
            "match_id": "M",
            "round_no": 1,
            "evaluations": [{"primary_rule_id": rule_id} for rule_id in candidate_rule_ids],
        }


def test_more_than_twelve_candidates_are_judged_in_batches_in_ranked_order() -> None:
    coach = RecordingCoach()
    analyzer = RoundAnalyzer.__new__(RoundAnalyzer)
    analyzer.coach = coach
    ids = [f"R-{n:02d}" for n in range(30)]
    output = analyzer._evaluate_in_batches(
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
