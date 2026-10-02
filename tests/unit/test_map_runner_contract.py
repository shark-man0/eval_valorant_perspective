"""Small contracts connecting the dataset runner to production map selection."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

from valorant_ai_coach.maps.calibration import CalibrationResult
from valorant_ai_coach.visual.map_pipeline import MapTimeline


def _map_step(*, eligible=False, attempted=False, calibration=None):
    timeline = MapTimeline({"map_zone": {"manual_map_id": "summit"}})
    observation = {
        "time_sec": 0.0,
        "frame_index": 0,
        "analysis_eligibility": {"player_mechanics": eligible},
        "motion": {},
        "minimap": {
            "self_x_norm": None,
            "self_y_norm": None,
            "track_confidence": 0.0,
            "ally_markers": [],
            "enemy_markers": [],
        },
    }
    proof = {"map_calibration_attempted": attempted}
    timeline.resolve(observation, proof, {}, calibration)
    return proof["zone_resolution"]


def test_map_hud_gate_is_not_reported_as_calibration_or_marker_failure():
    row = _map_step()
    codes = row["diagnostics"]
    assert "map_definition_unresolved" not in codes
    assert "map_calibration_skipped_hud_eligibility" in codes
    assert "map_marker_not_evaluated" in codes
    assert "map_location_not_evaluated" in codes
    assert "map_calibration_failed" not in codes
    assert "map_marker_missing" not in codes
    assert row["zone_id"] is None


def test_map_calibration_failure_and_marker_failure_are_distinct():
    failed = CalibrationResult(
        "calibration_required", 0.0, None, "v1", ("reference_asset_unavailable",)
    )
    codes = _map_step(eligible=True, attempted=True, calibration=failed)["diagnostics"]
    assert "map_calibration_failed" in codes and "reference_asset_unavailable" in codes
    assert "map_marker_not_evaluated" in codes
    ok = CalibrationResult("ok", 0.95, None, "v1", ())
    row = _map_step(eligible=True, attempted=True, calibration=ok)
    assert "map_calibration_accepted" in row["diagnostics"]
    assert "map_marker_missing" in row["diagnostics"]
    assert "map_location_unresolved" in row["diagnostics"]
    assert row["zone_id"] is None


def test_map_timeline_manual_selection_precedes_automatic_signals():
    timeline = MapTimeline(
        {
            "map_zone": {
                "manual_map_id": "summit",
                "trusted_map_label": "some-other-map",
                "map_label_confidence": 1.0,
            }
        }
    )

    assert timeline.definition is not None
    assert timeline.definition.map_id == "summit"
    unresolved_geometry = timeline.resolver.resolve(
        time_sec=0, frame_index=0, controlled_player=False
    )
    assert "map_definition_unresolved" not in unresolved_geometry["diagnostics"]
    assert unresolved_geometry["zone_id"] is None
    assert unresolved_geometry["map_id"] == "summit"


def test_real_video_runner_passes_manual_map_and_build_into_app_settings(tmp_path, monkeypatch):
    runner_path = Path(__file__).parents[1] / "e2e" / "run_real_video.py"
    spec = importlib.util.spec_from_file_location("run_real_video_contract", runner_path)
    assert spec is not None and spec.loader is not None
    run_real_video = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(run_real_video)

    received = {}

    class FakeProcessor:
        analyzer = SimpleNamespace(last_calibration_diagnostics={})

        def process(self, **_kwargs):
            raise RuntimeError("stop after settings capture")

    class FakeVideo:
        def probe(self, _source):
            return None

    def fake_build_services(_store, *, settings):
        received["manual_map_id"] = settings.manual_map_id
        received["map_client_build"] = settings.map_client_build
        return SimpleNamespace(
            video=FakeVideo(),
            pipeline=SimpleNamespace(hud_video_processor=FakeProcessor()),
        )

    monkeypatch.setattr(run_real_video, "build_services", fake_build_services)
    output = tmp_path / "out"
    status = run_real_video.main(
        [
            "--source-video",
            str(tmp_path / "clip.mp4"),
            "--output",
            str(output),
            "--manual-map-id",
            "summit",
            "--map-client-build",
            "13.06.00.5435758",
        ]
    )

    assert status == 2
    assert received == {
        "manual_map_id": "summit",
        "map_client_build": "13.06.00.5435758",
    }
