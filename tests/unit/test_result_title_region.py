import cv2
import numpy as np
import pytest

from scripts.diagnostics.result_title_region import title_region


def banner(text="LOST", *, x=85, baseline=105, scale=1):
    im = np.full((230 * scale, 520 * scale, 3), 30, np.uint8)
    cv2.putText(im, text, (x * scale, baseline * scale), cv2.FONT_HERSHEY_DUPLEX,
                2.2 * scale, (245, 245, 245), 5 * scale, cv2.LINE_8)
    return im


@pytest.mark.parametrize("text", ["LOST", "WON", "THRIFTY", "TEAM ACE"])
@pytest.mark.parametrize("scale", [1, 2])
def test_whole_glyphs_with_relative_halo_no_repaired_pixels(text, scale):
    im = banner(text, scale=scale)
    original = im.copy()
    found = title_region(im)
    assert found["status"] == "PROPOSAL"
    a, b, c, d = found["bounds"]
    assert 0 <= a < c <= im.shape[1] and 0 <= b < d <= im.shape[0]
    for x, y, w, h in found["glyph_boxes"]:
        assert a < x and b < y and x + w < c and y + h < d
    assert found["semantic_completeness"] == "UNKNOWN"
    assert not found["formal_events"] and not found["production_qualified"]
    np.testing.assert_array_equal(im, original)


@pytest.mark.parametrize("x,baseline", [(40, 85), (175, 180), (200, 130)])
def test_line_translation_is_not_bound_to_one_capture(x, baseline):
    found = title_region(banner(x=x, baseline=baseline))
    assert found["status"] == "PROPOSAL"
    assert found["bounds"][1] < baseline - 35


@pytest.mark.parametrize("x", [-12, 420])
def test_glyphs_clipped_by_outer_roi_cannot_supply_a_complete_line(x):
    found = title_region(banner(x=x))
    assert found["status"] == "UNKNOWN" and found["bounds"] is None


def test_two_large_text_lines_stay_unknown_without_ocr_label_selection():
    im = banner(baseline=85)
    cv2.putText(im, "WON", (85, 195), cv2.FONT_HERSHEY_DUPLEX,
                2.2, (245, 245, 245), 5, cv2.LINE_8)
    found = title_region(im)
    assert found["reason"] == "ambiguous_title_lines"
    assert found["status"] == "UNKNOWN"


@pytest.mark.parametrize("value", [0, 255])
def test_flat_background_has_no_title(value):
    assert title_region(np.full((230, 520, 3), value, np.uint8))["status"] == "UNKNOWN"


def test_banner_outline_is_not_a_glyph_line():
    im = np.full((230, 520, 3), 20, np.uint8)
    cv2.rectangle(im, (5, 5), (514, 224), (255, 255, 255), 3)
    assert title_region(im)["status"] == "UNKNOWN"


def test_differently_sized_fragments_on_baseline_are_not_silently_dropped():
    im = banner()
    cv2.rectangle(im, (330, 55), (345, 130), (245, 245, 245), -1)
    found = title_region(im)
    assert found["status"] == "UNKNOWN"


@pytest.mark.parametrize("im", [np.empty((0, 1), np.uint8), np.ones((10, 10), float),
                               np.ones((10, 10, 4), np.uint8)])
def test_invalid_roi_rejected(im):
    with pytest.raises(ValueError):
        title_region(im)
