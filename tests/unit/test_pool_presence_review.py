import json

import cv2
import numpy as np
import pytest
from test_numeric_blind_review import inputs

from scripts.diagnostics.prepare_pool_presence_review import prepare
from scripts.e2e.run_dataset_case import sha256_file


def source_pool(tmp_path):
    candidate, probe = inputs(tmp_path)
    pool = probe / "pool_frames"
    pool.mkdir()
    records = []
    for number in range(3):
        path = pool / f"frame_{number:02d}.jpg"
        assert cv2.imwrite(str(path), np.full((100, 160, 3), number * 50, np.uint8))
        records.append({"source_frame_pts": number, "sha256": sha256_file(path)})
    # Duplicate pixels must not become an independent review condition.
    (pool / "frame_03.jpg").write_bytes((pool / "frame_02.jpg").read_bytes())
    records.append({**records[2], "source_frame_pts": 3})
    selection = probe / "review_selection.json"
    selection.write_text(json.dumps({"pool_records": records,
                                    "selection_frozen_before_numeric_measurement": True}),
                         encoding="utf-8")
    report = probe / "candidate_report.json"
    report.write_text(json.dumps({"source_sha256": "1" * 64,
                                 "validation_frames": [records[0]]}), encoding="utf-8")
    summary = probe / "probe_summary.json"
    summary.write_text(json.dumps({"kind": "prospective_numeric_point_probe_not_lifecycle_e2e",
        "production_adopted": False, "selection_sha256": sha256_file(selection),
        "candidate_report_sha256": sha256_file(report), "source_sha256": "1" * 64,
        "pool_frame_count": 4, "ocr_prediction": "MUST_NOT_SHOW_OCR",
        "confidence": "MUST_NOT_SHOW_CONFIDENCE"}), encoding="utf-8")
    return candidate, probe


def test_reuses_frozen_sources_omits_reviewed_images_and_infers_no_labels(tmp_path):
    _, probe = source_pool(tmp_path)
    before = sha256_file(probe / "pool_frames/frame_01.jpg")
    output = tmp_path / "presence"
    receipt = prepare(probe, output)
    assert len(receipt["frames"]) == 2
    assert [row["pool_index"] for row in receipt["frames"]] == [1, 2]
    assert all(row["labels"] is None for row in receipt["frames"])
    assert receipt["labels_inferred"] is False and receipt["approved"] is False
    assert "MUST_NOT_SHOW" not in (output / "index.html").read_text(encoding="utf-8")
    assert sha256_file(probe / "pool_frames/frame_01.jpg") == before
    with pytest.raises(FileExistsError):
        prepare(probe, output)


@pytest.mark.parametrize("change", ["image", "selection", "missing"])
def test_changed_or_incomplete_pool_is_rejected_without_model_run(tmp_path, change):
    _, probe = source_pool(tmp_path)
    if change == "image":
        (probe / "pool_frames/frame_01.jpg").write_bytes(b"tampered")
    elif change == "selection":
        path = probe / "review_selection.json"
        path.write_text(path.read_text(encoding="utf-8") + " ", encoding="utf-8")
    else:
        (probe / "pool_frames/frame_01.jpg").unlink()
    with pytest.raises(ValueError):
        prepare(probe, tmp_path / "presence")
