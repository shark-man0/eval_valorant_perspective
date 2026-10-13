from copy import deepcopy

import pytest

from valorant_ai_coach.hud.round_lifecycle import BoundaryDecision
from valorant_ai_coach.rounds.boundaries import BoundaryObservation


def candidate():
    return BoundaryDecision("round_end", 12.25, .94, {"evidence_provenance": {
        "producer": "synthetic_composite_candidate",
        "confirmation_pts_sec": 13.10,
        "pts_sec": [12.25, 12.30, 13.10],
    }})


def test_delayed_confirmation_keeps_boundary_time_and_provisional_status():
    decision = candidate()
    original = deepcopy(decision.attributes)
    result = BoundaryObservation.provisional_from_decision(decision)
    assert result.boundary_time_sec == 12.25
    assert result.confirmation_time_sec == 13.10
    assert result.boundary_status == "provisional"
    assert result.confidence == .94
    assert decision.attributes == original
    assert BoundaryObservation.from_dict(result.to_dict()) == result


@pytest.mark.parametrize("field,value", [
    ("boundary_time_sec", 12.26), ("boundary_time_sec", True),
    ("confirmation_time_sec", 12.0), ("confirmation_time_sec", float("nan")),
    ("confidence", 1.1), ("confidence", True),
    ("evidence_times_sec", [13.10, 12.25]),
    ("boundary_status", "accepted"), ("kind", "player_death"),
])
def test_invalid_transport_rejected(field, value):
    data = BoundaryObservation.provisional_from_decision(candidate()).to_dict()
    data[field] = value
    with pytest.raises(ValueError):
        BoundaryObservation.from_dict(data)


def test_unknown_retains_reason_without_guessing_adjacent_boundary():
    result = BoundaryObservation("round_end", "unknown", None, None, (), None,
                                 {"reason": "no_observed_end"})
    assert BoundaryObservation.from_dict(result.to_dict()) == result
    with pytest.raises(ValueError, match="unknown boundary"):
        BoundaryObservation("round_end", "unknown", 12.0, None, (), None,
                            {"reason": "no_observed_end"})


def test_qualification_metadata_never_automatically_promotes_a_candidate():
    decision = candidate()
    decision.attributes["evidence_provenance"]["qualification_sha256"] = "a" * 64
    result = BoundaryObservation.provisional_from_decision(decision)
    assert result.boundary_status == "provisional"
    output = result.to_dict()
    output["provenance"]["producer"] = "mutated_export"
    assert result.provenance["producer"] == "synthetic_composite_candidate"
