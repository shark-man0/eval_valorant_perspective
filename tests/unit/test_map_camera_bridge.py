"""Synthetic tests for Map rank/Camera association, without owner promotion."""
from copy import deepcopy
from fractions import Fraction

from tests.unit.test_composite_view import cue, visual
from tests.unit.test_shared_game_timeline import obs
from valorant_ai_coach.temporal.application import build_application_timeline
from valorant_ai_coach.temporal.game import DevelopmentGameTimeline, observation
from valorant_ai_coach.temporal.map_camera_bridge import associate_generic_map
from valorant_ai_coach.temporal.visual_state import _attach_map_view


def fixture(camera="SELF", life="ALIVE", signals=("owner_hud",)):
    base = obs(0, signals)
    pool = observation(
        sample=base["sample"], producer="d" * 64, signals=[], raw={},
        context={"profile_fingerprint": "profile"},
        map_candidates=[
            {"center_frame_px": [float(i), 25.0], "roi": [0, 0, 70, 70]}
            for i in range(40)
        ],
    )
    ranks = [
        {"candidate_index": i, "score": float(40-i), "method": "synthetic"}
        for i in range(40)
    ]
    viewed = cue()
    viewed["marker_context_rankings"] = ranks
    viewed["marker_candidate_supplier"] = pool["producer_fingerprint"]
    record = visual(base, viewed)
    frame = {
        "sample": base["sample"],
        "camera": {
            "value": camera, "origin": "observation_projection",
            "evidence_ids": [base["observation_id"]],
        },
        "life": {
            "value": life, "origin": "observation_projection",
            "evidence_ids": [base["observation_id"]],
        },
        "viewed_identity": {
            "evidence_ids": [record["observation_id"]],
            "agent_signature_relation": "UNKNOWN",
            "viewed_agent_candidates": [{"agent": "Synthetic", "score": .9}],
        },
        "map": {
            "current_self_position_candidates": [],
            "marker_ranking_hypotheses": {
                "map_supplier_fingerprint": pool["producer_fingerprint"],
                "evidence_ids": [record["observation_id"]],
                "rankings": ranks,
            },
        },
    }
    return frame, [base, pool, record]


def test_rank_11_32_preserved_with_source_profile_and_unknown_ownership():
    frame, rows = fixture()
    _attach_map_view(frame, rows)
    result = frame["map"]["research_map_correspondence_hypotheses"]
    assert len(result) == 40
    assert result[10]["candidate_index"] == 10
    assert result[10]["rank"] == 11
    assert result[31]["candidate_index"] == 31
    assert result[31]["rank"] == 32
    assert result[31]["sample"] == frame["sample"]
    assert result[31]["map_profile_fingerprint"] == "profile"
    assert result[31]["candidate"]["roi"] == [0, 0, 70, 70]
    assert all("RECORDER_SELF" in h["role_hypotheses"] for h in result)
    assert all(h["ownership"] == "UNKNOWN" for h in result)
    assert all(not h["qualified"] and not h["position_authority"] for h in result)
    assert frame["map"]["current_self_position_candidates"] == []
    assert len(frame["map"]["research_view_position_hypotheses"]) == 5


def test_spectator_conflict_and_carried_self_never_gain_recorder_role():
    spec, rows = fixture("SPECTATOR", "DEAD", ("spectator",))
    _attach_map_view(spec, rows)
    assert all(
        "RECORDER_SELF" not in h["role_hypotheses"]
        for h in spec["map"]["research_map_correspondence_hypotheses"]
    )
    assert "SPECTATED_ACTOR" in (
        spec["map"]["research_map_correspondence_hypotheses"][0]["role_hypotheses"]
    )
    for mode in ("stale", "death", "different"):
        frame, rows = fixture(signals=(
            ("owner_hud", "death") if mode == "death" else ("owner_hud",)
        ))
        if mode == "stale":
            frame["camera"]["origin"] = "temporal_inference"
        if mode == "different":
            frame["viewed_identity"]["agent_signature_relation"] = "DIFFERENT"
        _attach_map_view(frame, rows)
        assert all(
            "RECORDER_SELF" not in h["role_hypotheses"]
            for h in frame["map"]["research_map_correspondence_hypotheses"]
        )


def test_foreign_source_and_forged_ranker_abstain():
    frame, rows = fixture()
    ranking = frame["map"]["marker_ranking_hypotheses"]
    assert len(associate_generic_map(frame, rows, ranking, rows[1])) == 40
    foreign = deepcopy(rows[1])
    foreign["sample"] = obs(5)["sample"]
    assert associate_generic_map(frame, rows, ranking, foreign) == []
    forged = deepcopy(ranking)
    forged["rankings"] = [
        ranking["rankings"][0], ranking["rankings"][0]
    ]
    assert associate_generic_map(frame, rows, forged, rows[1]) == []
    assert all("selected_index" not in item for item in ranking["rankings"])


def test_engine_application_export_preserves_timeline_and_no_formal_position():
    base = obs(0, ["owner_hud"])
    pool = observation(
        sample=base["sample"], producer="d" * 64, signals=[], raw={},
        map_candidates=[
            {"center_frame_px": [float(i), 25.0]} for i in range(40)
        ],
    )
    view = cue()
    view["marker_context_rankings"] = [
        {"candidate_index": i, "score": 40.0-i} for i in range(40)
    ]
    view["marker_candidate_supplier"] = pool["producer_fingerprint"]
    engine = DevelopmentGameTimeline(practical_visual_state=True)
    for row in (base, pool, visual(base, view)):
        engine.add(row)
    timeline = engine.rebuild()
    frame = timeline["frames"][0]
    assert frame["camera"]["value"] == "SELF"
    assert frame["life"]["value"] == "ALIVE"
    assert len(frame["map"]["research_map_correspondence_hypotheses"]) == 40
    bundle = build_application_timeline(
        timeline, duration=Fraction(1), origin=Fraction(0),
        source={
            "video_id": base["sample"]["source_id"],
            "source_sha256": base["sample"]["source_sha256"],
            "physical_match_id": "synthetic",
        },
    )
    data = bundle["seconds"][0]["map_observations"]
    assert len(data["research_map_correspondence_hypotheses"]) == 40
    assert data["current_self_position_candidates"] == []
    assert timeline["qualified_facts"] == timeline["qualified_events"] == []
    assert bundle["formal_outputs"] == 0
