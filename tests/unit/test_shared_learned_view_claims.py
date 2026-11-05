"""Research view models retain uncertainty and cannot sponsor Map ownership."""

import pytest
from test_shared_game_timeline import obs, replay

from valorant_ai_coach.temporal.game import map_context


def weak(tick, signals=(), **kwargs):
    return obs(tick, signals, context={"unqualified_view_model": True}, **kwargs)


def test_weak_owner_candidate_does_not_sponsor_current_map_or_correspondence():
    r = replay([weak(0, ["buy", "owner_hud"], maps=[{"candidate": "retained"}])])["frames"][0]
    assert r["life"]["value"] == "ALIVE" and r["camera"]["value"] == "SELF"
    assert r["life"]["hypotheses"] == ["ALIVE", "UNKNOWN"]
    assert r["camera"]["hypotheses"] == ["REMOTE", "SELF", "UNKNOWN"]
    assert r["camera"]["uncertainty"] == "unqualified_learned_view_candidate"
    assert r["map"]["candidates"] == [{"candidate": "retained"}]
    assert r["map"]["current_recorder_view_evidence_ids"] == []
    assert r["map"]["current_self_position_candidates"] == []
    assert (
        map_context(r, producer_fingerprint="b" * 64, revision="1")["recorder_correspondence"]
        == "UNKNOWN"
    )


def test_weak_spectator_does_not_attribute_positive_view_hp_to_recorder():
    r = replay([weak(0, ["spectator"])])["frames"][0]
    assert r["camera"]["value"] == "SPECTATOR"
    assert r["camera"]["hypotheses"] == ["SPECTATOR", "UNKNOWN"]
    assert r["life"]["value"] == "UNKNOWN"


def test_weak_owner_alternatives_survive_short_carry_and_offline_gap_fill():
    result = replay(
        [weak(0, ["owner_hud"]), obs(15), obs(30), weak(35, ["owner_hud"])], future_seconds=4
    )
    assert result["frames"][2]["camera"]["hypotheses"] == ["REMOTE", "SELF", "UNKNOWN"]
    carry = replay([weak(0, ["owner_hud"]), obs(10)])["frames"][1]
    assert carry["camera"]["hypotheses"] == ["REMOTE", "SELF", "UNKNOWN"]


def test_stronger_current_owner_can_still_supply_its_own_map_evidence():
    result = replay([weak(0, ["owner_hud"]), obs(0, ["owner_hud"])])
    frame = result["frames"][0]
    assert frame["camera"]["hypotheses"] == ["SELF"]
    strong = [
        r["observation_id"]
        for r in result["observations"]
        if r["context"].get("unqualified_view_model") is not True
    ]
    assert frame["map"]["current_recorder_view_evidence_ids"] == strong


@pytest.mark.parametrize("value", ["true", 1, None])
def test_malformed_weak_claim_tag_is_rejected(value):
    with pytest.raises(ValueError, match="boolean"):
        obs(0, ["owner_hud"], context={"unqualified_view_model": value})
