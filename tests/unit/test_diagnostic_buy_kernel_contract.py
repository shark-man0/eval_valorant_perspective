"""Synthetic evidence that the rejected Buy extractor cannot use a 41px halo.

These are dependency counterexamples, not production acceptance tests. They use
no recording, reference asset, label or detector state.
"""

import cv2
import numpy as np
import pytest


@pytest.mark.parametrize("vertical", [False, True])
def test_even_opening_can_propagate_changed_input_eighty_pixels(vertical):
    image = np.zeros((3, 260), dtype=np.uint8)
    image[1, 80:160] = 255
    changed = image.copy()
    changed[1, 80] = 0
    kernel = np.ones((1, 80), dtype=np.uint8)
    if vertical:
        image, changed, kernel = image.T, changed.T, kernel.T
    original_response = cv2.morphologyEx(image, cv2.MORPH_OPEN, kernel)
    changed_response = cv2.morphologyEx(changed, cv2.MORPH_OPEN, kernel)
    outputs = np.argwhere(original_response != changed_response)
    axis = outputs[:, 0 if vertical else 1]
    # Default even anchor 40 composes asymmetric source-influence [-78,+80].
    assert (int(axis.min()), int(axis.max())) == (81, 160)
    assert int(np.max(np.abs(axis - 80))) == 80


def test_full_gray_canny_opening_changes_outside_forty_one_pixel_halo():
    image = np.zeros((64, 300), dtype=np.uint8)
    image[31:34, 10:290] = 255
    changed = image.copy()
    changed[31, 70] = 0
    kernel = np.ones((1, 80), dtype=np.uint8)

    def response(source):
        return cv2.morphologyEx(
            cv2.Canny(source, 60, 150, L2gradient=True), cv2.MORPH_OPEN, kernel
        )

    before, after = response(image), response(changed)
    assert before[30, 12] != after[30, 12]
    assert abs(12 - 70) > 41


def test_canny_hysteresis_can_depend_on_strong_seed_far_outside_local_halo():
    image = np.zeros((320, 300), dtype=np.uint8)
    image[:, 150:] = 25
    image[270:290, 150:] = 50
    changed = image.copy()
    changed[270:290, 150:] = 25
    before = cv2.Canny(image, 60, 150, L2gradient=True)
    after = cv2.Canny(changed, 60, 150, L2gradient=True)
    assert before[20, 149] > 0
    assert after[20, 149] == 0
    assert 270 - 20 == 250
