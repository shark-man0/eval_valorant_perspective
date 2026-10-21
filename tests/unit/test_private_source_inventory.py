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
