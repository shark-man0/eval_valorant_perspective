import json

import pytest
from test_geometry_candidate_challenge import fixture

from scripts.diagnostics.prepare_geometry_review import prepare
from scripts.diagnostics.summarize_geometry_review import summarize
from scripts.e2e.run_dataset_case import sha256_file


def reviewed(tmp_path):
    candidate = fixture(tmp_path / "candidate")
    report_path = candidate / "candidate_report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["validation_frames"][0]["source_frame_pts"] = 1.25
    report_path.write_text(json.dumps(report), encoding="utf-8")
    fingerprint_path = candidate / "candidate_fingerprint.json"
    frozen = json.loads(fingerprint_path.read_text(encoding="utf-8"))
    frozen[report_path.name] = sha256_file(report_path)
    fingerprint_path.write_text(json.dumps(frozen), encoding="utf-8")
    receipt = prepare(candidate, tmp_path / "review")
    review = tmp_path / "review/review.json"
    specs = json.loads((candidate / "hud_layout.templates.json").read_text(encoding="utf-8"))
    approval = tmp_path / "approval.json"
    approval.write_text(json.dumps({
        "review_receipt_sha256": sha256_file(review),
        "candidate_report_sha256": receipt["candidate_report_sha256"],
        "candidate_fingerprint_sha256": receipt["candidate_fingerprint_sha256"],
        "scope": {"mask_fixed_ui_not_digits_or_variable_icons": True,
                  "all_reviewed_frames_fixed_ui_visible_at_guides": True,
                  "frame_numbers": [1], "anchors": list(specs["anchors"])}
    }), encoding="utf-8")
    return candidate, review, approval


def test_reviewed_measurements_do_not_qualify_or_mutate_candidate(tmp_path):
    candidate, review, approval = reviewed(tmp_path)
    before = {p.name: sha256_file(p) for p in candidate.iterdir() if p.is_file()}
    result = summarize(candidate, review, approval)
    assert result["sample_count"] == result["unique_source_image_count"] == 1
    assert result["production_adopted"] is False and result["production_qualified"] is False
    assert result["player_identity_qualified"] is False
    assert result["real_video_negative_qualification"] == "incomplete"
    assert result["validation_used_for_fitting"] is False
    assert all(row["human_visible_aligned_count"] == 1 for row in result["anchors"].values())
    assert all(row["edge_acceptance_threshold"] is None for row in result["anchors"].values())
    assert before == {p.name: sha256_file(p) for p in candidate.iterdir() if p.is_file()}


@pytest.mark.parametrize("field,value", [
    ("mask_fixed_ui_not_digits_or_variable_icons", "true"),
    ("all_reviewed_frames_fixed_ui_visible_at_guides", False),
    ("frame_numbers", []), ("anchors", ["round_timer"]),
])
def test_partial_or_coerced_approval_is_rejected(tmp_path, field, value):
    candidate, review, approval = reviewed(tmp_path)
    data = json.loads(approval.read_text(encoding="utf-8"))
    data["scope"][field] = value
    approval.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError):
        summarize(candidate, review, approval)


def test_review_and_source_tampering_are_rejected(tmp_path):
    candidate, review, approval = reviewed(tmp_path)
    review.write_text(review.read_text(encoding="utf-8") + " ", encoding="utf-8")
    with pytest.raises(ValueError, match="fingerprint"):
        summarize(candidate, review, approval)
    data = json.loads(approval.read_text(encoding="utf-8"))
    data["review_receipt_sha256"] = sha256_file(review)
    approval.write_text(json.dumps(data), encoding="utf-8")
    (candidate / "validation_frames/synthetic.jpg").write_bytes(b"changed")
    with pytest.raises(ValueError, match="source binding"):
        summarize(candidate, review, approval)


def test_missing_runtime_score_stays_unavailable_not_zero(tmp_path, monkeypatch):
    candidate, review, approval = reviewed(tmp_path)
    monkeypatch.setattr("scripts.diagnostics.summarize_geometry_review.replay_geometry",
                        lambda *_: {"frames": [{"scores": {}, "accepted_anchors": []}],
                                    "fresh_geometry_success_count": 0})
    result = summarize(candidate, review, approval)
    for row in result["anchors"].values():
        assert row["runtime_similarity"] is None
        assert row["runtime_score_unavailable_count"] == 1
        assert row["runtime_accept_count"] == 0
