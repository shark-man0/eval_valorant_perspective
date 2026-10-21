"""Synthetic automatic predictions are never human GT or qualified events."""
from copy import deepcopy

import pytest

from scripts.diagnostics.analyze_personal_candidates import candidate_runs
from scripts.temporal_gt.contract import ContractError


def row(tick, result=None, report=None):
    return {
        "tick": tick, "source_sha256": "a" * 64, "time_base": "1/10",
        "image_sha256": "b" * 64, "round_result": result, "report_present": report,
    }


def test_persistent_report_and_result_support_are_not_multiple_physical_events():
    out = candidate_runs([row(0, True, True), row(50, True, True), row(100, True, True)])
    assert out["candidate_counts"] == {"round_end": 1, "self_death": 1}
    assert out["persistent_support_rows_not_new_events"] == 4
    assert out["unknown_candidates"] == 1
    assert out["formal_events"] == []
    assert out["precision"] is None and out["recall"] is None
    assert not out["qualification_complete"] and not out["approved_gt"]
    assert all(c["physical_event_id"] is None for c in out["candidates"])


@pytest.mark.parametrize("gap", [False, None])
def test_report_reappearance_cannot_create_a_new_confirmed_death(gap):
    out = candidate_runs([row(0, report=True), row(50, report=gap), row(100, report=True)])
    a, b = out["candidates"]
    assert a["provisional_label"] == b["provisional_label"] == "UNKNOWN"
    assert b["possible_redisplay_of"] == a["candidate_id"]
    assert out["formal_events"] == []
    assert out["unmatched_or_unscanned_is_negative"] is False


def test_score_report_eof_and_killer_roles_cannot_be_round_end_or_self_death_gt():
    a = row(0, report=True)
    a.update(score_changed=True, eof=True, killer_role="self", victim_role="nonself")
    out = candidate_runs([a])
    assert out["candidate_counts"] == {"self_death": 1}
    assert out["candidates"][0]["provisional_label"] == "UNKNOWN"
    assert out["formal_events"] == []


def test_exact_duplicate_pts_is_suppressed_but_conflict_rejected():
    a = row(0, True)
    out = candidate_runs([a, deepcopy(a)])
    assert out["duplicate_input_rows_suppressed"] == 1
    assert out["candidates"][0]["support_count"] == 1
    with pytest.raises(ContractError, match="conflicting_duplicate"):
        candidate_runs([a, row(0, False)])


@pytest.mark.parametrize("changes", [
    {"tick": -1}, {"tick": True}, {"time_base": "-1/10"},
    {"source_sha256": "c" * 64}, {"time_base": "1/20"},
    {"round_result": 1}, {"report_present": "true"},
])
def test_invalid_or_mixed_source_measurements_fail(changes):
    b = row(50)
    b.update(changes)
    with pytest.raises(ContractError):
        candidate_runs([row(0), b])


def test_unordered_pts_and_empty_scan_do_not_become_negatives():
    with pytest.raises(ContractError, match="ordered_source_pts"):
        candidate_runs([row(50), row(0)])
    out = candidate_runs([])
    assert out["candidates"] == [] and out["formal_events"] == []
    assert out["unmatched_or_unscanned_is_negative"] is False
