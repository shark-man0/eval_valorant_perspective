import numpy as np
import pytest

from scripts.diagnostics.scene_track_footprint import projected_patch_support

IDENTITY = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])


def images():
    source = np.random.default_rng(101).integers(0, 256, (360, 640), np.uint8)
    return source, source.copy()


def test_small_matching_center_does_not_attest_occluded_context():
    source, current = images()
    current[185:216, 85:116] = 0
    current[193:208, 93:108] = source[193:208, 93:108]
    assert projected_patch_support(source, current, [100, 200], IDENTITY, radius=7)[
        "appearance_supported"
    ]
    for radius in (10, 15):
        result = projected_patch_support(source, current, [100, 200], IDENTITY, radius=radius)
        assert not result["appearance_supported"]
        assert not result["world_mask_authorized"]


def test_matching_full_footprint_is_not_semantic_or_temporal_authority():
    source, current = images()
    result = projected_patch_support(source, current, [100, 200], IDENTITY, radius=15)
    assert result["appearance_supported"]
    assert not result["world_mask_authorized"]
    assert not result["runtime_proof_authorized"]


def test_mean_ncc_can_hide_small_foreground_and_must_not_authorize_mask():
    source, current = images()
    current[200:202, 100:102] = 0
    result = projected_patch_support(source, current, [100, 200], IDENTITY, radius=15)
    assert result["appearance_supported"]
    assert not result["world_mask_authorized"]


@pytest.mark.parametrize("model", (np.zeros((2, 3)), np.full((2, 3), np.nan)))
def test_invalid_correspondence_model_is_rejected(model):
    source, current = images()
    with pytest.raises(ValueError):
        projected_patch_support(source, current, [100, 200], model, radius=15)


def test_excluded_timer_phase_values_do_not_affect_world_patch():
    source, current = images()
    before = projected_patch_support(source, current, [100, 200], IDENTITY, radius=15)
    current[:28] = 0
    current[28:120, 224:416] = 255
    assert projected_patch_support(source, current, [100, 200], IDENTITY, radius=15) == before


def test_projected_protected_tap_is_rejected_without_population_shrinkage():
    source, current = images()
    model = IDENTITY.copy()
    model[0, 2] = 100.5
    result = projected_patch_support(source, current, [120, 90], model, radius=15)
    assert result["reason"] == "projected_footprint_invalid_or_protected"
    assert result["ncc"] is None


@pytest.mark.parametrize("center", ([0, 150], [240, 90]))
def test_unreviewable_source_scope_is_rejected(center):
    source, current = images()
    assert (
        projected_patch_support(source, current, center, IDENTITY, radius=15)["reason"]
        == "source_footprint_invalid_or_protected"
    )
