"""Map v2: keep legacy ranks, group nearby proposals and abstain on ownership."""
from copy import deepcopy

import cv2
import numpy as np

from tests.unit.test_shared_game_timeline import obs
from valorant_ai_coach.temporal.evidence import digest
from valorant_ai_coach.temporal.game import observation
from valorant_ai_coach.temporal.map_marker_identity import attach_rank, pixel_rank


def case(camera="SELF", life="ALIVE", bound=True):
    base = obs(0, ["owner_hud"])
    image = np.zeros((160, 240, 3), np.uint8)
    cv2.fillConvexPoly(
        image, np.array([[48, 42], [38, 64], [58, 64]], np.int32), (255, 255, 255)
    )
    # Two close proposals for the same location; a distinct colored candidate.
    pool_values = [
        {"center_frame_px": [48.0, 53.0]},
        {"center_frame_px": [51.0, 54.0]},
        {"center_frame_px": [150.0, 54.0]},
    ]
    pool = observation(
        sample=base["sample"], producer="d"*64, signals=[],
        raw={}, map_candidates=pool_values,
    )
    context = [
        {"candidate_index": 2, "score": 2.0},
        {"candidate_index": 1, "score": 1.9},
        {"candidate_index": 0, "score": 1.8},
    ]
    raw = {
        "schema": "development_composite_view_pixels_v1",
        "marker_identity_supplier": pool["producer_fingerprint"],
        "marker_identity_pixels": pixel_rank(
            image, pool_values, [20, 20, 190, 80]
        ),
        "marker_context_rankings": context,
        "marker_candidate_supplier": pool["producer_fingerprint"],
    }
    if bound:
        raw["marker_identity_pool_digest"] = digest(pool_values)
    visual = observation(
        sample=base["sample"], producer="c"*64, signals=[], raw=raw
    )
    role = [{
        "role_hypotheses": ["RECORDER_SELF", "OTHER", "UNKNOWN"],
    }]
    frame = {
        "sample": base["sample"],
        "camera": {"value": camera, "evidence_ids": [base["observation_id"]]},
        "life": {"value": life, "evidence_ids": [base["observation_id"]]},
        "map": {
            "marker_ranking_hypotheses": {
                "rankings": context,
                "map_supplier_fingerprint": pool["producer_fingerprint"],
            },
            "research_map_correspondence_hypotheses": role,
        },
    }
    return frame, [base, pool, visual], pool


def test_v2_restores_original_top1_and_groups_nearby_proposals():
    frame, rows, pool = case()
    attach_rank(frame, rows, pool)
    v2 = frame["map"]["research_recorder_marker_v2"]
    assert v2["baseline_context_order"] == [2, 1, 0]
    assert v2["baseline_top_index"] == 2
    assert v2["spatial_diversified_order"][0]["candidate_index"] == 2
    assert v2["spatial_diversified_order"][1]["candidate_index"] == 1
    assert v2["proximity_groups"][1]["member_indices"] == [1, 0]
    assert v2["ordered_candidate_pool_digest"] == digest(pool["map_candidates"])
    assert v2["pixel_override_accepted"] is False
    assert v2["recorder_proposed_index"] is None
    assert v2["selection_status"] == "ABSTAIN"
    v1 = frame["map"]["research_marker_identity_ranking"]
    assert v1["proposed_index"] is None
    assert v1["selection_status"] == "ABSTAIN"


def test_spectator_remote_and_dead_views_never_select_recorder():
    for camera, life in (("SPECTATOR", "DEAD"), ("REMOTE", "ALIVE"),
                         ("SELF", "DEAD"), ("UNKNOWN", "ALIVE")):
        frame, rows, pool = case(camera, life)
        attach_rank(frame, rows, pool)
        result = frame["map"]["research_recorder_marker_v2"]
        assert result["camera_life_gate"] is False
        assert result["recorder_proposed_index"] is None
        assert result["abstain_reason"] == "not_current_recorder_view"
        assert frame["map"]["research_marker_identity_ranking"]["proposed_index"] is None


def test_no_independent_owner_link_abstains_even_with_self_camera():
    frame, rows, pool = case()
    attach_rank(frame, rows, pool)
    result = frame["map"]["research_recorder_marker_v2"]
    assert result["camera_life_gate"]
    assert result["self_role_gate"]
    assert result["abstain_reason"] == "no_independent_candidate_recorder_correspondence"
    assert result["ownership"] == "UNKNOWN"
    assert not result["qualified"] and not result["position_authority"]


def test_native_pool_order_digest_or_source_mismatch_fails_closed():
    frame, rows, pool = case()
    tampered = deepcopy(pool)
    tampered["map_candidates"].reverse()
    attach_rank(frame, rows, tampered)
    assert "research_marker_identity_ranking" not in frame["map"]
    assert "research_recorder_marker_v2" not in frame["map"]

    frame, rows, pool = case()
    rows[-1]["raw"]["marker_identity_pool_digest"] = "0"*64
    attach_rank(frame, rows, pool)
    assert "research_recorder_marker_v2" not in frame["map"]


def test_missing_ordered_digest_does_not_fabricate_verified_v2():
    frame, rows, pool = case(bound=False)
    attach_rank(frame, rows, pool)
    assert "research_recorder_marker_v2" not in frame["map"]
    assert frame["map"]["research_marker_identity_ranking"]["proposed_index"] is None


def test_corrupt_legacy_context_does_not_publish_baseline_v2():
    frame, rows, pool = case()
    frame["map"]["marker_ranking_hypotheses"]["rankings"] = [
        {"candidate_index": 2, "score": 2.0},
        {"candidate_index": 2, "score": 1.9},
    ]
    attach_rank(frame, rows, pool)
    assert "research_recorder_marker_v2" not in frame["map"]


def test_no_pixel_cue_can_override_baseline_rank():
    frame, rows, pool = case()
    rows[-1]["raw"]["marker_identity_pixels"]["rankings"] = [
        {"candidate_index": 0, "score": 999.0},
        {"candidate_index": 1, "score": 888.0},
        {"candidate_index": 2, "score": 777.0},
    ]
    attach_rank(frame, rows, pool)
    v2 = frame["map"]["research_recorder_marker_v2"]
    assert v2["baseline_top_index"] == 2
    assert v2["pixel_override_accepted"] is False
    assert v2["recorder_proposed_index"] is None
