"""Generic Map observations retain provenance and cannot qualify ownership."""

from fractions import Fraction

from test_conditional_state_tails import row

from valorant_ai_coach.temporal.application import build_application_timeline
from valorant_ai_coach.temporal.game import DevelopmentGameTimeline, observation


def test_map_names_zones_and_pool_survive_without_recorder_promotion():
    sample = row(0)["sample"]
    engine = DevelopmentGameTimeline(fuse_exact_native_evidence=True)
    engine.add(row(0, ["buy", "owner_hud"]))
    candidate = {"center_frame_px": [20, 30], "ownership": "UNKNOWN"}
    engine.add(
        observation(
            sample=sample,
            producer="f" * 64,
            signals=[],
            context={"stream_kind": "map_generic"},
            map_candidates=[candidate],
            raw={
                "schema": "development_generic_map_pixels_v1",
                "map_reader_status": "OBSERVED",
                "map_name_candidates": [{"map_id": "synthetic", "ownership": "UNKNOWN"}],
                "zone_candidates": [{"zone_id_candidate": "a", "ownership": "UNKNOWN"}],
            },
        )
    )
    timeline = engine.rebuild()
    state = timeline["frames"][0]["map"]
    assert state["observation_present"] is True
    assert state["candidates"] == [candidate]
    assert state["current_self_position_candidates"] == []
    assert state["current_recorder_zone_candidates"] == []
    assert state["map_name_candidates"][0]["sample"] == sample
    app = build_application_timeline(
        timeline,
        duration=Fraction(1),
        origin=Fraction(0),
        source={
            "video_id": "synthetic",
            "source_sha256": "a" * 64,
            "physical_match_id": "physical",
        },
    )
    current = app["seconds"][0]["map_observations"]
    assert current["map_name_candidates"][0]["map_id"] == "synthetic"
    assert current["zone_candidates"][0]["zone_id_candidate"] == "a"
    assert current["continuous_path"] is None
    assert timeline["qualified_facts"] == timeline["qualified_events"] == []


def test_reader_execution_with_zero_proposals_is_still_an_observation():
    engine = DevelopmentGameTimeline()
    engine.add(
        observation(
            sample=row(0)["sample"],
            producer="f" * 64,
            signals=[],
            raw={"schema": "development_generic_map_pixels_v1", "map_reader_status": "OBSERVED"},
        )
    )
    state = engine.rebuild()["frames"][0]["map"]
    assert state["observation_present"] is True
    assert state["status"] == "UNKNOWN"
    assert state["current_self_position_candidates"] == []
