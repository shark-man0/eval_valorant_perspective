import hashlib
import json
from argparse import Namespace

import cv2
import numpy as np
import pytest

from scripts.diagnostics.scene_correspondence import (
    SCALED_BACKGROUND_BOXES,
    measure_background_pair,
    run,
)


def source(seed):
    small = np.random.default_rng(seed).integers(0, 256, (360, 640, 3), dtype=np.uint8)
    return cv2.resize(small, (1920, 1080), interpolation=cv2.INTER_NEAREST)


def test_excluded_ui_cannot_change_any_correspondence_metric():
    before, after = source(1), source(2)
    expected = measure_background_pair(before, after)
    mask = np.zeros((1080, 1920), dtype=bool)
    for x1, y1, x2, y2 in SCALED_BACKGROUND_BOXES:
        mask[y1 * 3 : y2 * 3, x1 * 3 : x2 * 3] = True
    before[~mask] = 0
    after[~mask] = 255
    assert measure_background_pair(before, after) == expected


def test_unrelated_scenes_and_identical_images_are_distinguished_without_authorizing_events():
    frame = source(3)
    same = measure_background_pair(frame, frame)
    different = measure_background_pair(frame, source(4))
    assert all(region["ncc"] > 0.99 for region in same["regions"])
    assert all(abs(region["ncc"]) < 0.1 for region in different["regions"])
    assert same["lk_patch_ncc_0_90_tracks"] > 0
    assert different["lk_patch_ncc_0_90_tracks"] == 0
    assert "continuity_verified" not in same


@pytest.mark.parametrize(
    "image",
    [None, np.zeros((10, 10, 3), dtype=np.uint8), np.zeros((1080, 1920, 3), dtype=np.float32)],
)
def test_unsupported_images_fail_closed(image):
    with pytest.raises(ValueError, match="source image required"):
        measure_background_pair(image, image)


@pytest.mark.parametrize("ticks", [[100, 612], [100, 100], [612, 100]])
def test_missing_duplicate_or_backward_native_pts_rejected_before_image_loading(tmp_path, ticks):
    video = tmp_path / "video"
    video.write_bytes(b"bound source")
    report = tmp_path / "report.json"
    report.write_text(
        json.dumps(
            {
                "source_video_sha256": hashlib.sha256(video.read_bytes()).hexdigest(),
                "native_pts_coverage_verified": True,
                "windows": [
                    {"rows": [{"source_pts_ticks": tick, "time_base": "1/15360"} for tick in ticks]}
                ],
            }
        )
    )
    with pytest.raises(ValueError, match="every native frame"):
        run(Namespace(source_report=report, video=video, window_index=0, frames_root=tmp_path))


def test_motion_compensated_similarity_recovers_known_camera_translation():
    before = source(9)
    after = cv2.warpAffine(before, np.float32([[1, 0, 3], [0, 1, 3]]), (1920, 1080))
    metrics = measure_background_pair(before, after)
    assert all(abs(region["ncc"]) < 0.1 for region in metrics["regions"])
    assert all(
        region["ncc"] is not None and region["ncc"] > 0.99
        for region in metrics["motion_compensated_regions"]
    )
    assert "continuity_verified" not in metrics


def test_optional_track_export_keeps_all_existing_measurements_unchanged():
    before = source(11)
    after = cv2.warpAffine(before, np.float32([[1, 0, 3], [0, 1, 3]]), (1920, 1080))
    original = measure_background_pair(before, after)
    tracks = []
    exported = measure_background_pair(before, after, track_sink=tracks)
    assert exported == original
    assert len(tracks) > 0
