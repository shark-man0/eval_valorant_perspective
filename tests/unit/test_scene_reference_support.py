import cv2
import numpy as np
import pytest

from scripts.diagnostics.probe_scene_reference_bank import common_reference_support
from scripts.diagnostics.scene_reference_support import measure_reference_support

BOXES = ((20, 30, 120, 130), (150, 30, 250, 130), (20, 150, 120, 250))


def scene():
    return cv2.GaussianBlur(
        np.random.default_rng(18).integers(0, 256, (280, 300), dtype=np.uint8), (3, 3), 0
    )


def translated(source):
    target = source.copy()
    for x1, y1, x2, y2 in BOXES:
        target[y1:y2, x1:x2] = cv2.warpAffine(
            source[y1:y2, x1:x2], np.float32([[1, 0, 2], [0, 1, 1]]), (x2 - x1, y2 - y1)
        )
    return target


@pytest.mark.parametrize("scope", ["global", "region"])
def test_reviewed_reference_structure_matches_translated_view(scope):
    source = scene()
    result = measure_reference_support(source, translated(source), BOXES, model_scope=scope)
    assert all(r["ncc"] > 0.99 and r["reference_supported_descriptive"] for r in result["regions"])
    assert not result["runtime_proof_authorized"]


@pytest.mark.parametrize("scope", ["global", "region"])
def test_excluded_pixels_cannot_affect_reference_eligibility(scope):
    source = scene()
    target = translated(source)
    original = measure_reference_support(source, target, BOXES, model_scope=scope)
    excluded = np.ones(source.shape, bool)
    for x1, y1, x2, y2 in BOXES:
        excluded[y1:y2, x1:x2] = False
    source[excluded] = 0
    target[excluded] = 255
    assert measure_reference_support(source, target, BOXES, model_scope=scope) == original


def test_foreground_replacement_cannot_reuse_other_regions_match():
    source = scene()
    target = translated(source)
    x1, y1, x2, y2 = BOXES[1]
    target[y1:y2, x1:x2] = np.random.default_rng(21).integers(
        0, 256, (y2 - y1, x2 - x1), dtype=np.uint8
    )
    result = measure_reference_support(source, target, BOXES, model_scope="region")
    assert not result["regions"][1]["reference_supported_descriptive"]
    assert result["regions"][0]["reference_supported_descriptive"]
    assert result["regions"][2]["reference_supported_descriptive"]


def test_constant_regions_remain_unknown_and_duplicate_match_is_not_continuity():
    constant = np.full((280, 300), 60, np.uint8)
    result = measure_reference_support(constant, constant, BOXES)
    assert all(r["ncc"] is None for r in result["regions"])
    source = scene()
    result = measure_reference_support(source, source, BOXES)
    assert all(r["reference_supported_descriptive"] for r in result["regions"])
    assert not result["runtime_proof_authorized"]


@pytest.mark.parametrize(
    "boxes", [(), ((0, 0, 10, 10),), ((0, 0, 350, 350),), ((True, 0, 50, 50),)]
)
def test_invalid_reference_domain_is_rejected(boxes):
    source = scene()
    with pytest.raises(ValueError):
        measure_reference_support(source, source, boxes)


def test_adjacent_frames_need_three_same_reference_regions_with_spatial_support():
    def measured(supported):
        return {
            "regions": [
                {"region": i, "reference_supported_descriptive": i in supported} for i in range(5)
            ]
        }

    before = measured({0, 1, 4})
    assert common_reference_support(before, before)["distributed_descriptive_support"]
    # Both frames individually have three regions; only two are shared.
    assert not common_reference_support(before, measured({0, 2, 4}))[
        "distributed_descriptive_support"
    ]
    same_row = measured({1, 2, 4})
    assert not common_reference_support(same_row, same_row)["distributed_descriptive_support"]


def test_reference_feature_export_preserves_all_original_measurements():
    source = scene()
    target = translated(source)
    original = measure_reference_support(source, target, BOXES)
    tracks = []
    assert measure_reference_support(source, target, BOXES, track_sink=tracks) == original
    assert len(tracks) == original["accepted_reference_tracks"]
    assert all(t["patch_ncc"] >= 0.90 and t["fb_error_px"] <= 1 for t in tracks)


def test_projective_translation_keeps_same_crop_exclusion_and_validity():
    source = scene()
    target = translated(source)
    measured = measure_reference_support(source, target, BOXES, model_family="homography")
    assert all(r["reference_supported_descriptive"] for r in measured["regions"])
    assert measured["reference_to_current_affine"] is None
    assert np.array(measured["reference_to_current_homography"]).shape == (3, 3)
    excluded = np.ones(source.shape, bool)
    for x1, y1, x2, y2 in BOXES:
        excluded[y1:y2, x1:x2] = False
    source[excluded], target[excluded] = 0, 255
    assert measure_reference_support(source, target, BOXES, model_family="homography") == measured
