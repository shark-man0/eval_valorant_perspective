import cv2
import numpy as np
import pytest

from scripts.diagnostics.diagnose_geometry_edges import raw_scores
from scripts.diagnostics.geometry_enclosure_mask import enclosure_boundary_support


def test_enclosed_frame_keeps_outline_but_not_nested_numeric_content():
    template = np.full((100, 160), 25, np.uint8)
    cv2.rectangle(template, (20, 20), (85, 75), 220, 3)
    cv2.putText(template, "50", (32, 58), cv2.FONT_HERSHEY_SIMPLEX, .7, 200, 2)
    mask = enclosure_boundary_support(template)
    assert np.count_nonzero(mask) >= 64
    # Canny locates the outer transition of the thick stroke, not its centre.
    assert mask[17:23, 40].any()
    assert np.any(template[mask > 0] >= 200) and np.any(template[mask > 0] == 25)
    assert not mask[29:65, 29:76].any()
    changed = template.copy()
    changed[29:65, 29:76] = np.random.default_rng(7).integers(0, 255, (36, 47), dtype=np.uint8)
    first = raw_scores([cv2.cvtColor(template, cv2.COLOR_GRAY2BGR)], template, mask)[0]
    second = raw_scores([cv2.cvtColor(changed, cv2.COLOR_GRAY2BGR)], template, mask)[0]
    assert first >= .90 and second == pytest.approx(first, abs=1e-6)


def test_tiny_horizontal_line_cannot_replace_a_closed_2d_frame():
    template = np.full((100, 160), 25, np.uint8)
    cv2.line(template, (100, 50), (120, 50), 220, 2)
    assert not enclosure_boundary_support(template).any()
    assert not enclosure_boundary_support(np.full_like(template, 70)).any()


@pytest.mark.parametrize("image", [np.zeros((10, 10), np.uint8),
                                  np.zeros((100, 160, 3), np.uint8),
                                  np.zeros((100, 160), np.float32)])
def test_bad_enclosure_input_fails_closed(image):
    with pytest.raises(ValueError):
        enclosure_boundary_support(image)
