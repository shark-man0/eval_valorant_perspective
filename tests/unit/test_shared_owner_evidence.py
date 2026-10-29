from copy import deepcopy

import pytest
from test_shared_game_timeline import obs
from test_shared_timeline_adapters import frame

from valorant_ai_coach.temporal.adapters import owner_ui
from valorant_ai_coach.temporal.evidence import digest
from valorant_ai_coach.temporal.owner_evidence import recover_owner_item


def item():
    sample = obs(1)["sample"]
    profile = {
        "development_ownership_evidence": {
            "frame_size_px": sample["frame_size_px"],
            "slot_review": "source_reviewed_not_qualified",
        },
        "development_recorder_view": {
            "binding": {
                "source_id": sample["source_id"],
                "source_sha256": sample["source_sha256"],
                "physical_match_id": "match",
                "acquisition_ids": [sample["native_epoch"]],
                "review_kind": "human_source_roster",
                "review_sha256": "d" * 64,
                "recorder_agent_id": "recorder-agent",
            }
        },
    }
    return {
        "source_id": sample["source_id"],
        "frame_contract": {**frame(sample), "leakage_group_id": "match"},
        "profile": profile,
        "ui": {
            "sample_sha256": sample["sample_sha256"],
            "qualified": False,
            "formal_outputs": 0,
            "fingerprint": "c" * 64,
            "source_profile_fingerprint": digest(profile),
            "own_hud_support": False,
            "spectator_ui": False,
            "spectator_absence_checked": False,
            "combat_report_visible": True,
            "screen_measurements": {
                "status": "observed",
                "source_id": sample["source_id"],
                "acquisition_id": sample["native_epoch"],
                "frame_pixel_sha256": sample["native_pixel_sha256"],
                "spectator_slot": {"checked": True, "panel_present": False},
                "observed_cues": [{"claim": "first_person_hud", "status": "present"}],
            },
            "spectator_measurements": {"status": "disabled", "veto": False},
            "agent_measurements": {
                "status": "observed",
                "positive_agent_association": True,
                "block_position_candidate": False,
                "recorder_agent_id": "recorder-agent",
                "binding_review_sha256": "d" * 64,
            },
        },
    }


def test_disabled_redundant_probe_does_not_discard_observed_dedicated_absence():
    original = item()
    result = recover_owner_item(original)
    assert result["ui"]["own_hud_support"] is True
    assert result["ui"]["spectator_absence_checked"] is True
    assert result["ui"]["fingerprint"] != original["ui"]["fingerprint"]
    assert result["ui"]["gate_recovery"]["upstream_ui"] == original["ui"]
    assert result["ui"]["screen_measurements"] == original["ui"]["screen_measurements"]
    assert original["ui"]["own_hud_support"] is False
    normalized = owner_ui(result)
    assert "owner_hud" in normalized["signals"]
    assert "death" not in normalized["signals"]  # Report presence is not death.


@pytest.mark.parametrize("status", ["disabled", "unavailable"])
def test_unavailable_configured_probe_still_blocks_absence(status):
    row = item()
    row["profile"]["development_view_veto"] = {"mode": "configured"}
    row["ui"]["source_profile_fingerprint"] = digest(row["profile"])
    row["ui"]["spectator_measurements"]["status"] = status
    assert recover_owner_item(row)["ui"]["spectator_absence_checked"] is False


def test_template_nondetection_without_checked_slot_is_not_absence():
    row = item()
    row["ui"]["screen_measurements"]["spectator_slot"] = {"checked": False, "panel_present": None}
    assert recover_owner_item(row)["ui"]["own_hud_support"] is False


def test_positive_spectator_control_reaches_camera_and_blocks_owner():
    row = item()
    row["ui"]["screen_measurements"]["observed_cues"].append(
        {"claim": "spectator_controls", "status": "present"}
    )
    result = recover_owner_item(row)
    assert result["ui"]["spectator_ui"] is True
    assert result["ui"]["own_hud_support"] is False
    assert result["ui"]["spectator_absence_checked"] is False
    assert "spectator" in owner_ui(result)["signals"]


@pytest.mark.parametrize("change", ["pixels", "source", "epoch", "profile", "match"])
def test_recovery_rejects_unbound_or_changed_evidence(change):
    row = item()
    if change == "pixels":
        row["ui"]["screen_measurements"]["frame_pixel_sha256"] = "e" * 64
    elif change == "source":
        row["ui"]["screen_measurements"]["source_id"] = "other"
    elif change == "epoch":
        row["ui"]["screen_measurements"]["acquisition_id"] = "other"
    elif change == "profile":
        row["profile"]["unmeasured_change"] = True
    else:
        row["frame_contract"]["leakage_group_id"] = "other-match"
    with pytest.raises(ValueError):
        recover_owner_item(row)


def test_recovery_is_detached_and_cannot_be_applied_twice():
    original = item()
    frozen = deepcopy(original)
    result = recover_owner_item(original)
    result["ui"]["gate_recovery"]["upstream_ui"]["own_hud_support"] = True
    assert original == frozen
    with pytest.raises(ValueError, match="Already recovered"):
        recover_owner_item(result)


def test_unbound_roster_can_observe_camera_but_never_owner():
    row = item()
    row["profile"]["development_recorder_view"] = {}
    row["ui"]["source_profile_fingerprint"] = digest(row["profile"])
    row["ui"]["screen_measurements"]["observed_cues"].append(
        {"claim": "spectator_controls", "status": "present"}
    )
    result = recover_owner_item(row)["ui"]
    assert result["spectator_ui"] is True
    assert result["own_hud_support"] is False
