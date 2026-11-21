import pytest

from valorant_ai_coach.visual.development_boundary import candidate_boundary_evidence


def evidence(p=(.5, .5), polygon=None, radius=14):
    return candidate_boundary_evidence(p, polygon or [[0, 0], [1, 0], [1, 1], [0, 1]],
                                       reference_size_px=(100, 200),
                                       assumed_error_radius_px=radius)


def test_anisotropic_reference_pixels_and_strict_boundary_guard():
    assert evidence()["boundary_clearance_reference_px"] == 50
    assert evidence(radius=50)["boundary_assessment"] == "boundary_intersects_assumed_error"
    assert evidence(radius=49)["boundary_assessment"] == "interior_under_assumption"
    assert evidence((0, .5), radius=0)["boundary_assessment"] == "boundary_intersects_assumed_error"
    assert evidence(radius=None)["boundary_assessment"] == "unmeasured_error_radius"
    result = evidence((-.1, .5))
    assert result["boundary_assessment"] == "outside_region"
    assert result["boundary_clearance_reference_px"] == -10
    assert result["ownership"] == "UNKNOWN"


def test_concave_boundary_is_not_bounding_rectangle():
    poly = [[0, 0], [1, 0], [1, .4], [.4, .4], [.4, 1], [0, 1]]
    assert evidence((.5, .5), poly)["boundary_assessment"] == "outside_region"
    assert evidence((.3, .5), poly)["boundary_clearance_reference_px"] == pytest.approx(10)


@pytest.mark.parametrize("radius", [-1, True, "14", float("nan"), float("inf")])
def test_invalid_assumption_is_rejected(radius):
    with pytest.raises(ValueError):
        evidence(radius=radius)


def test_invalid_polygon_rejected():
    with pytest.raises(ValueError):
        evidence(polygon=[[0], [1, 0], [0, 1]])
    with pytest.raises(ValueError):
        evidence(polygon=[[0, 0], [1, 1], [1, 0], [0, 1]])
