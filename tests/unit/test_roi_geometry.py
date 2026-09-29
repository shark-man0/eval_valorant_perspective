import numpy as np
import pytest

from valorant_ai_coach.maps.calibration import MinimapCalibrator
from valorant_ai_coach.video.geometry import normalized_roi_bounds
from valorant_ai_coach.visual.pixels import _roi


@pytest.mark.parametrize("width,height", [(500, 500), (1920, 1080), (1280, 720)])
def test_calibration_and_markers_use_identical_fractional_roi(width, height):
    coordinates = [0.003, 0.019, 0.997, 0.963]
    image = np.zeros((height, width, 3), dtype=np.uint8)
    crop, bounds = _roi(image, {"rois": {"minimap": coordinates}}, "minimap")
    assert bounds == MinimapCalibrator._pixel_roi(coordinates, width, height)
    assert crop.shape[:2] == (bounds[3] - bounds[1], bounds[2] - bounds[0])
    if width == 500:
        assert bounds[0] == 2


@pytest.mark.parametrize(
    "roi", [None, [0, 0, 0, 1], [0, 0, float("nan"), 1], [-0.1, 0, 1, 1], [0, 0, 0.0001, 1]]
)
def test_invalid_or_empty_roi_rejected_consistently(roi):
    assert normalized_roi_bounds(roi, 500, 500) is None
    assert MinimapCalibrator._pixel_roi(roi, 500, 500) is None
    with pytest.raises(ValueError):
        _roi(np.zeros((500, 500, 3), dtype=np.uint8), {"rois": {"minimap": roi}}, "minimap")
