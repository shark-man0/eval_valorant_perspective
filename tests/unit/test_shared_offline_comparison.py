"""Offline future evidence changes uncertainty, never invents event timing."""

import pytest
from test_shared_game_timeline import obs, replay


def test_unread_frame_between_measured_buy_and_active_is_an_edge_hypothesis():
    rows = [obs(0, ["buy"]), obs(10), obs(20, ["active"])]
    baseline = replay(rows)
    candidate = replay(rows, mark_round_transition_gaps=True)
    a, b = baseline["frames"][1], candidate["frames"][1]
    assert a["round"]["value"] == "BUY"
    assert b["round"]["value"] == "UNKNOWN"
    assert b["round"]["hypotheses"] == ["ACTIVE", "BUY"]
    assert b["round"]["forward_estimate"] == a["round"]
    assert b["round"]["transition_bracket"]["lower_sample"] == rows[0]["sample"]
    assert b["round"]["transition_bracket"]["upper_sample"] == rows[2]["sample"]
    assert b["round"]["transition_bracket"]["internal_game_event_time"] is None
    assert candidate["transitions"] == baseline["transitions"]
    assert b["life"] == a["life"] and b["camera"] == a["camera"]
    assert candidate["qualified_events"] == candidate["qualified_facts"] == []


def test_direct_observed_round_state_is_never_replaced_by_a_gap_hypothesis():
    rows = [obs(0, ["buy"]), obs(10, ["buy"]), obs(20, ["active"])]
    result = replay(rows, mark_round_transition_gaps=True)
    assert result["frames"][1]["round"]["value"] == "BUY"
    assert "forward_estimate" not in result["frames"][1]["round"]


def test_no_transition_hypothesis_crosses_a_decode_break():
    rows = [obs(0, ["buy"]), obs(10, continuity={"decode_ok": False}), obs(20, ["active"])]
    result = replay(rows, mark_round_transition_gaps=True)
    assert not any("transition_bracket" in r["round"] for r in result["frames"])


def test_forward_control_cannot_use_later_result_to_confirm_a_score_edge():
    rows = [
        obs(0, ["active"], context={"score": [0, 0]}),
        obs(10, context={"score": [1, 0]}),
        obs(20, ["result"], context={"score": [1, 0]}),
    ]
    offline, forward = replay(rows), replay(rows, forward_only=True)
    assert offline["frames"][1]["round"]["value"] == "ENDED"
    assert forward["frames"][1]["round"]["value"] == "ACTIVE"
    assert offline["boundary_candidates"][0]["status"] == "context_supported"
    assert forward["boundary_candidates"][0]["status"] == "pending"


def test_forward_mode_cannot_claim_offline_transition_reconciliation():
    with pytest.raises(ValueError):
        replay([], forward_only=True, mark_round_transition_gaps=True)
