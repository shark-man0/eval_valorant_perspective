import json
from copy import deepcopy
from pathlib import Path

import pytest

from scripts.map_learning.evaluate_review import evaluate
from valorant_ai_coach.temporal.evidence import digest, freeze_native_sample
from valorant_ai_coach.temporal.map_recorder_path import VERSION, join_recorder_seconds
from valorant_ai_coach.temporal.map_timeline_report import load_map_timeline
from valorant_ai_coach.temporal.replay import file_sha


def fixture(tmp_path: Path):
    source = "a" * 64
    points = []
    for tick, count in ((3, 1), (4, 2), (5, 3)):
        sample = freeze_native_sample({
            "source_id": "source", "source_sha256": source, "acquisition_id": "run",
            "native_epoch": "run", "native_pts_tick": tick, "native_time_base": "1/5",
            "acquired_frame_sha256": "b" * 64, "native_pixel_sha256": f"{tick:064x}",
            "frame_size_px": [1920, 1080],
        })
        points.append({
            "sample": sample, "position_authority": False, "qualified": False,
            "map_id": "haven", "reference_sha256": "c" * 64, "kind": "selected",
            "map_reference_px": [40 + tick, 90.2], "support_count": count,
            "selection_method": "knowledge_agent_uuid", "track_anchor": "track",
            "zone_candidate": "plant area",
        })
    ids = [p["sample"]["sample_sha256"] for p in points]
    timeline = {
        "source": {"source_sha256": source}, "qualification": "development_only",
        "formal_outputs": 0,
        "native_frames": {
            key: {"sample": point["sample"], "camera": {"value": "SELF"},
                  "life": {"value": "ALIVE"}}
            for key, point in zip(ids, points, strict=True)
        },
        "seconds": [{"timestamp": i, "sample_refs": samples}
                    for i, samples in enumerate([ids[:2], ids[2:], []])],
    }
    timeline_path = tmp_path / "timeline.json"
    timeline_path.write_text(json.dumps(timeline), encoding="utf-8")
    report = {
        "schema": VERSION, "qualified": False, "formal_outputs": 0, "interpolated_samples": 0,
        "segments": [points], "timeline_sha256": file_sha(timeline_path),
    }
    report["second_rows"] = join_recorder_seconds(report, timeline)
    return timeline_path, timeline, report, ids


def test_map_sidecar_preserves_observations_and_unknown_intervals(tmp_path):
    path, timeline, report, ids = fixture(tmp_path)
    original = deepcopy(timeline)
    sidecar = tmp_path / "map.json"
    sidecar.write_text(json.dumps(report), encoding="utf-8")
    loaded = load_map_timeline(sidecar, path, timeline)
    assert loaded["summary"]["named_zone_observed_seconds"] == {"haven/plant area": 2}
    assert loaded["summary"]["unknown_seconds"] == 1
    assert loaded["summary"]["formal_outputs"] == 0
    a, b = loaded["rows"][1]["native_edges_ending_here"][0]
    assert (a["sample"]["sample_sha256"], b["sample"]["sample_sha256"]) == tuple(ids[1:])
    assert loaded["rows"][2]["trajectory_coverage"] == "UNKNOWN"
    assert timeline == original


@pytest.mark.parametrize("change", ["tick", "authority", "digest", "camera", "wrong_second"])
def test_map_sidecar_rejects_unbound_or_formal_claims(tmp_path, change):
    path, timeline, report, ids = fixture(tmp_path)
    if change == "digest":
        report["timeline_sha256"] = "0" * 64
    elif change == "tick":
        report["segments"][0][0]["sample"] = {**report["segments"][0][0]["sample"],
                                               "native_pts_tick": 29}
    elif change == "authority":
        report["segments"][0][0]["position_authority"] = True
    elif change == "camera":
        timeline["native_frames"][ids[0]]["camera"]["value"] = "SPECTATOR"
        path.write_text(json.dumps(timeline), encoding="utf-8")
        report["timeline_sha256"] = file_sha(path)
    else:
        report["second_rows"][0]["timestamp"] = 5
    sidecar = tmp_path / "map.json"
    sidecar.write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(ValueError):
        load_map_timeline(sidecar, path, timeline)


def test_review_separates_role_view_error_and_abstention(tmp_path):
    path, timeline, report, ids = fixture(tmp_path)
    point, wrong, _ = report["segments"][0]
    report["segments"] = [[point, wrong]]
    report["second_rows"] = join_recorder_seconds(report, timeline)
    sidecar = tmp_path / "map.json"
    sidecar.write_text(json.dumps(report), encoding="utf-8")
    review = tmp_path / "review.json"
    review.write_text(json.dumps({
        "schema": "development_map_independent_review_v1", "reviewer": "HUMAN",
        "timeline_sha256": file_sha(path), "cases": [
            {"sample_sha256": ids[0], "view": "SELF_LIVE", "candidate_role": "SELF",
             "candidate_sha256": digest(point), "reference_sha256": point["reference_sha256"],
             "independent_atlas_px": [46, 90.2]},
            {"sample_sha256": ids[1], "view": "REMOTE", "candidate_role": "OTHER",
             "candidate_sha256": digest(wrong)},
            {"sample_sha256": ids[2], "view": "DEAD", "candidate_role": "UNKNOWN"},
        ],
    }), encoding="utf-8")
    result = evaluate(path, sidecar, review)
    assert result["reviewed_selection_error_rate"] == 0.5
    assert result["by_view"]["REMOTE"]["selection_in_excluded_view"] == 1
    assert result["by_view"]["DEAD"]["rejected_excluded_view"] == 1
    assert result["atlas_error_reference_px"]["median"] == 3.0


def test_stratified_sample_and_review_use_exact_reports(tmp_path):
    from scripts.map_learning.sample_review import sample_review

    path, timeline, report, ids = fixture(tmp_path)
    old = tmp_path / "standard.json"
    new = tmp_path / "recovered.json"
    sample = tmp_path / "plan.json"
    review = tmp_path / "review.json"
    keep, recovered, _ = report["segments"][0]
    standard = {**report, "segments": [[keep]]}
    standard["second_rows"] = join_recorder_seconds(standard, timeline)
    old.write_text(json.dumps(standard), encoding="utf-8")
    final = {**report, "segments": [[keep, recovered]], "primary_report_sha256": file_sha(old)}
    final["second_rows"] = join_recorder_seconds(final, timeline)
    new.write_text(json.dumps(final), encoding="utf-8")

    plan = sample_review(path, old, new, per_stratum=1)
    assert plan == sample_review(path, old, new, per_stratum=1)
    assert {row["sample_sha256"]: row["stratum"] for row in plan["cases"]} == {
        ids[0]: "retained_selection", ids[1]: "new_selection", ids[2]: "abstained",
    }
    sample.write_text(json.dumps(plan), encoding="utf-8")
    review.write_text(json.dumps({
        "schema": "development_map_independent_review_v1", "reviewer": "HUMAN",
        "timeline_sha256": file_sha(path), "sample_plan_sha256": file_sha(sample),
        "cases": [
            {"sample_sha256": ids[1], "view": "SELF_LIVE", "candidate_role": "OTHER",
             "candidate_sha256": digest(recovered)},
            {"sample_sha256": ids[2], "view": "UNKNOWN", "candidate_role": "UNKNOWN"},
        ],
    }), encoding="utf-8")
    results = evaluate(path, new, review, sample_plan=sample)
    assert results["review_sample_abstention_rate"] == 0.5
    assert results["by_stratum"]["new_selection"]["wrong_role"] == 1
    assert results["by_stratum"]["retained_selection"]["planned"] == 1
    assert "wrong_role" not in results["by_stratum"]["abstained"]
    with pytest.raises(ValueError, match="matching standard report"):
        sample_review(path, new, old, per_stratum=1)
