import hashlib

import cv2
import numpy as np
import pytest

from valorant_ai_coach.visual.development_camera_marker_ui import inspect_camera_marker_ui
from valorant_ai_coach.visual.development_marker_attribution import freeze_native_sample
from valorant_ai_coach.visual.development_marker_features import _digest


def fixture(points):
    frame = np.zeros((96, 128, 3), np.uint8)
    for x, y in points:
        cv2.circle(frame, (x, y), 10, (80, 210, 210), 2)
    sample = freeze_native_sample(
        {
            "source_id": "synthetic",
            "source_sha256": "a" * 64,
            "acquisition_id": "epoch",
            "native_epoch": "epoch",
            "native_pts_tick": 10,
            "native_time_base": "1/60",
            "acquired_frame_sha256": "b" * 64,
            "native_pixel_sha256": hashlib.sha256(frame.tobytes()).hexdigest(),
        },
        frame_size_px=(128, 96),
    )
    pool = {
        "sample": sample,
        "ownership": "UNKNOWN",
        "formal_outputs": 0,
        "parent_count": len(points),
        "candidates": [{"center_frame_px": list(p)} for p in points],
    }
    pool["pool_sha256"] = _digest(pool)
    return frame, sample, pool


def test_rim_measurement_is_not_recorder_or_player_proof():
    result = inspect_camera_marker_ui(*fixture([(32, 32)]))
    assert result["selected_index"] == 0
    assert result["ownership"] == "UNKNOWN" and result["formal_outputs"] == 0
    assert result["semantic_role"] == "current_camera_or_other_highlight_not_recorder_proof"


def test_two_same_rims_are_ambiguous():
    result = inspect_camera_marker_ui(*fixture([(32, 32), (80, 32)]))
    assert result["selected_index"] is None and result["status"] == "UNKNOWN"


def test_empty_windows_are_unknown():
    assert inspect_camera_marker_ui(*fixture([]))["selected_index"] is None


def test_changed_native_pixels_are_rejected():
    frame, sample, pool = fixture([(32, 32)])
    frame[0, 0] = 255
    with pytest.raises(ValueError, match="pixel identity"):
        inspect_camera_marker_ui(frame, sample, pool)


def test_parent_count_must_match_available_windows():
    frame, sample, pool = fixture([(32, 32)])
    pool["parent_count"] = 2
    pool.pop("pool_sha256")
    pool["pool_sha256"] = _digest(pool)
    with pytest.raises(ValueError, match="parent"):
        inspect_camera_marker_ui(frame, sample, pool)
