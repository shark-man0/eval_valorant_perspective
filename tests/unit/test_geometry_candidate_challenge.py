import json

import cv2
import pytest
from test_geometry_candidate import layout
from test_geometry_edge_experiment import changing_brightness

from scripts.diagnostics import challenge_geometry_candidate as subject
from scripts.diagnostics.build_geometry_candidate import build
from scripts.e2e.run_dataset_case import sha256_file


def fixture(root):
    root.mkdir()
    build(changing_brightness(), layout(), {}, root)
    (root / "hud_layout.json").write_text(json.dumps({
        "schema_version": "1.0", "calibrated": True,
        "roi_coordinate_system": "normalized_0_to_1",
        "reference_resolution": {"width": 160, "height": 100},
        "regions": {name: {"x": 0, "y": 0, "width": 1, "height": 1}
                    for name in layout().regions}}))
    images = root / "validation_frames"
    images.mkdir()
    image = images / "synthetic.jpg"
    assert cv2.imwrite(str(image), changing_brightness()[15])
    (root / "candidate_report.json").write_text(json.dumps({
        "validation_frames": [{"sha256": sha256_file(image)}]}))
    (root / "candidate_fingerprint.json").write_text(json.dumps({
        path.name: sha256_file(path) for path in root.iterdir() if path.is_file()}))
    return root


def test_full_roi_ablation_does_not_prove_removed_anchor(tmp_path):
    root = fixture(tmp_path / "candidate")
    report = subject.challenge(root)
    assert report["case_count"] == 4 and report["false_match_cases"] == 0
    assert report["references_changed"] is False and report["production_adopted"] is False


def test_false_anchor_matches_are_exposed_not_hidden_by_other_geometry(tmp_path, monkeypatch):
    root = fixture(tmp_path / "candidate")
    monkeypatch.setattr(subject, "replay_geometry", lambda *_: {"frames": [{
        "accepted_anchors": list(layout().regions), "scores": {},
        "fresh_geometry_success": True}]})
    report = subject.challenge(root)
    assert report["false_match_cases"] == 4
    assert set(report["removed_anchor_false_match_counts"].values()) == {1}


def test_changed_candidate_is_rejected_before_challenge(tmp_path):
    root = fixture(tmp_path / "candidate")
    (root / "round_timer.mask.png").write_bytes(b"changed")
    with pytest.raises(ValueError, match="candidate changed"):
        subject.challenge(root)
