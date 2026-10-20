import json

import pytest
from test_numeric_blind_review import inputs

from scripts.diagnostics.compare_numeric_review import classify, compare
from scripts.diagnostics.freeze_numeric_review import FIELDS, freeze
from scripts.diagnostics.prepare_numeric_review import prepare
from scripts.e2e.run_dataset_case import sha256_file


def accepted(text="1", confidence=.95):
    return {"meets_ocr_floor_and_format": True, "ocr_confidence": confidence,
            "raw_ocr_text": text, "bounds_in_roi": [0, 0, 10, 10]}


@pytest.mark.parametrize("label,row,outcome", [
    ({"kind": "value", "display": "1"}, accepted(), "correct_value"),
    ({"kind": "value", "display": "2"}, accepted(), "wrong_value"),
    ({"kind": "absent"}, accepted(), "false_accept_absent"),
    ({"kind": "absent"}, {"meets_ocr_floor_and_format": False}, "correct_absent_rejection"),
    ({"kind": "value", "display": "2"}, {"meets_ocr_floor_and_format": False},
     "missing_visible_value"),
    ({"kind": "unknown"}, accepted(), "unknown"),
    (None, accepted(), "unreviewed"),
])
def test_explicit_outcomes_do_not_turn_unknown_or_absent_into_truth(label, row, outcome):
    assert classify(label, row, "ally_score") == outcome


@pytest.mark.parametrize("row", [accepted(confidence=.89), accepted(confidence=float("nan")),
                                 accepted("word"), {"meets_ocr_floor_and_format": 1}])
def test_false_acceptance_flags_cannot_bypass_frozen_floor_or_format(row):
    with pytest.raises(ValueError):
        classify({"kind": "absent"}, row, "ally_score")


def bundle(tmp_path, *, duplicate=False, missing=False, repeat=False, conflicting=False):
    candidate, probe = inputs(tmp_path)
    report = json.loads((candidate / "candidate_report.json").read_text(encoding="utf-8"))
    if repeat:
        report["validation_frames"].append({**report["validation_frames"][0],
                                            "source_frame_pts": 2.0})
        image = candidate / "validation_frames/synthetic.jpg"
        (image.parent / "synthetic_repeat.jpg").write_bytes(image.read_bytes())
        (candidate / "candidate_report.json").write_text(json.dumps(report), encoding="utf-8")
    source_hash = report["validation_frames"][0]["sha256"]
    rows = [{**accepted("1:40" if name == "round_timer" else "1"),
             "sample_index": 0, "region": name, "source_image_sha256": source_hash,
             "passed_to_analyzer": False, "localization_qualified": False,
             "runtime_geometry_valid": True}
            for name in FIELDS]
    if repeat:
        rows += [{**row, "sample_index": 1} for row in rows]
    if duplicate:
        rows.append(rows[0])
    if missing:
        rows.pop()
    raw = probe / "observations.json"
    raw.write_text(json.dumps({"production_adopted": False,
                              "localized_numeric_diagnostics_not_analyzer_input": rows}),
                   encoding="utf-8")
    summary = probe / "probe_summary.json"
    data = json.loads(summary.read_text(encoding="utf-8"))
    data.update(production_adopted=False, observations_sha256=sha256_file(raw),
                frames=2 if repeat else 1,
                candidate_report_sha256=sha256_file(candidate / "candidate_report.json"))
    summary.write_text(json.dumps(data), encoding="utf-8")
    review = tmp_path / "review"
    prepare(candidate, probe, review)
    response = tmp_path / "synthetic_response.csv"
    response.write_text("1,1:40,absent,2\n" + (
        ("2,1:40,absent,3\n" if conflicting else "2,1:40,absent,2\n") if repeat else ""),
        encoding="utf-8")
    labels = tmp_path / "labels.json"
    freeze(review, response, "synthetic-not-human-review", labels)
    return review, labels, response, probe


def test_comparison_bound_to_original_assets_keeps_raw_and_labels_private(tmp_path):
    review, labels, response, probe = bundle(tmp_path)
    raw = probe / "observations.json"
    before = sha256_file(raw)
    output = tmp_path / "comparison.json"
    result = compare(review, labels, response, probe, output)
    assert result["point_counts"]["round_timer"]["correct_value"] == 1
    assert result["point_counts"]["ally_score"]["false_accept_absent"] == 1
    assert result["point_counts"]["enemy_score"]["wrong_value"] == 1
    assert result["point_counts"]["round_timer"]["wrong_value"] == 0
    assert result["point_counts_by_runtime_geometry"]["valid"]["round_timer"]["correct_value"] == 1
    assert result["production_qualified"] is False
    assert sha256_file(raw) == before
    text = output.read_text(encoding="utf-8")
    for private in ("raw_ocr_text", "source_frame_pts", "bounds_in_roi", "1:40", str(tmp_path)):
        assert private not in text
    with pytest.raises(FileExistsError):
        compare(review, labels, response, probe, output)


@pytest.mark.parametrize("duplicate,missing", [(True, False), (False, True)])
def test_incomplete_or_duplicate_diagnostics_cannot_report_success(tmp_path, duplicate, missing):
    args = bundle(tmp_path, duplicate=duplicate, missing=missing)
    with pytest.raises(ValueError, match="inventory|missing"):
        compare(*args, tmp_path / "comparison.json")


@pytest.mark.parametrize("target", ["labels", "raw", "response", "roi"])
def test_changed_frozen_inputs_rejected(tmp_path, target):
    review, labels, response, probe = bundle(tmp_path)
    if target == "labels":
        data = json.loads(labels.read_text(encoding="utf-8"))
        data["frames"][0]["labels"]["ally_score"] = {"kind": "value", "display": "1"}
        labels.write_text(json.dumps(data), encoding="utf-8")
    elif target == "raw":
        raw = probe / "observations.json"
        raw.write_text(raw.read_text(encoding="utf-8") + " ", encoding="utf-8")
    elif target == "response":
        response.write_text("1,1:40,1,2\n", encoding="utf-8")
    else:
        (review / "frame_01_round_timer.png").write_bytes(b"tampered")
    with pytest.raises(ValueError):
        compare(review, labels, response, probe, tmp_path / "comparison.json")


def test_numeric_equivalence_never_fabricates_missing_colon():
    assert classify({"kind": "value", "display": "00:01"}, accepted("0:01"),
                    "round_timer") == "correct_value"
    with pytest.raises(ValueError):
        classify({"kind": "value", "display": "0:01"}, accepted("001"), "round_timer")


def test_fractional_source_label_is_not_rounded_to_make_reader_correct():
    label = {"kind": "value", "display": "0:27.46"}
    assert classify(label, accepted("0:27"), "round_timer") == "wrong_value"
    assert classify(label, {"meets_ocr_floor_and_format": False},
                    "round_timer") == "missing_visible_value"
    with pytest.raises(ValueError):
        classify(label, accepted("0:27.46"), "round_timer")


def test_repeated_source_images_are_not_independent_conditions(tmp_path):
    result = compare(*bundle(tmp_path, repeat=True), tmp_path / "comparison.json")
    assert result["frame_count"] == 2 and result["unique_source_image_count"] == 1
    assert result["point_counts"]["round_timer"]["correct_value"] == 2
    assert result["unique_image_counts"]["round_timer"]["correct_value"] == 1


def test_conflicting_labels_for_same_source_fail_closed(tmp_path):
    with pytest.raises(ValueError, match="duplicate image"):
        compare(*bundle(tmp_path, repeat=True, conflicting=True), tmp_path / "comparison.json")
