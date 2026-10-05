from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
import pytest


def load_script(name: str):
    path = Path(__file__).parents[2] / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def replay_module(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).parents[2] / "scripts"))
    return load_script("fixed_regression_replay")


def fixture_input(tmp_path, module):
    path = tmp_path / "frame.png"
    cv2.imwrite(str(path), np.full((8, 9, 3), 64, dtype=np.uint8))
    frames = [SimpleNamespace(time_sec=0.1, path=path)]
    manifest = module.validate_manifest(
        {
            "schema_version": 1,
            "set_id": "test_v1",
            "setkind": "canonical_uniform",
            "sourceSHA": "a" * 64,
            "stream_index": 0,
            "time_base": {"num": 1, "den": 100},
            "frames": [
                {"pts": 10, "source_frame_index": 6, "pixel_sha256": module.decoded_hash(path)}
            ],
            "provenance": {},
        }
    )
    return manifest, frames


def test_bind_rejects_pixel_and_pts_population_drift(tmp_path, replay_module):
    manifest, frames = fixture_input(tmp_path, replay_module)
    replay_module.bind_frames(manifest, frames)
    with pytest.raises(ValueError, match="population"):
        replay_module.bind_frames(manifest, [])
    frames[0].time_sec = 0.2
    with pytest.raises(ValueError, match="PTS"):
        replay_module.bind_frames(manifest, frames)
    frames[0].time_sec = 0.1
    cv2.imwrite(str(frames[0].path), np.full((8, 9, 3), 65, dtype=np.uint8))
    with pytest.raises(ValueError, match="pixel"):
        replay_module.bind_frames(manifest, frames)


def test_unsealed_and_oracle_input_rejected(tmp_path, replay_module):
    manifest, frames = fixture_input(tmp_path, replay_module)
    del manifest["frames"][0]["pixel_sha256"]
    with pytest.raises(ValueError, match="pixel hashes"):
        replay_module.bind_frames(manifest, frames)
    manifest["expected_state"] = "live_first_person"
    with pytest.raises(ValueError, match="unknown fields"):
        replay_module.bind_frames(manifest, frames)


def test_snapshot_keeps_actual_unavailable_scores_and_reader_ownership(replay_module):
    observation = {
        "primary_state": "unknown",
        "values": {"hp": None, "player_specific_hud_valid": False},
        "quality": {"state_confidence": 0.45, "hud_confidence": 0.45, "roi_confidence": {}},
        "state_flags": [],
        "view_context": {"remote_view_type": "none", "is_player_world_view_trustworthy": False},
    }
    trace = {
        "signals": {
            "spectator_detector_checked": True,
            "spectator_panel_present": False,
            "spectator_panel_absent": True,
        },
        "geometry_calibrated": True,
        "raw_accepted_reader_values": {"hp": 100},
        "identity": {
            "live": False,
            "positive_count": 0,
            "reason": "structure_evidence_insufficient",
        },
    }
    result = replay_module.snapshot(observation, trace, None, None)
    assert result["reader_values"]["hp"] is None
    assert result["accepted_reader_values"]["hp"] == 100
    assert result["structures"]["ability_bar_structure"]["score"] is None
    assert result["structures"]["ability_bar_structure"]["accepted"] is False
    assert result["spectator"]["checked"] is True
    assert result["remote_view_type"] == "none"
    assert result["structures"]["ability_bar_structure"]["score_exposed"] is False
    result["accepted_reader_values"]["hp"] = 0
    assert trace["raw_accepted_reader_values"]["hp"] == 100


def test_logical_hash_is_path_free_and_key_order_stable(replay_module):
    left = replay_module.stable_hash({"b": 1, "a": 2})
    assert left == replay_module.stable_hash({"a": 2, "b": 1})
