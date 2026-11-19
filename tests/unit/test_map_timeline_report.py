import json
from copy import deepcopy
from pathlib import Path

import pytest

from valorant_ai_coach.temporal.evidence import freeze_native_sample
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
