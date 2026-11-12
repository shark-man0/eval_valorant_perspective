"""A carried state cannot narrow a native display-observation bracket."""

import pytest
from test_shared_game_timeline import obs, replay


@pytest.mark.parametrize(
    ("before", "after", "kind"),
    [("buy", "active", "round_start"), ("active", "result", "round_end")],
)
def test_round_boundary_before_witness_is_measured_before_state(before, after, kind):
    rows = [obs(0, [before]), obs(1), obs(2, [after])]
    result = replay(rows)
    transition = next(t for t in result["transitions"] if t["kind"] == kind)
    assert result["frames"][1]["round"]["reason"] == "bounded_missing_observation"
    assert transition["lower_sample"] == rows[0]["sample"]
    assert transition["upper_sample"] == rows[2]["sample"]
    assert transition["carried_before_sample"] == rows[1]["sample"]
    assert transition["lower_sample_basis"] == "last_current_round_support"
    assert transition["internal_game_event_time"] is None
    assert result["qualified_facts"] == result["qualified_events"] == []


def test_most_recent_measured_buy_is_retained_as_the_lower_witness():
    rows = [obs(0, ["buy"]), obs(1, ["buy"]), obs(2), obs(3, ["active"])]
    transition = next(t for t in replay(rows)["transitions"] if t["kind"] == "round_start")
    assert transition["lower_sample"] == rows[1]["sample"]


def test_direct_adjacent_boundary_keeps_original_samples_without_a_carried_witness():
    rows = [obs(0, ["buy"]), obs(1, ["active"])]
    transition = next(t for t in replay(rows)["transitions"] if t["kind"] == "round_start")
    assert transition["lower_sample"] == rows[0]["sample"]
    assert "carried_before_sample" not in transition


@pytest.mark.parametrize(
    "change",
    [
        {"epoch": "other"},
        {"source": "c"},
        {"continuity": {"decode_ok": False}},
        {"continuity": {"content_break_confirmed": True}},
    ],
)
def test_reset_forbids_borrowing_a_pre_break_round_witness(change):
    result = replay([obs(0, ["buy"]), obs(1, **change), obs(2, ["active"], **change)])
    assert not any(t["kind"] == "round_start" for t in result["transitions"])


def test_conflict_does_not_reuse_an_older_buy_witness():
    result = replay([obs(0, ["buy"]), obs(1, ["buy", "active"]), obs(2), obs(3, ["active"])])
    assert not any(t["kind"] == "round_start" for t in result["transitions"])


def test_score_change_keeps_actual_before_score_even_if_round_was_carried():
    rows = [
        obs(0, ["active"], context={"score": [1, 1]}),
        obs(1, context={"score": [1, 1]}),
        obs(2, ["result"], context={"score": [2, 1]}),
    ]
    transition = next(t for t in replay(rows)["transitions"] if t["kind"] == "round_end")
    assert transition["lower_sample"] == rows[1]["sample"]
    assert "carried_before_sample" not in transition
