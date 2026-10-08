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


def make_builder():
    validator = SchemaValidator()
    return RoundPackageBuilder(
        contract=EventSourceContract.load(resource_path("config/event_source_contract_v1.json")),
        validator=validator,
    )


def build(samples, boundaries, *, continuity_segments=None):
    builder = make_builder()
    events = [
        {
            "event_id": f"e{i}",
            "time_sec": time,
            "type": kind,
            "actor": "system",
            "confidence": 0.95,
            "attributes": (
                {
                    "evidence_provenance": {
                        "continuity_segment": continuity_segments[i]
                    }
                }
                if continuity_segments and i in continuity_segments
                else {}
            ),
        }
        for i, (time, kind) in enumerate(boundaries)
    ]
    return builder.build(
        match_id="boundaries",
        video_metadata=VideoMetadata(Path("video.mp4"), 90, 1920, 1080, 60, "h264", None, False, 0),
        hud_observations=samples,
        hud_events=events,
    )


def test_global_phase_can_associate_preparation_without_inventing_player_identity():
    phase = observation(1)
    phase["primary_state"] = "unknown"
    phase["view_context"]["is_player_world_view_trustworthy"] = False
    phase["state_flags"] = ["buy_phase_banner"]
    phase["values"] = empty_hud_values()
    phase["values"]["buy_phase_visible"] = True
    phase["quality"]["hud_confidence"] = 0
    phase["quality"]["state_confidence"] = 0
    phase["quality"]["roi_confidence"]["center_phase_banner_semantic_text"] = 0.94
    active = observation(2)
    packages = build([phase, active, observation(3)], [(2, "round_start"), (3, "round_end")])
    assert packages[0]["round_window"]["start_sec"] == 1
    boundary_events = [
        event
        for event in packages[0]["events"]
        if event["type"] in {"round_start", "round_end"}
    ]
    assert [(event["type"], event["time_sec"]) for event in boundary_events] == [
        ("round_start", 2),
        ("round_end", 3),
    ]
    assert phase["values"]["player_specific_hud_valid"] is False
    assert phase["values"]["hp"] is None
    assert phase["primary_state"] == "unknown"
    phase["quality"]["roi_confidence"]["center_phase_banner_semantic_text"] = 0.89
    assert not make_builder()._is_preparation_observation(phase)
    phase["quality"]["roi_confidence"]["center_phase_banner_semantic_text"] = 0.94
    phase["state_flags"] = []
    assert not make_builder()._is_preparation_observation(phase)


def test_missing_starts_preserve_all_later_round_fragments():
    result = build([observation(5), observation(45)], [(30, "round_end"), (60, "round_end")])
    assert [item["round_window"] for item in result] == [
        {"start_sec": 5, "end_sec": 30},
        {"start_sec": 45, "end_sec": 60},
    ]
    assert [
        [event["type"] for event in package["events"] if event["type"] == "round_end"]
        for package in result
    ] == [["round_end"], ["round_end"]]
    assert all(item["observation_quality"]["timeline_completeness"] == 0 for item in result)


def test_initial_partial_round_is_not_lost_before_complete_round():
    result = build(
        [observation(round(step * 0.5, 1)) for step in range(10, 121)],
        [(30, "round_end"), (40, "round_start"), (60, "round_end")],
    )
    assert len(result) == 2
    assert result[0]["round_window"] == {"start_sec": 5, "end_sec": 39.5}
    assert result[1]["round_window"] == {"start_sec": 40, "end_sec": 60}
    assert result[0]["observation_quality"]["timeline_completeness"] == 0


def test_missing_end_gives_shared_timestamp_to_new_round_only():
    result = build(
        [observation(round(10 + step * 0.5, 1)) for step in range(101)],
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
    samples = [observation(10)]
    samples.extend(
        observation(round(30 + step * 0.5, 1), menu=35 <= 30 + step * 0.5 < 36)
        for step in range(31)
    )
    result = build(
        samples,
        [(10, "round_start"), (30, "round_end"), (40, "round_start"), (60, "round_end")],
    )
    assert len(result) == 2


def test_initial_buy_menu_context_is_covered_by_first_detected_round():
    result = build(
        [observation(8, menu=True), observation(9, menu=True), observation(10), observation(20)],
        [(10, "round_start"), (20, "round_end")],
    )
    assert len(result) == 1
    assert result[0]["round_window"] == {"start_sec": 8, "end_sec": 20}
    assert [
        event["type"] for event in result[0]["events"] if event["type"].startswith("round_")
    ] == ["round_start", "round_end"]
    snapshots = {snapshot["time_sec"] for snapshot in result[0]["state_snapshots"]}
    assert {8, 10} <= snapshots
    assert 9 not in snapshots


def test_next_round_owns_preparation_context_after_prior_end():
    after_end = observation(20.5)
    after_end["primary_state"] = "spectator_first_person"
    after_end["view_context"]["is_player_world_view_trustworthy"] = False
    after_end["values"]["player_specific_hud_valid"] = False
    after_end["values"]["spike_state"] = "planted"
    result = build(
        [
            observation(10),
            observation(20),
            after_end,
            observation(21, menu=True),
            observation(22, menu=True),
            observation(23),
            observation(30),
        ],
        [(10, "round_start"), (20, "round_end"), (23, "round_start"), (30, "round_end")],
    )
    assert len(result) == 2
    assert result[0]["round_window"] == {"start_sec": 10, "end_sec": 20.5}
    assert result[1]["round_window"] == {"start_sec": 21, "end_sec": 30}
    assert 20.5 in {item["time_sec"] for item in result[0]["state_snapshots"]}
    assert 21 in {item["time_sec"] for item in result[1]["state_snapshots"]}
    round_ends = [
        event
        for package in result
        for event in package["events"]
        if event["type"] == "round_end" and event["time_sec"] == 20
    ]
    assert len(round_ends) == 1


def test_context_extension_stops_at_gap_over_one_second():
    before_gap = observation(21)
    before_gap["primary_state"] = "spectator_first_person"
    before_gap["view_context"]["is_player_world_view_trustworthy"] = False
    before_gap["values"]["player_specific_hud_valid"] = False
    before_gap["values"]["spike_state"] = "planted"
    result = build(
        [
            observation(10),
            observation(20),
            before_gap,
            observation(22.1, menu=True),
            observation(23, menu=True),
            observation(24),
            observation(30),
        ],
        [(10, "round_start"), (20, "round_end"), (24, "round_start"), (30, "round_end")],
    )
    assert len(result) == 2
    assert result[0]["round_window"] == {"start_sec": 10, "end_sec": 21}
    assert result[1]["round_window"] == {"start_sec": 22.1, "end_sec": 30}
    first_times = {item["time_sec"] for item in result[0]["state_snapshots"]}
    second_times = {item["time_sec"] for item in result[1]["state_snapshots"]}
    assert 21 in first_times
    assert 22.1 in second_times
    assert not first_times & second_times


def test_shared_round_end_and_start_timestamp_keeps_each_boundary_once():
    result = build(
        [observation(10), observation(30), observation(40)],
        [(10, "round_start"), (30, "round_end"), (30, "round_start"), (40, "round_end")],
    )
    assert len(result) == 2
    shared = [
        event
        for package in result
        for event in package["events"]
        if event["time_sec"] == 30 and event["type"] in {"round_start", "round_end"}
    ]
    assert [(event["type"], event["event_id"]) for event in shared] == [
        ("round_end", "e1"),
        ("round_start", "e2"),
    ]


def test_dense_two_round_context_uses_latest_preparation_and_never_overlaps():
    samples = []
    for index in range(51):
        time = round(index * 0.2, 1)
        sample = observation(time, menu=time == 1.0 or 4.8 <= time <= 5.2)
        samples.append(sample)
    boundaries = [
        {"time_sec": 2.0, "type": "round_start"},
        {"time_sec": 4.5, "type": "round_end"},
        {"time_sec": 5.4, "type": "round_start"},
        {"time_sec": 7.0, "type": "round_end"},
    ]
    builder = make_builder()
    windows = builder._round_windows(samples, boundaries, 10.0)
    assert [(window.start_sec, window.end_sec) for window in windows] == [
        (1.0, 4.6),
        (4.8, 7.0),
        (7.2, 10.0),
    ]
    for sample in samples:
        time = sample["time_sec"]
        if 1.0 <= time <= 10.0:
            assert sum(window.contains(time) for window in windows) == 1


def test_observation_gap_splits_actual_round_boundaries_into_fragments():
    samples = [observation(time) for time in (10, 10.5, 12, 12.5, 13, 13.5, 14, 14.5, 15)]
    result = build(
        samples,
        [(10, "round_start"), (13, "round_end"), (13.5, "round_start"), (15, "round_end")],
    )
    assert [item["round_window"] for item in result] == [
        {"start_sec": 10, "end_sec": 10.5},
        {"start_sec": 12, "end_sec": 13},
        {"start_sec": 13.5, "end_sec": 15},
    ]
    assert result[0]["observation_quality"]["timeline_completeness"] == 0
    assert result[1]["observation_quality"]["timeline_completeness"] == 0
    assert result[2]["observation_quality"]["timeline_completeness"] > 0
    boundary_events = [
        event
        for package in result
        for event in package["events"]
        if event["type"] in {"round_start", "round_end"}
    ]
    assert [event["event_id"] for event in boundary_events] == ["e0", "e1", "e2", "e3"]


def test_explicit_continuity_segment_change_prevents_complete_pairing():
    samples = [observation(round(time * 0.5, 1)) for time in range(20, 41)]
    result = build(
        samples,
        [(10, "round_start"), (20, "round_end")],
        continuity_segments={0: 3, 1: 4},
    )
    assert len(result) == 2
    assert all(item["observation_quality"]["timeline_completeness"] == 0 for item in result)
    boundary_events = [
        event
        for package in result
        for event in package["events"]
        if event["type"] in {"round_start", "round_end"}
    ]
    assert [event["event_id"] for event in boundary_events] == ["e0", "e1"]


def test_low_confidence_buy_menu_does_not_extend_context():
    low_confidence_menu = observation(4, menu=True)
    low_confidence_menu["quality"]["hud_confidence"] = 0.4
    result = build(
        [low_confidence_menu, observation(5), observation(10)],
        [(5, "round_start"), (10, "round_end")],
    )
    assert len(result) == 1
    assert result[0]["round_window"]["start_sec"] == 5
