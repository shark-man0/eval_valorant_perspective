"""Development Map candidates reach the evaluation report without touching any score."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from valorant_ai_coach.application.timeline_evaluation import TimelineEvaluationError, main
from valorant_ai_coach.facts.map_position_promotion import MapGeometry, position_candidates
from valorant_ai_coach.temporal.evidence import freeze_native_sample
from valorant_ai_coach.temporal.map_recorder_path import VERSION, join_recorder_seconds
from valorant_ai_coach.temporal.replay import file_sha

SOURCE = "a" * 64


def _bundle_with_map(tmp_path: Path) -> tuple[Path, Path, dict]:
    numbers = [None] + [1] * 10 + [None]
    seconds, frames, points = [], {}, []
    for second, number in enumerate(numbers):
        sample = freeze_native_sample({
            "source_id": "synthetic", "source_sha256": SOURCE, "acquisition_id": "run",
            "native_epoch": "run", "native_pts_tick": second, "native_time_base": "1",
            "acquired_frame_sha256": "b" * 64, "native_pixel_sha256": f"{second:064x}",
            "frame_size_px": [1920, 1080],
        })
        key = sample["sample_sha256"]
        live = number is not None
        frames[key] = {"sample": sample, "camera": {"value": "SELF" if live else "UNKNOWN"},
                       "life": {"value": "ALIVE" if live else "UNKNOWN"}}
        state = {"value": "SELF" if live else "UNKNOWN", "status": "OBSERVED"}
        life = {"value": "ALIVE" if live else "UNKNOWN", "status": "OBSERVED"}
        seconds.append({
            "timestamp": second, "sample_refs": [key],
            "round_number": {"value": number, "status": "CANDIDATE" if live else "UNKNOWN"},
            "round_state": {"value": "ACTIVE"}, "life_state": life, "camera_state": state,
            "event_candidates": [],
        })
        if live:
            x = 100.0 if second < 6 else 100.0 + 80 * (second - 5)
            points.append({
                "sample": sample, "position_authority": False, "qualified": False,
                "map_id": "map-a", "reference_sha256": "c" * 64, "kind": "selected",
                "map_reference_px": [x, 100.0], "support_count": 2,
                "selection_method": "self_ring",
                "methods_agreeing": ["self_ring", "map_library_rim"],
            })
    bundle = {
        "version": "development_application_timeline_v1", "qualification": "development_only",
        "formal_outputs": 0,
        "source": {"source_id": "synthetic", "source_sha256": SOURCE,
                   "physical_match_id": "physical"},
        "recording": {"end_timestamp": float(len(numbers))},
        "seconds": seconds, "events": {}, "native_frames": frames,
    }
    timeline_path = tmp_path / "timeline_PRIVATE.json"
    timeline_path.write_text(json.dumps(bundle), encoding="utf-8")
    report = {
        "schema": VERSION, "qualified": False, "formal_outputs": 0, "interpolated_samples": 0,
        "segments": [points], "timeline_sha256": file_sha(timeline_path), "canonical_pass": {},
    }
    report["second_rows"] = join_recorder_seconds(report, bundle)
    report_path = tmp_path / "map_canonical_PRIVATE.json"
    report_path.write_text(json.dumps(report), encoding="utf-8")
    candidates = position_candidates(
        report, bundle, [(1, 1, 10)], MapGeometry("map-a", "test", 10.0),
        calibration={"corroborated": 0.86})
    candidates["provenance"] = {
        "report_sha256": hashlib.sha256(report_path.read_bytes()).hexdigest()}
    return timeline_path, report_path, candidates


def test_candidates_are_reported_per_round_and_never_scored(tmp_path: Path) -> None:
    timeline_path, report_path, candidates = _bundle_with_map(tmp_path)
    candidates_path = tmp_path / "candidates.json"
    candidates_path.write_text(json.dumps(candidates), encoding="utf-8")
    out = tmp_path / "out"
    assert main(["evaluate", "--timeline", str(timeline_path), "--output", str(out),
                 "--match-id", "DEV-map", "--no-promotion",
                 "--development-map-report", str(report_path),
                 "--development-map-candidates", str(candidates_path)]) == 0
    report = json.loads((out / "match_evaluation_PRIVATE.json").read_text(encoding="utf-8"))
    block = report["development_map"]["candidates"]
    assert block["used_by_rules"] is False and block["formal_outputs"] == 0
    assert block["continuous_path_inferred"] is False
    (round_row,) = [r for r in block["rounds"] if r["eligible_position_seconds"]]
    assert round_row["eligible_position_seconds"] == 10
    assert round_row["events"] == {"position_change": 1, "position_hold": 1}
    assert report["formal_outputs"] == 0
    markdown = (out / "match_evaluation_PRIVATE.md").read_text(encoding="utf-8")
    assert "開発用Map候補（評価には使っていません）" in markdown


@pytest.mark.parametrize("tamper", ["report", "timeline", "schema"])
def test_candidates_from_another_report_or_timeline_are_refused(tmp_path: Path,
                                                                tamper: str) -> None:
    timeline_path, report_path, candidates = _bundle_with_map(tmp_path)
    if tamper == "report":
        candidates["provenance"]["report_sha256"] = "0" * 64
    elif tamper == "timeline":
        candidates["timeline_sha256"] = "0" * 64
    else:
        candidates["schema"] = "development_map_position_candidates_v1"
    candidates_path = tmp_path / "candidates.json"
    candidates_path.write_text(json.dumps(candidates), encoding="utf-8")
    with pytest.raises(TimelineEvaluationError):
        main(["evaluate", "--timeline", str(timeline_path), "--output", str(tmp_path / "o"),
              "--match-id", "DEV-map", "--no-promotion",
              "--development-map-report", str(report_path),
              "--development-map-candidates", str(candidates_path)])


def test_candidates_need_the_map_report_they_came_from(tmp_path: Path) -> None:
    timeline_path, _, candidates = _bundle_with_map(tmp_path)
    candidates_path = tmp_path / "candidates.json"
    candidates_path.write_text(json.dumps(candidates), encoding="utf-8")
    with pytest.raises(TimelineEvaluationError):
        main(["evaluate", "--timeline", str(timeline_path), "--output", str(tmp_path / "o"),
              "--match-id", "DEV-map", "--no-promotion",
              "--development-map-candidates", str(candidates_path)])
