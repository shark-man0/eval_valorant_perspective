"""Synthetic image evidence ranking: no recorder ownership or timeline claims."""
from copy import deepcopy

import cv2
import numpy as np

from tests.unit.test_shared_game_timeline import obs
from valorant_ai_coach.temporal.game import observation
from valorant_ai_coach.temporal.map_marker_identity import attach_rank, pixel_rank


def scene():
    image = np.zeros((160, 240, 3), dtype=np.uint8)
    cv2.fillConvexPoly(
        image, np.array([[45, 45], [35, 63], [55, 63]], dtype=np.int32),
        (255, 255, 255),
    )
    cv2.circle(image, (110, 52), 8, (255, 220, 0), -1)
    cv2.circle(image, (170, 52), 8, (0, 190, 255), -1)
    return image, [
        {"center_frame_px": [45.0, 54.0]},
        {"center_frame_px": [110.0, 52.0]},
        {"center_frame_px": [170.0, 52.0]},
    ]


def test_local_white_arrow_ranks_before_colored_competitors():
    image, pool = scene()
    result = pixel_rank(image, pool, [20, 20, 190, 80])
    ranks = result["rankings"]
    assert ranks[0]["candidate_index"] == 0
    assert ranks[0]["white_triangle_support"] > 0
    assert result["ownership"] == "UNKNOWN" and not result["qualified"]
    assert all(h["score_scope"] == "heuristic_not_probability" for h in ranks)
    assert all(not h["qualified"] for h in ranks)
    no_roi = pixel_rank(image, pool, None)
    assert no_roi["selection_status"] == "ABSTAIN"
    assert no_roi["proposed_index"] is None
    assert [r["score"] for r in no_roi["rankings"]] == [r["score"] for r in ranks]


def test_dark_frame_and_duplicate_arrows_abstain():
    image, pool = scene()
    dark = pixel_rank(np.zeros_like(image), pool, [20, 20, 190, 80])
    assert dark["selection_status"] == "ABSTAIN"
    double = image.copy()
    cv2.fillConvexPoly(
        double, np.array([[85, 45], [75, 63], [95, 63]], dtype=np.int32),
        (255, 255, 255),
    )
    pool2 = pool + [{"center_frame_px": [85.0, 54.0]}]
    dup = pixel_rank(double, pool2, [20, 20, 190, 80])
    assert dup["selection_status"] == "ABSTAIN"


def test_exact_supplier_join_keeps_spectator_unowned():
    base = obs(0, ["spectator"])
    image, candidates = scene()
    pool = observation(
        sample=base["sample"], producer="d"*64, signals=[], raw={},
        map_candidates=candidates,
    )
    visual = observation(
        sample=base["sample"], producer="c"*64, signals=[],
        raw={
            "schema": "development_composite_view_pixels_v1",
            "marker_identity_supplier": pool["producer_fingerprint"],
            "marker_identity_pixels": pixel_rank(
                image, candidates, [20, 20, 190, 80]
            ),
        },
    )
    frame = {
        "sample": base["sample"],
        "camera": {"value": "SPECTATOR", "evidence_ids": [base["observation_id"]]},
        "map": {"research_map_correspondence_hypotheses": []},
    }
    attach_rank(frame, [base, pool, visual], pool)
    result = frame["map"]["research_marker_identity_ranking"]
    assert result["candidate_count"] == 3
    assert result["camera_candidate"] == "SPECTATOR"
    assert "RECORDER_SELF" not in result["role_hypotheses"]
    assert not result["qualified"] and not result["position_authority"]

    broken = deepcopy(visual)
    broken["sample"] = obs(1)["sample"]
    new_frame = deepcopy(frame)
    new_frame["map"] = {}
    attach_rank(new_frame, [base, pool, broken], pool)
    assert "research_marker_identity_ranking" not in new_frame["map"]


def test_duplicate_candidate_indices_cannot_join():
    base = obs(0)
    image, candidates = scene()
    pool = observation(
        sample=base["sample"], producer="d"*64, signals=[], raw={},
        map_candidates=candidates,
    )
    raw = pixel_rank(image, candidates, [20, 20, 190, 80])
    raw["rankings"][1]["candidate_index"] = raw["rankings"][0]["candidate_index"]
    visual = observation(
        sample=base["sample"], producer="c"*64, signals=[],
        raw={
            "schema": "development_composite_view_pixels_v1",
            "marker_identity_supplier": pool["producer_fingerprint"],
            "marker_identity_pixels": raw,
        },
    )
    frame = {
        "sample": base["sample"],
        "camera": {"value": "UNKNOWN", "evidence_ids": []},
        "map": {},
    }
    attach_rank(frame, [pool, visual], pool)
    assert frame["map"] == {}
