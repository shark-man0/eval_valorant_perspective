from __future__ import annotations

import numpy as np
import pytest

from scripts.diagnostics.scene_patch_search import (
    reviewed_patches,
    search_reviewed_world,
    unique_match,
)

BOXES = ((20, 150, 180, 220), (20, 230, 180, 300), (440, 130, 620, 200))


def image():
    return np.random.default_rng(51).integers(0, 256, (360, 640), dtype=np.uint8)


def test_search_can_follow_world_patch_into_another_allowed_crop():
    reference = image()
    current = np.roll(reference, 35, axis=0)
    metrics, tracks = search_reviewed_world(reference, current, BOXES)
    assert len(tracks) > 20
    assert metrics["model_inliers"] == len(tracks)
    assert all(t["current_xy"][1] - t["reference_xy"][1] == 35 for t in tracks)
    assert any(t["region"] == 0 and t["current_xy"][1] >= 230 for t in tracks)
    assert metrics["runtime_proof_authorized"] is False


def test_excluded_pixels_cannot_influence_search():
    reference = image()
    current = np.roll(reference, 35, axis=0)
    expected = search_reviewed_world(reference, current, BOXES)
    mask = np.ones(reference.shape, bool)
    for x1, y1, x2, y2 in BOXES:
        mask[y1:y2, x1:x2] = False
    reference[mask] = 255
    current[mask] = 0
    assert search_reviewed_world(reference, current, BOXES) == expected


def test_repeated_distinct_patch_is_ambiguous():
    source = image()
    patch = source[150:165, 30:45].copy()
    source[180:195, 80:95] = patch
    assert unique_match(patch, source, BOXES) is None


def test_different_view_abstains():
    reference = image()
    current = np.random.default_rng(89).integers(0, 256, reference.shape, dtype=np.uint8)
    metrics, tracks = search_reviewed_world(reference, current, BOXES)
    assert tracks == []
    assert metrics["reference_to_current_affine"] is None


def test_duplicate_image_is_not_authorization():
    reference = image()
    metrics, tracks = search_reviewed_world(reference, reference.copy(), BOXES)
    assert len(tracks) > 20
    assert metrics["runtime_proof_authorized"] is False


@pytest.mark.parametrize("box", [(250, 60, 320, 100), (30, 0, 100, 35), (0, 130, 700, 170)])
def test_protected_or_invalid_boxes_rejected(box):
    with pytest.raises(ValueError):
        reviewed_patches(image(), [box])


def test_textureless_reference_has_no_world_support():
    metrics, tracks = search_reviewed_world(np.zeros((360, 640), np.uint8), image(), BOXES)
    assert tracks == []
    assert metrics["model_inliers"] == 0


def test_rejection_observability_preserves_every_match_output():
    reference = image()
    current = np.roll(reference, 35, axis=0)
    expected = search_reviewed_world(reference, current, BOXES)
    reasons = []
    assert search_reviewed_world(reference, current, BOXES, rejection_sink=reasons) == expected
    assert reasons
    assert all(x["stage"] in {"forward", "reverse"} for x in reasons)
