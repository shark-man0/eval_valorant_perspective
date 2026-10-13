import copy
import json
import sys

import pytest

from scripts.diagnostics import assemble_approved_boundary_ledger as ledger
from scripts.diagnostics.assemble_approved_boundary_ledger import assemble, sha256_file


def approval(tmp_path, name="approved.json"):
    record = {"video_id": "match_test", "source_video_sha256": "a" * 64,
              "approved_ground_truth": True, "production_input": False,
              "review_provenance": {"reviewer": "human user in current chat",
                                    "approval_quote": "approved", "scope": "approximate times"},
              "items": [{"round_id": "r1", "event_type": kind, "event_time_sec": time}
                        for kind, time in [("round_start", 1), ("round_end", 2)]]}
    path = tmp_path / name
    path.write_text(json.dumps(record))
    return path, record


def test_ledger_preserves_approved_times_scope_and_unknown_brackets_without_inference(tmp_path):
    path, record = approval(tmp_path)
    record["items"][1]["last_absent_sec"] = None
    path.write_text(json.dumps(record))
    before = path.read_bytes()
    result = assemble([path], 1)
    assert [row["approved_time_sec"] for row in result["boundaries"]] == [1, 2]
    assert result["boundaries"][1]["approved_record"]["last_absent_sec"] is None
    assert result["production_input"] is False and result["formal_pack_completed"] is False
    assert result["new_evidence_brackets_inferred"] is False
    assert result["boundaries"][0]["approval_sha256"] == sha256_file(path)
    assert path.read_bytes() == before


@pytest.mark.parametrize("fault", ["unapproved", "production", "reviewer", "quote",
                                  "missing_end", "reversed", "nan", "bool", "duplicate"])
def test_unapproved_incomplete_or_conflicting_records_fail(tmp_path, fault):
    path, record = approval(tmp_path)
    if fault == "unapproved":
        record["approved_ground_truth"] = False
    elif fault == "production":
        record["production_input"] = True
    elif fault in {"reviewer", "quote"}:
        record["review_provenance"]["reviewer" if fault == "reviewer" else "approval_quote"] = ""
    elif fault == "missing_end":
        record["items"].pop()
    elif fault == "reversed":
        record["items"][1]["event_time_sec"] = 0
    elif fault in {"nan", "bool"}:
        record["items"][0]["event_time_sec"] = float("nan") if fault == "nan" else True
    else:
        record["items"].append(copy.deepcopy(record["items"][0]))
    path.write_text(json.dumps(record))
    with pytest.raises(ValueError):
        assemble([path], 1)


def test_source_mismatch_and_coverage_fail(tmp_path):
    path, record = approval(tmp_path)
    other = tmp_path / "other.json"
    record["source_video_sha256"] = "b" * 64
    other.write_text(json.dumps(record))
    with pytest.raises(ValueError, match="identity"):
        assemble([path, other], 1)
    with pytest.raises(ValueError, match="coverage"):
        assemble([path], 2)


def test_item_specific_quotes_are_preserved_without_inventing_a_shared_quote(tmp_path):
    path, record = approval(tmp_path)
    del record["review_provenance"]["approval_quote"]
    for i, row in enumerate(record["items"]):
        row["approval_quote"] = f"item {i} approved"
    path.write_text(json.dumps(record))
    result = assemble([path], 1)
    assert [row["review_provenance"]["approval_quote"] for row in result["boundaries"]] == [
        "item 0 approved", "item 1 approved",
    ]


@pytest.mark.parametrize("modified", [False, True])
def test_explicit_batch_approval_is_hash_bound_and_does_not_approve_other_items(tmp_path, modified):
    path, record = approval(tmp_path)
    batch = {"video_id": record["video_id"], "source_video_sha256": record["source_video_sha256"],
             "production_input": False, "recognizer_outputs_consulted": False,
             "items": [{"round_id": "r1", "evidence_type": kind, "candidate_time_sec": time,
                        "event_time_sec": None}
                       for kind, time in [("purchase_display_to_active_timer", 1),
                                          ("result_display_animation_onset", 2),
                                          ("post_side_switch_purchase_context", None)]]}
    batch_path = tmp_path / "batch.json"
    batch_path.write_text(json.dumps(batch))
    del record["items"]
    record["review_batch"] = {"file": "batch.json", "sha256": sha256_file(batch_path)}
    record["approved_batch_item_indices"] = [0, 1]
    path.write_text(json.dumps(record))
    if modified:
        batch_path.write_text("{}")
        with pytest.raises(ValueError, match="binding"):
            assemble([path], 1)
    else:
        result = assemble([path], 1)
        assert len(result["boundaries"]) == 2
        assert result["context_observations"] == []


def test_cli_writes_private_ledger_only_and_refuses_overwrite(tmp_path, monkeypatch):
    path, _ = approval(tmp_path)
    output = tmp_path / "ledger.json"
    monkeypatch.setattr(sys, "argv", ["ledger", "--approval", str(path),
                                     "--expected-round-count", "1", "--output", str(output)])
    ledger.main()
    before = output.read_bytes()
    report = json.loads(before)
    assert report["formal_pack_completed"] is False and report["production_input"] is False
    assert not (tmp_path / "manifest.json").exists()
    with pytest.raises(FileExistsError):
        ledger.main()
    assert output.read_bytes() == before


def test_cli_privacy_failure_does_not_write_partial_ledger(tmp_path, monkeypatch):
    path, _ = approval(tmp_path)
    output = tmp_path / "ledger.json"
    monkeypatch.setattr(sys, "argv", ["ledger", "--approval", str(path),
                                     "--expected-round-count", "1", "--output", str(output)])
    def reject(_):
        raise ValueError("output not ignored")
    monkeypatch.setattr(ledger, "_check_output_privacy", reject)
    with pytest.raises(ValueError, match="ignored"):
        ledger.main()
    assert not output.exists()
