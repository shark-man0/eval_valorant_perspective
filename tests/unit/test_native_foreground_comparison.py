import numpy as np
import pytest

from scripts.diagnostics.compare_native_foreground import compare_pose, pose_patches

BOXES = [(100, 500, 160, 560), (200, 500, 260, 560), (300, 600, 360, 660)]


def test_pose_match_is_descriptive_and_never_proves_normal_animation():
    image = np.random.default_rng(71).integers(0, 256, (720, 480, 3), np.uint8)
    patches = pose_patches(image, BOXES)
    result = compare_pose(patches, patches)
    assert result['minimum_ncc'] > .99
    assert not result['runtime_authorized']
    assert not result['normal_animation_proven']


def test_missing_contrast_in_one_crop_is_not_replaced_by_other_matches():
    image = np.random.default_rng(71).integers(0, 256, (720, 480, 3), np.uint8)
    patches = pose_patches(image, BOXES)
    changed = list(patches)
    changed[1] = np.zeros_like(changed[1])
    result = compare_pose(patches, changed)
    assert result['minimum_ncc'] is None
    assert result['crop_ncc'][1] is None
    assert not result['normal_animation_proven']


@pytest.mark.parametrize('boxes', [BOXES[:2], [BOXES[0]]*3,
                                  [(100, 10, 160, 60), *BOXES[1:]]])
def test_incomplete_duplicate_or_timer_phase_crops_are_rejected(boxes):
    image = np.zeros((720, 480, 3), np.uint8)
    with pytest.raises(ValueError):
        pose_patches(image, boxes)
