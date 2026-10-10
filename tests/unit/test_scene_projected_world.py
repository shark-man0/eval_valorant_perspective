import numpy as np
import pytest

from valorant_ai_coach.hud.scene_tracking import projected_world_regions

BOXES = ((20, 50, 100, 115), (20, 160, 100, 250), (450, 150, 550, 250))


def inputs():
    source = np.random.default_rng(62).integers(0, 256, (360, 640), dtype=np.uint8)
    mask = np.zeros(source.shape, bool)
    for x1, y1, x2, y2 in BOXES:
        mask[y1:y2, x1:x2] = True
    return source, mask


def test_translated_source_footprint_uses_only_reviewed_current_world():
    source, mask = inputs()
    current, current_mask = np.roll(source, 1, axis=1), np.roll(mask, 1, axis=1)
    model = np.array([[1, 0, 1], [0, 1, 0]], dtype=float)
    before = projected_world_regions(source, current, BOXES, model, mask, current_mask)
    assert all(row["supported"] and row["valid_fraction"] == 1 for row in before)
    current[~current_mask] = 0
    source[~mask] = 255
    assert projected_world_regions(source, current, BOXES, model, mask, current_mask) == before
    assert all(not row["runtime_proof_authorized"] for row in before)


def test_fractional_interpolation_never_imports_unreviewed_taps():
    source, mask = inputs()
    current_mask = mask.copy()
    current_mask[:, 50] = False
    model = np.array([[1, 0, 0.5], [0, 1, 0]], dtype=float)
    before = projected_world_regions(source, source, BOXES, model, mask, current_mask)
    current = source.copy()
    current[~current_mask] = 0
    assert projected_world_regions(source, current, BOXES, model, mask, current_mask) == before
    assert before[0]["valid_fraction"] < 1


def test_occlusion_and_padding_do_not_lower_population_denominator():
    source, mask = inputs()
    unknown = mask.copy()
    unknown[50:115, 20:50] = False
    result = projected_world_regions(source, source, BOXES, np.eye(2, 3), mask, unknown)
    assert result[0]["reason"] == "projected_review_coverage_insufficient"
    assert not result[0]["supported"]
    moved = projected_world_regions(
        source, source, BOXES, np.array([[1, 0, -200], [0, 1, 0]]), mask, mask
    )
    assert not moved[0]["supported"]
    mask[50, 20] = False
    assert (
        projected_world_regions(source, source, BOXES, np.eye(2, 3), mask, unknown)[0]["reason"]
        == "source_footprint_not_fully_reviewed"
    )


def test_protected_ui_and_degenerate_geometry_reject():
    source, mask = inputs()
    for bad in (np.zeros((2, 3)), np.eye(3), np.full((2, 3), np.nan)):
        with pytest.raises(ValueError):
            projected_world_regions(source, source, BOXES, bad, mask, mask)
    for point in ((10, 20), (40, 250)):
        unsafe = mask.copy()
        unsafe[point] = True
        with pytest.raises(ValueError, match="protected"):
            projected_world_regions(source, source, BOXES, np.eye(2, 3), mask, unsafe)


def test_review_metadata_alone_does_not_accept_wrong_or_textureless_appearance():
    source, mask = inputs()
    unrelated = np.random.default_rng(71).integers(0, 256, source.shape, dtype=np.uint8)
    result = projected_world_regions(source, unrelated, BOXES, np.eye(2, 3), mask, mask)
    assert all(row["valid_fraction"] == 1 and not row["supported"] for row in result)
    flat = np.full(source.shape, 127, dtype=np.uint8)
    result = projected_world_regions(flat, flat, BOXES, np.eye(2, 3), mask, mask)
    assert all(row["ncc"] is None and not row["supported"] for row in result)
