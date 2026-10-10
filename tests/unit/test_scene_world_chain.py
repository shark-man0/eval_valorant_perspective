from __future__ import annotations

import numpy as np

from valorant_ai_coach.hud.scene_tracking import ReviewedWorldChain

BOXES = ((20, 50, 100, 115), (20, 160, 100, 250), (450, 150, 550, 250))


def seed():
    return np.random.default_rng(62).integers(0, 256, (360, 640), dtype=np.uint8)


def test_native_chain_retains_original_world_identities_and_never_reseeds():
    original = seed()
    chain = ReviewedWorldChain(original, BOXES)
    initial = {(t["region"], *t["seed_xy"]) for t in chain.tracks}
    count = chain.seed_features
    for offset in range(1, 5):
        row = chain.advance(np.roll(original, offset, axis=0))
        assert row["descriptive_supported"]
        assert row["runtime_proof_authorized"] is False
        current = {(t["region"], *t["seed_xy"]) for t in chain.tracks}
        assert current <= initial
        assert len(current) <= count
        initial = current
        count = len(current)
        assert row["minimum_adjacent_ncc"] >= 0.90
        assert row["minimum_seed_ncc"] >= 0.90


def test_unknown_terminates_chain_without_automatic_reacquisition():
    original = seed()
    chain = ReviewedWorldChain(original, BOXES)
    unrelated = np.random.default_rng(59).integers(0, 256, original.shape, dtype=np.uint8)
    assert not chain.advance(unrelated)["descriptive_supported"]
    assert chain.advance(np.roll(original, 1, axis=0))["reason"] == "chain_terminated"


def test_duplicate_and_discontinuity_clear_world_labels():
    original = seed()
    duplicate = ReviewedWorldChain(original, BOXES)
    assert duplicate.advance(original.copy())["reason"] == "duplicate_image"
    assert duplicate.tracks == []
    cut = ReviewedWorldChain(original, BOXES)
    assert (
        cut.advance(np.roll(original, 1, axis=0), discontinuity=True)["reason"]
        == "content_discontinuity"
    )
    assert cut.advance(np.roll(original, 2, axis=0))["reason"] == "chain_terminated"


def test_every_excluded_pixel_is_independent_of_image_measurements():
    before = seed()
    after = np.roll(before, 1, axis=0)
    expected = ReviewedWorldChain(before, BOXES).advance(after)
    mask = np.ones(before.shape, bool)
    for x1, y1, x2, y2 in BOXES:
        mask[y1:y2, x1:x2] = False
    before[mask] = 0
    after[mask] = 255
    assert ReviewedWorldChain(before, BOXES).advance(after) == expected


def test_single_region_and_textureless_seed_never_authorize():
    original = seed()
    chain = ReviewedWorldChain(original, [BOXES[0]])
    assert not chain.advance(np.roll(original, 1, axis=0))["descriptive_supported"]
    zero = np.zeros_like(original)
    assert (
        ReviewedWorldChain(zero, BOXES).advance(np.ones_like(zero))["reason"] == "chain_terminated"
    )


def test_dense_world_crop_warp_excludes_every_external_pixel():
    from scripts.diagnostics.scene_world_chain import dense_world_regions

    original = seed()
    current = np.roll(original, 1, axis=0)
    model = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 1.0]])
    expected = dense_world_regions(original, current, BOXES, model)
    assert all(r["supported"] for r in expected)
    mask = np.ones(original.shape, bool)
    for x1, y1, x2, y2 in BOXES:
        mask[y1:y2, x1:x2] = False
    original[mask] = 0
    current[mask] = 255
    assert dense_world_regions(original, current, BOXES, model) == expected
    missing = dense_world_regions(
        original, current, BOXES, model + np.array([[0, 0, 500], [0, 0, 0]])
    )
    assert all(not r["supported"] and r["ncc"] is None for r in missing)


def test_dense_mode_preserves_content_break_and_never_authorizes():
    original = seed()
    chain = ReviewedWorldChain(original, BOXES, support_mode="dense_world")
    row = chain.advance(np.roll(original, 1, axis=0))
    assert row["descriptive_supported"]
    assert row["runtime_proof_authorized"] is False
    assert (
        chain.advance(np.roll(original, 2, axis=0), discontinuity=True)["reason"]
        == "content_discontinuity"
    )


def test_native_resolution_preserves_angular_policy_and_world_identity():
    original = np.repeat(np.repeat(seed(), 3, axis=0), 3, axis=1)
    boxes = [tuple(v * 3 for v in b) for b in BOXES]
    chain = ReviewedWorldChain(original, boxes, scale=3)
    identities = {(t["region"], *t["seed_xy"]) for t in chain.tracks}
    result = chain.advance(np.roll(original, 3, axis=0))
    assert result["descriptive_supported"]
    assert result["runtime_proof_authorized"] is False
    assert {(t["region"], *t["seed_xy"]) for t in chain.tracks} <= identities
    assert result["minimum_seed_ncc"] >= 0.90
    assert result["minimum_adjacent_ncc"] >= 0.90


def test_native_resolution_excluded_pixels_do_not_enter_flow_or_seed_warps():
    original = np.repeat(np.repeat(seed(), 3, axis=0), 3, axis=1)
    current = np.roll(original, 3, axis=0)
    boxes = [tuple(v * 3 for v in b) for b in BOXES]
    expected = ReviewedWorldChain(original, boxes, scale=3).advance(current)
    mask = np.ones(original.shape, bool)
    for x1, y1, x2, y2 in boxes:
        mask[y1:y2, x1:x2] = False
    original[mask] = 0
    current[mask] = 255
    assert ReviewedWorldChain(original, boxes, scale=3).advance(current) == expected


def test_native_resolution_validation_protects_phase_and_shape():
    import pytest

    original = np.zeros((1080, 1920), np.uint8)
    with pytest.raises(ValueError, match="protected"):
        ReviewedWorldChain(original, [(224 * 3, 28 * 3, 416 * 3, 120 * 3)], scale=3)
    with pytest.raises(ValueError, match="native grayscale"):
        ReviewedWorldChain(seed(), [tuple(v * 3 for v in b) for b in BOXES], scale=3)
    with pytest.raises(ValueError, match="only canonical or native"):
        ReviewedWorldChain(seed(), BOXES, scale=2)


def test_optional_stage_diagnostics_preserve_decisions_and_account_for_seed_population():
    original = seed()
    current = np.roll(original, 1, axis=0)
    plain = ReviewedWorldChain(original, BOXES)
    observed = ReviewedWorldChain(original, BOXES)
    assert (
        sum(r["seed_features"] for r in observed.seed_region_diagnostics) == observed.seed_features
    )
    for r in observed.seed_region_diagnostics:
        assert r["raw_corners"] == r["border_rejected"] + r["texture_rejected"] + r["seed_features"]
    stages = []
    assert observed.advance(current, region_sink=stages) == plain.advance(current)
    for r in stages:
        assert r["selected"] == r.get("flow_unavailable", 0) + r.get(
            "flow_status_or_nonfinite", 0
        ) + r.get("reciprocal_error_or_outside_crop", 0) + r.get(
            "adjacent_texture_unknown", 0
        ) + r.get("adjacent_ncc_below_floor", 0) + r.get("adjacent_candidates", 0)
        assert r.get("affine_inliers", 0) == r.get("seed_warp_invalid_footprint", 0) + r.get(
            "seed_texture_unknown", 0
        ) + r.get("seed_ncc_below_floor", 0) + r.get("retained", 0)
    assert sum(r.get("retained", 0) for r in stages) == len(observed.tracks)


def test_empty_or_terminated_chain_stage_diagnostics_do_not_reseed():
    original = np.zeros((360, 640), np.uint8)
    chain = ReviewedWorldChain(original, BOXES)
    sink = []
    assert chain.advance(np.ones_like(original), region_sink=sink)["reason"] == "chain_terminated"
    assert sink == [{} for _ in BOXES]
    assert all(r["seed_features"] == 0 for r in chain.seed_region_diagnostics)


def test_adjacent_dense_mode_keeps_original_world_tags_and_rejects_new_background():
    original = seed()
    boxes = ((20, 50, 100, 115), (20, 160, 100, 250), (270, 160, 350, 250), (450, 150, 550, 250))
    original[50:115, 20:100] = np.arange(80, dtype=np.uint8)[None, :]
    chain = ReviewedWorldChain(original, boxes, support_mode="adjacent_dense_world")
    identities = {(t["region"], *t["seed_xy"]) for t in chain.tracks}
    row = chain.advance(np.roll(original, 1, axis=0))
    assert row["descriptive_supported"]
    assert row["feature_spread_supported"] is False
    assert row["runtime_proof_authorized"] is False
    assert {(t["region"], *t["seed_xy"]) for t in chain.tracks} <= identities
    replacement = np.roll(original, 2, axis=0)
    replacement[50:115, 20:100] = np.arange(79, -1, -1, dtype=np.uint8)[None, :]
    assert not chain.advance(replacement)["descriptive_supported"]
    assert chain.advance(np.roll(original, 3, axis=0))["reason"] == "chain_terminated"


def test_adjacent_dense_mode_preserves_duplicate_and_discontinuity_veto():
    original = seed()
    duplicate = ReviewedWorldChain(original, BOXES, support_mode="adjacent_dense_world")
    assert duplicate.advance(original)["reason"] == "duplicate_image"
    cut = ReviewedWorldChain(original, BOXES, support_mode="adjacent_dense_world")
    assert (
        cut.advance(np.roll(original, 1, axis=0), discontinuity=True)["reason"]
        == "content_discontinuity"
    )
    assert cut.advance(np.roll(original, 2, axis=0))["reason"] == "chain_terminated"


def test_adjacent_dense_mode_never_imports_excluded_pixels_into_warps():
    original = seed()
    current = np.roll(original, 1, axis=0)
    expected = ReviewedWorldChain(original, BOXES, support_mode="adjacent_dense_world").advance(
        current
    )
    mask = np.ones(original.shape, bool)
    for x1, y1, x2, y2 in BOXES:
        mask[y1:y2, x1:x2] = False
    original[mask] = 0
    current[mask] = 255
    assert (
        ReviewedWorldChain(original, BOXES, support_mode="adjacent_dense_world").advance(current)
        == expected
    )


def test_full_valid_dense_footprint_rejects_padding_and_excludes_external_pixels():
    from scripts.diagnostics.scene_world_chain import dense_world_regions

    original = seed()
    current = np.roll(original, 1, axis=0)
    model = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 1.0]])
    expected = dense_world_regions(original, current, BOXES, model, footprint="full_valid")
    assert all(r["supported"] and 0.90 <= r["valid_fraction"] < 1 for r in expected)
    mask = np.ones(original.shape, bool)
    for x1, y1, x2, y2 in BOXES:
        mask[y1:y2, x1:x2] = False
    original[mask] = 0
    current[mask] = 255
    assert dense_world_regions(original, current, BOXES, model, footprint="full_valid") == expected
    invalid = dense_world_regions(
        original, current, BOXES, model + np.array([[0, 0, 500], [0, 0, 0]]), footprint="full_valid"
    )
    assert all(r["ncc"] is None and not r["supported"] for r in invalid)


def test_full_valid_coverage_rejects_fractional_padding():
    import cv2

    from scripts.diagnostics.scene_world_chain import dense_world_regions

    original = seed()
    # A subpixel translation still samples padding in the first row/column.
    # Full-valid support must exclude those pixels, not count fractional coverage.
    model = np.array([[1.0, 0.0, 1 / 32], [0.0, 1.0, 1 / 32]])
    crop = original[50:115, 20:100]
    rounded = cv2.warpAffine(np.full(crop.shape, 255, np.uint8), model, (80, 65))
    exact = cv2.warpAffine(np.ones(crop.shape, np.float32), model, (80, 65))
    assert rounded[0, 0] < 255 and exact[0, 0] < 1
    result = dense_world_regions(original, original, [BOXES[0]], model, footprint="full_valid")[0]
    assert result["valid_fraction"] == (79 * 64) / (80 * 65)


def test_full_valid_footprint_is_explicit_and_preserves_content_veto():
    import pytest

    original = seed()
    with pytest.raises(ValueError, match="requires explicit"):
        ReviewedWorldChain(original, BOXES, dense_footprint="full_valid")
    chain = ReviewedWorldChain(
        original, BOXES, support_mode="adjacent_dense_world", dense_footprint="full_valid"
    )
    row = chain.advance(np.roll(original, 1, axis=0))
    assert row["descriptive_supported"] and row["runtime_proof_authorized"] is False
    assert (
        chain.advance(np.roll(original, 2, axis=0), discontinuity=True)["reason"]
        == "content_discontinuity"
    )
    assert chain.advance(np.roll(original, 3, axis=0))["reason"] == "chain_terminated"


def test_optional_world_model_cloud_never_changes_chain_decisions():
    original = seed()
    plain = ReviewedWorldChain(original, BOXES)
    measured = ReviewedWorldChain(original, BOXES)
    for offset in [1, 2]:
        current = np.roll(original, offset, axis=0)
        sink = []
        assert measured.advance(current, model_sink=sink) == plain.advance(current)
        assert len(sink) == 1
        assert (
            len(sink[0]["seed_points"]) == len(sink[0]["current_points"]) == len(sink[0]["regions"])
        )
        assert min(sink[0]["adjacent_patch_ncc"]) >= 0.90
        assert sink[0]["original_partial_affine"] is not None


def test_final_membership_checks_both_pixel_spaces_without_expanding_floor():
    from scripts.diagnostics.scene_world_chain import symmetric_affine_membership

    source = np.float32([[0, 0], [10, 10], [20, 20]])
    model = np.array([[0.5, 0, 0], [0, 0.5, 0]])
    target = source * 0.5 + np.array([[0, 0], [1.5, 0], [3, 0]])
    # Middle forward error1.5 fits the2px floor but inverse error3 must reject.
    assert symmetric_affine_membership(source, target, model).tolist() == [1, 0, 0]
    assert symmetric_affine_membership(source, target, None).tolist() == [0, 0, 0]
    identity = np.array([[1.0, 0, 0], [0, 1.0, 0]])
    assert symmetric_affine_membership(
        source, source + np.array([[0, 0], [2, 0], [2.01, 0]]), identity
    ).tolist() == [1, 1, 0]


def test_final_membership_is_explicit_and_retains_original_world_ncc_and_cut_veto():
    import pytest

    original = seed()
    with pytest.raises(ValueError, match="requires explicit"):
        ReviewedWorldChain(original, BOXES, seed_membership="symmetric_final")
    chain = ReviewedWorldChain(
        original,
        BOXES,
        support_mode="adjacent_dense_world",
        dense_footprint="full_valid",
        seed_membership="symmetric_final",
    )
    sink = []
    row = chain.advance(np.roll(original, 1, axis=0), model_sink=sink)
    assert row["descriptive_supported"] and row["minimum_seed_ncc"] >= 0.90
    assert row["minimum_adjacent_ncc"] >= 0.90 and row["runtime_proof_authorized"] is False
    assert "selected_seed_inliers" in sink[0]
    assert (
        chain.advance(np.roll(original, 2, axis=0), discontinuity=True)["reason"]
        == "content_discontinuity"
    )


def test_passive_dense_model_sink_does_not_change_decisions_or_future_state():
    import cv2

    for mode in ("world_features", "dense_world", "adjacent_dense_world"):
        original = seed()
        plain = ReviewedWorldChain(original, BOXES, support_mode=mode)
        observed = ReviewedWorldChain(original, BOXES, support_mode=mode)
        for offset in (1, 2):
            current = np.roll(original, offset, axis=0)
            sink = []
            cv2.setRNGSeed(0)
            expected = plain.advance(current)
            cv2.setRNGSeed(0)
            actual = observed.advance(current, dense_model_sink=sink)
            assert actual == expected
            if mode == "world_features":
                assert sink == []
            else:
                assert len(sink) == 1
                sink[0]["model"][0][0] = 10000
