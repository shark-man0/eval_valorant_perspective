"""Second-stage admission preserves original allocation and first predictions."""

import pytest

from valorant_ai_coach.temporal import second_validation as stage
from valorant_ai_coach.temporal.replay import file_sha, read_json, write_private
from valorant_ai_coach.temporal.staged_validation import FROZEN_FLAGS


def settings():
    data = {k: False for k in FROZEN_FLAGS}
    data.update(
        coarse_seconds="1",
        dense_seconds="1/5",
        max_refinement_windows=40,
        refinement_selection_policy="balanced",
        refinement_padding_seconds="1",
        return_display_tail=True,
        current_hp_return_candidate=True,
        current_menu_return_candidate=True,
    )
    return data


def fixture(tmp_path, monkeypatch):
    batch = tmp_path / "batch"
    batch.mkdir()
    first = batch / "first_development"
    first.mkdir()
    write_private(first / "policy_PRIVATE.json", {"old": "immutable"})
    records = []
    for index, split in enumerate(
        [
            "DEVELOPMENT",
            "DEVELOPMENT",
            "QUALIFICATION",
            "QUALIFICATION",
            "FINAL_HOLDOUT",
            "FINAL_HOLDOUT",
        ]
    ):
        records.append(
            {
                "video_id": f"synthetic{index}",
                "source_sha256": str(index) * 64,
                "split": split,
                "exposure": "UNEXPOSED_AT_REGISTRATION",
                "status": "reserved",
                "original_path": str(tmp_path / f"{index}.mp4"),
            }
        )
    write_private(
        batch / "allocation.json",
        {
            "records": records,
            "first_development_source_id": "synthetic0",
            "future_five_order": [
                "synthetic1",
                "synthetic2",
                "synthetic3",
                "synthetic4",
                "synthetic5",
            ],
            "declarations": {"permission": True, "distinct_physical_matches": True},
        },
    )
    for name in ["old_timeline.json", "old_completion.json", "evidence.json"]:
        write_private(tmp_path / name, {"private": "synthetic"})
    write_private(
        batch / "first_full_prediction_receipt_PRIVATE.json",
        {
            "timeline_path": str(tmp_path / "old_timeline.json"),
            "timeline_sha256": file_sha(tmp_path / "old_timeline.json"),
            "completion_path": str(tmp_path / "old_completion.json"),
            "completion_sha256": file_sha(tmp_path / "old_completion.json"),
        },
    )
    protocol = tmp_path / "protocol.json"
    write_private(protocol, {"settings": settings()})
    assessment = tmp_path / "assessment.json"
    write_private(
        assessment,
        {
            "phase_1_to_4_complete": True,
            "second_content_accesses": 0,
            "protected_content_accesses": 0,
            "protocol_sha256": file_sha(protocol),
            "evidence_sha256s": {
                str(tmp_path / "evidence.json"): file_sha(tmp_path / "evidence.json")
            },
        },
    )
    monkeypatch.setattr(stage, "verify_protocol", read_json)
    monkeypatch.setattr(stage, "_verify_active_runtime", lambda _: None)
    return batch, protocol, assessment


def activate(batch, protocol, assessment):
    return stage.activate(
        batch=batch,
        protocol=protocol,
        assessment=assessment,
        allocation_sha256=file_sha(batch / "allocation.json"),
    )


def test_second_only_admission_retains_all_prior_bytes(tmp_path, monkeypatch):
    batch, protocol, assessment = fixture(tmp_path, monkeypatch)
    before = {p: file_sha(p) for p in batch.rglob("*.json")}
    activated = activate(batch, protocol, assessment)
    policy = read_json(activated / "policy_PRIVATE.json")
    assert policy["allowed_source_sha256s"] == ["1" * 64]
    assert len(policy["protected_source_sha256s"]) == 5
    assert all(file_sha(p) == sha for p, sha in before.items())
    assert stage._load(activated)[0]["protected_qualification_final_count"] == 4
    with pytest.raises(ValueError, match="already exists"):
        activate(batch, protocol, assessment)
    with pytest.raises(FileNotFoundError):
        stage.run(stage=activated, output=tmp_path / "full", phase="full")
    assert not (activated / "first_full_started_PRIVATE.json").exists()


def test_qualification_in_second_slot_is_rejected_before_activation(tmp_path, monkeypatch):
    batch, protocol, assessment = fixture(tmp_path, monkeypatch)
    data = read_json(batch / "allocation.json")
    data["future_five_order"][0] = "synthetic2"
    (batch / "allocation.json").unlink()
    write_private(batch / "allocation.json", data)
    with pytest.raises(ValueError, match="reserved second DEVELOPMENT"):
        activate(batch, protocol, assessment)
    assert not (batch / "second_development").exists()


def test_changed_assessment_and_unfrozen_flags_are_rejected(tmp_path, monkeypatch):
    batch, protocol, assessment = fixture(tmp_path, monkeypatch)
    (tmp_path / "evidence.json").write_text("changed", encoding="utf-8")
    with pytest.raises(ValueError, match="evidence changed"):
        activate(batch, protocol, assessment)
    with pytest.raises(ValueError, match="Every sampling"):
        stage.settings({"settings": {**settings(), "source_id": "forbidden"}})
    with pytest.raises(ValueError, match="offline return"):
        stage.settings({"settings": {**settings(), "return_display_tail": False}})


def test_started_failure_is_not_relabelled_as_a_first_attempt(tmp_path, monkeypatch):
    batch, protocol, assessment = fixture(tmp_path, monkeypatch)
    activated = activate(batch, protocol, assessment)
    write_private(activated / "first_pilot_started_PRIVATE.json", {"failed": True})
    with pytest.raises(ValueError, match="never overwrite"):
        stage.run(stage=activated, output=tmp_path / "pilot", phase="pilot")
