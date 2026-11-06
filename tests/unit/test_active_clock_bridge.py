from copy import deepcopy

import pytest
from test_shared_game_timeline import obs, replay


def inputs():
    return [
        obs(0, ["active", "owner_hud"], context={"timer_seconds": 50, "score": [0, 0]}),
        obs(10, ["active", "owner_hud"], context={"timer_seconds": 49, "score": [0, 0]}),
        obs(20, ["owner_hud"]), obs(30, ["owner_hud"]), obs(40, ["owner_hud"]),
        obs(50, ["owner_hud"], context={"timer_seconds": 45, "score": [0, 0]}),
        obs(60, ["owner_hud"], context={"timer_seconds": 44, "score": [0, 0]}),
        obs(70, ["owner_hud"], context={"timer_seconds": 43, "score": [0, 0]}),
    ]


def test_real_clock_chain_reacquires_only_round_candidate_after_unread_gap():
    rows = inputs()
    before, after = replay(rows), replay(rows, active_clock_bridge=True)
    assert before["frames"][5]["round"]["value"] == "UNKNOWN"
    assert after["frames"][5]["round"]["value"] == "ACTIVE"
    assert after["frames"][5]["round"]["hypotheses"] == ["ACTIVE", "BUY", "UNKNOWN"]
    assert after["frames"][4]["round"] == before["frames"][4]["round"]
    for old, new in zip(before["frames"], after["frames"], strict=True):
        assert {k: v for k, v in old.items() if k not in {"round", "round_number"}} == {
            k: v for k, v in new.items() if k not in {"round", "round_number"}}
    for field in ["observations", "transitions", "boundary_candidates", "qualified_events"]:
        assert before[field] == after[field]
    assert after["qualified_facts"] == []
    assert all(h["internal_game_event_time"] is None and not h["Map_authority"]
               and not h["lifecycle_authority"] for h in after["active_clock_projection_history"])


@pytest.mark.parametrize("change", [
    "no_anchor", "weak_anchor", "no_future", "stationary_future", "clock_jump",
    "different_score", "future_score", "intermediate_score", "buy", "result", "decode",
    "profile", "epoch",
])
def test_missing_or_contrary_clock_evidence_does_not_resolve_unknown(change):
    rows = inputs()
    if change == "no_anchor":
        rows = rows[2:]
    elif change == "weak_anchor":
        rows[:2] = [obs(i * 10, ["active"], context={"unqualified_round_model": True})
                    for i in range(2)]
    elif change == "no_future":
        rows = rows[:6]
    elif change == "stationary_future":
        rows[6:] = [obs(i * 10, ["owner_hud"], context={"timer_seconds": 45, "score": [0, 0]})
                    for i in [6, 7]]
    elif change == "clock_jump":
        rows[5] = obs(50, ["owner_hud"], context={"timer_seconds": 30, "score": [0, 0]})
    elif change == "different_score":
        rows[5] = obs(50, ["owner_hud"], context={"timer_seconds": 45, "score": [1, 0]})
    elif change == "future_score":
        rows[6] = obs(60, ["owner_hud"], context={"timer_seconds": 44, "score": [1, 0]})
    elif change == "intermediate_score":
        rows[4] = obs(40, ["owner_hud"], context={"score": [1, 0]})
    elif change in {"buy", "result"}:
        rows[4] = obs(40, [change, "owner_hud"])
    elif change == "decode":
        rows[4] = obs(40, ["owner_hud"], continuity={"decode_ok": False})
    elif change == "profile":
        rows[4] = obs(40, ["owner_hud"], context={"profile_fingerprint": "f" * 64})
    elif change == "epoch":
        rows[4:] = [obs(i * 10, ["owner_hud"], epoch="new",
                        context={"timer_seconds": 50 - i, "score": [0, 0]}) for i in range(4, 8)]
    result = replay(rows, active_clock_bridge=True)
    assert not any(h["sample"]["native_pts_tick"] == 50
                   for h in result["active_clock_projection_history"])


def test_later_evidence_retraction_restores_uncertainty_and_forward_mode_is_rejected():
    from valorant_ai_coach.temporal.game import DevelopmentGameTimeline
    with pytest.raises(ValueError):
        DevelopmentGameTimeline(active_clock_bridge=True, forward_only=True)
    engine = DevelopmentGameTimeline(active_clock_bridge=True)
    rows = inputs()
    for row in rows:
        engine.add(row)
    first = deepcopy(engine.rebuild())
    for row in rows[6:]:
        engine.retract(row["observation_id"])
    second = engine.rebuild()
    assert first["frames"][5]["round"]["value"] == "ACTIVE"
    assert second["frames"][5]["round"]["value"] == "UNKNOWN"


def test_long_reading_gap_requires_new_measured_clocks_and_keeps_gap_seconds_unknown():
    rows = inputs()[:2] + [obs(i * 10, ["owner_hud"]) for i in range(2, 21)] + [
        obs(i * 10, ["owner_hud"], context={"timer_seconds": 50 - i, "score": [0, 0]})
        for i in [21, 22, 23]
    ]
    before, after = replay(rows), replay(rows, active_clock_bridge=True)
    assert before["frames"][21]["round"]["value"] == "UNKNOWN"
    assert after["frames"][21]["round"]["value"] == "ACTIVE"
    assert after["frames"][10]["round"] == before["frames"][10]["round"]
