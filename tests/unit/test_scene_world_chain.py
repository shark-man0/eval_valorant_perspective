from __future__ import annotations

import numpy as np

from scripts.diagnostics.scene_world_chain import ReviewedWorldChain

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
