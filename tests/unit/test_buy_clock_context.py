"""Clock-supported phase hypotheses preserve all event/ownership boundaries."""

from copy import deepcopy

import pytest
from test_shared_game_timeline import obs, replay


def inputs():
    return [
        obs(0, ["buy", "owner_hud"], context={"score": [0, 0], "timer_seconds": 3}),
        obs(10, ["buy", "owner_hud"], context={"score": [0, 0], "timer_seconds": 2}),
        obs(20, ["buy", "owner_hud"], context={"score": [0, 0]}),
        obs(30, ["owner_hud"]),
        obs(40, ["owner_hud"], maps=[{"candidate_id": "unqualified-marker", "point": [1, 2]}]),
        obs(50, ["active", "owner_hud"], context={"score": [0, 0], "timer_seconds": 96}),
    ]


def test_two_clock_displays_and_future_active_revise_only_stale_round_candidate():
    rows = inputs()
    baseline = replay(rows)
    result = replay(rows, buy_clock_expiry=True)
    target = result["frames"][4]
    assert target["map"]["candidates"]
    assert baseline["frames"][4]["round"]["value"] == "BUY"
    assert target["round"]["value"] == "ACTIVE"
    assert target["round"]["hypotheses"] == ["ACTIVE", "BUY", "UNKNOWN"]
    assert target["round"]["forward_estimate"] == baseline["frames"][4]["round"]
    assert target["round"]["uncertainty"] == "game_clock_progress_and_pause_unverified"
    assert result["frames"][3]["round"] == baseline["frames"][3]["round"]
    for before, after in zip(baseline["frames"], result["frames"], strict=True):
        for field in before.keys() - {"round", "round_number"}:
            assert before[field] == after[field]
    assert result["transitions"] == baseline["transitions"]
    assert result["boundary_candidates"] == baseline["boundary_candidates"]
    assert result["qualified_events"] == result["qualified_facts"] == []
    history = result["buy_clock_projection_history"]
    assert len(history) == 1 and history[0]["internal_game_event_time"] is None
    assert history[0]["Map_authority"] is history[0]["lifecycle_authority"] is False
    assert "buy_clock_projection_history" not in baseline


@pytest.mark.parametrize(
    "change",
    [
        "one_clock",
        "stationary_clock",
        "increasing_clock",
        "clock_jump",
        "clock_gap",
        "source",
        "epoch",
        "decode",
        "profile",
        "PTS_gap",
        "future_score",
        "future_buy",
        "future_conflict",
        "no_active",
        "future_weak",
        "stale_clock",
    ],
)
def test_missing_or_contrary_evidence_never_gets_clock_candidate(change):
    rows = inputs()
    if change == "one_clock":
        rows[0] = obs(0, ["buy", "owner_hud"], context={"score": [0, 0]})
    elif change == "stationary_clock":
        rows[0] = obs(0, ["buy"], context={"score": [0, 0], "timer_seconds": 2})
    elif change == "increasing_clock":
        rows[0] = obs(0, ["buy"], context={"score": [0, 0], "timer_seconds": 1})
    elif change == "clock_jump":
        rows[0] = obs(0, ["buy"], context={"score": [0, 0], "timer_seconds": 10})
    elif change == "clock_gap":
        rows[0] = obs(-20, ["buy"], context={"score": [0, 0], "timer_seconds": 5})
    elif change in {"source", "epoch", "decode", "profile", "PTS_gap"}:
        kwargs = {
            "source": {"source": "c"},
            "epoch": {"epoch": "other"},
            "decode": {"continuity": {"decode_ok": False}},
            "profile": {"context": {"profile_fingerprint": "c" * 64}},
            "PTS_gap": {},
        }[change]
        rows[3] = obs(35 if change == "PTS_gap" else 30, ["owner_hud"], **kwargs)
        if change in {"source", "epoch"}:
            for j in range(3, 6):
                rows[j] = obs(
                    j * 10,
                    ["active"] if j == 5 else ["owner_hud"],
                    context={"score": [0, 0]} if j == 5 else None,
                    **kwargs,
                )
        if change == "PTS_gap":
            rows.pop(2)
    elif change == "future_score":
        rows[-1] = obs(50, ["active"], context={"score": [1, 0]})
    elif change == "future_buy":
        rows[-1] = obs(50, ["buy"], context={"score": [0, 0]})
        rows.append(obs(60, ["active"], context={"score": [0, 0]}))
    elif change == "future_conflict":
        rows[-1] = obs(50, ["buy", "active"], context={"score": [0, 0]})
    elif change == "future_weak":
        rows[-1] = obs(50, ["active"], context={"unqualified_round_model": True})
    elif change == "stale_clock":
        rows = (
            rows[:3]
            + [obs(t, ["buy"]) for t in [30, 40, 50, 60]]
            + [obs(70), obs(80), obs(90, ["active"], context={"score": [0, 0]})]
        )
    else:
        rows = rows[:-1]
    result = replay(rows, buy_clock_expiry=True)
    assert result["buy_clock_projection_history"] == []


def test_direct_buy_is_retained_even_after_expected_expiry():
    rows = inputs()
    rows[4] = obs(40, ["buy", "owner_hud"], context={"score": [0, 0]})
    assert replay(rows, buy_clock_expiry=True)["frames"][4]["round"]["value"] == "BUY"


def test_rule_uses_relative_clocks_without_source_or_absolute_timestamp_conditions():
    from valorant_ai_coach.temporal.game import observation

    shifted = []
    for row in inputs():
        sample = {k: v for k, v in row["sample"].items() if k != "sample_sha256"}
        sample.update(
            source_id="another-recording",
            source_sha256="d" * 64,
            native_pts_tick=sample["native_pts_tick"] + 137,
            acquisition_id="another-epoch",
            native_epoch="another-epoch",
        )
        context = deepcopy(row["context"])
        if "score" in context:
            context["score"] = [11, 9]
        shifted.append(
            observation(
                sample=sample,
                producer=row["producer_fingerprint"],
                signals=row["signals"],
                raw=row["raw"],
                context=context,
            )
        )
    result = replay(shifted, buy_clock_expiry=True)
    assert result["frames"][4]["round"]["value"] == "ACTIVE"
    assert len(result["buy_clock_projection_history"]) == 1


def test_option_requires_offline_and_retracting_confirmation_reverses_projection():
    with pytest.raises(ValueError):
        replay([], buy_clock_expiry=True, forward_only=True)
    from valorant_ai_coach.temporal.game import DevelopmentGameTimeline

    rows = inputs()
    engine = DevelopmentGameTimeline(buy_clock_expiry=True)
    for row in rows:
        engine.add(row)
    first = deepcopy(engine.rebuild())
    engine.retract(rows[-1]["observation_id"])
    second = engine.rebuild()
    assert first["frames"][4]["round"]["value"] == "ACTIVE"
    assert second["frames"][4]["round"]["value"] == "BUY"
    assert second["revision_history"][-1]["revised_sample_ids"]
