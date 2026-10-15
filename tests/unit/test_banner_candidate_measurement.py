import json

import pytest

from scripts.diagnostics import discover_banner_references as discovery
from scripts.diagnostics import measure_banner_candidates as subject
from tests.unit.test_unlabeled_banner_discovery import fixture


def prepare(tmp_path, monkeypatch):
    monkeypatch.setattr(discovery, "_check_output_privacy", lambda *_: None)
    monkeypatch.setattr(subject, "_check_output_privacy", lambda *_: None)
    pool, layout, partition, _ = fixture(tmp_path)
    audit = tmp_path / "audit"
    report = discovery.discover(pool, layout, partition, audit, set(),
                                training_candidate_audit=True)
    return pool, layout, audit / "candidate_report.json", report


def test_frozen_measurement_never_selects_candidates_or_asserts_absence(tmp_path, monkeypatch):
    pool, layout, path, frozen = prepare(tmp_path, monkeypatch)
    before = path.read_bytes()
    output = tmp_path / "measure.json"
    measured = subject.measure(path, pool, layout, output)
    assert path.read_bytes() == before
    assert [r["candidate_id"] for r in measured["candidates"]] == [
        r["candidate_id"] for r in frozen["roles"]["round_end_banner"]]
    assert measured["candidates_reselected"] is False
    assert measured["semantic_labels_assigned"] is False
    assert measured["qualification_created"] is False
    assert measured["production_adopted"] is False
    for row in measured["candidates"]:
        assert row["semantic_label"] is None
        assert all(m["absence_checked"] is False and m["runtime_transition_authorized"] is False
                   for m in row["held_measurements"])
    with pytest.raises(FileExistsError):
        subject.measure(path, pool, layout, output)


@pytest.mark.parametrize("fault", ["layout", "asset", "source", "label", "held"])
def test_changed_or_already_reviewed_inputs_reject_before_receipt(
        tmp_path, monkeypatch, fault):
    pool, layout, path, frozen = prepare(tmp_path, monkeypatch)
    if fault == "layout":
        layout.write_text('{}', encoding="utf-8")
    elif fault == "asset":
        name = next(iter(frozen["roles"]["round_end_banner"][0]["asset_hashes"]))
        (path.parent / name).write_bytes(b"changed asset")
    elif fault == "source":
        next((pool / "pool_frames").glob('*.jpg')).write_bytes(b"changed source")
    elif fault == "label":
        frozen["roles"]["round_end_banner"][0]["semantic_label"] = "unapproved"
        path.write_text(json.dumps(frozen), encoding="utf-8")
    else:
        frozen["held_predictions_measured"] = True
        path.write_text(json.dumps(frozen), encoding="utf-8")
    output = tmp_path / "rejected.json"
    with pytest.raises(ValueError):
        subject.measure(path, pool, layout, output)
    assert not output.exists()
