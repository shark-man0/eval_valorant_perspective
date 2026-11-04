"""Native identity belongs to transport; summary signals cannot replace suppliers."""

import pytest
from test_shared_game_timeline import obs

from valorant_ai_coach.temporal.match import _pts_expression, frame_observations


def payload():
    return {"producer_fingerprint": "b" * 64, "signals": ["spectator"], "raw": {}}


def test_refinement_summary_is_not_an_additional_state_observation():
    sample = obs(0)["sample"]
    rows = frame_observations(
        {"signals": ["owner_hud"], "supplier_observations": [payload()]}, sample, "a" * 64
    )
    assert len(rows) == 1 and rows[0]["signals"] == ["spectator"]
    assert rows[0]["sample"] == sample


def test_single_observer_cannot_replace_its_bound_producer():
    rows = frame_observations(
        {"producer_fingerprint": "f" * 64, "signals": [], "raw": {}},
        obs(0)["sample"],
        "a" * 64,
    )
    assert rows[0]["producer_fingerprint"] == "a" * 64


@pytest.mark.parametrize("key", ["sample", "continuity", "source_id", "native_pts_tick"])
def test_supplier_cannot_inject_native_identity_or_continuity(key):
    p = {**payload(), key: {}}
    with pytest.raises(ValueError, match="override acquisition"):
        frame_observations({"supplier_observations": [p]}, obs(0)["sample"], "a" * 64)


def test_duplicate_supplier_is_not_independent_confirmation():
    with pytest.raises(ValueError, match="Duplicate supplier"):
        frame_observations(
            {"supplier_observations": [payload(), payload()]}, obs(0)["sample"], "a" * 64
        )


def test_pts_expression_stays_balanced_for_native_audit_batches():
    expression = _pts_expression(list(range(512)))
    depth = highest = 0
    for char in expression:
        depth += (char == "(") - (char == ")")
        highest = max(highest, depth)
    assert depth == 0 and highest <= 10
    assert expression.count("eq(pts") == 512
