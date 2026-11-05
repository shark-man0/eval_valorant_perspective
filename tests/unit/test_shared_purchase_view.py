from copy import deepcopy

import pytest
from test_shared_current_map_view import marker
from test_shared_game_timeline import obs, replay

from valorant_ai_coach.temporal.current_view_claims import project_purchase_self_claim
from valorant_ai_coach.temporal.match import frame_observations


def measurement():
    return {"signals": ["buy", "report"], "supplier_observations": [
        {"producer_fingerprint": "a" * 64, "signals": ["buy", "report"],
         "context": {"stream_kind": "hud"},
         "raw": {"ui": {"buy_phase_template": True}}},
        {"producer_fingerprint": "b" * 64, "signals": [],
         "context": {"stream_kind": "view", "unqualified_view_model": True},
         "raw": {"camera_hypothesis": "SELF", "current_HUD_component_supported": True,
                 "owner_hypothesis_exclusions": ["combat_report_visible"],
                 "owned_verb_phrase": None,
                 "view_hp": {"display": "100", "confidence": .96}}},
    ]}


def test_current_purchase_view_retains_uncertainty_and_cannot_authorize_map():
    before = measurement()
    original = deepcopy(before)
    after, changed = project_purchase_self_claim(before)
    assert changed == 1
    assert before == original
    rows = frame_observations(after, obs(0)["sample"], "f" * 64)
    result = replay([*rows, marker(0)])
    frame = result["frames"][0]
    assert frame["life"]["value"] == "ALIVE"
    assert frame["camera"]["value"] == "SELF"
    assert "UNKNOWN" in frame["life"]["hypotheses"]
    assert "UNKNOWN" in frame["camera"]["hypotheses"]
    assert frame["map"]["current_self_position_candidates"] == []
    assert frame["map"]["current_recorder_view_evidence_ids"] == []
    assert result["qualified_facts"] == result["qualified_events"] == []
    again, added = project_purchase_self_claim(after)
    assert added == 0
    assert again == after


@pytest.mark.parametrize("conflict", ["active", "result", "spectator", "remote", "death", "downed"])
def test_conflicting_current_evidence_does_not_restore_owner(conflict):
    data = measurement()
    data["supplier_observations"][0]["signals"].append(conflict)
    after, changed = project_purchase_self_claim(data)
    assert changed == 0
    assert "owner_hud" not in after["supplier_observations"][1]["signals"]


@pytest.mark.parametrize("case", [
    "no_buy", "spectated_HP100", "owned_death", "no_HP", "remote_UI", "elimination_signal",
])
def test_purchase_rule_alone_and_spectated_health_do_not_establish_self(case):
    data = measurement()
    base, view = data["supplier_observations"]
    if case == "no_buy":
        base["raw"]["ui"]["buy_phase_template"] = False
    elif case == "spectated_HP100":
        view["raw"]["camera_hypothesis"] = "SPECTATOR"
    elif case == "owned_death":
        view["raw"]["owned_verb_phrase"] = {"accepted_current_relation": True}
    elif case == "no_HP":
        view["raw"]["view_hp"] = None
    elif case == "remote_UI":
        view["raw"]["owner_hypothesis_exclusions"].append("astral_view")
    elif case == "elimination_signal":
        view["signals"].append("recorder_elimination_display")
    after, changed = project_purchase_self_claim(data)
    assert changed == 0
    assert "owner_hud" not in after["supplier_observations"][1]["signals"]
