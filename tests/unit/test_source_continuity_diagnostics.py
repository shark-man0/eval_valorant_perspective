from __future__ import annotations

import cv2
import numpy as np
import pytest

from scripts.diagnostics.diagnose_source_continuity import camera_gray, measure_pair


def textured_frame(seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    source = rng.integers(0, 256, (360, 640, 3), dtype=np.uint8)
    return cv2.GaussianBlur(source, (5, 5), 0)


def test_camera_translation_has_bidirectional_spatial_correspondence() -> None:
    before = textured_frame(21)
    after = cv2.warpAffine(before, np.float32([[1, 0, 3], [0, 1, 2]]), (640, 360))
    result = measure_pair(before, after)
    assert result["patch_ncc_0_90_count"] > 100
    assert all(count > 0 for count in result["patch_ncc_cells"])
    assert result["median_flow_px"] == pytest.approx(np.sqrt(13), abs=0.2)
    assert "confidence" not in result and "segment" not in result


def test_unrelated_scene_has_little_high_ncc_support() -> None:
    result = measure_pair(textured_frame(21), textured_frame(83))
    assert result["patch_ncc_0_90_count"] < 10


def test_flat_scene_does_not_attest_continuity() -> None:
    frame = np.full((360, 640, 3), 80, np.uint8)
    result = measure_pair(frame, frame)
    assert result["corner_count"] == 0
    assert result["median_patch_ncc"] is None
    assert result["measurement_reason"] == "no_corners"


def test_top_hud_differences_are_outside_camera_region() -> None:
    before = textured_frame(42)
    after = before.copy()
    after[:60] = 0
    assert np.array_equal(camera_gray(before), camera_gray(after))


@pytest.mark.parametrize("frame", [
    np.zeros((360, 640), np.uint8),
    np.zeros((360, 640, 4), np.uint8),
    np.zeros((360, 640, 3), np.float32),
    np.zeros((10, 10, 3), np.uint8),
])
def test_invalid_source_image_rejected(frame: np.ndarray) -> None:
    with pytest.raises(ValueError):
        camera_gray(frame)
