"""Human labels cannot enter prediction or duplicate an evaluation point."""

import json

import pytest
from test_shared_game_timeline import obs

from valorant_ai_coach.temporal import compare_modes as module


def inputs(tmp_path, monkeypatch, labels):
    class Policy:
        def __init__(self, value):
            pass

        def admit(self, sample):
            assert sample["source_id"] == "a"

    monkeypatch.setattr(module, "SourcePolicy", Policy)
    rows = [obs(0, ["buy"]), obs(10), obs(20, ["active"])]
    data, policy, review = (
        tmp_path / name for name in ("input.json", "policy.json", "review.json")
    )
    data.write_text(json.dumps({"observations": rows}))
    policy.write_text("{}")
    label = {
        "sample_sha256": rows[1]["sample"]["sample_sha256"],
        "domain": "round",
        "value": "ACTIVE",
        "origin": "human_exact_frame",
        "review_sha256": "a" * 64,
    }
    review.write_text(json.dumps({"records": [dict(label, **extra) for extra in labels]}))
    return data, policy, review


def test_labels_are_read_only_after_all_mode_predictions_are_saved(tmp_path, monkeypatch):
    data, policy, review = inputs(tmp_path, monkeypatch, [{}])
    output = tmp_path / "compare"
    original = module.read_json

    def load(path):
        if path == review:
            assert all(
                (output / f"{mode}_predictions_PRIVATE.json").is_file() for mode in module.MODES
            )
        return original(path)

    monkeypatch.setattr(module, "read_json", load)
    result = module.compare_modes(
        policy_path=policy, input_path=data, output=output, reviews=[review]
    )
    evaluation = result["exact_point_evaluation"]
    assert evaluation["legacy_offline"]["matches"]["a"]["round_incorrect"] == 1
    assert evaluation["offline_transition_brackets"]["matches"]["a"]["round_abstained"] == 1
    assert result["modes"]["legacy_offline"]["matches"]["a"]["false_round_start"] is None


def test_duplicate_exact_review_does_not_inflate_the_denominator(tmp_path, monkeypatch):
    data, policy, review = inputs(tmp_path, monkeypatch, [{}, {}])
    result = module.compare_modes(
        policy_path=policy, input_path=data, output=tmp_path / "compare", reviews=[review, review]
    )
    assert result["exact_point_evaluation"]["legacy_offline"]["matches"]["a"]["round_reviewed"] == 1


def test_conflicting_reviews_are_reported_without_selecting_a_convenient_truth(
    tmp_path, monkeypatch
):
    data, policy, review = inputs(tmp_path, monkeypatch, [{}, {"value": "BUY"}])
    with pytest.raises(ValueError, match="Conflicting"):
        module.compare_modes(
            policy_path=policy, input_path=data, output=tmp_path / "compare", reviews=[review]
        )
