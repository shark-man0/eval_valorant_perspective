"""Private recording catalog (#62): intake, write-once splits, exposure, lineage, guard."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from valorant_ai_coach.recordings import (
    CatalogError,
    CatalogIntegrityError,
    LeakageError,
    RecordingCatalog,
    SplitImmutableError,
)
from valorant_ai_coach.recordings import catalog as catalog_module
from valorant_ai_coach.recordings.__main__ import main as cli


def video(directory: Path, name: str, payload: bytes) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_bytes(payload)
    return path


@pytest.fixture()
def catalog(tmp_path: Path) -> RecordingCatalog:
    return RecordingCatalog.create(tmp_path / "private" / "catalog", seed="fixed-seed")


def test_catalog_must_live_outside_git(tmp_path: Path):
    (tmp_path / "repo" / ".git").mkdir(parents=True)
    with pytest.raises(CatalogError):
        RecordingCatalog.create(tmp_path / "repo" / "catalog")


def test_registration_is_idempotent_and_split_is_write_once(catalog, tmp_path):
    first = video(tmp_path / "in", "a.mp4", b"match-a" * 100)
    result = catalog.register(first, physical_match_id="match_a")
    again = catalog.register(first, physical_match_id="match_a")
    assert result.added and not again.added and again.split == result.split
    other = next(s for s in ("DEVELOPMENT", "QUALIFICATION", "FINAL_HOLDOUT") if s != result.split)
    with pytest.raises(SplitImmutableError):
        catalog.register(first, split=other)
    with pytest.raises(CatalogError):
        catalog.register(first, physical_match_id="another_match")
    copy = video(tmp_path / "managed", "a_copy.mp4", b"match-a" * 100)
    catalog.register(copy, role="managed")
    recording = catalog.state.recordings[result.recording_id]
    assert set(recording.locations) == {"original", "managed"}
    assert RecordingCatalog(catalog.root).state.to_dict() == catalog.state.to_dict()


def test_one_physical_match_cannot_span_two_splits(catalog, tmp_path):
    a = video(tmp_path, "half1.mp4", b"first half" * 50)
    b = video(tmp_path, "half2.mp4", b"second half!" * 50)
    first = catalog.register(a, physical_match_id="match_x", split="DEVELOPMENT")
    assert first.split == "DEVELOPMENT"
    with pytest.raises(SplitImmutableError):
        catalog.register(b, physical_match_id="match_x", split="FINAL_HOLDOUT")
    second = catalog.register(b, physical_match_id="match_x")
    assert second.split == "DEVELOPMENT"
    assert catalog.state.recordings[second.recording_id].allocation == "physical_match_bound"


def test_content_blind_allocation_is_deterministic_and_matches_ratios(tmp_path):
    splits = [
        catalog_module.allocate_split("seed", catalog_module.DEFAULT_RATIOS, f"m{i}")
        for i in range(3000)
    ]
    share = {s: splits.count(s) / len(splits) for s in catalog_module.SPLITS}
    assert abs(share["DEVELOPMENT"] - 0.6) < 0.05
    assert splits == [
        catalog_module.allocate_split("seed", catalog_module.DEFAULT_RATIOS, f"m{i}")
        for i in range(3000)
    ]


def test_same_size_recordings_need_explicit_confirmation(catalog, tmp_path):
    catalog.register(video(tmp_path, "x.mp4", b"A" * 64), physical_match_id="m1")
    twin = video(tmp_path, "y.mp4", b"B" * 64)
    with pytest.raises(CatalogError):
        catalog.register(twin, physical_match_id="m2")
    result = catalog.register(twin, physical_match_id="m2", confirm_distinct=True)
    assert result.warnings == ("same_size_confirmed_distinct",)


def test_directory_intake_is_incremental(catalog, tmp_path, monkeypatch):
    folder = tmp_path / "drop"
    for index in range(5):
        video(folder, f"rec{index}.mp4", f"recording {index}".encode("ascii") * (index + 3))
    (folder / "notes.txt").write_text("not a video", encoding="utf-8")
    first = catalog.register_directory(folder, workers=2)
    assert sum(r.added for r in first) == 5
    calls: list[Path] = []
    original = catalog_module.sha256_file
    monkeypatch.setattr(catalog_module, "sha256_file",
                        lambda path: calls.append(path) or original(path))
    video(folder, "rec_new.mp4", b"brand new" * 9)
    second = catalog.register_directory(folder, workers=2)
    assert sum(r.added for r in second) == 1 and len(second) == 6
    assert calls == [folder / "rec_new.mp4"]  # only the new file was hashed


def test_journal_tampering_is_detected(catalog, tmp_path):
    catalog.register(
        video(tmp_path, "a.mp4", b"a" * 99), physical_match_id="m", split="DEVELOPMENT"
    )
    journal = catalog.root / "journal.jsonl"
    lines = journal.read_text(encoding="utf-8").splitlines()
    lines[1] = lines[1].replace("DEVELOPMENT", "QUALIFICATION")
    journal.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(CatalogIntegrityError):
        RecordingCatalog(catalog.root)
    journal.write_text("\n".join(lines[:1] + lines[2:]) + "\n", encoding="utf-8")
    with pytest.raises(CatalogIntegrityError):
        RecordingCatalog(catalog.root)


def test_concurrent_writer_is_refused_and_no_stale_lock_remains(catalog, tmp_path):
    import os

    descriptor = os.open(catalog.root / ".catalog.lock", os.O_RDWR | os.O_CREAT, 0o600)
    catalog_module._lock_exclusive(descriptor)  # another writer holds the lock
    try:
        with pytest.raises(CatalogError):
            catalog.register(video(tmp_path, "a.mp4", b"a" * 10), physical_match_id="m")
    finally:
        catalog_module._unlock(descriptor)
        os.close(descriptor)
    # Released by the OS; the lock file itself never has to be deleted.
    assert catalog.register(video(tmp_path, "b.mp4", b"b" * 10), physical_match_id="m").added


def _three(catalog, tmp_path):
    ids = {}
    for index, split in enumerate(("DEVELOPMENT", "QUALIFICATION", "FINAL_HOLDOUT")):
        path = video(tmp_path, f"{split}.mp4", split.encode("ascii") * 20 + b"x" * index)
        result = catalog.register(path, physical_match_id=f"m_{split}", split=split)
        ids[split] = result.recording_id
    return ids


def test_guard_blocks_holdout_ancestry_from_training_and_models(catalog, tmp_path):
    ids = _three(catalog, tmp_path)
    labels = catalog.register_artifact(
        kind="labels", parents=[ids["DEVELOPMENT"], ids["FINAL_HOLDOUT"]],
        producer={"name": "weak_labeler", "version": "1"}, sha256="1" * 64,
    )
    with pytest.raises(LeakageError):
        catalog.guard([labels], "training")
    with pytest.raises(LeakageError):
        catalog.register_artifact(kind="model", parents=[labels],
                                  producer={"name": "trainer"}, sha256="2" * 64)
    clean = catalog.register_artifact(kind="labels", parents=[ids["DEVELOPMENT"]],
                                      producer={"name": "weak_labeler"}, sha256="3" * 64)
    model = catalog.register_artifact(kind="model", parents=[clean],
                                      producer={"name": "trainer"}, sha256="4" * 64)
    assert catalog.lineage(model)["recordings"] == [
        {"recording_id": ids["DEVELOPMENT"], "split": "DEVELOPMENT", "blind": False}
    ]
    assert catalog.lineage(ids["DEVELOPMENT"])["descendants"] == sorted(
        [clean, labels, model]
    )


def test_holdout_evaluation_requires_explicit_opening_and_then_is_not_blind(catalog, tmp_path):
    ids = _three(catalog, tmp_path)
    assert catalog.state.recordings[ids["FINAL_HOLDOUT"]].blind
    with pytest.raises(LeakageError):
        catalog.guard([ids["FINAL_HOLDOUT"]], "final_evaluation")
    with pytest.raises(LeakageError):  # wrong split for this purpose
        catalog.open_for_evaluation([ids["QUALIFICATION"]], "final_evaluation", "approved")
    with pytest.raises(CatalogError):  # an opening needs a recorded reason
        catalog.open_for_evaluation([ids["FINAL_HOLDOUT"]], "final_evaluation", " ")
    catalog.open_for_evaluation([ids["FINAL_HOLDOUT"]], "final_evaluation", "coordinator ok")
    catalog.guard([ids["FINAL_HOLDOUT"]], "final_evaluation")
    assert not catalog.state.recordings[ids["FINAL_HOLDOUT"]].blind
    with pytest.raises(LeakageError):  # opened for evaluation is not opened for training
        catalog.guard([ids["FINAL_HOLDOUT"]], "training")


def test_user_authorised_development_use_keeps_the_split_label(catalog, tmp_path):
    ids = _three(catalog, tmp_path)
    catalog.record_exposure(ids["QUALIFICATION"], "user_authorized_development_use",
                            "2026-11-15 decision")
    recording = catalog.state.recordings[ids["QUALIFICATION"]]
    assert recording.split == "QUALIFICATION" and not recording.blind
    catalog.guard([ids["QUALIFICATION"]], "training")
    view = catalog.learning_view()
    assert {row["source_id"] for row in view} == {ids["DEVELOPMENT"]}
    exposed = catalog.learning_view(include_authorised_exposed=True)
    assert {row["catalog_split"] for row in exposed} == {"DEVELOPMENT", "QUALIFICATION"}
    assert [r["exposed_holdout"] for r in exposed if r["catalog_split"] == "QUALIFICATION"] == [
        True
    ]


def test_verify_quarantines_changed_sources_and_plans_skip_them(catalog, tmp_path):
    path = video(tmp_path, "a.mp4", b"original bytes" * 20)
    rid = catalog.register(path, physical_match_id="m", split="DEVELOPMENT").recording_id
    assert catalog.verify()["changed_sources"] == []
    producer = {"name": "timeline", "version": "2", "config_sha256": "c"}
    assert catalog.plan(producer) == [rid]
    catalog.register_artifact(kind="timeline", parents=[rid], producer=producer,
                              sha256="5" * 64)
    assert catalog.plan(producer) == []
    assert catalog.plan({**producer, "version": "3"}) == [rid]
    path.write_bytes(b"edited bytes!!" * 20)
    report = catalog.verify()
    assert report["changed_sources"] == [f"{rid}:original"]
    assert catalog.state.recordings[rid].status == "quarantined"
    assert catalog.plan({**producer, "version": "3"}) == []
    assert catalog.learning_view() == []


def _legacy_manifest(tmp_path: Path) -> Path:
    rows = []
    for index, (split, exposure, status) in enumerate([
        ("DEVELOPMENT", "DEVELOPMENT", "accepted"),
        ("QUALIFICATION_CANDIDATE", "PROSPECTIVE_HELD_OUT", "accepted"),
        ("FINAL_HOLDOUT_CANDIDATE", "PROSPECTIVE_HELD_OUT", "accepted"),
        ("FINAL_HOLDOUT_CANDIDATE", "UNKNOWN_EXPOSURE", "accepted"),
        ("DEVELOPMENT", "DEVELOPMENT", "rejected"),
    ]):
        source = video(tmp_path / "legacy", f"v{index}.mp4", f"legacy {index}".encode("ascii") * 40)
        rows.append({
            "original_path": str(source), "managed_path": str(source),
            "source_sha256": catalog_module.sha256_file(source),
            "video_id": f"batch_{index + 1:03d}", "physical_match_id": f"batch_{index + 1:03d}",
            "split": split, "exposure": exposure, "status": status, "failure_rule": None,
        })
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps({"allocation_rule": "source_sha256_lexical_5_2_2_before_content",
                                "records": rows}), encoding="utf-8")
    return path


def test_legacy_allocations_are_adopted_without_reclassification(catalog, tmp_path):
    manifest = _legacy_manifest(tmp_path)
    report = catalog.import_legacy(manifest)
    assert report == {"adopted": 4, "already_present": 0, "skipped_rejected": 1,
                      "conflicts": []}
    by_id = catalog.state.recordings
    assert by_id["batch_002"].split == "QUALIFICATION" and by_id["batch_002"].blind
    assert by_id["batch_003"].split == "FINAL_HOLDOUT" and by_id["batch_003"].blind
    assert not by_id["batch_004"].blind  # unknown prior exposure is never blind
    assert by_id["batch_001"].legacy["split_label"] == "DEVELOPMENT"
    assert catalog.import_legacy(manifest)["already_present"] == 4
    changed = json.loads(manifest.read_text(encoding="utf-8"))
    changed["records"][1]["split"] = "DEVELOPMENT"
    manifest.write_text(json.dumps(changed), encoding="utf-8")
    assert catalog.import_legacy(manifest)["conflicts"] == [
        {"recording_id": "batch_002", "reason": "split_or_match_differs"}
    ]
    assert by_id["batch_002"].split == "QUALIFICATION"
    assert catalog.verify()["changed_sources"] == []


def test_public_outputs_carry_no_private_tokens_and_leak_check_finds_them(catalog, tmp_path):
    ids = _three(catalog, tmp_path)
    summary = json.dumps(catalog.public_summary())
    for token in catalog.private_tokens():
        assert token not in summary
    leaky = tmp_path / "public.md"
    leaky.write_text(
        "hash: " + catalog.state.recordings[ids["DEVELOPMENT"]].source_sha256, encoding="utf-8"
    )
    clean = tmp_path / "clean.md"
    clean.write_text("no secrets here", encoding="utf-8")
    findings = catalog.leak_check([leaky, clean])
    assert findings == [{"file": str(leaky), "token_kind": "sha256"}]


def test_cli_round_trip(tmp_path, capsys):
    root = tmp_path / "private" / "cli"
    assert cli(["--catalog", str(root), "init", "--seed", "s"]) == 0
    folder = tmp_path / "drop"
    video(folder, "one.mp4", b"one" * 30)
    video(folder, "two.mp4", b"two!" * 30)
    capsys.readouterr()
    assert cli(["--catalog", str(root), "register", str(folder)]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["added"] == 2 and out["summary"]["recordings"] == 2
    assert cli(["--catalog", str(root), "verify"]) == 0
    capsys.readouterr()
    assert cli(["--catalog", str(root), "guard", "nope", "--purpose", "training"]) == 2
    assert cli(["--catalog", str(root), "init"]) == 2  # never re-initialise


# ------------------------------------------------------------- 2026-11-17 review


def test_tail_deletion_is_detected_by_head_and_trusted_anchor(catalog, tmp_path):
    for index in range(3):
        catalog.register(video(tmp_path, f"t{index}.mp4", b"t" * (40 + index)),
                         physical_match_id=f"m{index}", split="DEVELOPMENT")
    anchor = catalog.head_anchor()
    journal = catalog.root / "journal.jsonl"
    lines = journal.read_text(encoding="utf-8").splitlines()
    journal.write_text("\n".join(lines[:-2]) + "\n", encoding="utf-8")
    with pytest.raises(CatalogIntegrityError):
        RecordingCatalog(catalog.root)
    # Even with HEAD.json removed too, an anchor kept outside the catalog catches it.
    journal.write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert RecordingCatalog(catalog.root).verify(trusted_head=anchor)["journal_head"] == anchor
    (catalog.root / "HEAD.json").unlink()
    with pytest.raises(CatalogIntegrityError):
        RecordingCatalog(catalog.root)


def test_artifact_reregistration_must_repeat_its_lineage(catalog, tmp_path):
    ids = _three(catalog, tmp_path)
    producer = {"name": "crop", "version": "1"}
    crop = catalog.register_artifact(kind="frames", parents=[ids["DEVELOPMENT"]],
                                     producer=producer, sha256="6" * 64, artifact_id="crops_a")
    assert catalog.register_artifact(kind="frames", parents=[ids["DEVELOPMENT"]],
                                     producer=producer, sha256="6" * 64,
                                     artifact_id="crops_a") == crop
    with pytest.raises(LeakageError):  # same id, different parent
        catalog.register_artifact(kind="frames", parents=[ids["QUALIFICATION"]],
                                  producer=producer, sha256="6" * 64, artifact_id="crops_a")
    with pytest.raises(LeakageError):  # same content claimed from another recording
        catalog.register_artifact(kind="frames", parents=[ids["QUALIFICATION"]],
                                  producer=producer, sha256="6" * 64, artifact_id="crops_b")


def test_physical_match_id_is_inherited_by_derived_videos_and_crops(catalog, tmp_path):
    source = catalog.register(video(tmp_path, "full.mp4", b"full match" * 30),
                              physical_match_id="match_q", split="QUALIFICATION")
    clip = video(tmp_path, "clip.mp4", b"clip of it" * 7)
    with pytest.raises(SplitImmutableError):
        catalog.register(clip, derived_from=source.recording_id, split="DEVELOPMENT")
    derived = catalog.register(clip, derived_from=source.recording_id)
    record = catalog.state.recordings[derived.recording_id]
    assert (record.physical_match_id, record.split, record.allocation) == (
        "match_q", "QUALIFICATION", "derived_from_parent"
    )
    crops = catalog.register_artifact(kind="frames", parents=[derived.recording_id],
                                      producer={"name": "crop"}, sha256="7" * 64)
    assert catalog.state.artifacts[crops].physical_match_ids == ("match_q",)
    other = catalog.register(video(tmp_path, "other.mp4", b"other one" * 31),
                             physical_match_id="match_d", split="DEVELOPMENT")
    with pytest.raises(CatalogError):  # a crop archive cannot mix two matches
        catalog.register_artifact(kind="frames", parents=[crops, other.recording_id],
                                  producer={"name": "crop"}, sha256="8" * 64)
    features = catalog.register_artifact(kind="features", parents=[crops, other.recording_id],
                                         producer={"name": "f"}, sha256="9" * 64)
    assert catalog.state.artifacts[features].physical_match_ids == ("match_d", "match_q")


def test_exposed_recordings_never_serve_independent_evaluation(catalog, tmp_path):
    ids = _three(catalog, tmp_path)
    catalog.record_exposure(ids["FINAL_HOLDOUT"], "user_authorized_development_use", "dev")
    with pytest.raises(LeakageError):
        catalog.open_for_evaluation([ids["FINAL_HOLDOUT"]], "final_evaluation", "approved")
    with pytest.raises(LeakageError):
        catalog.guard([ids["FINAL_HOLDOUT"]], "final_evaluation")
    catalog.guard([ids["FINAL_HOLDOUT"]], "training")  # development use stays allowed


def test_bounded_batches_resume_and_location_prefix_selects(catalog, tmp_path):
    folder = tmp_path / "full_match_x"
    for index in range(5):
        video(folder, f"m{index}.mp4", f"match {index}".encode("ascii") * (index + 5))
    first = catalog.register_directory(folder, max_new_files=2, split="DEVELOPMENT")
    assert sum(r.added for r in first) == 2
    second = catalog.register_directory(folder, max_new_files=2, split="DEVELOPMENT")
    assert sum(r.added for r in second) == 2 and len(second) == 4
    third = catalog.register_directory(folder, split="DEVELOPMENT")
    assert sum(r.added for r in third) == 1 and len(third) == 5
    assert len(catalog.recordings_under(folder)) == 5
    assert catalog.recordings_under(tmp_path / "full_match") == []  # no prefix confusion
    batch = catalog.recordings_under(folder)[:2]
    assert catalog.verify(recording_ids=batch)["locations_checked"] == 2


class _FakeContinualRegistry:
    """The intake contract of #154 ``DatasetRegistry`` (same signature)."""

    def __init__(self) -> None:
        self.rows: dict[str, tuple[str, str]] = {}

    def intake(self, source_id, physical_match_id, archive, *, split=None, note=""):
        if source_id in self.rows:
            return self.rows[source_id], False
        for other_physical, other_split in self.rows.values():
            if other_physical == physical_match_id and other_split != split:
                raise ValueError("leakage")
        self.rows[source_id] = (physical_match_id, split)
        return self.rows[source_id], True


def test_continual_learning_receives_only_development_archives(catalog, tmp_path):
    ids = _three(catalog, tmp_path)
    archives = {}
    for split, rid in ids.items():
        path = video(tmp_path / "crops", f"{split}.zip", split.encode("ascii") * 9)
        archives[split] = catalog.register_artifact(
            kind="frames", parents=[rid], producer={"name": "crop"}, path=path
        )
    rows = catalog.learning_archives()
    assert [row["source_id"] for row in rows] == [archives["DEVELOPMENT"]]
    assert rows[0]["physical_match_id"] == "m_DEVELOPMENT"
    registry = _FakeContinualRegistry()
    assert catalog.sync_learning_registry(registry, rows) == {"added": 1, "already_present": 0}
    assert catalog.sync_learning_registry(registry, rows) == {"added": 0, "already_present": 1}
    catalog.record_exposure(ids["QUALIFICATION"], "user_authorized_development_use", "ok")
    exposed = catalog.learning_archives(include_authorised_exposed=True)
    assert {row["source_id"] for row in exposed} == {archives["DEVELOPMENT"],
                                                      archives["QUALIFICATION"]}


def test_source_policy_reads_the_catalog_and_keeps_legacy_receipts(catalog, tmp_path):
    from valorant_ai_coach.temporal.replay import SourcePolicy

    manifest = _legacy_manifest(tmp_path)
    catalog.import_legacy(manifest)
    anchor = catalog_module.sha256_file(manifest)
    policy = SourcePolicy({"catalog": str(catalog.root),
                           "allowed_recording_ids": ["batch_001"]})
    record = catalog.state.recordings["batch_001"]
    sample = {"source_sha256": record.source_sha256, "source_id": "batch_001"}
    frame = {"leakage_group_id": "batch_001", "source_sha256": record.source_sha256,
             "split": "DEVELOPMENT_TRAIN",
             "source_acceptance": {"accepted": True, "manifest_sha256": anchor,
                                   "allocation_sha256": anchor}}
    policy.admit(sample, frame)  # a receipt written under the legacy manifest
    new_receipt = {**frame, "source_acceptance": {
        "accepted": True, "manifest_sha256": policy.manifest_sha,
        "allocation_sha256": policy.allocation_sha}}
    policy.admit(sample, new_receipt)
    with pytest.raises(ValueError):
        policy.admit(sample, {**frame, "source_acceptance": {
            "accepted": True, "manifest_sha256": "0" * 64, "allocation_sha256": anchor}})
    with pytest.raises(LeakageError):  # a blind hold-out is not development material
        SourcePolicy({"catalog": str(catalog.root), "allowed_recording_ids": ["batch_002"]})


def test_path_map_keeps_canonical_paths_while_reading_a_mount(tmp_path):
    mount = tmp_path / "mnt" / "full_match"
    clip = video(mount, "a.mp4", b"mounted bytes" * 9)
    canonical = "/Users/someone/Desktop/full_match"
    root = tmp_path / "private" / "cat"
    RecordingCatalog.create(root, seed="s")
    catalog = RecordingCatalog(root, path_map={canonical: str(mount)})
    rid = catalog.register(clip, physical_match_id="m", split="DEVELOPMENT").recording_id
    stored = catalog.state.recordings[rid].locations["original"]["path"]
    assert stored == f"{canonical}/a.mp4"
    assert catalog.recordings_under(mount) == [rid]
    assert catalog.verify()["missing_locations"] == []
    assert RecordingCatalog(root).verify(quarantine=False)["missing_locations"] == [
        f"{rid}:original"
    ]  # without the map the canonical path is simply not mounted here
