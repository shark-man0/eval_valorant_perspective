import json
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from scripts.diagnostics import discover_banner_references as subject
from scripts.e2e.run_dataset_case import sha256_file


def text():
    crop = np.full((80, 220), 30, np.uint8)
    for x in (20, 65, 110, 155):
        cv2.rectangle(crop, (x, 25), (x + 18, 54), 240, -1)
    return crop


def test_training_proposals_never_assign_semantics_or_accept_blank_background():
    crops = [text() for _ in range(3)]
    hashes = [str(i) * 64 for i in range(1, 4)]
    candidates = subject.propose(crops, hashes)
    assert candidates
    for box, _, _, _, matcher, support in candidates:
        assert matcher.threshold == .90 and support == (0, 1, 2)
        x1, y1, x2, y2 = box
        assert matcher.score(np.full((y2 - y1, x2 - x1), 30, np.uint8)) < .90
    assert subject.propose(crops, ["1" * 64] * 3) == []
    assert subject.propose([np.zeros_like(c) for c in crops], hashes) == []


def test_short_caption_proposal_does_not_relax_grouped_ncc_or_training_support():
    crop = np.full((80, 220), 30, np.uint8)
    for x in (20, 90, 160):
        cv2.rectangle(crop, (x, 25), (x + 18, 54), 240, -1)
    assert subject.text_rows(crop) == []
    assert subject.text_rows(crop, minimum_glyphs=3)
    hashes = [str(i) * 64 for i in range(1, 4)]
    candidates = subject.propose([crop] * 3, hashes, minimum_glyphs=3)
    assert candidates
    assert all(candidate[4].threshold == .90 for candidate in candidates)
    assert subject.propose([crop] * 2, hashes[:2], minimum_glyphs=3) == []
    diagnostics = {}
    assert subject.propose([crop] * 2, hashes[:2], minimum_glyphs=3,
                           diagnostics=diagnostics) == []
    assert diagnostics["training_row_proposals"] == 2
    assert diagnostics["returned_candidates"] == 0
    assert diagnostics["rejections"] == {
        "semantic text requires three distinct source-frame hashes": 2}
    crop[:, 155:] = 30
    assert subject.text_rows(crop, minimum_glyphs=3) == []


@pytest.mark.parametrize("value", [True, 0, 2, 5, 3.0])
def test_no_arbitrary_component_floor(value):
    with pytest.raises(ValueError):
        subject.text_rows(text(), minimum_glyphs=value)


def fixture(tmp_path):
    pool = tmp_path / "pool"
    frames = pool / "pool_frames"
    frames.mkdir(parents=True)
    records = []
    for i in range(10):
        image = cv2.cvtColor(text(), cv2.COLOR_GRAY2BGR)
        # Distinct synthetic parents, stable text; not real-image qualification.
        image[0:4, 0:4] = 30 + i * 20
        path = frames / f"frame_{i:02d}.jpg"
        assert cv2.imwrite(str(path), image)
        records.append({"source_frame_pts": float(i + 1), "sha256": sha256_file(path)})
    (pool / "review_selection.json").write_text(json.dumps({
        "pool_records": records, "selected_pool_indices": [0],
        "expected_states": ["poison_should_not_be_consumed"]}), encoding="utf-8")
    (pool / "candidate_report.json").write_text(json.dumps({"source_sha256": "a" * 64}),
                                                encoding="utf-8")
    layout = tmp_path / "layout.json"
    layout.write_text(json.dumps({"schema_version": "1.0", "calibrated": True,
        "roi_coordinate_system": "normalized_0_to_1",
        "reference_resolution": {"width": 220, "height": 80},
        "regions": {role: {"x": 0, "y": 0, "width": 1, "height": 1}
                    for role in ("center_phase_banner", "round_end_banner")}}), encoding="utf-8")
    partition = tmp_path / "partition.json"
    partition.write_text(json.dumps({"kind": "development_holdout_partition_not_gt",
        "source_video_sha256": "a" * 64,
        "development": {"start_sec_inclusive": 0, "end_sec_exclusive": 20},
        "holdout": {"start_sec_inclusive": 20, "end_sec_exclusive": 30}}), encoding="utf-8")
    return pool, layout, partition, records


def test_fixed_groups_and_reserved_source_hashes_are_kept_out_of_training(tmp_path, monkeypatch):
    monkeypatch.setattr(subject, "_check_output_privacy", lambda *_: None)
    pool, layout, partition, records = fixture(tmp_path)
    reserved = {records[1]["sha256"]}
    output = tmp_path / "candidate"
    result = subject.discover(pool, layout, partition, output, reserved)
    training, held = set(result["training_hashes"]), set(result["held_hashes"])
    assert not training & held and min(len(training), len(held)) >= 3
    assert not (reserved | {records[0]["sha256"]}) & (training | held)
    assert result["semantic_labels_assigned"] is False
    assert result["production_adopted"] is False and result["qualification_created"] is False
    for rows in result["roles"].values():
        assert rows and all(row["semantic_label"] is None for row in rows)
    assert not list(output.glob("*.templates.json"))
    assert not list(output.glob("*.global_qualification.json"))
    with pytest.raises(FileExistsError):
        subject.discover(pool, layout, partition, output, reserved)


def test_held_pixels_do_not_change_candidates(tmp_path, monkeypatch):
    monkeypatch.setattr(subject, "_check_output_privacy", lambda *_: None)
    pool, layout, partition, _ = fixture(tmp_path)
    before = subject.discover(pool, layout, partition, tmp_path / "before", set())
    selection_path = pool / "review_selection.json"
    selection = json.loads(selection_path.read_text(encoding="utf-8"))
    # Fixed splitting follows source indices 1,2,... after reserved index0.
    for i in (2, 4, 6, 8):
        path = pool / "pool_frames" / f"frame_{i:02d}.jpg"
        image = np.full((80, 220, 3), 40 + i, np.uint8)
        assert cv2.imwrite(str(path), image)
        selection["pool_records"][i]["sha256"] = sha256_file(path)
    selection_path.write_text(json.dumps(selection), encoding="utf-8")
    after = subject.discover(pool, layout, partition, tmp_path / "after", set())
    for role in before["roles"]:
        keys = ("bounds_in_roi", "asset_hashes", "training_support_indices")
        assert [[r[k] for k in keys] for r in before["roles"][role]] == [
            [r[k] for k in keys] for r in after["roles"][role]]
        assert all(row["held_accept_count"] == 0 for row in after["roles"][role])


def test_training_candidate_audit_never_scores_held_images(tmp_path, monkeypatch):
    monkeypatch.setattr(subject, "_check_output_privacy", lambda *_: None)
    pool, layout, partition, _ = fixture(tmp_path)
    original = subject.propose

    def training_only(*args, **kwargs):
        assert kwargs["candidate_limit"] == 16
        proposals = original(*args, **kwargs)
        return [(*p[:4], SimpleNamespace(score=lambda *_: pytest.fail("held score in audit")),
                 p[5]) for p in proposals]

    monkeypatch.setattr(subject, "propose", training_only)
    output = tmp_path / "audit"
    result = subject.discover(pool, layout, partition, output, set(),
                              training_candidate_audit=True)
    assert result["held_predictions_measured"] is False
    assert result["review_frames"] == []
    assert not list(output.glob("held_*.png"))
    for rows in result["roles"].values():
        assert rows
        assert all(row["held_scores"] is None and row["held_accept_count"] is None
                   and row["semantic_label"] is None for row in rows)


@pytest.mark.parametrize("limit", [0, 3, 5, 100, True])
def test_audit_candidate_output_is_bounded(limit):
    with pytest.raises(ValueError):
        subject.propose([text()] * 3, ["1" * 64, "2" * 64, "3" * 64], candidate_limit=limit)


@pytest.mark.parametrize("fault", ["hash", "holdout"])
def test_changed_images_and_holdout_are_rejected_before_output(tmp_path, monkeypatch, fault):
    monkeypatch.setattr(subject, "_check_output_privacy", lambda *_: None)
    pool, layout, partition, _ = fixture(tmp_path)
    path = pool / "review_selection.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    if fault == "hash":
        raw["pool_records"][0]["sha256"] = "b" * 64
    else:
        raw["pool_records"][0]["source_frame_pts"] = 21
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError):
        subject.discover(pool, layout, partition, tmp_path / "rejected", set())
    assert not (tmp_path / "rejected").exists()
