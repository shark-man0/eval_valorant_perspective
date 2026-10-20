import json

import cv2
import numpy as np
import pytest

from scripts.diagnostics.prepare_numeric_review import prepare
from scripts.e2e.run_dataset_case import sha256_file


def fixture(root):
    """Same synthetic review raster, without invoking a Geometry candidate builder."""
    root.mkdir()
    (root / "hud_layout.json").write_text(json.dumps({
        "schema_version": "1.0", "calibrated": True,
        "roi_coordinate_system": "normalized_0_to_1",
        "reference_resolution": {"width": 160, "height": 100},
        "regions": {name: {"x": 0, "y": 0, "width": 1, "height": 1}
                    for name in ("round_timer", "top_match_bar", "player_hp_armor", "abilities")},
    }), encoding="utf-8")
    images = root / "validation_frames"
    images.mkdir()
    # Exact pixels of the former changing_brightness()[15] fixture.
    image = np.full((100, 160, 3), 80, np.uint8)
    cv2.rectangle(image, (15, 15), (140, 80), (140,) * 3, 3)
    cv2.line(image, (25, 30), (120, 65), (180,) * 3, 3)
    path = images / "synthetic.jpg"
    assert cv2.imwrite(str(path), image)
    (root / "candidate_report.json").write_text(json.dumps({
        "validation_frames": [{"sha256": sha256_file(path)}],
    }), encoding="utf-8")
    return root


def inputs(tmp_path):
    candidate = fixture(tmp_path / "candidate")
    layout_path = candidate / "hud_layout.json"
    layout = json.loads(layout_path.read_text(encoding="utf-8"))
    for key in ("ally_score", "enemy_score"):
        layout["regions"][key] = {"x": 0, "y": 0, "width": 1, "height": 1}
    layout_path.write_text(json.dumps(layout), encoding="utf-8")
    report_path = candidate / "candidate_report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["source_sha256"] = "1" * 64
    report["validation_frames"][0]["source_frame_pts"] = 1.25
    report_path.write_text(json.dumps(report), encoding="utf-8")
    probe = tmp_path / "probe"
    probe.mkdir()
    (probe / "hud_layout.json").write_bytes(layout_path.read_bytes())
    (probe / "probe_summary.json").write_text(json.dumps({
        "source_sha256": report["source_sha256"],
        "candidate_report_sha256": sha256_file(report_path), "frames": 1,
        "ocr_prediction": "MUST_NOT_EXPOSE_READER_OUTPUT",
        "confidence": "MUST_NOT_EXPOSE_CONFIDENCE",
    }), encoding="utf-8")
    return candidate, probe


def test_numeric_review_shows_source_only_and_infers_no_labels(tmp_path):
    candidate, probe = inputs(tmp_path)
    image = candidate / "validation_frames/synthetic.jpg"
    before = sha256_file(image)
    output = tmp_path / "review"
    receipt = prepare(candidate, probe, output)
    page = (output / "index.html").read_text(encoding="utf-8")
    assert "MUST_NOT_EXPOSE" not in page
    assert receipt["model_outputs_exposed"] is False
    assert receipt["production_input"] is False and receipt["approved"] is False
    assert receipt["frames"][0]["labels"] is None
    assert len(list(output.glob("*.png"))) == 3
    assert sha256_file(image) == before
    with pytest.raises(FileExistsError):
        prepare(candidate, probe, output)


def test_numeric_review_rejects_mismatched_source_or_changed_image(tmp_path):
    candidate, probe = inputs(tmp_path)
    report = candidate / "candidate_report.json"
    report.write_text(report.read_text(encoding="utf-8") + " ", encoding="utf-8")
    with pytest.raises(ValueError, match="do not match"):
        prepare(candidate, probe, tmp_path / "review")
