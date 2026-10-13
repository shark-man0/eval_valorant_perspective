import json

import pytest
from test_geometry_candidate_challenge import fixture

from scripts.diagnostics.prepare_geometry_review import prepare


def test_geometry_review_hides_model_results_and_preserves_originals(tmp_path):
    candidate = fixture(tmp_path / "candidate")
    path = candidate / "candidate_report.json"
    report = json.loads(path.read_text(encoding="utf-8"))
    report["validation_frames"][0]["source_frame_pts"] = 1.25
    report["secret_score"] = "MUST_NOT_SHOW"
    # This test owns its synthetic frozen fixture; it updates its fingerprint.
    path.write_text(json.dumps(report), encoding="utf-8")
    fingerprint = candidate / "candidate_fingerprint.json"
    data = json.loads(fingerprint.read_text(encoding="utf-8"))
    from scripts.e2e.run_dataset_case import sha256_file

    data[path.name] = sha256_file(path)
    fingerprint.write_text(json.dumps(data), encoding="utf-8")
    before = sha256_file(candidate / "validation_frames/synthetic.jpg")
    output = tmp_path / "review"
    receipt = prepare(candidate, output)
    page = (output / "index.html").read_text(encoding="utf-8")
    assert "MUST_NOT_SHOW" not in page and receipt["model_scores_exposed"] is False
    assert receipt["frames"][0]["labels"] is None
    assert receipt["production_input"] is False and receipt["approved_ground_truth"] is False
    assert sha256_file(candidate / "validation_frames/synthetic.jpg") == before
    with pytest.raises(FileExistsError):
        prepare(candidate, output)
