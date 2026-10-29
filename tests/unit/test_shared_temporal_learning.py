import pytest
from test_shared_game_timeline import obs, replay

from valorant_ai_coach.temporal.learning import compare_temporal_learning


def test_temporal_learning_keeps_physical_splits_and_does_not_adopt():
    result = replay(
        [
            obs(t, ["buy"] if t < 2 else ["active"], source=source)
            for source in ("a", "c")
            for t in range(4)
        ]
    )
    kwargs = {
        "physical_matches": {"a" * 64: "match1", "c" * 64: "match2"},
        "train_groups": {"match1"},
        "compare_groups": {"match2"},
    }
    study = compare_temporal_learning(result, **kwargs)
    assert study["adopted"] is False
    assert study["pretext"]["train_pairs"] == study["pretext"]["comparison_pairs"] == 3
    assert study["weak_and_rerank"]["life"]["recognition_accuracy"] is None
    assert study["formal_outputs"] == 0
    with pytest.raises(ValueError, match="Disjoint"):
        compare_temporal_learning(
            result,
            physical_matches=kwargs["physical_matches"],
            train_groups={"match1"},
            compare_groups={"match1"},
        )
    with pytest.raises(ValueError, match="identity"):
        compare_temporal_learning(
            result, physical_matches={}, train_groups={"a"}, compare_groups={"b"}
        )
