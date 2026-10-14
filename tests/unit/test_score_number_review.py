import json

import pytest

from scripts.diagnostics.prepare_score_number_review import prepare
from scripts.e2e.run_dataset_case import sha256_file


def fragments(tmp_path):
    image = tmp_path / "frame.jpg"
    image.write_bytes(b"synthetic source fixture")
    record = {"kind": "private_v3_boundary_point_fragments_not_complete_pack",
              "production_input": False, "formal_pack_completed": False,
              "source_video_sha256": "source", "ledger_sha256": "ledger",
              "points": [{"round_id": "sample_round_99", "point": {
                  "type": "round_start", "evidence": ["frame.jpg"]}}],
              "evidence_bindings": [{"evidence_path": "frame.jpg",
                                     "sha256": sha256_file(image), "source_frame_pts": 45.3}]}
    path = tmp_path / "points.json"
    path.write_text(json.dumps(record), encoding="utf-8")
    return path, record, image


def test_label_and_timestamp_do_not_supply_game_round_number(tmp_path):
    path, _, image = fragments(tmp_path)
    before = image.read_bytes()
    report = prepare(path)
    row = report["items"][0]
    assert row["annotation_round_id"] == "sample_round_99"
    assert row["match_round_number_from_score"] is None
    assert row["score_left"] is None and row["score_right"] is None
    assert report["approved_ground_truth"] is False
    assert report["production_input"] is False
    assert image.read_bytes() == before


@pytest.mark.parametrize("mutation", ["image", "duplicate", "escape", "production", "empty"])
def test_unsafe_or_ambiguous_score_review_rejected(tmp_path, mutation):
    path, record, image = fragments(tmp_path)
    if mutation == "image":
        image.write_bytes(b"changed")
    elif mutation == "duplicate":
        record["points"] *= 2
    elif mutation == "escape":
        record["points"][0]["point"]["evidence"] = ["../frame.jpg"]
        record["evidence_bindings"][0]["evidence_path"] = "../frame.jpg"
    elif mutation == "production":
        record["production_input"] = True
    else:
        record["points"] = []
    path.write_text(json.dumps(record), encoding="utf-8")
    with pytest.raises(ValueError):
        prepare(path)
