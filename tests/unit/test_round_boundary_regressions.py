from pathlib import Path

from valorant_ai_coach.events import EventSourceContract
from valorant_ai_coach.hud.models import HudObservationV2, empty_hud_quality, empty_hud_values
from valorant_ai_coach.resources import resource_path
from valorant_ai_coach.rounds import RoundPackageBuilder
from valorant_ai_coach.schema_validation import SchemaValidator
from valorant_ai_coach.video import VideoMetadata


def observation(time, *, menu=False):
    values = empty_hud_values()
    values.update(player_specific_hud_valid=not menu, score_ally=0, score_enemy=0)
    quality = empty_hud_quality()
    quality.update(hud_confidence=0.95, state_confidence=0.95)
    return HudObservationV2(
        time,
        int(time * 60),
        "buy_menu_open" if menu else "live_first_person",
        values=values,
        quality=quality,
        is_player_world_view_trustworthy=not menu,
    ).to_dict()


def build(samples, boundaries):
    validator = SchemaValidator()
    builder = RoundPackageBuilder(
        contract=EventSourceContract.load(resource_path("config/event_source_contract_v1.json")),
        validator=validator,
    )
    events = [
        {
            "event_id": f"e{i}",
            "time_sec": time,
            "type": kind,
            "actor": "system",
            "confidence": 0.95,
            "attributes": {},
        }
        for i, (time, kind) in enumerate(boundaries)
    ]
    return builder.build(
        match_id="boundaries",
        video_metadata=VideoMetadata(Path("video.mp4"), 90, 1920, 1080, 60, "h264", None, False, 0),
        hud_observations=samples,
        hud_events=events,
    )


def test_missing_starts_preserve_all_later_round_fragments():
    result = build([observation(5), observation(45)], [(30, "round_end"), (60, "round_end")])
    assert [item["round_window"] for item in result] == [
        {"start_sec": 5, "end_sec": 30},
        {"start_sec": 45, "end_sec": 60},
    ]
    assert all(item["observation_quality"]["timeline_completeness"] == 0 for item in result)


def test_initial_partial_round_is_not_lost_before_complete_round():
    result = build(
        [observation(5), observation(45)],
        [(30, "round_end"), (40, "round_start"), (60, "round_end")],
    )
    assert len(result) == 2
    assert result[0]["round_window"] == {"start_sec": 5, "end_sec": 30}
    assert result[1]["round_window"] == {"start_sec": 40, "end_sec": 60}
    assert result[0]["observation_quality"]["timeline_completeness"] == 0


def test_missing_end_gives_shared_timestamp_to_new_round_only():
    result = build(
        [observation(10), observation(40), observation(50)],
        [(10, "round_start"), (40, "round_start"), (60, "round_end")],
    )
    assert len(result) == 2
    assert all(item["time_sec"] < 40 for item in result[0]["events"])
    assert all(item["time_sec"] < 40 for item in result[0]["state_snapshots"])
    assert (
        sum(
            item["type"] == "round_start" and item["time_sec"] == 40
            for package in result
            for item in package["events"]
        )
        == 1
    )
    assert result[0]["observation_quality"]["timeline_completeness"] == 0


def test_menu_between_rounds_does_not_become_a_partial_gameplay_round():
    result = build(
        [observation(10), observation(35, menu=True), observation(45)],
        [(10, "round_start"), (30, "round_end"), (40, "round_start"), (60, "round_end")],
    )
    assert len(result) == 2
