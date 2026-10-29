import pytest
from test_shared_game_timeline import obs, replay

from valorant_ai_coach.temporal.game import DevelopmentGameTimeline


def episode(*, reset=None):
    return [
        obs(0, ["buy", "owner_hud"]),
        obs(1, ["active", "owner_hud"]),
        obs(2, ["spectator", "report", "recorder_elimination_display"], continuity=reset),
        obs(3, ["spectator"]),
        obs(4, ["result"]),
        obs(5, ["buy"]),
        obs(6, ["active"]),
        obs(7, ["active", "owner_hud"]),
    ]


def test_owned_victim_display_and_spectator_support_competing_episode_only():
    result = replay(episode())
    death = result["frames"][2]["life"]
    assert death["value"] == "DEAD"
    assert death["hypotheses"] == ["DEAD", "DOWNED", "UNKNOWN"]
    assert death["uncertainty"] == "competing_unqualified_life_hypothesis"
    assert result["frames"][5]["life"]["value"] == "UNKNOWN"
    assert result["frames"][-1]["life"]["value"] == "ALIVE"
    candidates = [t for t in result["transitions"] if t["kind"].endswith("_hypothesis")]
    assert [t["kind"] for t in candidates] == ["death_hypothesis", "return_hypothesis"]
    assert candidates[1]["linked_elimination_candidate_id"] == candidates[0]["candidate_id"]
    assert candidates[1]["lower_sample"]["native_pts_tick"] == 3
    assert all(t["internal_game_event_time"] is None for t in candidates)
    assert result["qualified_facts"] == result["qualified_events"] == []
    assert set(result["seconds"][0]["life"]["hypotheses"]) >= {"DEAD", "DOWNED", "UNKNOWN"}
    assert "competing_unqualified_life_hypothesis" in result["seconds"][0]["life"]["uncertainties"]


@pytest.mark.parametrize("missing", ["owner_hud", "spectator", "recorder_elimination_display"])
def test_missing_positive_evidence_does_not_invent_death(missing):
    rows = [
        obs(0, ["buy"] + ([] if missing == "owner_hud" else ["owner_hud"])),
        obs(
            1, [s for s in ["spectator", "report", "recorder_elimination_display"] if s != missing]
        ),
    ]
    result = replay(rows)
    assert not any(t["kind"] == "death_hypothesis" for t in result["transitions"])
    assert result["frames"][-1]["life"]["value"] != "DEAD"


def test_confirmed_source_break_prevents_linking_prior_owner():
    result = replay(episode(reset={"content_break_confirmed": True}))
    assert not any(t["kind"].endswith("_hypothesis") for t in result["transitions"])


def test_downed_observation_overrides_the_elimination_hypothesis():
    result = replay(episode()[:3] + [obs(3, ["downed"])])
    assert result["frames"][-1]["life"]["value"] == "DOWNED"


def test_same_round_self_without_revival_leaves_return_unresolved():
    result = replay(episode()[:3] + [obs(3, ["active", "owner_hud"])])
    assert result["frames"][-1]["life"]["value"] == "UNKNOWN"
    assert not any(t["kind"] == "return_hypothesis" for t in result["transitions"])


def test_direct_death_can_return_after_observed_next_buy_even_if_first_self_is_active():
    result = replay(
        [
            obs(0, ["buy", "owner_hud"]),
            obs(1, ["active", "death"]),
            obs(2, ["buy"]),
            obs(3, ["active", "owner_hud"]),
        ]
    )
    assert result["frames"][-1]["life"]["value"] == "ALIVE"
    assert sum(t["kind"] == "return" for t in result["transitions"]) == 1


def test_later_downed_evidence_revises_prior_elimination_without_changing_candidate_id():
    engine = DevelopmentGameTimeline()
    for row in episode()[:3]:
        engine.add(row)
    before = engine.rebuild()
    engine.add(obs(3, ["downed"]))
    after = engine.rebuild()
    assert before["frames"][2]["life"]["value"] == "DEAD"
    assert after["frames"][2]["life"]["value"] == "DOWNED"

    def hypothesis(result):
        return next(t for t in result["transitions"] if t["kind"] == "death_hypothesis")

    assert hypothesis(before)["candidate_id"] == hypothesis(after)["candidate_id"]
    assert after["revision_history"][-1]["revised_sample_ids"]


def test_later_downed_cannot_revise_across_a_confirmed_break():
    result = replay(episode()[:3] + [obs(3, ["downed"], continuity={"decode_ok": False})])
    assert result["frames"][2]["life"]["value"] == "DEAD"
