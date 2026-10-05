import numpy as np
import pytest

from scripts.diagnostic_edge_geometry import masked_spatial_hog


def test_excluded_pixel_changes_cannot_supply_descriptor_evidence():
    rng = np.random.default_rng(913)
    first = rng.integers(0, 256, (64, 64, 3), dtype=np.uint8)
    mask = np.zeros((64, 64), dtype=bool)
    mask[5:42, 7:58] = True
    second = first.copy()
    second[~mask] = rng.integers(0, 256, second[~mask].shape, dtype=np.uint8)
    a, b = masked_spatial_hog(first, mask), masked_spatial_hog(second, mask)
    np.testing.assert_array_equal(a.descriptor, b.descriptor)
    assert a.gradient_magnitude_sum == b.gradient_magnitude_sum
    assert a.occupied_cell_count == b.occupied_cell_count > 0


def test_mask_boundary_on_constant_visible_region_is_not_an_edge():
    image = np.full((64, 64), 180, dtype=np.uint8)
    image[42:] = 0
    mask = np.zeros_like(image, dtype=bool)
    mask[:42] = True
    result = masked_spatial_hog(image, mask)
    assert result.valid_pixel_count > 0
    assert result.gradient_magnitude_sum == 0
    assert result.occupied_cell_count == 0
    assert not np.any(result.descriptor)


def test_insufficient_mask_has_no_gradient_support():
    image = np.arange(64 * 64, dtype=np.uint8).reshape(64, 64)
    mask = np.zeros_like(image, dtype=bool)
    mask[10, 10] = True
    result = masked_spatial_hog(image, mask)
    assert result.valid_pixel_count == 0
    assert not np.any(result.descriptor)


def test_visible_distributed_edges_survive_dynamic_pixel_exclusion():
    image = np.zeros((64, 64), dtype=np.uint8)
    image[:, 15:20] = 255
    image[:, 45:50] = 255
    mask = np.zeros_like(image, dtype=bool)
    mask[:48] = True
    result = masked_spatial_hog(image, mask)
    assert result.occupied_cell_count >= 12
    assert np.linalg.norm(result.descriptor) == pytest.approx(1)


@pytest.mark.parametrize("mask", [np.ones((63, 64), dtype=bool), np.ones((64, 64), dtype=np.uint8)])
def test_invalid_mask_rejects(mask):
    with pytest.raises(ValueError):
        masked_spatial_hog(np.zeros((64, 64), dtype=np.uint8), mask)
