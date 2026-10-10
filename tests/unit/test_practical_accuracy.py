import pytest

from scripts.e2e.practical_accuracy import evaluate_matched_boundary
from valorant_ai_coach.rounds.boundaries import BoundaryObservation


def predicted(time):
    return BoundaryObservation("round_start", "provisional", time, time + .85,
                               (time, time + .85), .93, {"producer": "synthetic"})


@pytest.mark.parametrize("offset,status", [
    (-.1, "PASS"), (.1, "PASS"), (.099, "PASS"), (.101, "FAIL"),
])
def test_tolerance_scores_boundary_and_never_confirmation(offset, status):
    result = evaluate_matched_boundary(predicted(4 + offset), truth_kind="round_start",
                                       truth_time_sec=4)
    assert result["status"] == status
    assert result["boundary_status"] == "provisional"
    assert result["absolute_error_sec"] == pytest.approx(abs(offset))


def test_wrong_kind_and_missing_boundary_never_pass():
    assert evaluate_matched_boundary(predicted(4), truth_kind="round_end",
                                      truth_time_sec=4)["status"] == "FAIL"
    assert evaluate_matched_boundary(None, truth_kind="round_start",
                                      truth_time_sec=4)["status"] == "FAIL"
    assert evaluate_matched_boundary(predicted(4), truth_kind="round_start",
                                      truth_time_sec=None)["status"] == "NE"
