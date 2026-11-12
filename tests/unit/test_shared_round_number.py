"""Round number candidates cannot fabricate missing scores or event counts."""

from copy import deepcopy

import pytest
from test_shared_game_timeline import obs, replay


@pytest.mark.parametrize("phase", ["buy", "active"])
@pytest.mark.parametrize("score", [[0, 0], [3, 4], [17, 17]])
def test_current_score_and_phase_are_unqualified_candidates(phase, score):
    row = obs(500, [phase], context={"score": score})
    result = replay([row])
    number = result["frames"][0]["round_number"]
    assert number["value"] == sum(score) + 1
    assert number["unknown_possible"] is True and number["qualified"] is False
    assert number["score_observations"][0]["sample"] == row["sample"]
    assert number["score_observations"][0]["observation_id"] == row["observation_id"]
    assert result["qualified_facts"] == result["qualified_events"] == []


@pytest.mark.parametrize("phase", [[], ["result"], ["intermission"], ["active", "buy"]])
def test_ended_or_unknown_phase_keeps_score_update_ambiguity(phase):
    number = replay([obs(0, phase, context={"score": [3, 4]})])["frames"][0]["round_number"]
    assert number["value"] is None
    assert number["candidates"] == [7, 8]


def test_zero_score_does_not_resolve_an_unobserved_phase():
    number = replay([obs(0, context={"score": [0, 0]})])["frames"][0]["round_number"]
    assert number["candidates"] == [1] and number["value"] is None


def test_carried_phase_is_not_a_current_phase_observation():
    result = replay([obs(0, ["active"]), obs(1, context={"score": [2, 1]})])
    assert result["frames"][1]["round"]["value"] == "ACTIVE"
    assert result["frames"][1]["round_number"]["value"] is None


@pytest.mark.parametrize("epoch", ["e", "new"])
def test_number_does_not_carry_a_previous_score_across_any_epoch(epoch):
    result = replay(
        [obs(0, ["buy"], context={"score": [2, 1]}), obs(1, ["active"], epoch=epoch)]
    )
    number = result["frames"][1]["round_number"]
    assert number["value"] is None and number["candidates"] == []


def test_same_total_conflicting_scores_are_not_consensus():
    result = replay(
        [obs(0, ["active"], context={"score": [2, 3]}),
         obs(0, ["active"], context={"score": [3, 2]})]
    )
    number = result["frames"][0]["round_number"]
    assert number["value"] is None and number["candidates"] == [5, 6]
    assert number["reason"] == "conflicting_current_scores"
    assert len(number["score_observations"]) == 2


@pytest.mark.parametrize("score", [[True, 0], [-1, 2], [100, 1], [1.0, 2], [1], "1:2"])
def test_invalid_score_is_retained_without_a_number(score):
    number = replay([obs(0, ["buy"], context={"score": score})])["frames"][0]["round_number"]
    assert number["value"] is None and number["candidates"] == []
    assert number["score_observations"][0]["displayed_score"] == score
    assert number["reason"] == "invalid_score_observation"


def test_unread_frame_and_empty_seconds_are_not_filled_by_known_numbers():
    result = replay(
        [obs(0, ["active"], context={"score": [1, 1]}), obs(1),
         obs(30, ["active"], context={"score": [1, 1]})]
    )
    seconds = result["seconds"]
    assert seconds[0]["round_number"]["value"] is None
    assert seconds[0]["round_number"]["candidates"] == [3]
    assert seconds[1]["round_number"]["candidates"] == []
    assert seconds[1]["observation_present"] is False
    assert seconds[-1]["round_number"]["value"] == 3


def test_number_aggregation_does_not_collapse_parallel_acquisition_uncertainty():
    result = replay(
        [obs(0, ["active"], context={"score": [1, 1]}), obs(0, epoch="other")]
    )
    assert result["seconds"][0]["round_number"]["value"] is None
    assert result["seconds"][0]["round_number"]["candidates"] == [3]
    assert len(result["acquisition_seconds"]) == 2


def test_exact_pixel_alias_keeps_score_provenance_in_its_original_epoch():
    current = obs(0, ["active"])
    other = obs(0, epoch="other", context={"score": [1, 1]})
    result = replay([current, other], fuse_exact_native_evidence=True)
    assert len(result["frames"]) == 2
    for f in result["frames"]:
        assert f["round_number"]["value"] == 3
        assert f["round_number"]["score_observations"][0]["sample"] == other["sample"]
    assert current["sample"]["native_epoch"] == "e"


def test_retracting_a_score_revises_number_without_counting_round_events():
    from valorant_ai_coach.temporal.game import DevelopmentGameTimeline

    engine = DevelopmentGameTimeline()
    row = obs(0, ["buy"], context={"score": [0, 0]})
    engine.add(row)
    before = deepcopy(engine.rebuild())
    engine.retract(row["observation_id"])
    engine.add(obs(0, ["buy"]))
    engine.add(obs(1, ["active"]))
    after = engine.rebuild()
    assert before["frames"][0]["round_number"]["value"] == 1
    assert after["frames"][0]["round_number"]["value"] is None
    assert after["revision_history"][-1]["revised_sample_ids"] == [row["sample"]["sample_sha256"]]
    assert any(t["kind"] == "round_start" for t in after["transitions"])
    assert all(f["round_number"]["candidates"] == [] for f in after["frames"])
