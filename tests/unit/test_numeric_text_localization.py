import cv2
import numpy as np
import pytest

from scripts.diagnostics.numeric_text_localization import propose


def clock():
    gray = np.full((85, 125), 35, np.uint8)
    for x, w in ((25, 8), (48, 16), (71, 15)):
        cv2.rectangle(gray, (x, 28), (x + w - 1, 55), 240, -1)
    for y in (35, 47):
        cv2.rectangle(gray, (38, y), (41, y + 3), 240, -1)
    return gray


def test_timer_crop_requires_observed_colon_and_preserves_source_pixels():
    gray = clock()
    before = gray.copy()
    assert propose(gray, timer=True) == (21, 24, 90, 60)
    assert np.array_equal(gray, before)
    gray[:, 38:42] = 35
    assert propose(gray, timer=True) is None


def test_frame_shapes_and_blank_background_are_not_text_rows():
    gray = np.full((85, 125), 35, np.uint8)
    cv2.rectangle(gray, (2, 2), (122, 82), 240, 2)
    assert propose(gray, timer=False) is None
    assert propose(gray, timer=True) is None
    assert propose(np.full_like(gray, 240), timer=False) is None


def test_two_possible_score_rows_are_ambiguous_not_best_guess():
    gray = np.full((85, 125), 35, np.uint8)
    cv2.rectangle(gray, (25, 10), (36, 30), 240, -1)
    cv2.rectangle(gray, (25, 48), (36, 68), 240, -1)
    assert propose(gray, timer=False) is None


@pytest.mark.parametrize("image", [np.zeros((8, 8), np.uint8),
                                  np.zeros((85, 125, 3), np.uint8),
                                  np.zeros((85, 125), np.float32)])
def test_bad_numeric_roi_fails_closed(image):
    with pytest.raises(ValueError):
        propose(image, timer=True)
