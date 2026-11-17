from __future__ import annotations

import hashlib
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from valorant_ai_coach.temporal.evidence import freeze_native_sample
from valorant_ai_coach.temporal.game import observation
from valorant_ai_coach.temporal.map_direct_recorder import (
    DensePortraitSearch,
    DirectPeak,
    DirectRecorderTracker,
    RecorderUUID,
)


def _sample(image, tick=0, source="a"):
    return freeze_native_sample({
        "source_id": "example", "source_sha256": source*64,
        "acquisition_id": "capture", "native_epoch": "capture",
        "native_pts_tick": tick, "native_time_base": "1/10",
        "acquired_frame_sha256": "e"*64,
        "native_pixel_sha256": hashlib.sha256(image.tobytes()).hexdigest(),
        "frame_size_px": list(image.shape[:2][::-1]),
    })


def test_source_identity_requires_spaced_distinct_votes():
    base = np.full((32, 32, 3), 120, np.uint8)
    samples = [_sample(base + i, i*30) for i in range(5)]
    assert RecorderUUID.bind([(samples[0], "r")] * 4) is None
    assert RecorderUUID.bind([(s, "r" if i % 2 else "other")
                              for i, s in enumerate(samples)]) is None
    one = RecorderUUID.bind([(s, "r") for s in samples])
    assert one and one.source_sha256 == "a"*64 and len(one.evidence_samples) == 5
    with pytest.raises(ValueError, match="one source"):
        RecorderUUID.bind([(samples[0], "r"), (_sample(base + 1, 30, "b"), "r")])


def test_search_locates_a_portrait_without_candidate_pool():
    avatar = np.random.default_rng(10).integers(20, 230, (15, 15, 3), dtype=np.uint8)
    search = DensePortraitSearch([("r", avatar)], augment=False)
    view = np.full((140, 180, 3), 70, np.uint8)
    view[43:58, 89:104] = avatar
    cv2.circle(view, (96, 50), 8, (165, 246, 248), 1)
    peak = search.peaks(view, "r", scale=1.0)[0]
    assert peak.center == (96, 50) and peak.response > .98
    assert peak.warm_sectors >= 9


def test_recording_identity_does_not_prove_current_view():
    frame_pixels = np.zeros((220, 1920, 3), np.uint8)
    sample = _sample(frame_pixels)
    identity = RecorderUUID("a"*64, "r", (sample["sample_sha256"],))
    peaks = [DirectPeak((50, 65), .9, 12, 5, 0)]
    detector = DirectRecorderTracker(
        SimpleNamespace(peaks=lambda *args, **kwargs: peaks),
        identity,
        SimpleNamespace(_uuids=("r", "t"), _portrait_scores=lambda *args: np.array([.93, .49])),
    )
    panel = observation(
        sample=sample, producer="c"*64, signals=["owner_hud"],
        context={"stream_kind": "camera_panel"},
        raw={"camera_panel": {"label": {"checked": True, "state": "ABSENT"},
                              "own_ability_bar_score": .9},
             "qualified": False, "formal_outputs": 0},
    )
    oid = panel["observation_id"]
    frame = {"sample": sample, "observation_ids": [oid],
             "camera": {"value": "SELF", "evidence_ids": [oid]}, "life": {"value": "ALIVE"}}
    pool, selected = detector.observe(frame_pixels, (0, 0, 155, 158), frame, [panel])
    assert len(pool) == 1 and selected["research_candidate_index"] == 0
    assert selected["ownership"] == "UNKNOWN" and not selected["position_authority"]
    peaks.append(DirectPeak((80, 65), .94, 13, 5, 0))
    _, ambiguity = detector.observe(frame_pixels, (0, 0, 155, 158), frame, [panel])
    assert ambiguity["selection_reason"] == "ambiguous_direct_portraits"
    assert detector.previous is None
    frame["viewed_identity"] = {"agent_signature_relation": "DIFFERENT"}
    _, conflict = detector.observe(frame_pixels, (0, 0, 155, 158), frame, [panel])
    assert conflict["selection_reason"] == "viewed_identity_conflicts_with_recording"
    frame["camera"]["value"] = "SPECTATOR"
    pool, skipped = detector.observe(frame_pixels, (0, 0, 155, 158), frame, [panel])
    assert pool == [] and skipped["recording_agent_uuid"] == "r"
    assert skipped["support_count"] == 0 and skipped["research_candidate_index"] is None


def test_tipless_track_requires_fresh_observations_inside_one_camera_and_round():
    image = np.zeros((220, 1920, 3), np.uint8)
    detector = DirectRecorderTracker(
        SimpleNamespace(peaks=lambda *args, **kwargs: [DirectPeak((50, 65), .85, 7, 2, 0)]),
        RecorderUUID("a"*64, "r", ()),
        SimpleNamespace(_uuids=("r", "t"), _portrait_scores=lambda *args: np.array([.85, .49])),
    )
    frame = {"round_token": "round-1", "continuity": {"carry_allowed": True}}

    def measure(tick, camera="camera-1"):
        image[0, 0, 0] = tick
        _, result = detector._observe_measured(
            image, (0, 0, 155, 158), _sample(image, tick), frame, camera,
        )
        return result["selection_status"]

    assert measure(0) == "ABSTAIN"
    assert measure(2) == "RESEARCH_SELECTED"
    assert measure(5) == "ABSTAIN"
    assert measure(7, "camera-2") == "ABSTAIN"
    frame["round_token"] = "round-2"
    assert measure(9, "camera-2") == "ABSTAIN"
    assert measure(11, "camera-2") == "RESEARCH_SELECTED"
