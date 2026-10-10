import hashlib
from dataclasses import replace

import numpy as np
import pytest

from scripts.diagnostics.scene_world_review_gate import FrameWorldReview, ReviewedSceneDiagnostic

BOXES = ((20, 50, 100, 115), (20, 160, 100, 250), (450, 150, 550, 250))
DOMAINS = ((10, 40, 110, 125), (10, 150, 110, 260), (440, 140, 560, 260))


def frame_review(image, tick, boxes=BOXES):
    return FrameWorldReview(
        "a" * 64,
        hashlib.sha256(image.tobytes()).hexdigest(),
        tick,
        "same-epoch",
        tuple((box, "world_only") for box in boxes),
        "synthetic reviewed world",
    )


def tracker(seed):
    return ReviewedSceneDiagnostic(
        seed,
        frame_review(seed, 1024),
        source_video_sha256="a" * 64,
        source_epoch="same-epoch",
        projected=True,
    )


def seed():
    return np.random.default_rng(62).integers(0, 256, (360, 640), dtype=np.uint8)


def test_continuous_projected_chain_retains_identities_and_original_floors():
    source = seed()
    chain = tracker(source)
    identities = {(p["region"], *p["seed_xy"]) for p in chain.chain.tracks}
    for offset in (1, 2, 3):
        image = np.roll(source, offset, axis=1)
        result = chain.advance(image, frame_review(image, 1024 + 256 * offset, DOMAINS))
        assert result["descriptive_supported"]
        assert result["runtime_proof_authorized"] is False
        assert result["minimum_seed_ncc"] >= 0.90
        assert result["minimum_adjacent_ncc"] >= 0.90
        assert all(row["valid_fraction"] >= 0.90 for row in result["dense_world_regions"])
        retained = {(p["region"], *p["seed_xy"]) for p in chain.chain.tracks}
        assert retained <= identities
        identities = retained


@pytest.mark.parametrize("failure", ["gap", "epoch", "occlusion", "cut", "missing"])
def test_projected_chain_never_rejoins_after_source_or_review_break(failure):
    source = seed()
    chain = tracker(source)
    image = np.roll(source, 1, axis=1)
    review = frame_review(image, 1280, DOMAINS)
    if failure == "gap":
        review = replace(review, source_pts_ticks=1536)
    elif failure == "epoch":
        review = replace(review, source_epoch="new-epoch")
    elif failure == "occlusion":
        review = replace(review, regions=((DOMAINS[0], "unknown"),) + review.regions[1:])
    elif failure == "missing":
        review = None
    result = chain.advance(image, review, discontinuity=failure == "cut")
    assert not result["descriptive_supported"]
    assert not chain.chain.tracks
    next_image = np.roll(source, 2, axis=1)
    assert chain.advance(next_image, frame_review(next_image, 1536, DOMAINS))["reason"] == (
        "reviewed_chain_terminated"
    )


def test_projected_direct_interface_requires_fresh_world_mask():
    source = seed()
    chain = tracker(source)
    current = np.roll(source, 1, axis=1)
    assert chain.chain.advance(current)["reason"] == "current_world_mask_missing_or_invalid"
    assert not chain.chain.tracks


def test_overlapping_unknown_review_cannot_be_hidden_by_larger_world_box():
    source = seed()
    review = frame_review(source, 1024, DOMAINS)
    review = replace(review, regions=review.regions + ((BOXES[0], "unknown"),))
    with pytest.raises(ValueError, match="contradictory"):
        ReviewedSceneDiagnostic(
            source,
            review,
            source_video_sha256="a" * 64,
            source_epoch="same-epoch",
            projected=True,
        )


def test_complete_temporal_result_is_independent_of_excluded_pixels():
    source = seed()
    current = np.roll(source, 1, axis=1)
    ordinary = tracker(source)
    expected = ordinary.advance(current, frame_review(current, 1280, DOMAINS))
    source_mask = ordinary._mask(source, BOXES)
    current_mask = ordinary._mask(current, DOMAINS)
    modified_source, modified_current = source.copy(), current.copy()
    modified_source[~source_mask] = 0
    modified_current[~current_mask] = 255
    changed = tracker(modified_source)
    actual = changed.advance(modified_current, frame_review(modified_current, 1280, DOMAINS))
    assert actual == expected
