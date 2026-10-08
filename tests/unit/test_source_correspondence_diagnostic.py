import json
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.diagnostics.measure_source_correspondence import load_method, measure  # noqa: E402


def method():
    return {"version": "camera_lk_fb_ncc_diagnostic_v1", "thumbnail_wh": [640, 360],
            "camera_bounds_norm": [.2, .2, .9, .8],
            "corners": {"maxCorners": 300, "qualityLevel": .01, "minDistance": 8},
            "lk": {"winSize": [21, 21], "maxLevel": 3}, "forward_backward_error_px": 1.0,
            "patch_width": 11, "descriptive_patch_ncc": .90, "spatial_grid": [3, 3]}


def texture(seed):
    image = np.random.default_rng(seed).integers(0, 255, (360, 640, 3), dtype=np.uint8)
    return cv2.GaussianBlur(image, (3, 3), 0)


def test_identical_source_is_reported_but_never_attested():
    image = texture(10)
    report = measure(image, image.copy(), method())
    assert report["source_pixels_identical"] is True
    assert report["camera_pixels_identical"] is True
    assert report["descriptive_ncc_match_count"] > 0
    assert report["continuity_attested"] is False


def test_correspondence_measurements_do_not_create_state_or_cut_decisions():
    image = texture(10)
    moved = cv2.warpAffine(image, np.float32([[1, 0, 2], [0, 1, 1]]), (640, 360))
    matched = measure(image, moved, method())
    unrelated = measure(image, texture(12), method())
    assert matched["descriptive_ncc_match_count"] > unrelated["descriptive_ncc_match_count"]
    assert matched["source_pixels_identical"] is False
    assert matched["continuity_attested"] is False
    assert unrelated["continuity_attested"] is False
    assert "cut" not in unrelated and "confidence" not in matched
    assert sum(matched["grid_match_counts"]) == matched["descriptive_ncc_match_count"]


def test_low_texture_has_no_correspondence_witness():
    blank = np.full((360, 640, 3), 100, np.uint8)
    report = measure(blank, blank, method())
    assert report["corner_count"] == 0
    assert report["patch_ncc"]["median"] is None
    assert report["continuity_attested"] is False


def test_invalid_source_and_changed_method_rejected(tmp_path):
    image = texture(10)
    with pytest.raises(ValueError):
        measure(image, image[:10], method())
    path = tmp_path / "method.json"
    value = method()
    path.write_text(json.dumps({"method": value}))
    assert load_method(path) == value
    value["descriptive_patch_ncc"] = .8
    path.write_text(json.dumps({"method": value}))
    with pytest.raises(ValueError):
        load_method(path)


def test_static_ui_cannot_supply_scene_witnesses():
    image = np.full((360, 640, 3), 70, np.uint8)
    ui = texture(91)[100:170, 240:400]
    image[100:170, 240:400] = ui
    raw = measure(image, image.copy(), method())
    excluded = measure(image, image.copy(), method(),
                       excluded_bounds_norm=[(240 / 640, 100 / 360, 400 / 640, 170 / 360)])
    assert raw["descriptive_ncc_match_count"] > 0
    assert excluded["corner_count"] == raw["corner_count"]
    assert excluded["excluded_ui_patch_count"] > 0
    assert excluded["descriptive_ncc_match_count"] == 0
    assert excluded["continuity_attested"] is False


def test_patch_footprint_outside_ui_keeps_scene_support():
    image = texture(10)
    raw = measure(image, image.copy(), method())
    excluded = measure(image, image.copy(), method(),
                       excluded_bounds_norm=[(.38, .28, .63, .47)])
    assert excluded["corner_count"] == raw["corner_count"]
    assert 0 < excluded["descriptive_ncc_match_count"] < raw["descriptive_ncc_match_count"]
    assert excluded["excluded_ui_patch_count"] > 0
    assert sum(excluded["grid_match_counts"]) == excluded["descriptive_ncc_match_count"]
    assert excluded["continuity_attested"] is False


@pytest.mark.parametrize("initial_x,moved_x", [(238, 238), (230, 239), (239, 230)])
def test_patch_touching_ui_is_rejected_at_either_endpoint(monkeypatch, initial_x, moved_x):
    initial = np.float32([[[initial_x, 130]]])
    moved = np.float32([[[moved_x, 130]]])
    monkeypatch.setattr(cv2, "goodFeaturesToTrack", lambda *args, **kwargs: initial)
    calls = iter((moved, initial))
    monkeypatch.setattr(cv2, "calcOpticalFlowPyrLK", lambda *args, **kwargs: (
        next(calls), np.ones((1, 1), np.uint8), np.zeros((1, 1), np.float32),
    ))
    image = texture(10)
    result = measure(image, image, method(),
                     excluded_bounds_norm=[(240 / 640, 100 / 360, 400 / 640, 170 / 360)])
    assert result["forward_backward_count"] == 1
    assert result["excluded_ui_patch_count"] == 1
    assert result["descriptive_ncc_match_count"] == 0


@pytest.mark.parametrize("bounds", [(0, 0, 1), (0, 0, 2, 1),
                                     (0, 0, float("nan"), 1), (False, 0, 1, 1)])
def test_invalid_ui_exclusion_is_not_silently_ignored(bounds):
    image = texture(10)
    with pytest.raises(ValueError, match="exclusion rectangles"):
        measure(image, image.copy(), method(), excluded_bounds_norm=[bounds])
