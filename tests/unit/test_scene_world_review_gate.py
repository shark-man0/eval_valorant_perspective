import hashlib
from dataclasses import replace

import numpy as np
import pytest

from scripts.diagnostics.scene_correspondence import SCALED_BACKGROUND_BOXES
from scripts.diagnostics.scene_world_review_gate import (
    FrameWorldReview,
    ReviewedSceneDiagnostic,
    approved_world_boxes,
)


def inputs():
    image = np.random.default_rng(41).integers(0, 256, (360, 640), dtype=np.uint8)
    review = FrameWorldReview(
        "a" * 64,
        hashlib.sha256(image.tobytes()).hexdigest(),
        1000,
        "camera-epoch",
        tuple((box, "world_only") for box in SCALED_BACKGROUND_BOXES),
        "independent image review",
    )
    return image, review


def test_source_binding_and_unknown_regions_are_not_world_labels():
    image, review = inputs()
    assert approved_world_boxes(image, review, "a" * 64, "camera-epoch") == SCALED_BACKGROUND_BOXES
    for bad in (
        replace(review, source_video_sha256="b" * 64),
        replace(review, input_pixel_sha256="b" * 64),
        replace(review, source_epoch="after-cut"),
        replace(review, provenance=""),
        replace(review, provenance=None),
        replace(review, regions=None),
        replace(review, source_pts_ticks=True),
        replace(review, regions=tuple((box, "unknown") for box in SCALED_BACKGROUND_BOXES)),
    ):
        with pytest.raises(ValueError):
            approved_world_boxes(image, bad, "a" * 64, "camera-epoch")


def test_review_cannot_import_timer_phase_or_duplicate_boxes():
    image, review = inputs()
    for boxes in (
        ((0, 0, 100, 40),),
        ((224, 30, 416, 120),),
        (SCALED_BACKGROUND_BOXES[0], SCALED_BACKGROUND_BOXES[0]),
    ):
        bad = replace(review, regions=tuple((box, "world_only") for box in boxes))
        with pytest.raises(ValueError):
            approved_world_boxes(image, bad, "a" * 64, "camera-epoch")


@pytest.mark.parametrize("failure", ["missing", "occlusion", "gap", "stale", "epoch", "cut"])
def test_current_review_failure_terminates_without_reacquisition(failure):
    image, review = inputs()
    tracker = ReviewedSceneDiagnostic(
        image, review, source_video_sha256="a" * 64, source_epoch="camera-epoch"
    )
    current = replace(review, source_pts_ticks=1256)
    if failure == "missing":
        current = None
    elif failure == "occlusion":
        current = replace(
            current, regions=((SCALED_BACKGROUND_BOXES[0], "contaminated"),) + current.regions[1:]
        )
    elif failure == "gap":
        current = replace(current, source_pts_ticks=1512)
    elif failure == "stale":
        current = review
    elif failure == "epoch":
        current = replace(current, source_epoch="after-cut")
    result = tracker.advance(image, current, discontinuity=failure == "cut")
    assert not result["descriptive_supported"]
    assert not tracker.chain.tracks
    assert not tracker.advance(image, replace(review, source_pts_ticks=1512))[
        "descriptive_supported"
    ]


def test_valid_review_does_not_make_duplicate_images_continuous():
    image, review = inputs()
    tracker = ReviewedSceneDiagnostic(
        image, review, source_video_sha256="a" * 64, source_epoch="camera-epoch"
    )
    result = tracker.advance(image, replace(review, source_pts_ticks=1256))
    assert result["reason"] == "duplicate_image"
    assert not result["descriptive_supported"]


def test_reviewed_translation_keeps_original_identities_without_runtime_authority():
    image, review = inputs()
    tracker = ReviewedSceneDiagnostic(
        image, review, source_video_sha256="a" * 64, source_epoch="camera-epoch"
    )
    originals = {(t["region"], *t["seed_xy"]) for t in tracker.chain.tracks}
    current = np.roll(image, 1, axis=0)
    current_review = replace(
        review,
        source_pts_ticks=1256,
        input_pixel_sha256=hashlib.sha256(current.tobytes()).hexdigest(),
    )
    result = tracker.advance(current, current_review)
    assert result["descriptive_supported"]
    assert result["runtime_proof_authorized"] is False
    assert {(t["region"], *t["seed_xy"]) for t in tracker.chain.tracks} <= originals
    assert result["minimum_seed_ncc"] >= 0.90
    assert result["minimum_adjacent_ncc"] >= 0.90
