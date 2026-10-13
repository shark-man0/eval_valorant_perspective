import copy
import json
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from scripts.e2e import prepare_boundary_points as preparation

PACK = Path(__file__).resolve().parents[2] / "ValorantData/valorant_e2e_validation_pack_v3"


def inputs(tmp_path):
    root = tmp_path / "review"
    root.mkdir()
    frames = []
    for t in [1.0, 1.1]:
        image = root / f"frame_{t}.jpg"
        image.write_bytes(f"source image {t}".encode())
        frames.append({"source_frame_pts": t, "requested_sec": t, "image": image.name,
                       "evidence_frame_sha256": preparation.sha256_file(image)})
    manifest = root / "review_evidence.json"
    manifest.write_text(json.dumps({"frames": frames}))
    ledger = {"kind": "private_approved_boundary_ledger_not_validation_pack",
              "production_input": False, "video_id": "match_test",
              "source_video_sha256": "a" * 64, "boundaries": [{
                  "round_id": "sample_round_1", "boundary_kind": "round_start",
                  "approved_time_sec": 1.1, "approved_record": {},
              }]}
    witness = {"production_input": False, "video_id": "match_test",
               "source_video_sha256": "a" * 64, "pairs": [[1, "round_start", 1.0, 1.1]]}
    catalog = {f["source_frame_pts"]: [(manifest, f)] for f in frames}
    policy = json.loads((PACK / "ground_truth/evaluation_policy_v3.json").read_text())
    return ledger, witness, catalog, policy


def test_v3_fragment_does_not_invent_confidence_or_unknown_facts(tmp_path):
    ledger, witness, frames, policy = inputs(tmp_path)
    before = copy.deepcopy((ledger, witness, frames, policy))
    points, bindings = preparation.prepare(ledger, witness, frames, policy)
    point = points[0]["point"]
    schema = json.loads((PACK / "schemas/e2e_ground_truth_schema_v3.json").read_text())
    Draft202012Validator({"$ref": "#/$defs/point_event", "$defs": schema["$defs"]}).validate(point)
    assert point["evidence_bracket"] == {"last_absent_sec": 1.0, "first_present_sec": 1.1}
    assert point["tolerance_before_sec"] == point["tolerance_after_sec"] == .1
    assert point["facts"] == {} and "confidence" not in point
    assert len(bindings) == 2
    assert (ledger, witness, frames, policy) == before


@pytest.mark.parametrize("fault", ["retime", "null", "bool", "reversed", "missing",
                                  "duplicate", "ambiguous", "image", "escape", "unobservable"])
def test_unproven_or_mutated_witnesses_do_not_become_point_gt(tmp_path, fault):
    ledger, witness, frames, policy = inputs(tmp_path)
    pair = witness["pairs"][0]
    if fault == "retime":
        pair[3] = 1.2
    elif fault == "null":
        pair[2] = None
    elif fault == "bool":
        pair[2] = True
    elif fault == "reversed":
        pair[2] = 1.2
    elif fault == "missing":
        frames.pop(1.0)
    elif fault == "duplicate":
        witness["pairs"].append(copy.deepcopy(pair))
    elif fault == "ambiguous":
        path, frame = frames[1.0][0]
        frames[1.0].append((path, {**frame, "evidence_frame_sha256": "b" * 64}))
    elif fault == "image":
        path, frame = frames[1.0][0]
        (path.parent / frame["image"]).write_bytes(b"modified")
    elif fault == "escape":
        frames[1.0][0][1]["image"] = "../outside.jpg"
    else:
        ledger["boundaries"][0]["approved_record"]["first_native_onset_verified"] = False
    with pytest.raises(ValueError):
        preparation.prepare(ledger, witness, frames, policy)


def test_cli_preserves_source_bytes_and_writes_only_private_staging_not_a_manifest(
    tmp_path, monkeypatch,
):
    ledger, witness, frames, _policy = inputs(tmp_path)
    root = tmp_path / "review"
    manifest = root / "review_evidence.json"
    manifest.write_text(json.dumps({"frames": [row[0][1] for row in frames.values()],
                                   "kind": "source_overview_not_gt", "video_id": "match_test",
                                   "source_video_sha256": "a" * 64,
                                   "source_hash_verified_after_extraction": True,
                                   "recognizer_outputs_consulted": False}))
    ledger_path, witness_path = tmp_path / "ledger.json", tmp_path / "witness.json"
    ledger_path.write_text(json.dumps(ledger))
    witness["ledger_sha256"] = preparation.sha256_file(ledger_path)
    witness_path.write_text(json.dumps(witness))
    output = tmp_path / "staging"
    monkeypatch.setattr(sys, "argv", ["prepare", "--ledger", str(ledger_path),
                                     "--witnesses", str(witness_path),
                                     "--review-root", str(tmp_path),
                                     "--canonical-pack", str(PACK), "--output", str(output)])
    preparation.main()
    report = json.loads((output / "point_fragments.json").read_text())
    assert report["formal_pack_completed"] is False and report["production_input"] is False
    assert not (output / "timeline_ground_truth_v3.json").exists()
    for binding in report["evidence_bindings"]:
        assert preparation.sha256_file(output / binding["evidence_path"]) == binding["sha256"]
        assert preparation.sha256_file(Path(binding["source_path"])) == binding["sha256"]
    with pytest.raises(FileExistsError):
        preparation.main()


def test_source_manifest_changes_after_cataloging_are_rejected(tmp_path):
    ledger, witness, frames, policy = inputs(tmp_path)
    manifest = frames[1.0][0][0]
    digest = preparation.sha256_file(manifest)
    for rows in frames.values():
        rows[0][1]["_catalog_manifest_sha256"] = digest
    manifest.write_text("{}")
    with pytest.raises(ValueError, match="changed after cataloging"):
        preparation.prepare(ledger, witness, frames, policy)
