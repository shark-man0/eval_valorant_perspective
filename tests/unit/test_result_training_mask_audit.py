import numpy as np
import pytest

from scripts.diagnostics.result_training_mask_audit import persistent_white_feature


def test_dynamic_background_and_colored_brightness_do_not_become_stable_white():
    regions = np.ones((2, 3), dtype=np.uint8)
    images = [np.zeros((2, 3, 3), dtype=np.uint8) for _ in range(3)]
    for image in images:
        image[0, 0] = 255
        image[0, 1] = [0, 255, 255]  # Bright yellow is not white.
    images[1][1, 2] = 255
    before = [image.copy() for image in images]
    reference, mask, supported, features = persistent_white_feature(images, regions)
    assert reference[0, 0] == 255 and reference[0, 1] == 0
    assert mask[1, 2] == 0 and supported[1, 2] == 0
    assert all(np.array_equal(a, b) for a, b in zip(images, before, strict=True))
    assert len(features) == 3


def test_missing_or_grayscale_source_is_rejected():
    regions = np.ones((2, 3), dtype=np.uint8)
    with pytest.raises(ValueError):
        persistent_white_feature([np.zeros((2, 3), dtype=np.uint8)] * 3, regions)
    with pytest.raises(ValueError):
        persistent_white_feature([np.zeros((2, 3, 3), dtype=np.uint8)] * 2, regions)
