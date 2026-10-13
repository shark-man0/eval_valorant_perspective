import json
import sys

import pytest

from scripts.diagnostics import assemble_boundary_review_batch as batch


def inputs(tmp_path):
    image = tmp_path / "frame.jpg"
    image.write_bytes(b"private source image")
    evidence = {"kind": "source_overview_not_gt", "video_id": "match_x",
                "source_video_sha256": "a" * 64,
                "source_hash_verified_after_extraction": True,
                "recognizer_outputs_consulted": False,
                "frames": [{"source_frame_pts": 1.0, "image": "frame.jpg",
                            "evidence_frame_sha256": batch.sha256_file(image)}]}
    manifest = tmp_path / "evidence.json"
    manifest.write_text(json.dumps(evidence))
    candidate = {"video_id": "match_x", "source_video_sha256": "a" * 64,
                 "production_input": False, "approved_ground_truth": False,
                 "review_provenance": {"recognizer_outputs_consulted": False},
                 "review_evidence_sha256": batch.sha256_file(manifest),
                 "items": [{"round_id": "r1", "evidence_type": "display_onset",
                            "candidate_time_sec": 1.0, "event_time_sec": None,
                            "notes": "<script>private</script>",
                            "continuity_status": "verified",
                            "evidence": [{"source_frame_pts": 1.0,
                                          "evidence_frame_hash": batch.sha256_file(image)}]}]}
    path = tmp_path / "candidate.json"
    path.write_text(json.dumps(candidate))
    return manifest, path, evidence, candidate


def test_explicit_hash_bindings_stay_private_unapproved_and_do_not_infer_continuity(tmp_path):
    manifest, candidate, _, _ = inputs(tmp_path)
    before = manifest.read_bytes(), candidate.read_bytes()
    result = batch.assemble([candidate], [manifest])
    row = result["items"][0]
    assert result["production_input"] is False and result["approved_ground_truth"] is False
    assert row["event_time_sec"] is None and row["approved_ground_truth"] is False
    assert row["continuity_status"] == "not_independently_verified"
    assert row["evidence"][0]["image_uri"] == (tmp_path / "frame.jpg").as_uri()
    assert before == (manifest.read_bytes(), candidate.read_bytes())


@pytest.mark.parametrize("fault", ["approved", "recognizer", "source", "event",
                                  "missing_manifest", "image_hash", "outside_pts",
                                  "nan", "bool", "unbound_time", "duplicate_item",
                                  "duplicate_pts"])
def test_unsafe_or_unbound_candidates_rejected(tmp_path, fault):
    manifest, path, _, candidate = inputs(tmp_path)
    row = candidate["items"][0]
    if fault == "approved":
        candidate["approved_ground_truth"] = True
    elif fault == "recognizer":
        candidate["review_provenance"]["recognizer_outputs_consulted"] = True
    elif fault == "source":
        candidate["source_video_sha256"] = "b" * 64
    elif fault == "event":
        row["event_time_sec"] = 1.0
    elif fault == "missing_manifest":
        candidate["review_evidence_sha256"] = "b" * 64
    elif fault == "image_hash":
        (tmp_path / "frame.jpg").write_bytes(b"modified")
    elif fault == "outside_pts":
        row["evidence"][0]["source_frame_pts"] = 2
    elif fault in {"nan", "bool"}:
        row["candidate_time_sec"] = float("nan") if fault == "nan" else True
    elif fault == "unbound_time":
        row["candidate_time_sec"] = 2.0
    elif fault == "duplicate_item":
        candidate["items"].append(row)
    else:
        row["evidence"].append(row["evidence"][0])
    path.write_text(json.dumps(candidate))
    with pytest.raises(ValueError):
        batch.assemble([path], [manifest])


def test_prefix_manifest_resolution_and_timestamp_only_references(tmp_path):
    manifest, path, evidence, candidate = inputs(tmp_path)
    image = tmp_path / "prefix.jpg"
    image.write_bytes(b"prefix")
    evidence["frames"] = [{"source_frame_pts": 0.9, "image": "prefix.jpg",
                           "evidence_frame_sha256": batch.sha256_file(image)}]
    prefix = tmp_path / "prefix.json"
    prefix.write_text(json.dumps(evidence))
    candidate["prefix_review_evidence_sha256"] = batch.sha256_file(prefix)
    del candidate["items"][0]["evidence"]
    candidate["items"][0]["evidence_pts"] = [0.9, 1.0]
    path.write_text(json.dumps(candidate))
    result = batch.assemble([path], [manifest, prefix])
    assert [p["source_frame_pts"] for p in result["items"][0]["evidence"]] == [0.9, 1.0]


@pytest.mark.parametrize("fault", ["escape", "duplicate", "unverified", "recognizer"])
def test_bad_source_evidence_rejected(tmp_path, fault):
    manifest, path, evidence, candidate = inputs(tmp_path)
    if fault == "escape":
        evidence["frames"][0]["image"] = "../frame.jpg"
    elif fault == "duplicate":
        evidence["frames"].append(evidence["frames"][0])
    elif fault == "unverified":
        evidence["source_hash_verified_after_extraction"] = False
    else:
        evidence["recognizer_outputs_consulted"] = True
    manifest.write_text(json.dumps(evidence))
    candidate["review_evidence_sha256"] = batch.sha256_file(manifest)
    path.write_text(json.dumps(candidate))
    with pytest.raises(ValueError):
        batch.assemble([path], [manifest])


def test_cli_escapes_text_and_refuses_overwrite(tmp_path, monkeypatch):
    manifest, candidate, _, _ = inputs(tmp_path)
    output = tmp_path / "batch"
    monkeypatch.setattr(sys, "argv", ["batch", "--candidate", str(candidate),
                                     "--evidence", str(manifest), "--output", str(output)])
    batch.main()
    page = (output / "index.html").read_text()
    assert "&lt;script&gt;" in page and "<script>" not in page
    assert "NOT GT" in page
    with pytest.raises(FileExistsError):
        batch.main()


@pytest.mark.parametrize("fault", ["privacy", "image_hash"])
def test_cli_does_not_create_partial_output_on_privacy_or_integrity_failure(
    tmp_path, monkeypatch, fault,
):
    manifest, candidate, _, _ = inputs(tmp_path)
    output = tmp_path / "batch"
    monkeypatch.setattr(sys, "argv", ["batch", "--candidate", str(candidate),
                                     "--evidence", str(manifest), "--output", str(output)])
    if fault == "privacy":
        def reject(_):
            raise ValueError("not ignored")
        monkeypatch.setattr(batch, "_check_output_privacy", reject)
    else:
        (tmp_path / "frame.jpg").write_bytes(b"modified")
    with pytest.raises(ValueError):
        batch.main()
    assert not output.exists()
