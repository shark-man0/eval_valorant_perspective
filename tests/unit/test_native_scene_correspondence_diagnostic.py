import json
import sys
from pathlib import Path

import cv2
import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.diagnostics.diagnose_round_lifecycle import sha256_file  # noqa: E402
from scripts.diagnostics.measure_native_scene_correspondence import (  # noqa: E402
    measure_run,
    numeric_consistency_runs,
)
from tests.unit.test_source_correspondence_diagnostic import method, texture  # noqa: E402


def inputs(tmp_path):
    video = tmp_path / "source.mp4"
    video.write_bytes(b"synthetic fixture; not a real video qualification")
    run = tmp_path / "run"
    frames = run / "window-000"
    frames.mkdir(parents=True)
    rows = []
    for index, pts in enumerate((1.0, 1.02), 1):
        path = frames / f"frame_{index:06d}.png"
        assert cv2.imwrite(str(path), texture(10))
        rows.append({"pts_sec": pts, "frame_sha256": sha256_file(path)})
    report = {"source_video_sha256": sha256_file(video), "native_pts_coverage_verified": True,
              "windows": [{"window_sec": [1.0, 1.02], "rows": rows}]}
    (run / "results.json").write_text(json.dumps(report))
    layout = tmp_path / "layout.json"
    layout.write_text(json.dumps({
        "schema_version": "1.0", "roi_coordinate_system": "normalized_0_to_1",
        "calibrated": True, "reference_resolution": {"width": 640, "height": 360},
        "regions": {"phase": {"x": .38, "y": .28, "width": .25, "height": .19}},
    }))
    declared = tmp_path / "method.json"
    declared.write_text(json.dumps({"method": method()}))
    return video, run, layout, declared


def test_native_comparison_uses_identical_feature_population_without_attesting(tmp_path):
    args = inputs(tmp_path)
    result = measure_run(*args, ["phase"])
    pair = result["windows"][0]["pairs"][0]
    assert pair["raw"]["corner_count"] == pair["outside_configured_ui"]["corner_count"]
    assert pair["outside_configured_ui"]["excluded_ui_patch_count"] > 0
    assert pair["outside_configured_ui"]["continuity_attested"] is False
    assert result["qualification_created"] is False
    assert result["production_changed"] is False
    assert result["hud_layout_sha256"] == sha256_file(args[2])


@pytest.mark.parametrize("failure", ["frame", "coverage", "source", "order", "roi", "nan", "bool"])
def test_native_comparison_rejects_invalid_source_contract(tmp_path, failure):
    video, run, layout, declared = inputs(tmp_path)
    report = json.loads((run / "results.json").read_text())
    roles = ["phase"]
    if failure == "frame":
        report["windows"][0]["rows"][0]["frame_sha256"] = "0" * 64
    elif failure == "coverage":
        report["native_pts_coverage_verified"] = False
    elif failure == "source":
        report["source_video_sha256"] = "0" * 64
    elif failure == "order":
        report["windows"][0]["rows"][1]["pts_sec"] = 0.5
    elif failure == "nan":
        report["windows"][0]["rows"][0]["pts_sec"] = float("nan")
    elif failure == "bool":
        report["windows"][0]["rows"][0]["pts_sec"] = True
    else:
        roles = ["unconfigured"]
    (run / "results.json").write_text(json.dumps(report))
    with pytest.raises((ValueError, KeyError)):
        measure_run(video, run, layout, declared, roles)


def timer_row(pts, value, score=.95):
    return {"pts_sec": pts, "timer_sec": value, "timer_confidence": score}


def test_transient_numeric_run_is_not_a_stable_clock_or_continuity_claim():
    runs = numeric_consistency_runs([
        timer_row(10.0, 0), timer_row(10.07, 0),
        timer_row(10.08, 173), timer_row(10.10, 173),
        timer_row(10.12, 98), timer_row(10.20, 98),
    ])
    assert len(runs) == 3
    assert [r["meets_50ms_duration_floor"] for r in runs] == [True, False, True]
    assert all(r["continuity_attested"] is False for r in runs)
    assert all("round_start" not in r and "round_end" not in r for r in runs)


@pytest.mark.parametrize("value,score", [(None, 1.0), (0, .89), (True, 1.0),
                                        (-1, 1.0), (float("nan"), 1.0), (0, True)])
def test_unknown_or_weak_numeric_input_cannot_bridge_a_run(value, score):
    runs = numeric_consistency_runs([
        timer_row(1.0, 5), timer_row(1.02, value, score), timer_row(1.07, 5),
    ])
    assert len(runs) == 2
    assert not any(r["meets_50ms_duration_floor"] for r in runs)


def test_countdown_physics_and_gap_are_not_relaxed():
    rows = [timer_row(1.0, 10), timer_row(1.06, 9), timer_row(1.1, 4),
            timer_row(2.5, 4)]
    runs = numeric_consistency_runs(rows)
    assert [r["observation_count"] for r in runs] == [2, 1, 1]
    assert runs[0]["meets_50ms_duration_floor"] is True
