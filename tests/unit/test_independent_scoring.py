"""Scoring protocol of the independent evaluation: fixed draws and plain counting."""

from __future__ import annotations

from fractions import Fraction

from valorant_ai_coach.temporal import independent_scoring as sc


def test_draws_depend_only_on_the_recording_id_and_duration():
    first = sc.frame_seconds("rec_a", Fraction(1800))
    assert first == sc.frame_seconds("rec_a", Fraction(1800))
    assert first != sc.frame_seconds("rec_b", Fraction(1800))
    assert len(first) == sc.PROTOCOL["frames_per_recording"] == len(set(first))
    assert all(s >= 0 and s + 0.5 < 1800 for s in first)
    assert sc.frame_seconds("rec_a", Fraction(10)) == list(range(9))
    order = sc.round_order("rec_a")
    assert sorted(order) == list(range(1, 41)) and order == sc.round_order("rec_a")
    chosen = sc.selected_rounds(order, 19)
    assert len(chosen) == 6 and all(n <= 19 for n in chosen)


def test_frames_count_correct_wrong_abstain_and_undefined_separately():
    key = [{"no": f"{i:03d}", "recording_id": "r", "second": i} for i in range(6)]
    predictions = {"r": [
        {"round": "ACTIVE", "life": "ALIVE", "camera": "SELF"},
        {"round": "BUY", "life": "DEAD", "camera": "UNKNOWN"},
        {"round": "UNKNOWN", "life": "ALIVE", "camera": "SPECTATOR"},
        {"round": "ENDED", "life": "UNKNOWN", "camera": "SELF"},
        {"round": "UNKNOWN", "life": "UNKNOWN", "camera": "UNKNOWN"},
        {"round": "BUY", "life": "ALIVE", "camera": "SELF"},
    ]}
    labels = {
        "000": {"round": "ACTIVE", "life": "ALIVE", "camera": "SELF"},
        "001": {"round": "ACTIVE", "life": "DEAD", "camera": "SELF"},
        "002": {"round": "ACTIVE", "life": "ALIVE", "camera": "SELF"},
        "003": {"round": "unsure", "life": "ALIVE", "camera": "SELF"},
        "004": {"round": "OUT_OF_ROUND", "life": "NA", "camera": "NA"},
        "005": {"round": "OUT_OF_ROUND", "life": "NA", "camera": "NA"},
    }
    result = sc.score_frames(key, labels, predictions)
    rnd = result["round"]
    assert (rnd["correct"], rnd["wrong"], rnd["abstain"], rnd["unsure"]) == (1, 1, 1, 1)
    assert rnd["undefined_frames"] == 2 and rnd["undefined_false_claims"] == 1
    assert rnd["accuracy"] == round(1 / 3, 4) and rnd["coverage"] == round(2 / 3, 4)
    assert rnd["precision_when_answered"] == 0.5
    cam = result["camera"]
    assert (cam["correct"], cam["wrong"], cam["abstain"]) == (2, 1, 1)
    assert result["life"]["correct"] == 3 and result["life"]["abstain"] == 1


def test_boundary_error_is_zero_inside_the_bracket_and_misses_are_counted():
    items = [
        {"id": "A01S", "recording_id": "r", "kind": "start"},
        {"id": "A02S", "recording_id": "r", "kind": "start"},
        {"id": "A03S", "recording_id": "r", "kind": "start"},
        {"id": "A01E", "recording_id": "r", "kind": "end"},
    ]
    candidates = {"r": [
        {"kind": "round_start", "lower_timestamp": 99.0, "upper_timestamp": 101.0},
        {"kind": "round_start", "lower_timestamp": 203.0, "upper_timestamp": 204.0},
        {"kind": "round_end", "lower_timestamp": 150.0, "upper_timestamp": 152.0},
    ]}
    labels = {"A01S": "100", "A02S": "200", "A03S": "400", "A01E": "UNSURE"}
    result = sc.score_boundaries(items, labels, candidates)
    start = result["start"]
    assert start["labelled"] == 3 and start["missed"] == 1 and start["detected"] == 2
    assert start["within_bracket"] == 1 and start["error_max_seconds"] == 2.5
    assert result["end"]["unsure"] == 1 and result["end"]["labelled"] == 0


def test_wilson_interval_and_label_page():
    assert sc.wilson(0, 0) is None
    low, high = sc.wilson(27, 30)
    assert low < 0.9 < high
    page = sc._label_page(["001", "002"])
    assert "frames/002.jpg" in page and "frame_labels.csv" in page
