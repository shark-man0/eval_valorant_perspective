import json

import pytest

from scripts.e2e import freeze_fixture_provenance as subject


def fixture(tmp_path, monkeypatch):
    """Guard-only synthetic input; not a fabricated independent review fixture."""
    pack = tmp_path / "pack"
    (pack / "ground_truth").mkdir(parents=True)
    (pack / "ground_truth/timeline_ground_truth_v3.json").write_text(json.dumps({
        "fixture_id": "synthetic", "rounds": [{}]}),
        encoding="utf-8",
    )
    approval = tmp_path / "approval.json"
    approval.write_text('{"synthetic": true}', encoding="utf-8")
    ledger = tmp_path / "ledger.json"
    ledger.write_text(json.dumps({"video_id": "synthetic", "source_video_sha256": "a" * 64,
                                  "inputs": [{"file": approval.name,
                                              "sha256": subject.digest(approval)}]}),
        encoding="utf-8",
    )
    # These tests stop before fragment generation; structural validation and
    # each original converter have their own real integration tests.
    monkeypatch.setattr(subject, "validate", lambda *_: None)
    return pack, ledger, approval


def test_ledger_must_match_fixture_identity(tmp_path, monkeypatch):
    pack, ledger, _ = fixture(tmp_path, monkeypatch)
    data = json.loads(ledger.read_text(, encoding="utf-8"))
    data["video_id"] = "wrong"
    ledger.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="fixture mismatch"):
        subject.verify_chain(pack, tmp_path, {"ledger": ledger}, tmp_path)


def test_changed_approval_fails_before_assembly(tmp_path, monkeypatch):
    pack, ledger, approval = fixture(tmp_path, monkeypatch)
    approval.write_text('{"changed": true}', encoding="utf-8")
    with pytest.raises(ValueError, match="approval changed"):
        subject.verify_chain(pack, tmp_path, {"ledger": ledger}, tmp_path)


def test_escaped_approval_is_not_accepted(tmp_path, monkeypatch):
    pack, ledger, _ = fixture(tmp_path, monkeypatch)
    outside = tmp_path.parent / "synthetic-outside.json"
    data = json.loads(ledger.read_text(, encoding="utf-8"))
    data["inputs"][0]["file"] = str(outside)
    ledger.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="escaped"):
        subject.verify_chain(pack, tmp_path, {"ledger": ledger}, tmp_path)


def test_reassembly_difference_is_not_silently_resealed(tmp_path, monkeypatch):
    pack, ledger, _ = fixture(tmp_path, monkeypatch)
    monkeypatch.setattr(subject, "assemble", lambda *_: {"not": "same ledger"})
    before = ledger.read_bytes()
    with pytest.raises(ValueError, match="no longer reproduces"):
        subject.verify_chain(pack, tmp_path, {"ledger": ledger}, tmp_path)
    assert ledger.read_bytes() == before


def test_change_during_reassembly_is_rejected(tmp_path, monkeypatch):
    pack, ledger, _ = fixture(tmp_path, monkeypatch)
    data = json.loads(ledger.read_text(, encoding="utf-8"))

    def changed(*_):
        ledger.write_text(json.dumps({**data, "changed": True}),
            encoding="utf-8",
        )
        return data

    monkeypatch.setattr(subject, "assemble", changed)
    with pytest.raises(ValueError, match="changed before provenance"):
        subject.verify_chain(pack, tmp_path, {"ledger": ledger}, tmp_path)


@pytest.mark.parametrize("field,value", [
    ("video_id", "match_001"), ("policy_version", "different"),
    ("question_reference", "different"), ("human_response", ""),
    ("production_recognizer_input", True)])
def test_policy_approval_scope_cannot_drift(field, value):
    policy = {"version": "match_002.snapshot_source_confidence.v1",
              "approval_reference": "call_4761db3ce4aa458a9a7f2fee43c9fda7:0"}
    approval = {"video_id": "match_002", "policy_version": policy["version"],
                "question_reference": policy["approval_reference"],
                "human_response": "match_002専用の版付き評価修正を承認",
                "production_recognizer_input": False}
    subject.verify_policy_approval(approval, policy, "match_002")
    approval[field] = value
    with pytest.raises(ValueError, match="explicit versioned"):
        subject.verify_policy_approval(approval, policy, "match_002")
