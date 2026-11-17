"""Older admission paths answer to the recording catalog (#62 follow-up)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from test_second_development_validation import activate as second_activate_legacy
from test_second_development_validation import fixture as second_fixture
from test_staged_six_validation import setup  # noqa: F401  (pytest fixture)

from valorant_ai_coach.recordings import LeakageError, RecordingCatalog
from valorant_ai_coach.recordings.admission import ENV_CATALOG
from valorant_ai_coach.temporal import second_validation as second
from valorant_ai_coach.temporal import staged_validation as staged
from valorant_ai_coach.temporal.replay import SourcePolicy, file_sha, read_json, write_private


@pytest.fixture
def catalog(tmp_path: Path) -> RecordingCatalog:
    return RecordingCatalog.create(tmp_path / "private_catalog", seed="s")


@pytest.fixture(autouse=True)
def _no_ambient_catalog(monkeypatch):
    monkeypatch.delenv(ENV_CATALOG, raising=False)


# --------------------------------------------------------------- staged six


def test_staged_reservation_and_first_use_go_through_the_catalog(
    setup, catalog  # noqa: F811
):
    tmp, protocol, declaration, _ = setup
    allocation = staged.register_six(
        declaration=declaration, protocol=protocol, registry=tmp / "registry",
        batch_id="six", prior_registries=[], catalog=catalog.root,
    )
    reloaded = RecordingCatalog(catalog.root)
    assert {r["video_id"]: r["split"] for r in allocation["records"]} == {
        rid: rec.split for rid, rec in reloaded.state.recordings.items()
    }
    assert all(rec.blind or rec.split == "DEVELOPMENT"
               for rec in reloaded.state.recordings.values())
    policy_path = staged.activate_first_development(tmp / "registry" / "six",
                                                    catalog=catalog.root)
    policy_file = read_json(policy_path)
    assert policy_file["catalog"] == str(catalog.root)  # the catalog decides admission
    policy = SourcePolicy(policy_file)
    first = allocation["first_development_source_id"]
    assert [r["video_id"] for r in policy.allowed.values()] == [first]
    after = RecordingCatalog(catalog.root).state.recordings
    assert [e["kind"] for e in after[first].exposures] == ["development_use"]
    assert all(not after[rid].exposures for rid in after if rid != first)


def test_staged_reservation_that_contradicts_the_catalog_writes_nothing(
    setup, catalog, tmp_path  # noqa: F811
):
    tmp, protocol, declaration, request = setup
    # Learn the frozen split of the first source without a catalog, then make the
    # catalog disagree with it.
    probe = staged.register_six(
        declaration=declaration, protocol=protocol, registry=tmp / "probe",
        batch_id="six", prior_registries=[],
    )
    first = request["records"][0]
    frozen = next(r["split"] for r in probe["records"]
                  if r["source_sha256"] == first["source_sha256"])
    other = "FINAL_HOLDOUT" if frozen != "FINAL_HOLDOUT" else "DEVELOPMENT"
    clash = tmp_path / "clash.json"
    clash.write_text(json.dumps({"records": [{
        "video_id": "older_id", "source_sha256": first["source_sha256"],
        "physical_match_id": first["physical_match_id"], "split": other,
        "status": "accepted", "exposure": "PROSPECTIVE_HELD_OUT",
    }]}), encoding="utf-8")
    catalog.import_legacy(clash)
    with pytest.raises(LeakageError):
        staged.register_six(
            declaration=declaration, protocol=protocol, registry=tmp / "registry",
            batch_id="six", prior_registries=[], catalog=catalog.root,
        )
    assert not (tmp / "registry" / "six").exists()
    assert RecordingCatalog(catalog.root).state.recordings["older_id"].split == other


# ----------------------------------------------------------- second activation


def _register_second_batch(catalog: RecordingCatalog, batch: Path) -> None:
    for index, row in enumerate(read_json(batch / "allocation.json")["records"]):
        Path(row["original_path"]).write_bytes(b"recording" * (index + 1))
    report = catalog.import_legacy(batch / "allocation.json")
    assert report["conflicts"] == []


def test_second_activation_is_decided_and_journaled_by_the_catalog(
    tmp_path, monkeypatch, catalog
):
    batch, protocol, assessment = second_fixture(tmp_path, monkeypatch)
    _register_second_batch(catalog, batch)
    stage_policy = second.activate(
        batch=batch, protocol=protocol, assessment=assessment,
        allocation_sha256=file_sha(batch / "allocation.json"), catalog=catalog.root,
    )
    policy_file = read_json(batch / "second_development" / "policy_PRIVATE.json")
    assert stage_policy is not None
    assert policy_file["allowed_recording_ids"] == ["synthetic1"]
    exposures = RecordingCatalog(catalog.root).state.recordings["synthetic1"].exposures
    assert [e["kind"] for e in exposures] == ["development_use"]


def test_second_activation_refuses_a_source_the_catalog_does_not_allow(
    tmp_path, monkeypatch, catalog
):
    batch, protocol, assessment = second_fixture(tmp_path, monkeypatch)
    allocation = read_json(batch / "allocation.json")
    # The catalog knows the "second DEVELOPMENT" recording as a FINAL_HOLDOUT match.
    other = {**allocation, "records": [
        {**row, "split": "FINAL_HOLDOUT"} if row["video_id"] == "synthetic1" else row
        for row in allocation["records"]
    ]}
    write_private(tmp_path / "catalog_view.json", other)
    catalog.import_legacy(tmp_path / "catalog_view.json")
    with pytest.raises(LeakageError):
        second.activate(
            batch=batch, protocol=protocol, assessment=assessment,
            allocation_sha256=file_sha(batch / "allocation.json"), catalog=catalog.root,
        )
    assert not (batch / "second_development" / "policy_PRIVATE.json").exists()


def test_second_activation_without_a_catalog_keeps_its_legacy_behaviour(
    tmp_path, monkeypatch
):
    batch, protocol, assessment = second_fixture(tmp_path, monkeypatch)
    stage_dir = second_activate_legacy(batch, protocol, assessment)
    assert stage_dir is not None


# --------------------------------------------------- legacy SourcePolicy bypass


def _legacy_policy(tmp_path: Path, sha: str, split: str = "DEVELOPMENT") -> dict:
    manifest = tmp_path / "manifest.json"
    allocation = tmp_path / "allocation.json"
    row = {"video_id": "rec_legacy", "source_sha256": sha, "physical_match_id": "m1",
           "split": split, "exposure": "DEVELOPMENT", "status": "accepted",
           "managed_path": str(tmp_path / "v.mp4")}
    write_private(manifest, {"records": [row]})
    write_private(allocation, {"records": [row]})
    return {"manifest": str(manifest), "allocation": str(allocation),
            "manifest_sha256": file_sha(manifest), "allocation_sha256": file_sha(allocation),
            "allowed_source_sha256s": [sha], "protected_source_sha256s": []}


def _catalog_with(catalog: RecordingCatalog, tmp_path: Path, sha: str, split: str) -> None:
    source = tmp_path / "catalog_rows.json"
    source.write_text(json.dumps({"records": [{
        "video_id": "rec_catalog", "source_sha256": sha, "physical_match_id": "m1",
        "split": split, "status": "accepted",
        "exposure": "DEVELOPMENT" if split == "DEVELOPMENT" else "PROSPECTIVE_HELD_OUT",
    }]}), encoding="utf-8")
    catalog.import_legacy(source)


def test_a_hand_written_policy_cannot_admit_a_holdout_when_a_catalog_is_bound(
    tmp_path, catalog, monkeypatch
):
    sha = "a" * 64
    _catalog_with(catalog, tmp_path, sha, "FINAL_HOLDOUT")
    policy = _legacy_policy(tmp_path, sha)  # claims DEVELOPMENT for the hold-out
    assert SourcePolicy(policy).catalog_checked is False  # unbound: legacy behaviour
    monkeypatch.setenv(ENV_CATALOG, str(catalog.root))
    with pytest.raises(LeakageError):
        SourcePolicy(policy)
    monkeypatch.delenv(ENV_CATALOG)
    with pytest.raises(LeakageError):
        SourcePolicy({**policy, "catalog_check": str(catalog.root)})


def test_legacy_policy_for_an_unregistered_recording_is_refused_when_bound(
    tmp_path, catalog, monkeypatch
):
    monkeypatch.setenv(ENV_CATALOG, str(catalog.root))
    with pytest.raises(LeakageError):
        SourcePolicy(_legacy_policy(tmp_path, "b" * 64))


def test_consistent_legacy_policy_is_admitted_and_marked_checked(
    tmp_path, catalog, monkeypatch
):
    sha = "c" * 64
    _catalog_with(catalog, tmp_path, sha, "DEVELOPMENT")
    monkeypatch.setenv(ENV_CATALOG, str(catalog.root))
    policy = SourcePolicy(_legacy_policy(tmp_path, sha))
    assert policy.catalog_checked is True and list(policy.allowed) == [sha]
