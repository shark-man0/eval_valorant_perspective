"""Runtime consumers of the #31 policy fields and the #25 opt-in (default off)."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest
from match_fixtures import MATCH, case_package, make_analyzer, round_input, three_round_match

from valorant_ai_coach.application import MockCoachAdapter, RoundAnalyzer
from valorant_ai_coach.application.match_aggregation import MatchAggregator
from valorant_ai_coach.facts import FactBuilder
from valorant_ai_coach.resources import resource_path
from valorant_ai_coach.rules import DeterministicRuleEngine, RuleSelector
from valorant_ai_coach.rules.policy_runtime import (
    GATE_REPORT_ONLY,
    GATE_UNSCORE_INCOMPLETE,
    ProvisionalAdmissionTable,
    ProvisionalEvaluationPolicy,
    RoundTimelineGate,
    occurrence_summaries,
)
from valorant_ai_coach.rules.temporal_contract import TemporalPolicyTable
from valorant_ai_coach.schema_validation import SchemaValidator

# The classification is pinned: changing it changes which rules could ever be scored in a
# provisional Round, which is an approval item (#25).
ADMISSIBLE = {
    "AIM-02", "AIM-03", "AIM-04", "DEC-03", "INFO-02", "INFO-04", "MOV-01", "MOV-02",
    "MOV-03", "MOV-04", "PEEK-02", "PEEK-04", "PEEK-05", "POS-01", "POS-03", "UTL-01",
    "WPN-01",
}


def analyzer(**kwargs: Any) -> RoundAnalyzer:
    return RoundAnalyzer(
        fact_builder=FactBuilder(),
        selector=RuleSelector(resource_path("config/rule_trigger_registry_v2.json")),
        rule_engine=DeterministicRuleEngine(),
        coach=MockCoachAdapter(),
        validator=SchemaValidator(),
        **kwargs,
    )


def provisional(case_id: str, round_no: int = 2, *, missing: list[tuple[float, float]] = ()):
    package = case_package(case_id, round_no=round_no)
    window = package["round_window"]

    def endpoint(kind: str, at: float) -> dict[str, Any]:
        return {
            "status": "provisional",
            "formal_event_id": None,
            "candidate": {
                "kind": kind, "boundary_status": "provisional", "boundary_time_sec": at,
                "confirmation_time_sec": None, "evidence_times_sec": [at],
                "confidence": 0.9, "provenance": {"scope": "synthetic"},
            },
        }

    package["round_lifecycle"] = {
        "mode": "practical", "observed_round_no": None,
        "start": endpoint("round_start", window["start_sec"]),
        "end": endpoint("round_end", window["end_sec"]),
    }
    package["observation_quality"].update(
        hud_confidence=0, visual_confidence=0, timeline_completeness=0,
        missing_intervals=[{"start_sec": a, "end_sec": b} for a, b in missing],
    )
    return package


# ------------------------------------------------------------------- #25 table


def test_admission_table_covers_all_44_rules_with_reasons():
    table = ProvisionalAdmissionTable.load()
    rows = table.rows()
    assert len(rows) == 44
    assert table.admissible_rule_ids() == ADMISSIBLE
    for row in rows:
        assert row.admissible == (not row.reasons)
    by_id = {row.rule_id: row for row in rows}
    assert "requires_previous_round_context" in by_id["ECO-01"].reasons
    assert "requires_match_context" in by_id["AIM-01"].reasons
    assert by_id["ROLE-02"].reasons == ("round_context_trigger:site_state",)
    assert by_id["AIM-02"].match_aggregated and by_id["AIM-02"].admissible


def test_default_analyzer_keeps_withholding_provisional_rounds():
    result = analyzer().analyze(provisional("TC-005"))
    assert result.admission == "provisional_withheld"
    assert result.output["evaluations"] == []
    disabled = ProvisionalEvaluationPolicy(ProvisionalAdmissionTable.load(), enabled=False)
    assert analyzer(provisional_policy=disabled).analyze(provisional("TC-005")).output[
        "evaluations"
    ] == []


def test_opt_in_admits_only_self_contained_rules_with_their_confirmed_labels():
    policy = ProvisionalEvaluationPolicy(ProvisionalAdmissionTable.load(), enabled=True)
    confirmed = make_analyzer().analyze(case_package("TC-005", round_no=2))
    partial = analyzer(provisional_policy=policy).analyze(provisional("TC-005"))
    assert partial.admission == "provisional_partial"
    got = sorted((e["primary_rule_id"], e["label"]) for e in partial.output["evaluations"])
    expected = sorted((e["primary_rule_id"], e["label"]) for e in confirmed.output["evaluations"])
    assert got and got == expected  # same decision; nothing new is invented
    for item in partial.output["evaluations"]:
        assert item["primary_rule_id"] in ADMISSIBLE


@pytest.mark.parametrize("case_id", ["TC-001", "TC-012", "TC-008", "TC-019"])
def test_opt_in_never_scores_round_context_rules(case_id: str):
    policy = ProvisionalEvaluationPolicy(ProvisionalAdmissionTable.load(), enabled=True)
    partial = analyzer(provisional_policy=policy).analyze(provisional(case_id))
    assert all(e["primary_rule_id"] in ADMISSIBLE for e in partial.output["evaluations"])


def test_opt_in_drops_a_pivot_inside_an_observation_gap():
    policy = ProvisionalEvaluationPolicy(ProvisionalAdmissionTable.load(), enabled=True)
    package = provisional("TC-005")
    shot = next(e["time_sec"] for e in package["events"] if e["type"] == "shot")
    gapped = provisional("TC-005", missing=[(shot - 1.0, shot + 1.0)])
    assert analyzer(provisional_policy=policy).analyze(gapped).output["evaluations"] == []


# --------------------------------------------------------------- #31 §6-1 gate


def _incomplete(package: dict[str, Any]) -> dict[str, Any]:
    value = deepcopy(package)
    value["observation_quality"]["timeline_completeness"] = 0.6
    value["observation_quality"]["missing_intervals"] = [
        {"start_sec": value["round_window"]["start_sec"],
         "end_sec": value["round_window"]["start_sec"] + 1.0}
    ]
    return value


def test_gate_report_only_changes_nothing_and_lists_affected_rules():
    gate = RoundTimelineGate(TemporalPolicyTable.load(), GATE_REPORT_ONLY)
    package = _incomplete(case_package("TC-001"))  # DEC-01 requires the Round timeline
    baseline = make_analyzer().analyze(package)
    result = analyzer(round_timeline_gate=gate).analyze(package)
    assert result.output == baseline.output
    assert result.timeline_gate and {r.action for r in result.timeline_gate} == {"reported"}
    assert {r.rule_id for r in result.timeline_gate} <= {"DEC-01", "INFO-03"}


def test_gate_unscore_mode_converts_without_raising_confidence():
    gate = RoundTimelineGate(TemporalPolicyTable.load(), GATE_UNSCORE_INCOMPLETE)
    package = _incomplete(case_package("TC-001"))
    baseline = make_analyzer().analyze(package)
    result = analyzer(round_timeline_gate=gate).analyze(package)
    before = {e["evaluation_id"]: e for e in baseline.output["evaluations"]}
    changed = {r.evaluation_id for r in result.timeline_gate}
    assert changed
    for item in result.output["evaluations"]:
        if item["evaluation_id"] in changed:
            assert item["label"] == "unscored" and item["display_clip"] is None
            assert item["confidence"] == before[item["evaluation_id"]]["confidence"]
            assert any(t.startswith("round_timeline_not_complete:") for t in
                       item["missing_information"])


def test_gate_leaves_complete_timelines_and_windowed_rules_alone():
    gate = RoundTimelineGate(TemporalPolicyTable.load(), GATE_UNSCORE_INCOMPLETE)
    complete = analyzer(round_timeline_gate=gate).analyze(case_package("TC-001"))
    assert complete.timeline_gate == ()
    micro = analyzer(round_timeline_gate=gate).analyze(_incomplete(case_package("TC-005")))
    assert micro.timeline_gate == ()  # AIM-03 does not require the Round timeline


def test_gate_rejects_unknown_modes():
    with pytest.raises(ValueError):
        RoundTimelineGate(TemporalPolicyTable.load(), "score_harder")


# ---------------------------------------------------------- #31 §6-6 summary


def test_occurrence_summary_is_structured_and_verdict_free():
    view = MatchAggregator().aggregate(
        [round_input("TC-003", round_no=n) for n in (1, 2, 3)], match_id=MATCH
    ).to_dict()
    summaries = {row["rule_id"]: row for row in view["occurrence_summaries"]}
    mov = summaries["MOV-01"]
    assert mov["occurrences"] == 3 and mov["threshold"] == 3 and mov["summary_required"]
    assert mov["rounds"] == [1, 2, 3] and mov["text"] is None
    assert mov["text_status"] == "requires_approval"
    assert len(mov["evidence_start_seconds"]) == 3
    # Only rules that ask for repeated-occurrence aggregation are listed.
    assert set(summaries) <= {"AIM-01", "AIM-02", "AIM-03", "AIM-04", "MOV-01", "MOV-02"}


def test_occurrence_summary_below_threshold_and_ignores_other_rules():
    view = MatchAggregator().aggregate(three_round_match(), match_id=MATCH).to_dict()
    for row in view["occurrence_summaries"]:
        assert row["summary_required"] is (row["occurrences"] >= row["threshold"])
    assert occurrence_summaries(
        [{"rule_id": "DEC-01", "aggregate_repeated_occurrences": False, "counts": {}}], []
    ) == []


# ------------------------------------------------- stored view of the opt-in rows


def _store(tmp_path, *, marker: bool):
    from valorant_ai_coach.storage import SQLiteRepository

    policy = ProvisionalEvaluationPolicy(ProvisionalAdmissionTable.load(), enabled=True)
    result = analyzer(provisional_policy=policy).analyze(provisional("TC-005"))
    repository = SQLiteRepository(tmp_path / "app.db")
    repository.create_match(MATCH, tmp_path / "video.mp4", status="completed")
    repository.save_round_package(result.round_package)
    repository.save_analysis_result(result.output)
    checkpoint = {"completed_rounds": [2], "failed_rounds": []}
    if marker:
        checkpoint["provisional_evaluation"] = "boundary_independent_v1"
    repository.save_job_checkpoint(MATCH, "completed", checkpoint)
    return repository, result


def test_stored_opt_in_rows_are_accepted_only_with_their_marker(tmp_path):
    from valorant_ai_coach.application.match_aggregation import MatchAggregationError
    from valorant_ai_coach.application.match_aggregation_service import aggregate_saved_match

    repository, result = _store(tmp_path, marker=True)
    view = aggregate_saved_match(repository, MATCH)
    assert [r["status"] for r in view["rounds"]] == ["included"]
    assert len(view["evaluations"]) == len(result.output["evaluations"])
    (tmp_path / "unmarked").mkdir()
    unmarked, _ = _store(tmp_path / "unmarked", marker=False)
    with pytest.raises(MatchAggregationError):
        aggregate_saved_match(unmarked, MATCH)


def test_gui_summary_lists_rules_that_reached_the_summary_threshold():
    from valorant_ai_coach.ui.view_model import format_match_summary

    view = MatchAggregator().aggregate(
        [round_input("TC-003", round_no=n) for n in (1, 2, 3)], match_id=MATCH
    ).to_dict()
    text = format_match_summary(view)
    assert "繰り返し集約の対象: MOV-01 3件（Round 3）" in text
    small = MatchAggregator().aggregate([round_input("TC-003")], match_id=MATCH).to_dict()
    assert "繰り返し集約" not in format_match_summary(small)


# ------------------------------------------------------------- 2026-11-17 review


def test_round_timeline_gate_report_always_runs_in_every_view(tmp_path):
    from valorant_ai_coach.application.match_aggregation_service import aggregate_saved_match
    from valorant_ai_coach.storage import SQLiteRepository

    package = _incomplete(case_package("TC-001"))
    default = make_analyzer().analyze(package)  # no gate passed in
    assert default.timeline_gate and {r.action for r in default.timeline_gate} == {"reported"}
    view = MatchAggregator().aggregate([default], match_id=MATCH).to_dict()
    gate = view["round_timeline_gate"]
    assert gate["mode"] == "report_only"
    assert {row["evaluation_id"] for row in gate["affected"]} == {
        r.evaluation_id for r in default.timeline_gate
    }
    repository = SQLiteRepository(tmp_path / "app.db")
    repository.create_match(MATCH, tmp_path / "v.mp4", status="completed")
    repository.save_round_package(default.round_package)
    repository.save_analysis_result(default.output)
    repository.save_job_checkpoint(MATCH, "completed", {"completed_rounds": [1],
                                                        "failed_rounds": []})
    assert aggregate_saved_match(repository, MATCH)["round_timeline_gate"] == gate


def test_display_clip_policy_is_transcribed_not_invented():
    import json
    import re

    rules = json.loads(resource_path("config/valorant_evaluation_rules_v4.json").read_text(
        encoding="utf-8"))["rules"]
    table = TemporalPolicyTable.load()
    assert len(rules) == 44
    for rule in rules:
        text = rule["temporal_context"]["display_clip_strategy"]
        clip = table.get(rule["id"]).display_clip
        low, high = map(float, re.search(r"(\d+)〜(\d+)", text).groups())
        assert (clip.min_seconds, clip.max_seconds) == (low, high)
        assert (clip.clips_per_evaluation == 1) == ("1クリップ" in text)
        assert (clip.max_clips_per_match is not None) == ("最大" in text)
        assert clip.supplement_required == ("併記" in text or "＋" in text)


def test_display_clip_policy_rejects_numbers_not_in_the_text():
    import json
    from copy import deepcopy

    from valorant_ai_coach.rules.temporal_contract import ContractValidationError

    config = json.loads(resource_path("config/valorant_evaluation_rules_v4.json").read_text(
        encoding="utf-8"))
    broken = deepcopy(config)
    broken["rules"][0]["temporal_context"]["display_clip_policy"]["max_seconds"] = 30
    with pytest.raises(ContractValidationError):
        TemporalPolicyTable.from_config(broken)


def test_display_clip_report_measures_clips_without_changing_them():
    rounds = [round_input("TC-003", round_no=n) for n in (1, 2, 3)]
    before = [deepcopy(r.output) for r in rounds]
    view = MatchAggregator().aggregate(rounds, match_id=MATCH).to_dict()
    assert [r.output for r in rounds] == before
    rows = {row["rule_id"]: row for row in view["display_clip_report"]}
    mov = rows["MOV-01"]
    assert mov["clips"] == 3 and mov["within_length"] + mov["shorter"] + mov["longer"] == 3
    assert mov["policy"]["min_seconds"] == 8.0 and mov["policy"]["max_seconds"] == 15.0
    assert mov["exceeds_max_clips_per_match"] is False
