from fractions import Fraction

from tests.unit.test_shared_game_timeline import obs, replay
from valorant_ai_coach.temporal.event_round import attach_event_round_context, group_round_starts


def test_second_start_witness_can_follow_dropout_with_original_bracket_retained():
    rows = [
        obs(0, ["buy"], context={"score": [0, 0]}),
        obs(10, ["active"], context={"score": [0, 0]}),
        obs(20),
        obs(30, ["active"], context={"score": [0, 0]}),
    ]
    states = replay(rows)["frames"]
    first = {
        "kind": "round_start", "lower_sample": rows[0]["sample"],
        "upper_sample": rows[1]["sample"], "evidence_ids": ["a"],
    }
    second = {
        "kind": "round_start", "lower_sample": rows[0]["sample"],
        "upper_sample": rows[3]["sample"], "evidence_ids": ["b"],
    }
    events = [first, second]
    group_round_starts(events, states, Fraction(3))
    assert len(events) == 1
    assert events[0]["upper_sample"] == rows[1]["sample"]
    assert events[0]["evidence_ids"] == ["a", "b"]
    assert events[0]["round_start_witnesses"][1] == second


def test_nearby_starts_for_two_observed_rounds_stay_separate():
    rows = [
        obs(0, ["buy"], context={"score": [0, 0]}),
        obs(1, ["active"], context={"score": [0, 0]}),
        obs(2, ["result"], context={"score": [1, 0]}),
        obs(3, ["buy"], context={"score": [1, 0]}),
        obs(4, ["active"], context={"score": [1, 0]}),
    ]
    timeline = replay(rows, practical_visual_state=True)
    starts = [event for event in timeline["transitions"] if event["kind"] == "round_start"]
    assert [event["round_membership"]["candidates"] for event in starts] == [[1], [2]]


def test_round_end_and_return_keep_different_endpoint_rounds():
    rows = [
        obs(0, ["buy", "owner_hud"], context={"score": [0, 0]}),
        obs(1, ["active", "owner_hud"], context={"score": [0, 0]}),
        obs(2, ["death", "spectator", "active"], context={"score": [0, 0]}),
        obs(3, ["result"], context={"score": [1, 0]}),
        obs(4, ["buy", "owner_hud"], context={"score": [1, 0]}),
    ]
    result = replay(rows, practical_visual_state=True)
    end = next(event for event in result["transitions"] if event["kind"] == "round_end")
    returned = next(event for event in result["transitions"] if event["kind"] == "return")
    assert end["round_membership"]["candidates"] == [1]
    assert returned["round_membership"]["source"]["candidates"] == [1]
    assert returned["round_membership"]["destination"]["candidates"] == [2]
    assert returned["round_membership"]["cross_round_candidate"] is True
    assert returned["internal_game_event_time"] is None
    assert result["qualified_facts"] == result["qualified_events"] == []


def test_membership_does_not_borrow_a_number_from_later_round_or_epoch():
    rows = [
        obs(0, ["buy"]), obs(1, ["active"]), obs(2, ["result"]),
        obs(3, ["buy"], context={"score": [4, 5]}),
        obs(4, ["active"], epoch="changed", context={"score": [4, 5]}),
    ]
    result = replay(rows, practical_visual_state=True)
    end = next(event for event in result["transitions"] if event["kind"] == "round_end")
    assert end["round_membership"]["status"] == "UNKNOWN"


def test_return_uses_settled_ending_score_and_new_buy_for_source_round():
    rows = [
        obs(0, ["buy"], context={"score": [0, 0]}),
        obs(1, ["active"], context={"score": [0, 0]}),
        obs(2, ["result"], context={"score": [1, 0]}),
        obs(3, ["buy"], context={"score": [1, 0]}),
    ]
    states = replay(rows)["frames"]
    event = {
        "kind": "return_hypothesis", "lower_sample": rows[2]["sample"],
        "upper_sample": rows[3]["sample"], "evidence_ids": [],
    }
    attach_event_round_context([event], states, Fraction(10))
    member = event["round_membership"]
    assert member["source"]["candidates"] == [1]
    assert member["destination"]["candidates"] == [2]
    assert member["source"]["basis"] == "settled_ending_score_and_observed_next_buy"
