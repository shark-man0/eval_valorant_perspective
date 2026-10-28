from unittest.mock import Mock

import pytest
from test_development_marker_topk import fixture, pool_for

from valorant_ai_coach.visual.development_camera_marker_ui import inspect_camera_marker_ui
from valorant_ai_coach.visual.development_marker_features import _digest
from valorant_ai_coach.visual.development_owner_binding import (
    DevelopmentOwnerAppearance,
    DevelopmentVisibleHp,
    propose_owner_marker_binding,
)


def inputs():
    image, sample, parent = fixture()
    pool = pool_for(image, sample, parent)
    ui = inspect_camera_marker_ui(image, sample, pool)
    ui["rows"][0].update(warm_rim_arc=0.5, radial_alignment=0.9, score=1.5)
    roster = {
        "review_kind": "human_source_roster",
        "source_id": sample["source_id"],
        "source_sha256": sample["source_sha256"],
        "recorder_agent_id": "synthetic",
    }
    hud = {
        "sample_sha256": sample["sample_sha256"],
        "measurement": {
            "positive_agent_association": True,
            "visible_agent_candidate": "synthetic",
            "recorder_agent_id": "synthetic",
            "block_position_candidate": False,
        },
    }
    hp = {"sample_sha256": sample["sample_sha256"], "value": 100}
    spectator = {"sample_sha256": sample["sample_sha256"], "status": "UNKNOWN"}
    appearance = {
        "sample_sha256": sample["sample_sha256"],
        "reference_source_agent_supported": True,
        "consistent_indices": [0],
    }
    return dict(
        sample=sample,
        pool=pool,
        ui=ui,
        roster=roster,
        hud=hud,
        hp=hp,
        spectator=spectator,
        appearance=appearance,
    )


def test_current_ui_selects_id_but_does_not_certify_account_or_recorder_life():
    args = inputs()
    row = propose_owner_marker_binding(**args)
    assert row["candidate_index"] == 0
    assert row["marker_id"] == args["ui"]["rows"][0]["marker_observation_id"]
    assert row["camera"] == "first_person_candidate" and row["life_evidence"] == "none"
    assert row["ownership"] == "UNKNOWN" and row["formal_outputs"] == 0
    assert not row["recorder_account_identity_qualified"]


@pytest.mark.parametrize(
    "change",
    [
        "spectator",
        "name_slot",
        "HUD_missing",
        "HP_zero",
        "HP_only",
        "wrong_source",
        "reference_missing",
        "no_UI",
    ],
)
def test_missing_or_conflicting_evidence_never_initializes(change):
    args = inputs()
    if change == "spectator":
        args["spectator"]["status"] = "spectator_ui"
    elif change == "name_slot":
        args["hud"]["measurement"]["actor_alias_evidence"] = {
            "slot_kind": "spectated_player_name",
            "status": "observed",
        }
    elif change == "HUD_missing":
        args["hud"]["measurement"]["positive_agent_association"] = False
    elif change == "HP_zero":
        args["hp"]["value"] = 0
    elif change == "HP_only":
        args["appearance"]["consistent_indices"] = []
    elif change == "wrong_source":
        args["roster"]["source_sha256"] = "f" * 64
    elif change == "reference_missing":
        args["appearance"]["reference_source_agent_supported"] = False
    elif change == "no_UI":
        args["ui"]["rows"][0]["warm_rim_arc"] = 0.0
    row = propose_owner_marker_binding(**args)
    assert row["marker_id"] is None and row["life_evidence"] == "none"


def test_better_ranked_spike_does_not_erase_existing_agent_consistent_window():
    args = inputs()
    args["ui"]["rows"].append(
        {
            **args["ui"]["rows"][0],
            "candidate_index": 1,
            "score": 2.0,
            "marker_observation_id": "spike",
        }
    )
    assert propose_owner_marker_binding(**args)["candidate_index"] == 0


def test_multiple_similar_eligible_markers_remain_unknown():
    args = inputs()
    args["pool"]["parent_count"] = 2
    args["pool"].pop("pool_sha256")
    args["pool"]["pool_sha256"] = _digest(args["pool"])
    args["ui"]["pool_sha256"] = args["pool"]["pool_sha256"]
    args["ui"]["rows"].append(
        {**args["ui"]["rows"][0], "candidate_index": 1, "marker_observation_id": "other"}
    )
    args["appearance"]["consistent_indices"] = [0, 1]
    assert propose_owner_marker_binding(**args)["marker_id"] is None


@pytest.mark.parametrize("reader", ["ui", "hud", "hp", "spectator", "appearance"])
def test_cross_frame_reader_outputs_are_rejected(reader):
    args = inputs()
    args[reader]["sample_sha256"] = "f" * 64
    with pytest.raises(ValueError, match="Same-frame"):
        propose_owner_marker_binding(**args)


def test_native_geometry_change_does_not_attempt_HP_OCR():
    image, sample, _ = fixture()
    reader = Mock()
    row = DevelopmentVisibleHp(reader).inspect(image, sample)
    assert row["value"] is None
    reader.read.assert_not_called()


def test_inspector_category_is_reused_without_unrelated_HUD_threshold(monkeypatch):
    image, sample, parent = fixture()
    pool = pool_for(image, sample, parent)
    inspector = DevelopmentOwnerAppearance()
    inspector.inspector.inspect = Mock(
        return_value={
            "reference_fingerprint": "d" * 64,
            "matches": [
                {
                    "reference_category": "self_reference_appearance",
                    "positive_similarity": 0.82,
                    "x_roi_norm": (55 - 10) / 120,
                    "y_roi_norm": (55 - 10) / 100,
                }
            ],
        }
    )
    monkeypatch.setattr(
        "valorant_ai_coach.visual.development_owner_binding.marker_binding_matches",
        lambda *a, **k: True,
    )
    result = inspector.inspect(image, sample, pool, spec={}, binding={}, roster={})
    assert result["consistent_indices"] == [0] and result["ownership"] == "UNKNOWN"
