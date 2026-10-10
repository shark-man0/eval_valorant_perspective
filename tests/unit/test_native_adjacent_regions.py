import numpy as np
import pytest

from scripts.diagnostics.audit_native_adjacent_regions import measure_regions


def test_excluded_ui_pixels_cannot_change_measurements():
    rng = np.random.default_rng(17)
    image = rng.integers(0, 256, (1080, 1920, 3), dtype=np.uint8)
    current = image.copy()
    current[135:281, 738:1183] = 0
    current[20:90, 860:1060] = 255
    regions = {'candidate_background': [[30, 519, 501, 741]],
               'mixed_foreground': [[1440, 930, 1600, 1050]]}
    assert measure_regions(image, current, regions) == measure_regions(image, image, regions)


def test_flat_region_is_unknown_and_perfect_match_cannot_authorize():
    image = np.zeros((1080, 1920, 3), dtype=np.uint8)
    result = measure_regions(image, image, {'candidate_background': [[30, 519, 501, 741]]})
    assert result['regions'][0]['scene_ncc'] is None
    assert result['regions'][0]['masked_reference_ncc'] is None
    assert result['source_continuity'] is None
    assert result['runtime_authorized'] is False


@pytest.mark.parametrize('box', [[860, 20, 1060, 90], [738, 135, 1183, 281], [-1, 0, 40, 40]])
def test_invalid_or_excluded_regions_rejected(box):
    image = np.zeros((1080, 1920, 3), dtype=np.uint8)
    with pytest.raises(ValueError):
        measure_regions(image, image, {'candidate_background': [box]})
