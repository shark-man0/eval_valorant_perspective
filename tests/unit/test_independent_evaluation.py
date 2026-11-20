"""Independent evaluation path: only opened, otherwise unexposed hold-out; frozen plans."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from valorant_ai_coach.recordings import LeakageError, RecordingCatalog
from valorant_ai_coach.temporal import independent_evaluation as ie
from valorant_ai_coach.temporal.replay import SourcePolicy


def _video(directory: Path, name: str, payload: bytes) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_bytes(payload)
    return path


@pytest.fixture()
def setup(tmp_path: Path):
    catalog = RecordingCatalog.create(tmp_path / "private" / "catalog", seed="fixed-seed")
    ids = {}
    for index, split in enumerate(("DEVELOPMENT", "QUALIFICATION", "FINAL_HOLDOUT")):
        payload = split.encode("ascii") * 20 + b"x" * index
        path = _video(tmp_path / "videos", f"{split}.mp4", payload)
        result = catalog.register(path, physical_match_id=f"m_{split}", split=split)
        ids[split] = result.recording_id
    refs = {name: _video(tmp_path / "refs", f"{name}.png", name.encode("ascii"))
            for name in ie.REFERENCE_NAMES}
    reader = _video(tmp_path / "refs", "screen.json", b"{}")
    return catalog, ids, refs, reader, tmp_path


def _prepare(catalog, ids, refs, reader, tmp_path, rid, purpose="qualification", name="plan"):
    return ie.prepare(catalog_root=catalog.root, recording_ids=[ids[rid]], purpose=purpose,
                      reader_config=reader, references=refs,
                      plan_path=tmp_path / "out" / f"{name}_PRIVATE.json")


def test_development_admission_refuses_opened_holdout(setup):
    catalog, ids, *_ = setup
    rid = ids["QUALIFICATION"]
    catalog.open_for_evaluation([rid], "qualification", "approved by the coordinator")
    policy = {"catalog": str(catalog.root), "allowed_recording_ids": [rid]}
    with pytest.raises(LeakageError):
        SourcePolicy(policy)  # development commands keep the development purpose
    evaluation = SourcePolicy({**policy, "purpose": "qualification"}, purpose="qualification")
    (record,) = evaluation.allowed.values()
    assert record["exposure"] == "INDEPENDENT_QUALIFICATION"


def test_policy_and_caller_purpose_must_agree(setup):
    catalog, ids, *_ = setup
    rid = ids["QUALIFICATION"]
    catalog.open_for_evaluation([rid], "qualification", "approved")
    evaluation_policy = {"catalog": str(catalog.root), "allowed_recording_ids": [rid],
                         "purpose": "qualification"}
    with pytest.raises(ValueError):
        SourcePolicy(evaluation_policy)  # an evaluation policy given to a development command
    with pytest.raises(ValueError):
        SourcePolicy({"catalog": str(catalog.root), "allowed_recording_ids": [rid]},
                     purpose="qualification")
    with pytest.raises(ValueError):
        SourcePolicy({"manifest": "x", "purpose": "qualification"}, purpose="qualification")
    with pytest.raises(ValueError):
        SourcePolicy(evaluation_policy, purpose="training")


def test_prepare_admits_only_opened_and_otherwise_unexposed_holdout(setup):
    catalog, ids, refs, reader, tmp_path = setup
    with pytest.raises(LeakageError):  # not opened
        _prepare(catalog, ids, refs, reader, tmp_path, "QUALIFICATION")
    with pytest.raises(LeakageError):  # development material is never evaluation material
        _prepare(catalog, ids, refs, reader, tmp_path, "DEVELOPMENT", name="dev")
    with pytest.raises(ValueError):
        _prepare(catalog, ids, refs, reader, tmp_path, "FINAL_HOLDOUT", purpose="training",
                 name="bad")
    catalog.record_exposure(ids["FINAL_HOLDOUT"], "user_authorized_development_use", "dev")
    with pytest.raises(LeakageError):  # exposed before opening
        _prepare(catalog, ids, refs, reader, tmp_path, "FINAL_HOLDOUT",
                 purpose="final_evaluation", name="exposed")
    catalog.open_for_evaluation([ids["QUALIFICATION"]], "qualification", "approved")
    head = catalog.head_anchor()
    plan = _prepare(catalog, ids, refs, reader, tmp_path, "QUALIFICATION", name="ok")
    assert RecordingCatalog(catalog.root).head_anchor() == head  # prepare writes no exposure
    assert plan["options"] == ie.FROZEN_OPTIONS and plan["formal_qualification"] == "NOT_GRANTED"
    assert plan["code_digest"] == ie.code_digest()


def test_execute_needs_approval_and_an_unchanged_plan(setup, monkeypatch):
    catalog, ids, refs, reader, tmp_path = setup
    catalog.open_for_evaluation([ids["QUALIFICATION"]], "qualification", "approved")
    _prepare(catalog, ids, refs, reader, tmp_path, "QUALIFICATION")
    plan_path = tmp_path / "out" / "plan_PRIVATE.json"
    with pytest.raises(ValueError):
        ie.execute(plan_path=plan_path, approval_note=" ", output=tmp_path / "run0")
    monkeypatch.setattr(ie, "code_digest", lambda: "0" * 64)
    with pytest.raises(ValueError, match="code changed"):
        ie.execute(plan_path=plan_path, approval_note="ok", output=tmp_path / "run1")
    monkeypatch.undo()
    refs["camera_hint"].write_bytes(b"changed")
    with pytest.raises(ValueError, match="reference"):
        ie.execute(plan_path=plan_path, approval_note="ok", output=tmp_path / "run2")


def test_execute_runs_the_frozen_pipeline_with_the_evaluation_purpose(setup, monkeypatch):
    catalog, ids, refs, reader, tmp_path = setup
    rid = ids["QUALIFICATION"]
    catalog.open_for_evaluation([rid], "qualification", "approved")
    _prepare(catalog, ids, refs, reader, tmp_path, "QUALIFICATION")
    calls: dict[str, dict] = {}

    def fake_run_match(**kwargs):
        calls["run_match"] = kwargs
        SourcePolicy(json.loads(Path(kwargs["policy_path"]).read_text(encoding="utf-8")),
                     purpose=kwargs["admission_purpose"])
        kwargs["output"].mkdir()
        return {}

    def fake_camera(argv):
        calls["camera"] = {"argv": argv}
        return 0

    def fake_export(**kwargs):
        calls["export"] = kwargs
        return {"output_sha256s": {"timeline_PRIVATE.json": "a" * 64}}

    from valorant_ai_coach.temporal import application, camera_panel, match

    monkeypatch.setattr(match, "run_match", fake_run_match)
    monkeypatch.setattr(camera_panel, "main", fake_camera)
    monkeypatch.setattr(application, "export_application", fake_export)
    receipt = ie.execute(plan_path=tmp_path / "out" / "plan_PRIVATE.json",
                         approval_note="coordinator approval 2026-11-21",
                         output=tmp_path / "run")
    assert calls["run_match"]["admission_purpose"] == "qualification"
    assert calls["run_match"]["evidence_continuity"] is True
    assert calls["export"]["admission_purpose"] == "qualification"
    assert calls["export"]["measured_view_precedence"] is True
    assert "--camera-hint" in calls["camera"]["argv"]
    assert receipt["formal_qualification"] == "NOT_GRANTED"
    assert receipt["scoring"] == "NOT_PERFORMED" and receipt["formal_outputs"] == 0
    assert [r["recording_id"] for r in receipt["results"]] == [rid]
    assert (tmp_path / "run" / "independent_evaluation_receipt_PRIVATE.json").exists()
