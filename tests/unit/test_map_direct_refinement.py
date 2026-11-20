from __future__ import annotations

import hashlib
from types import SimpleNamespace

import numpy as np
import pytest

from valorant_ai_coach.temporal.evidence import digest, freeze_native_sample
from valorant_ai_coach.temporal.map_direct_recorder import corroborate_direct_selection
from valorant_ai_coach.temporal.map_portrait_rendering import (
    fit_portrait_rendering,
    render_portrait,
)
from valorant_ai_coach.temporal.map_recorder_path import project_recorder_witness
from valorant_ai_coach.temporal.map_recording_alignment import RecordingMapAlignment


def test_fitted_witness_requires_same_image_agent_and_marker():
    direct = {"sample_sha256": "a", "support_count": 1, "support_candidate_index": 3,
              "support_center_frame_px": [60, 40], "recording_agent_uuid": "recorder",
              "selection_status": "ABSTAIN",
              "selection_reason": "direct_portrait_needs_adjacent_observation",
              "ownership": "UNKNOWN", "position_authority": False}
    legacy = {"sample_sha256": "a", "selection_status": "RESEARCH_SELECTED",
              "support_center_frame_px": [61, 40], "selection_method": "knowledge_agent_uuid",
              "recorder_agent_uuid_candidate": "recorder", "knowledge_reason": "matched_agent_uuid"}
    agreement = corroborate_direct_selection(direct, legacy, 1.)
    assert agreement["research_candidate_index"] == 3 and agreement["ownership"] == "UNKNOWN"
    for other in ({"support_center_frame_px": [76, 40]}, {"recorder_agent_uuid_candidate": "ally"},
                  {"selection_reason": "recorder_selection_conflict"}):
        result = corroborate_direct_selection(direct, {**legacy, **other}, 1.)
        assert result["selection_status"] == "ABSTAIN" and result["support_count"] == 0
    assert corroborate_direct_selection(direct, {**legacy, "sample_sha256": "b"}, 1.) == direct
    assert corroborate_direct_selection(
        direct, {**legacy, "recorder_agent_uuid_candidate": None}, 1.,
    ) == direct


def test_recording_map_recovery_checks_current_geometry_and_source_scope():
    identity = np.eye(3)
    first = {"map_id": "m", "reference_to_roi_homography_candidate": identity.tolist()}
    ok = {"map_name_candidates": [first]}
    weak = {"map_name_candidates": [], "reference_ranking": [{**first, "inliers": 15}],
            "roi_pixel_bounds": [0, 0, 100, 100]}
    other = {"map_name_candidates": [{**first, "map_id": "other-map"}]}
    reader = SimpleNamespace(inspect=lambda image: {"raw": ok})
    align = RecordingMapAlignment(reader)
    image = np.zeros((100, 100, 3), np.uint8)

    def sample(tick, source="s"):
        return {"source_id": source, "source_sha256": source, "acquisition_id": "capture",
                "native_epoch": "e", "native_time_base": "1/10", "native_pts_tick": tick,
                "native_pixel_sha256": str(tick), "frame_size_px": [100, 100]}

    for tick in (0, 20):
        assert align.inspect(image, sample(tick), ok) == ok
    assert align.inspect(image, sample(21), weak) == weak
    align.inspect(image, sample(40), ok)
    assert align.map_uuid == "m"
    assert align.inspect(image, sample(41), weak)["map_name_candidates"] == [first]
    assert align.inspect(image, sample(41), other)["map_name_candidates"] == []
    shifted = identity.copy()
    shifted[0, 2] = 15
    reader.inspect = lambda image: {"raw": {"map_name_candidates": [
        {**first, "reference_to_roi_homography_candidate": shifted.tolist()},
    ]}}
    assert align.inspect(image, sample(43), weak) == weak
    assert align.inspect(image, sample(41, source="new"), weak) == weak
    assert align.map_uuid is None


def test_color_rendering_preserves_alpha_and_requires_supported_train_examples():
    rng = np.random.default_rng(104)
    image = rng.integers(0, 256, (9, 9, 4), dtype=np.uint8)
    rgb = image[:, :, :3]
    matrix = fit_portrait_rendering([("a", rgb)], [("a", rgb.astype(float))]*3)
    np.testing.assert_allclose(matrix, np.eye(3), atol=1e-9)
    assert np.array_equal(render_portrait(image, matrix)[:, :, 3], image[:, :, 3])
    with pytest.raises(ValueError, match="Insufficient"):
        fit_portrait_rendering([("a", rgb)], [])


def test_aligned_proposals_keep_the_strong_single_frame_witness():
    from valorant_ai_coach.temporal.map_direct_recorder import (
        DirectPeak,
        DirectRecorderTracker,
        RecorderUUID,
    )

    strong = DirectPeak((52, 61), .89, 12, 4, 0)
    marginal = DirectPeak((53, 61), .96, 6, 1, 0)

    def scores(image, center):
        return np.array([.89 if center == strong.center else .96, .30])

    tracker = DirectRecorderTracker(
        SimpleNamespace(peaks=lambda *a, **kw: [strong]),
        RecorderUUID("s", "a", ("p",)),
        SimpleNamespace(_uuids=("a", "b"), _portrait_scores=scores),
        fallback_search=SimpleNamespace(peaks=lambda *a, **kw: [marginal]),
        compare_centers=True,
    )
    sample = {"sample_sha256": "x", "source_sha256": "s"}
    img = np.zeros((100, 1920, 3), np.uint8)
    _, result = tracker._observe_measured(img, (0, 0, 100, 100), sample, {}, "camera")
    assert result["research_marker_center_frame_px"] == list(strong.center)


def test_native_flow_needs_current_landmarks_and_cannot_chain():
    import cv2

    from valorant_ai_coach.temporal.map_recording_alignment import NativeMapFlowAlignment

    flow = NativeMapFlowAlignment()
    image = np.random.default_rng(13).integers(0, 255, (160, 160, 3), np.uint8)
    matrix = np.eye(3)
    matrix[:2, 2] = (2, 1)
    moved = cv2.warpAffine(image, matrix[:2], (160, 160))
    previous = {"source_id": "m", "source_sha256": "a"*64, "acquisition_id": "a",
                "native_epoch": "a", "native_time_base": "1/10", "native_pts_tick": 40,
                "acquired_frame_sha256": "b"*64, "frame_size_px": [160, 160],
                "native_pixel_sha256": hashlib.sha256(image.tobytes()).hexdigest()}
    sample = freeze_native_sample({
        **previous, "native_pts_tick": 42,
        "native_pixel_sha256": hashlib.sha256(moved.tobytes()).hexdigest(),
    })
    hit = {"map_id": "map", "reference_to_roi_homography_candidate": np.eye(3).tolist(),
           "fit_residual_p95_reference_px": 1., "qualified": False,
           "position_authority": False}
    anchor = {"map_name_candidates": [hit], "roi_pixel_bounds": [0, 0, 160, 160]}
    ranked = {**hit, "inliers": 17, "reference_to_roi_homography_candidate": matrix.tolist()}
    current = {
        **anchor, "map_name_candidates": [], "reference_ranking": [ranked],
        "marker_transform_qualified": False, "roi_pixel_sha256": sample["native_pixel_sha256"],
    }

    def recover(s, row):
        return flow.recover(moved, s, "track", row, (80, 80), "map", carry=True)

    flow.remember(image, previous, "track", anchor)
    result = recover(sample, current)
    assert result["alignment_recovery"] == "native_flow"
    assert recover(sample, current) == current
    pool = [{"center_frame_px": [80, 80]}]
    selection = {
        "contract": "development_map_recorder_selection_v1",
        "sample_sha256": sample["sample_sha256"], "ordered_candidate_pool_digest": digest(pool),
        "support_count": 2, "support_candidate_index": 0, "research_candidate_index": 0,
        "support_center_frame_px": [80, 80], "selection_status": "RESEARCH_SELECTED",
        "qualified": False, "position_authority": False,
    }
    assets = {"map": "c"*64}
    projected = project_recorder_witness(moved, sample, pool, selection, result,
                                         reference_sha256s=assets)
    assert projected is not None and projected["alignment_recovery"] == "native_flow"
    np.testing.assert_allclose(projected["map_reference_px"], [78, 79], atol=.1)
    for tampered in (
        {**result, "alignment_recovery": None},
        {**result, "roi_pixel_sha256": "d"*64},
    ):
        assert project_recorder_witness(moved, sample, pool, selection, tampered,
                                        reference_sha256s=assets) is None
    for s, row in [
        ({**sample, "native_pts_tick": 44}, current),
        ({**sample, "native_epoch": "disconnected"}, current),
        (sample, {**current, "reference_ranking": []}),
        (sample, {**current, "reference_ranking": [{**ranked, "map_id": "other"}]}),
    ]:
        flow.remember(image, previous, "track", anchor)
        assert recover(s, row) == row


def test_adjacent_portrait_recovery_requires_independent_anchor_and_does_not_chain():
    from valorant_ai_coach.temporal.map_direct_recorder import (
        ADJACENT_PORTRAIT_REASON,
        DirectPeak,
        DirectRecorderTracker,
        RecorderUUID,
    )

    image = np.random.default_rng(218).integers(0, 255, (100, 1920, 3), dtype=np.uint8)
    portrait = DirectPeak((50, 50), .92, 10, 4, 0)
    scores = [.93, .50]
    reader = SimpleNamespace(_uuids=("a", "b"), _portrait_scores=lambda *args: np.array(scores))
    tracker = DirectRecorderTracker(
        SimpleNamespace(peaks=lambda *a, **kw: [portrait]),
        RecorderUUID("a"*64, "a", ("p",)),
        reader,
        recover_adjacent_portrait=True,
    )
    frame = {"round_token": "round-1", "continuity": {"carry_allowed": True}}

    def observe(tick, camera="self"):
        image[0, 0, 0] = tick
        sample = freeze_native_sample({
            "source_id": "match", "source_sha256": "a"*64, "acquisition_id": "e",
            "native_epoch": "e", "native_pts_tick": tick, "native_time_base": "1/10",
            "acquired_frame_sha256": "b"*64, "frame_size_px": [1920, 100],
            "native_pixel_sha256": hashlib.sha256(image.tobytes()).hexdigest(),
        })
        _, result = tracker._observe_measured(image, (0, 0, 100, 100), sample, frame, camera)
        return result

    assert observe(0)["selection_status"] == "RESEARCH_SELECTED"
    tracker.remember_projection(image)
    scores[:] = [.81, .75]
    recovered = observe(2)
    assert recovered["selection_reason"] == ADJACENT_PORTRAIT_REASON
    assert recovered["support_center_frame_px"] == [50, 50]
    assert observe(4)["selection_status"] == "ABSTAIN"

    scores[:] = [.93, .50]
    assert observe(6)["selection_status"] == "RESEARCH_SELECTED"
    tracker.remember_projection(image)
    scores[:] = [.81, .75]
    assert observe(8, camera="spectator")["selection_status"] == "ABSTAIN"
