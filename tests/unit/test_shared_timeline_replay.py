import json

import pytest
from test_shared_game_timeline import obs
from test_shared_timeline_adapters import frame

from valorant_ai_coach.temporal.replay import SourcePolicy, file_sha, replay


def write(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def policy_fixture(tmp_path, *, split="DEVELOPMENT"):
    source = {
        "source_sha256": "a" * 64,
        "video_id": "a",
        "physical_match_id": "physical1",
        "status": "accepted",
        "split": split,
        "exposure": split,
        "managed_path": "must_never_be_opened.mp4",
    }
    manifest = write(tmp_path / "manifest.json", {"records": [source]})
    allocation = write(tmp_path / "allocation.json", {"immutable": True})
    policy = {
        "manifest": str(manifest),
        "allocation": str(allocation),
        "manifest_sha256": file_sha(manifest),
        "allocation_sha256": file_sha(allocation),
        "allowed_source_sha256s": ["a" * 64],
        "protected_source_sha256s": [],
    }
    return policy


def test_protected_source_and_mutated_registry_are_rejected(tmp_path):
    policy = policy_fixture(tmp_path, split="FINAL_HOLDOUT")
    with pytest.raises(ValueError, match="Protected"):
        SourcePolicy(policy)
    policy = policy_fixture(tmp_path)
    policy["protected_source_sha256s"] = ["a" * 64]
    with pytest.raises(ValueError, match="Protected"):
        SourcePolicy(policy)
    policy["protected_source_sha256s"] = []
    write(tmp_path / "manifest.json", {})
    with pytest.raises(ValueError, match="Frozen"):
        SourcePolicy(policy)


def test_end_to_end_development_replay_never_opens_video(tmp_path):
    policy = policy_fixture(tmp_path)
    sample = obs(0)["sample"]
    record = frame(sample)
    record.update(
        leakage_group_id="physical1",
        split="DEVELOPMENT_TRAIN",
        source_acceptance={
            "accepted": True,
            "manifest_sha256": policy["manifest_sha256"],
            "allocation_sha256": policy["allocation_sha256"],
        },
    )
    item = {
        "frame_contract": record,
        "source_id": "a",
        "ui": {
            "sample_sha256": sample["sample_sha256"],
            "qualified": False,
            "formal_outputs": 0,
            "fingerprint": "c" * 64,
            "source_profile_fingerprint": "d" * 64,
            "own_hud_support": True,
        },
    }
    hud = write(
        tmp_path / "hud.json",
        {
            "version": "hud_supplier_replay_input_v1",
            "owner_frames": [item],
            "round_frames": [],
            "boundary_hints": [],
        },
    )
    result = replay(policy_path=write(tmp_path / "policy.json", policy), hud_path=hud)
    assert result["frames"][0]["life"]["value"] == "ALIVE"
    assert result["reproduction"]["new_video_decodes"] == 0
    assert result["reproduction"]["source_bytes_revalidated"] is False
    assert result["qualified_events"] == []
    item["frame_contract"]["leakage_group_id"] = "another_physical_match"
    write(
        hud,
        {
            "version": "hud_supplier_replay_input_v1",
            "owner_frames": [item],
            "round_frames": [],
            "boundary_hints": [],
        },
    )
    with pytest.raises(ValueError, match="physical-match"):
        replay(policy_path=tmp_path / "policy.json", hud_path=hud)


def test_killfeed_archive_is_source_admitted_and_digest_checked(tmp_path):
    from valorant_ai_coach.temporal.game import observation

    policy = policy_fixture(tmp_path)
    policy_path = write(tmp_path / "policy.json", policy)
    sample = obs(0)["sample"]
    contract = frame(sample)
    contract.update(
        leakage_group_id="physical1",
        split="DEVELOPMENT_TRAIN",
        source_acceptance={
            "accepted": True,
            "manifest_sha256": policy["manifest_sha256"],
            "allocation_sha256": policy["allocation_sha256"],
        },
    )
    event = observation(
        sample=sample,
        producer="e" * 64,
        signals=["recorder_elimination_display"],
        raw={"normal_kill_confirmed": False},
    )
    archive = {
        "version": "development_killfeed_victim_observations_v1",
        "records": [{"observation": event, "frame_contract": contract}],
    }
    path = write(tmp_path / "events.json", archive)
    result = replay(policy_path=policy_path, hud_events=path)
    # No prior self/spectator/round witness: a display alone never establishes death.
    assert result["frames"][0]["life"]["value"] == "UNKNOWN"
    assert not result["qualified_events"]
    contract["leakage_group_id"] = "another_physical_match"
    write(path, archive)
    with pytest.raises(ValueError, match="physical-match"):
        replay(policy_path=policy_path, hud_events=path)
    contract["leakage_group_id"] = "physical1"
    event["signals"] = ["death"]
    write(path, archive)
    with pytest.raises(ValueError):
        replay(policy_path=policy_path, hud_events=path)
