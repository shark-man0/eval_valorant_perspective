"""Weak current Round text/shape cannot grant lifecycle or position authority."""

import pytest
from test_shared_game_timeline import obs, replay


def weak(tick, signals=("active",), **kwargs):
    return obs(tick, signals, context={"unqualified_round_model": True}, **kwargs)


def test_weak_active_preserves_unknown_and_rule_estimate_without_events():
    result = replay([weak(0)])
    frame = result["frames"][0]
    assert frame["round"]["value"] == "ACTIVE"
    assert frame["round"]["hypotheses"] == ["ACTIVE", "UNKNOWN"]
    assert frame["round"]["rule_estimate"]["value"] == "UNKNOWN"
    assert frame["round_token"] is None
    assert frame["life"]["value"] == frame["camera"]["value"] == "UNKNOWN"
    assert frame["map"]["current_recorder_view_evidence_ids"] == []
    assert result["transitions"] == []
    assert result["round_model_projection_history"][0]["sample"] == frame["sample"]
    assert result["qualified_facts"] == result["qualified_events"] == []


def test_weak_active_does_not_select_a_number_from_current_score():
    result = replay([obs(0, context={"score": [2, 1]}), weak(0)])
    number = result["frames"][0]["round_number"]
    assert number["value"] is None and number["candidates"] == [3, 4]


@pytest.mark.parametrize("signal", ["buy", "active", "result", "intermission"])
def test_independent_current_phase_and_other_domains_are_retained(signal):
    strong = obs(0, [signal], context={"score": [1, 1]})
    before, after = replay([strong]), replay([strong, weak(0)])
    for domain in ["round", "round_number", "life", "camera", "map"]:
        assert before["frames"][0][domain] == after["frames"][0][domain]
    assert before["transitions"] == after["transitions"]


def test_weak_current_claim_is_not_carried_or_backward_filled():
    result = replay([weak(0), obs(1), weak(2)])
    assert [f["round"]["value"] for f in result["frames"]] == ["ACTIVE", "UNKNOWN", "ACTIVE"]
    assert result["transitions"] == []
    assert len(result["round_model_projection_history"]) == 2


def test_weak_claim_does_not_advance_round_token_or_life_context():
    rows = [obs(0, ["buy", "owner_hud"]), weak(1), obs(2, ["buy", "owner_hud"])]
    before = replay([rows[0], obs(1), rows[2]])
    after = replay(rows)
    assert [f["round_token"] for f in before["frames"]] == [
        f["round_token"] for f in after["frames"]
    ]
    assert before["transitions"] == after["transitions"]
    assert [f["life"] for f in before["frames"]] == [f["life"] for f in after["frames"]]


@pytest.mark.parametrize("signals", [["owner_hud"], ["death"], ["result"], ["active", "spectator"]])
def test_round_model_cannot_supply_other_domain_claims(signals):
    with pytest.raises(ValueError, match="only an unqualified"):
        weak(0, signals)


@pytest.mark.parametrize("field", ["score", "timer_seconds"])
def test_round_model_cannot_supply_numeric_rule_context(field):
    with pytest.raises(ValueError, match="only an unqualified"):
        obs(0, ["active"], context={"unqualified_round_model": True, field: [1, 1]})


def test_round_model_cannot_supply_map_positions():
    with pytest.raises(ValueError, match="only an unqualified"):
        weak(0, maps=[{"position": "candidate"}])


def test_round_model_flag_requires_an_explicit_boolean():
    with pytest.raises(ValueError, match="must be a boolean"):
        obs(0, ["active"], context={"unqualified_round_model": 1})


@pytest.mark.parametrize("fuse", [False, True])
def test_future_result_evidence_never_includes_empty_round_model_rows(fuse):
    rows = [obs(0, ["active"], context={"score": [1, 1]}),
            obs(1, ["active"], context={"score": [2, 1]}),
            obs(2, ["result"], context={"score": [2, 1]})]
    before = replay(rows, fuse_exact_native_evidence=fuse)
    after = replay(rows + [weak(t, signals=()) for t in range(3)], fuse_exact_native_evidence=fuse)
    assert before["transitions"] == after["transitions"]
    assert before["boundary_candidates"] == after["boundary_candidates"]
    for a, b in zip(before["frames"], after["frames"], strict=True):
        for field in ["round", "life", "camera", "map", "round_number"]:
            assert a[field] == b[field]


def test_exact_pixel_projection_retains_original_model_epoch_without_carry():
    measured = weak(0, epoch="other")
    result = replay([obs(0), measured], fuse_exact_native_evidence=True)
    assert len(result["frames"]) == 2
    for frame in result["frames"]:
        assert frame["round"]["hypotheses"] == ["ACTIVE", "UNKNOWN"]
        assert frame["round_model_hypotheses"]["input_samples"] == [measured["sample"]]
        assert frame["continuity"]["semantic"] == "UNKNOWN"
    assert result["transitions"] == []
