import cv2
import numpy as np
import pytest

from scripts.diagnostics.scene_descriptor_acquisition import (
    _descriptors,
    _distinct_correspondences,
    descriptor_domain_proposal,
)

BOXES = ((30, 40, 180, 110), (40, 155, 180, 240), (450, 155, 580, 240))
SEARCH = ((0, 28, 224, 288), (416, 28, 640, 288), (224, 120, 416, 288))


def test_spatial_context_is_identical_at_same_point_and_overlap_does_not_add_witnesses():
    image = source()
    points, values = _descriptors(image, BOXES, feature_source="spatial_corners")
    others, descriptors = _descriptors(image, SEARCH, feature_source="spatial_corners")
    locations = [tuple(p[1]) for p in points]
    assert len(locations) == len(set(locations))
    lookup = {tuple(p[1]): d for p, d in zip(others, descriptors, strict=True)}
    common = [(xy, d) for xy, d in zip(locations, values, strict=True) if xy in lookup]
    assert len(common) >= 10
    for xy, descriptor in common:
        np.testing.assert_array_equal(descriptor, lookup[xy])


def source():
    return cv2.GaussianBlur(
        np.random.default_rng(124).integers(0, 256, (360, 640), np.uint8), (3, 3), 0
    )


@pytest.mark.parametrize("rotate", [False, True])
@pytest.mark.parametrize("feature_source", ["sift", "reviewed_corners", "spatial_corners"])
def test_geometry_proposals_need_real_projected_photometric_support(rotate, feature_source):
    reference = source()
    if rotate:
        model = cv2.getRotationMatrix2D((0, 0), 2, 1.02)
        model[:, 2] += [20, 10]
    else:
        model = np.array([[1.0, 0.0, 20], [0.0, 1.0, 0]])
    current = cv2.warpAffine(reference, model, (640, 360))
    result = descriptor_domain_proposal(
        reference, current, BOXES, SEARCH, feature_source=feature_source
    )
    assert result["diagnostic_initialization_proposed"]
    np.testing.assert_allclose(result["model"], model, atol=0.1)
    assert result["photometric_inliers"] >= 0.90 * len(result["tracks"])
    assert result["joint"]["locally_unique_joint_appearance"]
    assert not result["runtime_proof_authorized"]
    assert not result["world_mask_authorized"]


def test_unknown_feature_variant_is_not_a_hidden_fallback():
    with pytest.raises(ValueError, match="feature representation"):
        descriptor_domain_proposal(source(), source(), BOXES, SEARCH, feature_source="auto")


@pytest.mark.parametrize("feature_source", ["sift", "reviewed_corners", "spatial_corners"])
def test_unknown_texture_and_other_scene_cannot_supply_a_descriptor_proof(feature_source):
    reference = source()
    constant = np.zeros(reference.shape, np.uint8)
    assert not descriptor_domain_proposal(
        constant, constant, BOXES, SEARCH, feature_source=feature_source
    )["diagnostic_initialization_proposed"]
    other = np.random.default_rng(125).integers(0, 256, reference.shape, np.uint8)
    assert not descriptor_domain_proposal(
        reference, other, BOXES, SEARCH, feature_source=feature_source
    )["diagnostic_initialization_proposed"]


@pytest.mark.parametrize("feature_source", ["sift", "reviewed_corners", "spatial_corners"])
def test_ui_pixels_outside_source_and_current_domains_are_not_proposal_evidence(feature_source):
    reference = source()
    current = np.roll(reference, 20, axis=1)
    expected = descriptor_domain_proposal(
        reference, current, BOXES, SEARCH, feature_source=feature_source
    )
    reference[:28] = 0
    current[:28] = 255
    reference[28:120, 224:416] = 0
    current[28:120, 224:416] = 255
    assert (
        descriptor_domain_proposal(reference, current, BOXES, SEARCH, feature_source=feature_source)
        == expected
    )


def test_protected_destinations_are_rejected_before_descriptor_generation():
    with pytest.raises(ValueError, match="protected"):
        descriptor_domain_proposal(source(), source(), BOXES, ((224, 28, 416, 120),))


def test_orientation_duplicates_are_one_witness_and_conflicting_locations_are_unknown():
    a = {"reference_xy": [30.1, 40.2], "current_xy": [50.1, 40.2], "region": 0}
    b = {"reference_xy": [90.1, 60.2], "current_xy": [110.1, 60.2], "region": 1}
    assert _distinct_correspondences([a, dict(a), b, dict(b)]) == [a, b]
    assert _distinct_correspondences([a, {**a, "current_xy": [60.1, 40.2]}]) is None
    assert _distinct_correspondences([a, {**b, "current_xy": a["current_xy"]}]) is None
