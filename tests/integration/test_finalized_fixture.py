import json
from pathlib import Path

import pytest
from test_fixture_validation import valid_pack

from scripts.e2e import finalize_fixture as subject
from scripts.e2e.run_dataset_case import pack_identity
from scripts.e2e.validate_fixture import digest

ROOT = Path(__file__).resolve().parents[2]


def archive(tmp_path):
    root = tmp_path / "archive"
    root.mkdir()
    (root / "freezer.py").write_text("# synthetic recipe",
        encoding="utf-8",
    )
    (root / "ledger.json").write_text('{"synthetic": true}',
        encoding="utf-8",
    )
    receipt = {"production_input": False, "recognizer_qualified": False,
               "formal_pack_completed": False, "source_verified_before_and_after": True,
               "freezer_sha256": digest(root / "freezer.py"),
               "inputs": {"ledger": {"file": "ledger.json",
                                     "sha256": digest(root / "ledger.json")}}}
    (root / "provenance.json").write_text(json.dumps(receipt),
        encoding="utf-8",
    )
    return root


def test_archive_inventory_and_recipe_are_verified(tmp_path):
    root = archive(tmp_path)
    _, values = subject.archive_inputs(root)
    assert values == {"ledger": {"synthetic": True}}
    (root / "unexpected.json").write_text("{}",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="inventory"):
        subject.archive_inputs(root)


@pytest.mark.parametrize("fault", ["recipe", "input", "escape", "unverified"])
def test_invalid_archive_rejected(tmp_path, fault):
    root = archive(tmp_path)
    receipt = json.loads((root / "provenance.json").read_text(
        encoding="utf-8",
    ))
    if fault == "recipe":
        (root / "freezer.py").write_text("# changed",
            encoding="utf-8",
        )
    elif fault == "input":
        (root / "ledger.json").write_text("{}",
            encoding="utf-8",
        )
    elif fault == "escape":
        receipt["inputs"]["ledger"]["file"] = "../outside.json"
    else:
        receipt["source_verified_before_and_after"] = False
    (root / "provenance.json").write_text(json.dumps(receipt),
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        subject.archive_inputs(root)


def test_finalization_transport_keeps_fixture_bytes_and_pins_validator(tmp_path, monkeypatch):
    stage = valid_pack(tmp_path, monkeypatch)
    approved = archive(tmp_path)
    stage_hash = digest(stage / "MANIFEST.json")
    # Transport test only: independent GT provenance and physical source are
    # tested by the original converters and actual private CLI, not this mock.
    monkeypatch.setattr(subject, "verify_approved_gt", lambda *_: {
        "stage_manifest_sha256": stage_hash})
    monkeypatch.setattr(subject, "validate_source", lambda *_: None)
    output = tmp_path / "final"
    before = (stage / "MANIFEST.json").read_bytes()
    subject.finalize(stage, approved, tmp_path / "synthetic.mp4", output, ROOT)
    assert (stage / "MANIFEST.json").read_bytes() == before
    assert (output / "ground_truth/timeline_ground_truth_v3.json").read_bytes() == (
        stage / "ground_truth/timeline_ground_truth_v3.json").read_bytes()
    assert pack_identity(output)[0]["formal_pack_completed"] is True
    manifest = json.loads((output / "MANIFEST.json").read_text(
        encoding="utf-8",
    ))
    manifest["validation_tools"]["scripts/e2e/finalize_fixture.py"] = "0" * 64
    (output / "MANIFEST.json").write_text(json.dumps(manifest),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="validation tool changed"):
        subject.validate_complete(output, ROOT)
    with pytest.raises(FileExistsError):
        subject.finalize(stage, approved, tmp_path / "synthetic.mp4", output, ROOT)
