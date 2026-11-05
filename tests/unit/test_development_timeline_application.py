from copy import deepcopy
from fractions import Fraction

import pytest

from valorant_ai_coach.rules.development_timeline import evaluation_package, review_timeline
from valorant_ai_coach.temporal.application import build_application_timeline
from valorant_ai_coach.temporal.evidence import digest, freeze_native_sample
from valorant_ai_coach.temporal.game import DevelopmentGameTimeline, observation
from valorant_ai_coach.temporal.viewer import byte_range


def make_timeline(extra_raw=None):
    engine = DevelopmentGameTimeline()
    for tick, signals in [
        (51, ["buy", "owner_hud"]),
        (56, ["active", "owner_hud"]),
        (71, ["death", "spectator"]),
        (81, ["buy", "owner_hud"]),
    ]:
        sample = freeze_native_sample(
            {
                "source_id": "synthetic",
                "source_sha256": "a" * 64,
                "acquisition_id": "e",
                "native_epoch": "e",
                "native_pts_tick": tick,
                "native_time_base": "1/10",
                "frame_size_px": [32, 32],
                "acquired_frame_sha256": digest([tick]),
                "native_pixel_sha256": digest([tick, 1]),
            }
        )
        engine.add(
            observation(
                sample=sample,
                producer="b" * 64,
                signals=signals,
                raw={"view_hp": {"display": "100", "confidence": 0.96}, **(extra_raw or {})},
                context={"score": [0, 0]},
                map_candidates=[{"zone": "unqualified"}],
            )
        )
    return engine.rebuild()


def build(timeline=None):
    return build_application_timeline(
        timeline or make_timeline(),
        duration=Fraction(7, 2),
        origin=Fraction(51, 10),
        source={
            "video_id": "synthetic",
            "source_sha256": "a" * 64,
            "physical_match_id": "physical",
        },
    )


def test_recording_grid_keeps_missing_seconds_and_subsecond_conflicts():
    timeline = make_timeline()
    before = deepcopy(timeline)
    result = build(timeline)
    assert timeline == before
    assert [r["timestamp"] for r in result["seconds"]] == [0, 1, 2, 3]
    first = result["seconds"][0]
    assert first["native_start_seconds"] == "51/10"
    assert first["round_state"]["value"] == "UNKNOWN"
    assert first["round_state"]["hypotheses"] == ["ACTIVE", "BUY"]
    assert len(first["round_state"]["native_estimates"]) == 2
    missing = result["seconds"][1]
    assert missing["observation_present"] is False
    assert missing["round_state"]["value"] == "UNKNOWN"
    assert missing["hud_observations"]["hp"]["status"] == "UNKNOWN"
    assert result["seconds"][-1]["end_timestamp"] == 3.5
    assert result["observations"]
    assert all(
        e["qualified"] is False and e["internal_event_time"] is None
        for e in result["events"].values()
    )


def test_real_candidates_are_not_dropped_or_promoted():
    result = build()
    row = result["seconds"][0]
    assert row["hud_observations"]["hp"]["candidates"][0]["value"] == "100"
    assert row["hud_observations"]["armor"]["status"] == "UNKNOWN"
    assert row["map_observations"]["position_candidates"]
    assert row["map_observations"]["current_self_position_candidates"] == []
    assert row["map_observations"]["continuous_path"] is None
    assert all(ref in result["observations"] for ref in row["evidence_refs"])


def test_existing_evaluation_handoff_keeps_development_channels_separate():
    bundle = build()
    package = evaluation_package(bundle, 0, 4)
    assert package["development_timeline"] == bundle["seconds"]
    assert package["development_event_candidates"]
    assert package["deterministic_facts"] == package["events"] == []
    review = review_timeline(bundle)
    assert review["seconds_consumed"] == 4
    assert review["candidate_review_queue"]
    assert review["existing_scope_resolver_consumed"]
    assert review["deterministic_engine_decision"] is None


def test_hud_supplier_fields_and_event_candidates_keep_exact_observation_refs():
    bundle = build(
        make_timeline(
            {
                "measurements": [
                    {"name": "armor", "value": "25", "confidence": 0.6},
                    {"name": "weapon", "value": "candidate rifle"},
                ],
                "event_candidates": [{"kind": "spike_planted_display", "status": "unqualified"}],
            }
        )
    )
    first = bundle["seconds"][0]
    assert first["hud_observations"]["armor"]["candidates"][0]["value"] == "25"
    assert first["hud_observations"]["weapon"]["candidates"]
    event = next(e for e in bundle["events"].values() if e["kind"] == "spike_planted_display")
    assert event["internal_event_time"] is None
    assert event["timing_basis"] == "observation_time_not_verified_event_time"
    assert event["qualified"] is False
    assert event["evidence_refs"][0] in bundle["observations"]


@pytest.mark.parametrize("change", ["formal", "observation", "source", "outside"])
def test_reject_malformed_or_unrelated_evidence(change):
    timeline = make_timeline()
    if change == "formal":
        timeline["formal_outputs"] = 1
    elif change == "observation":
        timeline["observations"][0]["raw"]["tamper"] = True
    elif change == "source":
        timeline["frames"][0]["sample"]["source_sha256"] = "c" * 64
    else:
        timeline["frames"][0]["sample"]["native_pts_tick"] = 0
    with pytest.raises(ValueError):
        build(timeline)


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        (None, (0, 99, 200)),
        ("bytes=10-19", (10, 19, 206)),
        ("bytes=95-", (95, 99, 206)),
        ("bytes=-5", (95, 99, 206)),
        ("bytes=0-200", (0, 99, 206)),
    ],
)
def test_original_video_byte_ranges(header, expected):
    assert byte_range(header, 100) == expected


@pytest.mark.parametrize(
    "header", ["bytes=100-", "bytes=20-10", "bytes=-0", "bytes=", "bytes=0-1,3-4"]
)
def test_invalid_video_ranges(header):
    with pytest.raises(ValueError):
        byte_range(header, 100)
