from copy import deepcopy

import cv2
import numpy as np
import pytest

from tests.unit.test_shared_game_timeline import obs
from valorant_ai_coach.temporal.evidence import digest, freeze_native_sample
from valorant_ai_coach.temporal.map_portrait_rim import (
    compare_recorder_anchor,
    measure_portrait_rims,
    shared_structure_groups,
)


def test_detached_icon_does_not_become_the_portrait_rim():
    image = np.zeros((160, 1920, 3), dtype=np.uint8)
    # Yellow portrait rim and two-tone interior, with a separate white icon.
    cv2.circle(image, (60, 50), 8, (0, 255, 250), 2)
    image[46:54, 55:60] = (60, 80, 115)
    image[46:54, 60:65] = (255, 255, 255)
    cv2.fillConvexPoly(image, np.array([[100, 42], [105, 46], [100, 50]]), (255, 255, 255))
    pool = [{"center_frame_px": [60, 50]}, {"center_frame_px": [102, 46]}]
    measured = measure_portrait_rims(image, pool)
    assert measured["candidates"][0]["features"] is not None
    assert measured["candidates"][1]["features"] is None
    assert shared_structure_groups(measured) == []


def test_hud_agreement_requires_bound_pixels_and_a_causal_anchor():
    sample = obs(1)["sample"]
    anchor = {"sample": obs(0)["sample"], "agent_candidates": [{"agent": "Example", "score": .95}]}
    frame = {"sample": sample, "camera": {"value": "SELF"}, "life": {"value": "ALIVE"},
             "viewed_identity": {"recording_player_anchor": anchor}}
    pool = [{"center_frame_px": [1, 1]}]
    measurement = {
        "native_pixel_sha256": sample["native_pixel_sha256"],
        "frame_size_px": sample["frame_size_px"], "ordered_candidate_pool_digest": digest(pool),
        "candidates": [{"candidate_index": 0,
                        "features": {"agent_candidates": [{"agent": "Example", "score": .75}]}}],
    }
    matched = compare_recorder_anchor(measurement, pool, frame)
    assert matched["agent_agreement_candidate_indices"] == [0]
    moved = deepcopy(frame)
    other_epoch = {k: v for k, v in anchor["sample"].items() if k != "sample_sha256"}
    other_epoch.update(native_epoch="foreign", acquisition_id="foreign")
    moved_anchor = moved["viewed_identity"]["recording_player_anchor"]
    moved_anchor["sample"] = freeze_native_sample(other_epoch)
    for blocked in (moved, {**frame, "camera": {"value": "SPECTATOR"}}):
        evidence = compare_recorder_anchor(measurement, pool, blocked)
        assert evidence["agent_agreement_candidate_indices"] == []
        assert evidence["recorder_proposed_index"] is None
    with pytest.raises(ValueError, match="do not match"):
        compare_recorder_anchor(measurement, [{"center_frame_px": [2, 2]}], frame)
