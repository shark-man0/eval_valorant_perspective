import json
from copy import deepcopy
from pathlib import Path

import pytest

from scripts.map_learning.evaluate_review import evaluate
from valorant_ai_coach.temporal.evidence import digest, freeze_native_sample
from valorant_ai_coach.temporal.map_recorder_path import VERSION, join_recorder_seconds
from valorant_ai_coach.temporal.map_timeline_report import load_map_timeline, summarize_map_seconds
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

    candidate = tmp_path / "all_abstained.json"
    report["segments"] = []
    report["second_rows"] = join_recorder_seconds(report, timeline)
    candidate.write_text(json.dumps(report), encoding="utf-8")
    changes = evaluate(path, sidecar, review, candidate_report=candidate)["selection_changes"]
    assert changes == {"selection_removed": 2, "removed_other_role": 1, "removed_self_role": 1,
                       "removed_in_excluded_view": 1, "both_abstained": 1}

    labels = json.loads(review.read_text(encoding="utf-8"))
    labels["cases"][1]["candidate_sha256"] = "a" * 64
    review.write_text(json.dumps(labels), encoding="utf-8")
    changes = evaluate(path, sidecar, review, candidate_report=candidate)["selection_changes"]
    assert "removed_other_role" not in changes
    assert changes["removed_unverified_role"] == 1
    assert changes["removed_in_excluded_view"] == 1


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
    with pytest.raises(ValueError, match="1 of 3 missing"):
        evaluate(path, new, review, sample_plan=sample)
    results = evaluate(path, new, review, sample_plan=sample, allow_partial=True)
    assert results["review_completion"] == {
        "planned": 3, "reviewed": 2, "missing": 1, "complete": False,
    }
    assert results["review_sample_abstention_rate"] == 0.5
    assert results["by_stratum"]["new_selection"]["wrong_role"] == 1
    assert results["by_stratum"]["retained_selection"]["planned"] == 1
    assert results["by_stratum"]["retained_selection"]["missing"] == 1
    assert "wrong_role" not in results["by_stratum"]["abstained"]
    with pytest.raises(ValueError, match="matching standard report"):
        sample_review(path, new, old, per_stratum=1)

    labels = json.loads(review.read_text(encoding="utf-8"))
    labels["cases"].append({
        "sample_sha256": ids[0], "view": "UNKNOWN", "candidate_role": "UNKNOWN",
        "candidate_sha256": digest(keep),
    })
    review.write_text(json.dumps(labels), encoding="utf-8")
    complete = evaluate(path, new, review, sample_plan=sample)
    assert complete["review_completion"]["complete"] is True
    assert complete["by_stratum"]["retained_selection"]["unreviewed_selection"] == 1

    labels["cases"].append(labels["cases"][0])
    review.write_text(json.dumps(labels), encoding="utf-8")
    with pytest.raises(ValueError, match="Unique review"):
        evaluate(path, new, review, sample_plan=sample)
    labels["cases"].pop()

    labels["cases"][2]["candidate_sha256"] = "a" * 64
    review.write_text(json.dumps(labels), encoding="utf-8")
    with pytest.raises(ValueError, match="candidate does not match"):
        evaluate(path, new, review, sample_plan=sample, allow_partial=True)

    labels["cases"][2]["candidate_sha256"] = digest(keep)
    labels["cases"][1]["candidate_role"] = "SELF"
    review.write_text(json.dumps(labels), encoding="utf-8")
    with pytest.raises(ValueError, match="candidate does not match"):
        evaluate(path, new, review, sample_plan=sample)


def test_review_can_sample_excluded_view_kinds_separately(tmp_path):
    from scripts.map_learning.sample_review import sample_review

    path, timeline, report, ids = fixture(tmp_path)
    timeline["native_frames"][ids[0]]["camera"]["value"] = "SPECTATOR"
    timeline["native_frames"][ids[1]]["camera"]["value"] = "REMOTE"
    timeline["native_frames"][ids[2]]["life"]["value"] = "DEAD"
    path.write_text(json.dumps(timeline), encoding="utf-8")
    old, new = tmp_path / "standard.json", tmp_path / "recovered.json"
    report["segments"] = []
    report["timeline_sha256"] = file_sha(path)
    report["second_rows"] = join_recorder_seconds(report, timeline)
    old.write_text(json.dumps(report), encoding="utf-8")
    report["primary_report_sha256"] = file_sha(old)
    new.write_text(json.dumps(report), encoding="utf-8")

    plan = sample_review(path, old, new, per_stratum=1, split_view_controls=True)
    assert {row["sample_sha256"]: row["stratum"] for row in plan["cases"]} == {
        ids[0]: "spectator_view_control", ids[1]: "remote_view_control",
        ids[2]: "dead_or_downed_control",
    }



def test_map_summary_keeps_witnesses_and_conflicting_zones_out_of_unique_selected_zones():
    def point(kind, zone, ref="a"):
        return {"map_id": "map", "reference_sha256": ref * 64,
                "kind": kind, "zone_candidate": zone}

    observations = [
        [point("measured_witness", "A")],
        [point("selected", "A"), point("selected", None)],
        [point("selected", "A"), point("selected", "B")],
        [point("selected", "A", "a"), point("selected", "A", "b")],
        [point("selected", "A"), point("measured_witness", "B")],
        [],
    ]
    report = summarize_map_seconds([
        {"recorder_map_observations": points, "trajectory_coverage": "UNKNOWN"}
        for points in observations
    ])
    assert report["seconds_with_position"] == 5
    assert report["seconds_with_recorder_selection"] == 4
    assert report["seconds_with_support_only"] == 1
    assert report["seconds_with_conflicting_selected_zones"] == 2
    assert report["unique_selected_zone_observed_seconds"] == {"map/A": 1}
    assert report["named_zone_observed_seconds"] == {"map/A": 5, "map/B": 2}
    assert report["formal_outputs"] == 0


def test_map_regression_gate_flags_losses_even_when_aggregate_matches():
    from scripts.map_learning.compare_runs import regression_failures

    counts = {
        "seconds_with_lost_observations": 0, "native_selections_lost": 0,
        "native_edges_lost": 0, "changed_map_references": 0, "lost_named_zone_candidates": 0,
        "gained_named_zone_candidates": 2, "changed_positions_on_same_reference": 0,
        "lost_operable_seconds": [], "gained_operable_seconds": [],
    }
    assert regression_failures({"outputs": {"standard": counts}}) == {}
    assert regression_failures({"outputs": {"standard": {**counts, "native_edges_lost": 1}}}) == {
        "standard": ["native_edges_lost"],
    }


def test_map_regression_compares_equal_count_operable_sets_and_retained_coordinates(tmp_path):
    from scripts.map_learning.compare_runs import compare, regression_failures

    _, timeline, report, ids = fixture(tmp_path)

    def run(name, operable_refs, position_change):
        root = tmp_path / name
        (root / "timeline").mkdir(parents=True)

        def save(filename, value):
            path = root / filename
            path.write_text(json.dumps(value), encoding="utf-8")
            return file_sha(path)

        timeline_name = "timeline/timeline_PRIVATE.json"
        hashes = {timeline_name: save(timeline_name, timeline)}
        map_report = deepcopy(report)
        map_report["segments"][0][0]["map_reference_px"][0] += position_change
        map_report["timeline_sha256"] = hashes[timeline_name]
        map_report["second_rows"] = join_recorder_seconds(map_report, timeline)
        reference_sha = save("map_reference_PRIVATE.json", {
            **map_report, "comparison_evidence": {"operable_sample_refs": operable_refs},
        })
        map_report.update(reference_report_sha256=reference_sha, operable_coverage={
            "operable_seconds_with_current_evidence": 1,
        })
        for mode in ("standard", "recovered"):
            filename = f"map_{mode}_PRIVATE.json"
            hashes[filename] = save(filename, map_report)
        save("run_PRIVATE.json", {
            "schema": "development_map_recording_run_v1", "formal_map_outputs": 0,
            "source_sha256": timeline["source"]["source_sha256"], "output_sha256s": hashes,
        })
        return root / "run_PRIVATE.json"

    baseline = run("baseline", ids[:2], 0)
    candidate = run("candidate", ids[2:], 2.5)
    assert regression_failures(compare(baseline, baseline)) == {}
    result = compare(baseline, candidate)
    for mode in ("standard", "recovered"):
        counts = result["outputs"][mode]
        assert counts["before"] == counts["after"]
        assert counts["lost_operable_seconds"] == [0]
        assert counts["gained_operable_seconds"] == [1]
        assert counts["changed_positions_on_same_reference"] == 1
        assert counts["max_position_change_reference_px"] == 2.5
    assert regression_failures(result) == {
        mode: ["changed_positions_on_same_reference", "operable_seconds_changed"]
        for mode in ("standard", "recovered")
    }


def test_merge_recovery_fills_empty_seconds_and_preserves_incumbent(tmp_path, monkeypatch):
    scripts = Path(__file__).resolve().parents[2] / "scripts/map_learning"
    monkeypatch.syspath_prepend(str(scripts))
    from merge_recovery_candidates import merge_recovery_candidates

    timeline_path, timeline, report, ids = fixture(tmp_path)
    reference = tmp_path / "reference.json"
    reference.write_text(json.dumps({
        **report, "comparison_evidence": {"operable_sample_refs": ids},
    }), encoding="utf-8")
    report.update({
        "reference_report_sha256": file_sha(reference), "primary_report_sha256": "b" * 64,
        "frame_manifest_sha256": "c" * 64, "zone_catalog_sha256": "d" * 64,
        "operable_coverage": {"operable_seconds_with_current_evidence": 2},
    })
    first, linked, fill = report["segments"][0]
    incumbent = {**report, "segments": [[first, linked]]}
    changed = {**first, "map_reference_px": [3, 5]}
    fill = {**fill, "fit_residual_p95_reference_px": 1.0}
    candidate = {**report, "segments": [[changed, linked, fill]]}

    def save(name, report):
        report["second_rows"] = join_recorder_seconds(report, timeline)
        path = tmp_path / name
        path.write_text(json.dumps(report), encoding="utf-8")
        return path

    old = save("incumbent.json", incumbent)
    new = save("candidate.json", candidate)
    merged = merge_recovery_candidates(timeline_path, old, new, reference)
    assert merged["segments"] == [[first, linked], [fill]]
    assert merged["operable_coverage"]["operable_seconds_with_position"] == 2
    assert merged["operable_coverage"]["operable_seconds_with_native_edge"] == 1
    assert merged["formal_outputs"] == 0

    candidate["zone_catalog_sha256"] = "e" * 64
    with pytest.raises(ValueError, match="zone_catalog_sha256"):
        merge_recovery_candidates(timeline_path, old, save("candidate.json", candidate), reference)
