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


def test_legacy_split_names_and_implicit_match_ids_are_read_like_import_legacy(
    tmp_path, catalog
):
    """Real manifests use ``*_CANDIDATE`` splits and may omit the physical match id."""
    from valorant_ai_coach.recordings.admission import check_allowlist, precheck_allocation

    video = tmp_path / "q.mp4"
    video.write_bytes(b"qualification" * 50)
    rid = catalog.register(video, physical_match_id="batch_007",
                           split="QUALIFICATION").recording_id
    recording = catalog.state.recordings[rid]
    sha = recording.source_sha256
    legacy = {"video_id": "batch_007", "source_sha256": sha,
              "split": "QUALIFICATION_CANDIDATE"}
    precheck_allocation(catalog, [legacy])  # consistent: no error
    with pytest.raises(LeakageError):
        precheck_allocation(catalog, [{**legacy, "split": "DEVELOPMENT"}])
    with pytest.raises(LeakageError):
        precheck_allocation(catalog, [{**legacy, "split": "SOMETHING_ELSE"}])
    with pytest.raises(LeakageError):  # consistent row, but blind QUALIFICATION
        check_allowlist(catalog, [legacy])
    catalog.record_exposure(recording.recording_id, "user_authorized_development_use",
                            note="test")
    assert check_allowlist(catalog, [legacy]) == [recording.recording_id]


# ------------------------------------------- formal operation requires a catalog


def test_formal_operation_requires_the_catalog_on_every_admission_path(
    setup, tmp_path, monkeypatch  # noqa: F811
):
    from valorant_ai_coach.recordings import CatalogError
    from valorant_ai_coach.recordings.admission import ENV_LEGACY_COMPAT

    tmp, protocol, declaration, _ = setup
    monkeypatch.delenv(ENV_LEGACY_COMPAT, raising=False)
    with pytest.raises(CatalogError):
        staged.register_six(declaration=declaration, protocol=protocol,
                            registry=tmp / "formal", batch_id="six", prior_registries=[])
    assert not (tmp / "formal" / "six").exists()
    policy = _legacy_policy(tmp_path, "d" * 64)
    with pytest.raises(CatalogError):
        SourcePolicy(policy)
    # Only the explicit compatibility mode runs the allocation-file-only reading.
    assert SourcePolicy({**policy, "legacy_compat": True}).catalog_checked is False
    allocation = staged.register_six(
        declaration=declaration, protocol=protocol, registry=tmp / "compat",
        batch_id="six", prior_registries=[], legacy_compat=True,
    )
    assert allocation["legacy_compat"] is True
    with pytest.raises(CatalogError):
        staged.activate_first_development(tmp / "compat" / "six")
    policy_path = staged.activate_first_development(tmp / "compat" / "six",
                                                    legacy_compat=True)
    assert read_json(policy_path)["legacy_compat"] is True
    assert SourcePolicy(read_json(policy_path)).catalog_checked is False


def test_second_activation_requires_the_catalog(tmp_path, monkeypatch):
    from valorant_ai_coach.recordings import CatalogError
    from valorant_ai_coach.recordings.admission import ENV_LEGACY_COMPAT

    batch, protocol, assessment = second_fixture(tmp_path, monkeypatch)
    monkeypatch.delenv(ENV_LEGACY_COMPAT, raising=False)
    with pytest.raises(CatalogError):
        second.activate(batch=batch, protocol=protocol, assessment=assessment,
                        allocation_sha256=file_sha(batch / "allocation.json"))
    assert not (batch / "second_development").exists()


# --------------------------------------------- all-or-nothing registration


def test_a_conflict_found_at_adoption_leaves_no_reservation_and_no_journal_entry(
    setup, catalog, tmp_path, monkeypatch  # noqa: F811
):
    """Even if the catalog changes between the check and the adoption (another
    process), the reservation is removed and the catalog journal gains nothing."""
    tmp, protocol, declaration, request = setup
    first = request["records"][0]
    clash = tmp_path / "clash.json"

    def racing_precheck(bound, rows):
        clash.write_text(json.dumps({"records": [{
            "video_id": "racing_id", "source_sha256": "e" * 64,
            "physical_match_id": first["physical_match_id"],
            "split": "FINAL_HOLDOUT" if rows[0]["split"] != "FINAL_HOLDOUT"
            else "DEVELOPMENT",
            "status": "accepted", "exposure": "PROSPECTIVE_HELD_OUT",
        }]}), encoding="utf-8")
        RecordingCatalog(catalog.root).import_legacy(clash)

    monkeypatch.setattr(staged, "precheck_allocation", racing_precheck)
    with pytest.raises(ValueError):
        staged.register_six(declaration=declaration, protocol=protocol,
                            registry=tmp / "registry", batch_id="six",
                            prior_registries=[], catalog=catalog.root)
    assert not (tmp / "registry" / "six").exists()
    after = RecordingCatalog(catalog.root)
    # Only the racing import is in the journal; none of the six was adopted.
    assert set(after.state.recordings) == {"racing_id"}


def test_atomic_import_rejects_rows_that_contradict_each_other(tmp_path, catalog):
    rows = [
        {"video_id": "a_001", "source_sha256": "1" * 64, "physical_match_id": "m",
         "split": "DEVELOPMENT", "status": "accepted"},
        {"video_id": "a_002", "source_sha256": "2" * 64, "physical_match_id": "m",
         "split": "FINAL_HOLDOUT_CANDIDATE", "status": "accepted"},
    ]
    path = tmp_path / "allocation.json"
    path.write_text(json.dumps({"records": rows}), encoding="utf-8")
    assert [c["reason"] for c in catalog.legacy_conflicts(rows)] == ["identity_conflict"]
    report = catalog.import_legacy(path, atomic=True)
    assert report["adopted"] == 0 and report["conflicts"]
    assert RecordingCatalog(catalog.root).state.recordings == {}
