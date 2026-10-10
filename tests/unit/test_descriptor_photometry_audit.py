import numpy as np

from scripts.diagnostics.audit_descriptor_photometry import measure


def test_partition_separates_source_and_current_texture_from_model_and_footprint():
    image = np.random.default_rng(1).integers(0, 256, (360, 640), np.uint8)
    blank = np.zeros_like(image)
    allowed = np.ones(image.shape, np.float32)
    identity = [[1, 0, 0], [0, 1, 0]]
    assert (
        measure(blank, image, allowed, [50, 50], identity)["reason"] == "source_texture_unavailable"
    )
    assert measure(image, image, allowed, [50, 50], None)["reason"] == "model_unavailable"
    assert (
        measure(image, blank, allowed, [50, 50], identity)["reason"]
        == "current_texture_unavailable"
    )
    assert measure(image, image, allowed, [50, 50], identity)["reason"] == "ncc_supported"
    allowed[50, 50] = 0
    assert (
        measure(image, image, allowed, [50, 50], identity)["reason"]
        == "current_footprint_unavailable"
    )


def test_fractional_projection_cannot_trim_unavailable_taps():
    image = np.random.default_rng(2).integers(0, 256, (360, 640), np.uint8)
    allowed = np.ones(image.shape, np.float32)
    allowed[:, 58:] = 0
    assert (
        measure(image, image, allowed, [50, 50], [[1, 0, 0.5], [0, 1, 0]])["reason"]
        == "current_footprint_unavailable"
    )


def test_unrelated_photometry_is_not_supported_by_model_identity():
    image = np.random.default_rng(3).integers(0, 256, (360, 640), np.uint8)
    other = np.random.default_rng(4).integers(0, 256, (360, 640), np.uint8)
    result = measure(
        image, other, np.ones(image.shape, np.float32), [50, 50], [[1, 0, 0], [0, 1, 0]]
    )
    assert result["reason"] == "ncc_rejected"
    assert result["ncc"] < 0.9
