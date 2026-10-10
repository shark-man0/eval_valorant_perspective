import hashlib
import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from scripts.diagnostics.scene_correspondence import sha256
from valorant_ai_coach.hud.scene_references import WorldLandmarkBootstrap

BOXES = ((20, 50, 100, 115), (20, 160, 100, 250), (450, 150, 550, 250))


def profile(tmp_path: Path):
    image = np.random.default_rng(62).integers(0, 256, (360, 640), dtype=np.uint8)
    asset = tmp_path / "world.png"
    cv2.imwrite(str(asset), cv2.resize(image, (1920, 1080), interpolation=cv2.INTER_NEAREST))
    native = cv2.imread(str(asset))
    data = {
        "schema_version": 1,
        "scope": "diagnostic_landmarks_only",
        "references": [
            {
                "id": "wall",
                "asset": "world.png",
                "asset_sha256": sha256(asset),
                "source_pixel_sha256": hashlib.sha256(native.tobytes()).hexdigest(),
                "world_boxes_640x360": BOXES,
                "review_provenance": "synthetic reviewed world",
            }
        ],
    }
    path = tmp_path / "profile.json"
    path.write_text(json.dumps(data))
    return image, path, data


def test_image_bootstrap_outputs_landmarks_without_region_or_temporal_authority(tmp_path):
    image, path, _ = profile(tmp_path)
    result = WorldLandmarkBootstrap(path).recognize(image)
    assert result["single_frame_landmark_quorum"]
    assert not result["whole_roi_world_attested"]
    assert not result["runtime_proof_authorized"]
    assert not result["qualification_created"]
    assert all(
        p["patch_ncc"] >= 0.90 and p["fb_error_px"] <= 1
        for p in result["references"][0]["linked_landmarks"]
    )


def test_wrong_image_does_not_inherit_reference_world_labels(tmp_path):
    image, path, _ = profile(tmp_path)
    unrelated = np.random.default_rng(71).integers(0, 256, image.shape, dtype=np.uint8)
    assert not WorldLandmarkBootstrap(path).recognize(unrelated)["single_frame_landmark_quorum"]


def test_timer_and_phase_changes_cannot_affect_landmark_output(tmp_path):
    image, path, _ = profile(tmp_path)
    bootstrap = WorldLandmarkBootstrap(path)
    original = bootstrap.recognize(image)
    altered = image.copy()
    altered[:28] = 0
    altered[28:120, 224:416] = 255
    assert bootstrap.recognize(altered) == original


@pytest.mark.parametrize(
    "corruption", ["bytes", "pixels", "escape", "qualification", "timestamp", "ui"]
)
def test_profile_rejects_unbound_assets_runtime_metadata_or_protected_pixels(tmp_path, corruption):
    _, path, data = profile(tmp_path)
    entry = data["references"][0]
    if corruption == "bytes":
        entry["asset_sha256"] = "0" * 64
    elif corruption == "pixels":
        entry["source_pixel_sha256"] = "0" * 64
    elif corruption == "escape":
        entry["asset"] = "../world.png"
    elif corruption == "qualification":
        data["qualification"] = {"accepted": True}
    elif corruption == "timestamp":
        entry["expected_start_timestamp"] = 4.1
    elif corruption == "ui":
        entry["world_boxes_640x360"] = ((0, 0, 100, 100),) + BOXES[1:]
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        WorldLandmarkBootstrap(path)
