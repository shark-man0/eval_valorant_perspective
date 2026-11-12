from copy import deepcopy

import pytest
from test_shared_game_timeline import obs, replay

from valorant_ai_coach.temporal.compare import compare
from valorant_ai_coach.temporal.replay import summary


def fixture_inputs():
    result = replay([obs(0)])
    result.update(summary=summary(result), reproduction={}, supplier_boundary_hints=[])
    packet = {"sample": result["frames"][0]["sample"], "pool": {"candidates": []}}
    return {
        "common": result,
        "hud": result,
        "map_only": result,
        "consumer": {
            "formal_outputs": 0,
            "map_observations": [packet],
            "records": [{"current_observation": None}],
        },
        "supplier": {"map_observations": [packet]},
        "legacy": {"rows": [{"observation": packet, "B": {"current_observation": {}}}]},
        "role_review": {
            "reviewed_cases": [
                {
                    "role": "RECORDER_SELF",
                    "review_scope": "exact_image_only",
                    "B": "reviewed_role_match",
                },
                {"role": "UNKNOWN", "review_scope": "exact_image_only", "B": "UNKNOWN"},
            ]
        },
    }


def test_all_abstention_reports_lost_prior_reviewed_roles_without_accuracy_claim():
    result = compare(**fixture_inputs())
    assert result["previous_reviewed_self_role_selections_lost"] == 1
    assert result["one_second_accuracy"] is None
    assert result["self_ownership_accuracy"] is None
    assert result["recognition_improvement"] == "NOT_ESTABLISHED"


def test_nonzero_current_selection_cannot_be_joined_using_legacy_label_order():
    kwargs = fixture_inputs()
    kwargs["consumer"]["records"][0]["current_observation"] = {"point": [1, 2]}
    assert compare(**kwargs)["previous_reviewed_self_role_selections_lost"] is None


def test_foreign_map_sample_cannot_enter_same_input_comparison():
    kwargs = deepcopy(fixture_inputs())
    kwargs["consumer"]["map_observations"] = [{"sample": {}, "pool": {}}]
    with pytest.raises(ValueError, match="same ordered exact native"):
        compare(**kwargs)
