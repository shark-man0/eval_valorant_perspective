from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from scripts.diagnostics import register_private_sources as inventory
from scripts.e2e.run_dataset_case import sha256_file


@pytest.fixture
def sources(tmp_path, monkeypatch):
    source = tmp_path / "inputs"
    source.mkdir()
    for i in range(9):
        (source / f"private-name-{i}.mp4").write_bytes(f"source-{i}".encode("ascii"))
    monkeypatch.setattr(inventory, "decode_source", lambda *args: None)

    def inspect(video, video_id, *args, **kwargs):
        return {"source_sha256": sha256_file(video), "video_id": video_id}

    monkeypatch.setattr(inventory, "inspect_recording", inspect)
    return source, tmp_path / "registry"


def test_freeze_before_inspection_and_revalidate_sources(sources, monkeypatch):
    source, registry = sources
    inspect = inventory.inspect_recording

    def frozen(video, video_id, *args, **kwargs):
        plan = json.loads((registry / "new" / "allocation.json").read_text(encoding="utf-8"))
        assert all(row["status"] == "pending" for row in plan["records"])
        assert [row["source_sha256"] for row in plan["records"]] == sorted(
            row["source_sha256"] for row in plan["records"]
        )
        return inspect(video, video_id, *args, **kwargs)

    monkeypatch.setattr(inventory, "inspect_recording", frozen)
    batch, summary = inventory.register(source, registry, "new", unused_and_distinct=True)
    assert summary["registered"] == 9
    assert summary["accepted_by_split"] == dict(zip(inventory.SPLITS, (5, 2, 2), strict=True))
    assert summary["exposure_counts"]["PROSPECTIVE_HELD_OUT"] == 4
    assert summary["e2e_registered"] is False
    assert summary["qualification_completed"] is False
    assert "private-name" not in json.dumps(summary)
    manifest_hash = sha256_file(batch / "manifest.json")
    allocation_hash = sha256_file(batch / "allocation.json")
    assert inventory.verify(batch, manifest_hash, allocation_hash)["registered"] == 9
    (source / "private-name-0.mp4").write_bytes(b"tampered")
    with pytest.raises(ValueError, match="SOURCE_INTEGRITY_FAILED"):
        inventory.verify(batch, manifest_hash, allocation_hash)


def test_unknown_is_never_upgraded_without_attestation(sources):
    batch, summary = inventory.register(*sources, "new")
    assert summary["exposure_counts"]["UNKNOWN_EXPOSURE"] == 9
    value = json.loads((batch / "manifest.json").read_text(encoding="utf-8"))
    value["records"][-1]["exposure"] = "PROSPECTIVE_HELD_OUT"
    with pytest.raises(ValueError, match="UNSUPPORTED_UNUSED_CLAIM"):
        inventory.validate_inventory(value)


def test_reject_duplicates_before_enrollment(sources):
    source, registry = sources
    (source / "private-name-1.mp4").write_bytes((source / "private-name-0.mp4").read_bytes())
    with pytest.raises(ValueError, match="DUPLICATE_SOURCE"):
        inventory.register(source, registry, "new")
    assert not (registry / "new").exists()


def test_existing_id_and_cross_batch_hash_reservations_are_not_overwritten(sources):
    source, registry = sources
    inventory.register(source, registry, "new")
    with pytest.raises(ValueError, match="BATCH_EXISTS"):
        inventory.register(source, registry, "NEW")
    with pytest.raises(ValueError, match="DUPLICATE_SOURCE"):
        inventory.register(source, registry, "other")


def test_existing_match_hash_and_id_rejected(sources, monkeypatch):
    source, registry = sources
    digest = sha256_file(source / "private-name-0.mp4")
    monkeypatch.setattr(inventory, "prior_sources", lambda _: (set(), {digest}, []))
    with pytest.raises(ValueError, match="DUPLICATE_SOURCE"):
        inventory.register(source, registry, "new")
    monkeypatch.setattr(inventory, "prior_sources", lambda _: ({"new_001"}, set(), []))
    with pytest.raises(ValueError, match="DUPLICATE_ID"):
        inventory.register(source, registry, "new")


def test_failed_decode_is_quarantined_without_reallocation(sources, monkeypatch):
    def broken(*args):
        raise ValueError("DECODE_INTEGRITY_FAILED")

    monkeypatch.setattr(inventory, "decode_source", broken)
    batch, summary = inventory.register(*sources, "new", unused_and_distinct=True)
    assert summary["failed"] == 9
    assert summary["registered"] == 0
    assert sum(summary["reserved_by_split"].values()) == 9
    assert (batch / "allocation.json").exists()
    assert len(list(batch.glob("*.result.json"))) == 9


def test_decode_rejects_nonzero_or_error_stderr(monkeypatch):
    for status, stderr in [(1, b"bad source"), (0, b"decode failure")]:
        monkeypatch.setattr(subprocess, "run", lambda *a, status=status, stderr=stderr, **k:
                            subprocess.CompletedProcess(
            a, status, None, stderr,
        ))
        with pytest.raises(ValueError, match="DECODE_INTEGRITY_FAILED"):
            inventory.decode_source(Path("synthetic.mp4"), "ffmpeg")


def test_trusted_anchor_and_match_split_conflicts_rejected(sources):
    batch, _ = inventory.register(*sources, "new")
    with pytest.raises(ValueError, match="TRUSTED_ANCHOR_MISMATCH"):
        inventory.verify(batch, "0" * 64, "0" * 64)
    value = json.loads((batch / "manifest.json").read_text(encoding="utf-8"))
    value["records"][-1]["physical_match_id"] = value["records"][0]["physical_match_id"]
    with pytest.raises(ValueError, match="DUPLICATE_ID_SOURCE_OR_MATCH"):
        inventory.validate_inventory(value)


def test_public_summary_strips_unknown_private_fields(sources):
    batch, _ = inventory.register(*sources, "new")
    value = json.loads((batch / "manifest.json").read_text(encoding="utf-8"))
    value["records"][0]["original_path"] = "secret-account/private.mp4"
    assert "secret-account" not in json.dumps(inventory.public_summary(value))


def test_registry_inside_checkout_is_rejected(sources):
    with pytest.raises(ValueError, match="EXTERNAL_PRIVATE_STORAGE_REQUIRED"):
        inventory.register(sources[0], inventory.ROOT / "work/private", "new")


def test_original_mutation_during_decode_rejects_source(sources, monkeypatch):
    source, registry = sources
    target = source / "private-name-0.mp4"

    def mutate(*args):
        target.write_bytes(b"changed-original")

    monkeypatch.setattr(inventory, "decode_source", mutate)
    _, summary = inventory.register(source, registry, "new")
    assert summary["failed"] == 1
    assert summary["registered"] == 8


def test_registry_lock_prevents_concurrent_registration(sources):
    source, registry = sources
    registry.mkdir()
    (registry / ".registration-lock").mkdir()
    with pytest.raises(FileExistsError):
        inventory.register(source, registry, "new")
    assert not (registry / "new").exists()


def test_development_all_freezes_nine_slots_before_inspection(sources, monkeypatch):
    source, registry = sources
    original_inspect = inventory.inspect_recording

    def inspect_after_freeze(video, video_id, *args, **kwargs):
        batch = registry / "dev_batch"
        allocation = json.loads((batch / "allocation.json").read_text(encoding="utf-8"))
        history = json.loads((batch / "exposure_history.json").read_text(encoding="utf-8"))
        assert all(row["status"] == "pending" for row in allocation["records"])
        assert len(history["events"]) == 9
        assert history["prior_exposure_verified"] is False
        return original_inspect(video, video_id, *args, **kwargs)

    monkeypatch.setattr(inventory, "inspect_recording", inspect_after_freeze)
    originals = {p.name: sha256_file(p) for p in source.iterdir()}
    batch, summary = inventory.register(
        source, registry, "dev_batch", allocation_mode="development-all",
    )
    assert summary["registered"] == 9
    assert summary["failed"] == 0
    assert summary["allocation_mode"] == "development-all"
    assert summary["accepted_by_split"] == dict(zip(inventory.SPLITS, (9, 0, 0)))
    assert summary["reserved_by_split"] == dict(zip(inventory.SPLITS, (9, 0, 0)))
    assert summary["exposure_counts"]["UNKNOWN_EXPOSURE"] == 9
    assert summary["distinct_physical_matches_verified"] is False
    assert summary["e2e_registered"] is False
    assert summary["qualification_completed"] is False
    assert originals == {p.name: sha256_file(p) for p in source.iterdir()}
    manifest = json.loads((batch / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["allocation_rule"] == inventory.ALLOCATION_RULES["development-all"]
    assert all(
        row["physical_match_verification"] == "unverified"
        for row in manifest["records"]
    )
    assert manifest["backup"]["separate_failure_domain_backup"] == "pending_operator_action"
    assert (batch / "exposure_history.json").is_file()
    assert "private-name" not in json.dumps(summary)
    assert all(row["split"] == "DEVELOPMENT" for row in manifest["records"])
    assert inventory.verify(
        batch, sha256_file(batch / "manifest.json"),
        sha256_file(batch / "allocation.json"),
    )["registered"] == 9


def test_development_all_rejects_unsubstantiated_holdout_claim(sources):
    source, registry = sources
    with pytest.raises(ValueError, match="UNSUPPORTED_UNUSED_CLAIM"):
        inventory.register(
            source, registry, "new", allocation_mode="development-all",
            unused_and_distinct=True,
        )
    assert not registry.exists()


def test_development_all_schema_and_split_exposure_are_immutable(sources):
    source, registry = sources
    batch, _ = inventory.register(source, registry, "new", allocation_mode="development-all")
    manifest = json.loads((batch / "manifest.json").read_text(encoding="utf-8"))
    manifest["records"][0]["split"] = "QUALIFICATION_CANDIDATE"
    with pytest.raises(ValueError, match="ALLOCATION_COUNT_MISMATCH"):
        inventory.validate_inventory(manifest)
    manifest["records"][0]["split"] = "DEVELOPMENT"
    manifest["records"][0]["exposure"] = "PROSPECTIVE_HELD_OUT"
    with pytest.raises(ValueError, match="DEVELOPMENT_EXPOSURE_OR_MATCH_UNVERIFIED_REQUIRED"):
        inventory.validate_inventory(manifest)
    manifest["records"][0]["exposure"] = "UNKNOWN_EXPOSURE"
    manifest["records"][0]["physical_match_verification"] = "verified"
    with pytest.raises(Exception):
        inventory.validate_inventory(manifest)


def test_development_all_journal_tampering_is_rejected(sources):
    source, registry = sources
    batch, _ = inventory.register(source, registry, "new", allocation_mode="development-all")
    manifest_hash = sha256_file(batch / "manifest.json")
    allocation_hash = sha256_file(batch / "allocation.json")
    journal_path = batch / "exposure_history.json"
    data = json.loads(journal_path.read_text(encoding="utf-8"))
    data["events"][0]["prior_use"] = "pretend_unseen"
    journal_path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="EXPOSURE_HISTORY_CHANGED"):
        inventory.verify(batch, manifest_hash, allocation_hash)


def test_development_all_rejects_duplicate_and_preserves_existing_freeze(sources):
    source, registry = sources
    batch, summary = inventory.register(
        source, registry, "dev", allocation_mode="development-all",
    )
    assert summary["registered"] == 9
    freeze = sha256_file(batch / "allocation.json")
    history = sha256_file(batch / "exposure_history.json")
    with pytest.raises(ValueError, match="BATCH_EXISTS"):
        inventory.register(source, registry, "DEV", allocation_mode="legacy-5-2-2")
    with pytest.raises(ValueError, match="DUPLICATE_SOURCE"):
        inventory.register(source, registry, "another", allocation_mode="development-all")
    assert sha256_file(batch / "allocation.json") == freeze
    assert sha256_file(batch / "exposure_history.json") == history


def test_development_all_decode_failure_does_not_reassign(sources, monkeypatch):
    monkeypatch.setattr(
        inventory, "decode_source",
        lambda *args: (_ for _ in ()).throw(ValueError("DECODE_INTEGRITY_FAILED")),
    )
    batch, summary = inventory.register(
        *sources, "new", allocation_mode="development-all",
    )
    assert summary["failed"] == 9
    assert summary["accepted_by_split"] == dict(zip(inventory.SPLITS, (0, 0, 0)))
    assert summary["reserved_by_split"] == dict(zip(inventory.SPLITS, (9, 0, 0)))
    assert (batch / "exposure_history.json").exists()


@pytest.mark.parametrize("count", [8, 10])
def test_development_all_refuses_non_nine_input(sources, count):
    source, registry = sources
    if count == 8:
        next(source.iterdir()).unlink()
    else:
        (source / "extra.mp4").write_bytes(b"not-a-source")
    with pytest.raises(ValueError, match="EXACTLY_NINE_REGULAR_RECORDINGS_REQUIRED"):
        inventory.register(source, registry, "new", allocation_mode="development-all")
    assert not (registry / "new").exists()


def test_legacy_default_is_still_five_two_two(sources):
    batch, summary = inventory.register(*sources, "legacy")
    manifest = json.loads((batch / "manifest.json").read_text(encoding="utf-8"))
    assert summary["allocation_mode"] == "legacy-5-2-2"
    assert summary["reserved_by_split"] == dict(zip(inventory.SPLITS, (5, 2, 2)))
    assert manifest["allocation_rule"] == inventory.ALLOCATION_RULES["legacy-5-2-2"]
    assert not (batch / "exposure_history.json").exists()
