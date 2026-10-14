import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_pool_presence_review import source_pool

from scripts.diagnostics import verify_score_absence as subject
from scripts.diagnostics.prepare_pool_presence_review import prepare
from scripts.e2e.run_dataset_case import sha256_file
from scripts.e2e.run_metrics import code_fingerprint
from valorant_ai_coach.hud.readers import ReaderResult
from valorant_ai_coach.hud.templates import HudTemplateProfile


def test_sparse_review_never_fills_unmentioned_frames_or_other_side():
    result = subject.parse_response("両方非表示: 1\n味方のみ非表示: 2\n", {1, 2, 3})
    assert set(result) == {1, 2}
    assert result[1] == {"ally_score": {"kind": "absent"}, "enemy_score": {"kind": "absent"}}
    assert result[2]["ally_score"] == {"kind": "absent"}
    assert result[2]["enemy_score"] is None


@pytest.mark.parametrize("text", ["", "全部承認", "両方非表示: 99", "両方非表示: 1,1",
    "両方非表示: 1\n敵のみ非表示: 1", "両方非表示: -1", "両方非表示: unknown"])
def test_ambiguous_conflicting_or_unknown_frames_rejected(text):
    with pytest.raises(ValueError):
        subject.parse_response(text, {1, 2})


def frozen(tmp_path):
    candidate, pool = source_pool(tmp_path)
    review = tmp_path / "review"
    prepare(pool, review)
    response = tmp_path / "synthetic_response.txt"
    response.write_text("両方非表示: 1\n", encoding="utf-8")
    labels = tmp_path / "labels.json"
    receipt = subject.freeze(review, response, "synthetic-not-human-proof", labels)
    return candidate, pool, review, response, labels, receipt


def test_source_freeze_preserves_original_receipt_and_unreviewed_frames(tmp_path):
    _, _, review, response, labels, receipt = frozen(tmp_path)
    assert receipt["frames"][0]["labels"]["ally_score"] == {"kind": "absent"}
    assert receipt["frames"][1]["labels"] is None
    assert receipt["production_adoption_approved"] is False
    assert receipt["review_sha256"] == sha256_file(review / "review.json")
    original = json.loads((review / "review.json").read_text())
    assert all(r["labels"] is None for r in original["frames"])
    with pytest.raises(FileExistsError):
        subject.freeze(review, response, "synthetic", labels)


def setup_measurement(tmp_path, monkeypatch, value):
    candidate, pool = source_pool(tmp_path)
    layout = candidate / "hud_layout.json"
    profile_path = layout.with_suffix(".templates.json")
    profile = HudTemplateProfile.load(profile_path)
    model_paths = [layout, profile_path, Path(subject.numeric_text_localization.__file__),
                   *[profile.resolve_asset(str(p)) for p in profile.asset_paths]]
    plan_path = pool.parent / "plan.json"
    plan_path.write_text(json.dumps({"inputs_sha256": {str(p.resolve()): sha256_file(p)
                        for p in model_paths}, "toolchain_fingerprints": {"synthetic": "fixed"}}))
    summary_path = pool / "probe_summary.json"
    data = json.loads(summary_path.read_text())
    data["plan_sha256"] = sha256_file(plan_path)
    summary_path.write_text(json.dumps(data))
    review = tmp_path / "review"
    prepare(pool, review)
    response = tmp_path / "synthetic_response.txt"
    response.write_text("両方非表示: 1\n", encoding="utf-8")
    labels = tmp_path / "labels.json"
    subject.freeze(review, response, "synthetic-not-human-proof", labels)
    reader = tmp_path / "reader_receipt.json"
    reader.write_text(json.dumps({"adapter_code_sha256": sha256_file(
        Path(subject.localized_digits_reader.__file__)), "production_qualified": False,
        "runtime_code_fingerprint": code_fingerprint(Path(subject.__file__).resolve().parents[2])}))
    calls = []
    def read(image, roi):
        # Pixel-only API: no labels, frame IDs or expected values enter the reader.
        calls.append((image.shape, roi.shape))
        return ReaderResult(value, .98, ("synthetic-pixel-reader",))
    monkeypatch.setattr(subject.localized_digits_reader, "build_readers", lambda _: {
        field: SimpleNamespace(read=read) for field in subject.FIELDS})
    monkeypatch.setattr(subject, "toolchain_fingerprints", lambda: {"synthetic": "fixed"})
    return (review, labels, response, pool, candidate / "hud_layout.json", reader), calls


@pytest.mark.parametrize("value,false_positive", [(None, 0), ("1", 1)])
def test_actual_false_positive_is_reported_not_hidden_by_qualification_flag(
        tmp_path, monkeypatch, value, false_positive):
    args, calls = setup_measurement(tmp_path, monkeypatch, value)
    output = tmp_path / "measured"
    result = subject.measure(*args, output)
    assert len(calls) == 2
    for field in subject.FIELDS:
        assert result["counts"][field] == {"reviewed": 1, "false_positive": false_positive}
    assert result["production_qualified"] is False and result["outside_analyzer"] is True
    assert result["native_geometry_bypass"] is False
    assert "frame_number" not in (output / "summary.json").read_text()
    with pytest.raises(FileExistsError):
        subject.measure(*args, output)


def test_tampered_sparse_labels_cannot_redefine_source_truth(tmp_path, monkeypatch):
    args, calls = setup_measurement(tmp_path, monkeypatch, None)
    labels = args[1]
    data = json.loads(labels.read_text())
    data["frames"][1]["labels"] = {f: {"kind": "absent"} for f in subject.FIELDS}
    labels.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="binding changed"):
        subject.measure(*args, tmp_path / "measured")
    assert not calls


def test_changed_reviewed_roi_or_missing_provenance_cannot_be_frozen(tmp_path):
    _, _, review, response, _, _ = frozen(tmp_path)
    with pytest.raises(ValueError, match="provenance"):
        subject.freeze(review, response, " ", tmp_path / "other.json")
    (review / "frame_01_ally_score.png").write_bytes(b"changed")
    with pytest.raises(ValueError, match="ROI changed"):
        subject.freeze(review, response, "synthetic", tmp_path / "other.json")


def test_model_profile_drift_is_rejected_before_reading_pixels(tmp_path, monkeypatch):
    args, calls = setup_measurement(tmp_path, monkeypatch, None)
    profile = args[4].with_suffix(".templates.json")
    profile.write_text(profile.read_text() + " ")
    with pytest.raises(ValueError, match="since fixed source pool"):
        subject.measure(*args, tmp_path / "measured")
    assert not calls


def test_unknown_and_no_matches_never_manufacture_absence():
    assert subject.parse_response("unknown: 1", {1}) == {
        1: {"ally_score": {"kind": "unknown"}, "enemy_score": {"kind": "unknown"}}}
    assert subject.parse_response("該当なし", {1, 2}) == {}
