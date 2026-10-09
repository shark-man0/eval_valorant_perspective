from __future__ import annotations

from copy import deepcopy
from itertools import count

import cv2
import numpy as np
import pytest

from valorant_ai_coach.hud.global_lifecycle import GlobalLifecycleQualification
from valorant_ai_coach.hud.source_continuity import CompositeSourceContinuity


def producer() -> CompositeSourceContinuity:
    return CompositeSourceContinuity(
        GlobalLifecycleQualification(
            "a" * 64,
            "b" * 64,
            frozenset({"timer", "purchase_phase", "continuity"}),
            "c" * 64,
        )
    )


def frame(seed: int = 7) -> np.ndarray:
    image = np.random.default_rng(seed).integers(0, 256, (360, 640, 3), dtype=np.uint8)
    return cv2.GaussianBlur(image, (5, 5), 0)


_source_sequence = count(1)


def source_step(
    tracker: CompositeSourceContinuity,
    image: np.ndarray,
    row: dict,
    evidence: dict,
    *,
    geometry_valid: bool,
) -> dict:
    # Ordinary video fixtures have evolving HUD pixels outside the tested camera
    # region. Stale-source tests below intentionally call advance without this.
    current = image.copy()
    sequence = next(_source_sequence)
    current[0, 0] = (sequence >> 16 & 255, sequence >> 8 & 255, sequence & 255)
    return tracker.advance(current, row, evidence, geometry_valid=geometry_valid)


def observation(pts: float, timer: float | None, *, phase: bool = False) -> dict:
    return {
        "time_sec": pts,
        "primary_state": "unknown",
        "state_flags": ["buy_phase_banner"] if phase else [],
        "values": {"round_time_remaining_sec": timer, "buy_phase_visible": phase},
        "quality": {
            "roi_confidence": {
                "round_timer_value": 0.96,
                "center_phase_banner_semantic_text": 0.95 if phase else 0,
            }
        },
    }


def test_unknown_identity_composite_proof_does_not_write_player_facts() -> None:
    tracker = producer()
    a, b = observation(1, 60), observation(1.2, 60)
    original = deepcopy(b)
    image = frame()
    assert source_step(tracker, image, a, {}, geometry_valid=True) == {}
    proof = source_step(tracker, image, b, {}, geometry_valid=True)
    assert proof["source_pts_sec"] == 1.2
    assert proof["previous_source_pts_sec"] == 1
    assert proof["qualification_sha256"] == "b" * 64
    assert proof["confidence"] >= 0.90
    assert len(proof["camera_witness_cells"]) == 9
    assert b == original


def test_qualified_phase_reset_can_preserve_composite_segment() -> None:
    tracker = producer()
    image = frame()
    source_step(tracker, image, observation(1, 0, phase=True), {}, geometry_valid=True)
    first = source_step(tracker, image, observation(1.1, 0, phase=True), {}, geometry_valid=True)
    reset = source_step(tracker, image, observation(1.2, 100), {}, geometry_valid=True)
    assert first["segment"] == reset["segment"]


def test_timer_reset_without_phase_breaks_segment() -> None:
    tracker = producer()
    image = frame()
    source_step(tracker, image, observation(1, 0), {}, geometry_valid=True)
    assert source_step(tracker, image, observation(1.1, 100), {}, geometry_valid=True) == {}
    assert tracker.last_reason == "timer_transition_inconsistent"


@pytest.mark.parametrize("current", [None, 2, 62])
def test_unavailable_or_impossible_countdown_is_not_continuity(current: float | None) -> None:
    tracker = producer()
    image = frame()
    source_step(tracker, image, observation(1, 60), {}, geometry_valid=True)
    assert source_step(tracker, image, observation(1.1, current), {}, geometry_valid=True) == {}


@pytest.mark.parametrize("pts", [1.0, 0.9, 2.1, float("nan"), True])
def test_bad_pts_or_gap_cannot_inherit_segment(pts: float) -> None:
    tracker = producer()
    image = frame()
    source_step(tracker, image, observation(1, 60), {}, geometry_valid=True)
    assert source_step(tracker, image, observation(pts, 60), {}, geometry_valid=True) == {}


def test_discontinuity_or_abstention_changes_next_segment() -> None:
    tracker = producer()
    image = frame()
    source_step(tracker, image, observation(1, 60), {}, geometry_valid=True)
    first = source_step(tracker, image, observation(1.1, 60), {}, geometry_valid=True)
    assert (
        source_step(
            tracker, image, observation(1.2, 60), {"content_jump": True}, geometry_valid=True
        )
        == {}
    )
    second = source_step(tracker, image, observation(1.3, 60), {}, geometry_valid=True)
    assert first["segment"] != second["segment"]


def test_invalid_geometry_cannot_supply_previous_frame_proof() -> None:
    tracker = producer()
    image = frame()
    source_step(tracker, image, observation(1, 60), {}, geometry_valid=True)
    assert source_step(tracker, image, observation(1.1, 60), {}, geometry_valid=False) == {}
    assert source_step(tracker, image, observation(1.2, 60), {}, geometry_valid=True) == {}
    assert source_step(tracker, image, observation(1.3, 60), {}, geometry_valid=True)


@pytest.mark.parametrize("mode", ["unrelated", "flat", "one_cell"])
def test_camera_witnesses_must_be_nonflat_and_spatially_distributed(mode: str) -> None:
    tracker = producer()
    first, second = frame(), frame(42)
    if mode == "flat":
        first.fill(80)
        second.fill(80)
    elif mode == "one_cell":
        second[72:144, 128:277] = first[72:144, 128:277]
    source_step(tracker, first, observation(1, 60), {}, geometry_valid=True)
    assert source_step(tracker, second, observation(1.1, 60), {}, geometry_valid=True) == {}
    assert tracker.last_reason == "insufficient_spatial_camera_support"


def test_external_token_cannot_replace_actual_source_witnesses() -> None:
    tracker = producer()
    source_step(tracker, frame(), observation(1, 60), {}, geometry_valid=True)
    assert (
        source_step(
            tracker,
            frame(42),
            observation(1.1, 60),
            {
                "global_continuity_segment": "injected",
                "global_continuity_confidence": 1,
            },
            geometry_valid=True,
        )
        == {}
    )


@pytest.mark.parametrize("score", [0.89, float("nan"), True, None, 2.0])
def test_weak_or_invalid_timer_confidence_breaks_link(score: object) -> None:
    tracker = producer()
    image = frame()
    source_step(tracker, image, observation(1, 60), {}, geometry_valid=True)
    current = observation(1.1, 60)
    current["quality"]["roi_confidence"]["round_timer_value"] = score
    assert source_step(tracker, image, current, {}, geometry_valid=True) == {}
    assert tracker.last_reason == "accepted_timer_pair_unavailable"


def test_identical_pixels_at_different_pts_cannot_corroborate_continuity() -> None:
    tracker = producer()
    image = frame()
    assert tracker.advance(image, observation(1, 60), {}, geometry_valid=True) == {}
    assert tracker.advance(image.copy(), observation(1.1, 60), {}, geometry_valid=True) == {}
    assert tracker.last_reason == "duplicate_source_pixels"


def test_stale_source_break_cannot_restore_prior_segment() -> None:
    tracker = producer()
    image = frame()
    source_step(tracker, image, observation(1, 60), {}, geometry_valid=True)
    first = source_step(tracker, image, observation(1.1, 60), {}, geometry_valid=True)
    # Reproduce the exact latest fixture source pixels at a new presentation PTS.
    frozen = image.copy()
    # Independently seed two source frames to make the repeated image explicit.
    tracker.advance(frozen, observation(1.2, 60), {}, geometry_valid=True)
    assert tracker.advance(frozen, observation(1.3, 60), {}, geometry_valid=True) == {}
    resumed = source_step(tracker, image, observation(1.4, 60), {}, geometry_valid=True)
    assert resumed["segment"] != first["segment"]
    assert resumed["source_pixel_sha256"] != resumed["previous_source_pixel_sha256"]


@pytest.mark.parametrize("scale", [1, 3])
def test_phase_pixels_do_not_change_any_camera_witness(scale):
    before, after = frame(15), frame(15)
    if scale != 1:
        before = cv2.resize(before, (640 * scale, 360 * scale), interpolation=cv2.INTER_NEAREST)
        after = before.copy()
    expected = CompositeSourceContinuity.camera_support(
        CompositeSourceContinuity.camera_image(before),
        CompositeSourceContinuity.camera_image(after),
    )
    x1, y1, x2, y2 = CompositeSourceContinuity.PHASE_EXCLUSION
    before[y1 * scale : y2 * scale, x1 * scale : x2 * scale] = 0
    after[y1 * scale : y2 * scale, x1 * scale : x2 * scale] = 255
    actual = CompositeSourceContinuity.camera_support(
        CompositeSourceContinuity.camera_image(before),
        CompositeSourceContinuity.camera_image(after),
    )
    assert actual == expected


def test_shared_phase_overlay_cannot_create_background_witnesses():
    before, after = frame(19), frame(42)
    x1, y1, x2, y2 = CompositeSourceContinuity.PHASE_EXCLUSION
    # Shared structured panel over unrelated world images is a negative control.
    after[y1:y2, x1:x2] = before[y1:y2, x1:x2]
    assert not CompositeSourceContinuity.camera_support(
        CompositeSourceContinuity.camera_image(before),
        CompositeSourceContinuity.camera_image(after),
    )


def test_phase_exclusion_does_not_relax_timer_anomaly_or_content_cut():
    for evidence in ({}, {"content_jump": True}):
        tracker = producer()
        source_step(tracker, frame(9), observation(1, 0), {}, geometry_valid=True)
        assert not source_step(
            tracker, frame(9), observation(1.1, 100), evidence, geometry_valid=True
        )
        assert tracker.last_reason in {"timer_transition_inconsistent", "explicit_discontinuity"}
