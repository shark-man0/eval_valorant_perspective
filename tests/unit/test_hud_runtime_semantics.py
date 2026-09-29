from dataclasses import replace

import numpy as np
import pytest

from valorant_ai_coach.hud.analyzers import (
    RealHudAnalyzer,
    _debounced_roster_count,
    _normalize_reader_value,
)
from valorant_ai_coach.hud.readers import FrameFeatureObservation, ReaderResult
from valorant_ai_coach.hud.temporal import resolve_kill_sides
from valorant_ai_coach.resources import resource_path
from valorant_ai_coach.schema_validation import SchemaValidator


class SequenceReader:
    def __init__(self, values):
        self.values = iter(values)

    def read(self, image, roi):
        return ReaderResult(next(self.values), 0.95)


def test_real_analyzer_connects_round_boundaries_roster_and_feed():
    analyzer = RealHudAnalyzer(
        resource_path("config/hud_layout_1080p_v3.json"),
        readers={
            "round_timer": SequenceReader([2, 1, 100, 99, None]),
            "ally_score": SequenceReader([0, 0, 0, 0, 1]),
            "enemy_score": SequenceReader([0, 0, 0, 0, 0]),
            "ally_roster": SequenceReader([5] * 5),
            "enemy_roster": SequenceReader([5, 5, 5, 4, 4]),
            "player_hp_armor": SequenceReader([{"hp": 100, "armor": 50}] * 5),
        },
    )
    buy = {
        "buy_menu_grid_present": True,
        "buy_menu_close_anchor_present": True,
        "buy_phase_template": True,
    }
    signals = [
        buy,
        buy,
        {"live_first_person": True},
        {
            "live_first_person": True,
            "kill_feed_row_added": True,
            "killfeed_color_agrees": True,
            "normal_kill_confirmed": True,
        },
        {"live_first_person": True, "round_end_template": True},
    ]
    frames = [np.full((1080, 1920, 3), 60, dtype=np.uint8)] * 5
    anchors = {
        name: analyzer.layout.normalized_roi(name)
        for name in ("round_timer", "top_match_bar", "player_hp_armor", "abilities")
    }
    result = analyzer.observe_frames(frames, anchor_detections=anchors, additional_signals=signals)
    for observation in result.observations:
        SchemaValidator().validate_hud_observation(observation)
    assert result.observations[0]["values"]["hp"] is None
    assert result.observations[2]["values"]["hp"] == 100
    by_type = {event["type"]: event for event in result.hud_events}
    assert by_type["round_start"]["time_sec"] == 2
    assert by_type["round_end"]["time_sec"] == 4
    assert by_type["kill"]["attributes"]["victim_side"] == "enemy"
    assert by_type["kill"]["attributes"]["killer_side"] == "ally"
    assert not {"shot", "peek", "utility_used"} & by_type.keys()


def test_roster_debounce_rejects_single_frame_and_long_gaps():
    slots = [{"alive_candidate": True, "confidence": 0.9}] * 5
    frame = FrameFeatureObservation(0, {}, {"ally_liveness_candidates": slots}, {}, {})
    assert _debounced_roster_count([frame], 0, "ally") is None
    assert _debounced_roster_count([frame, replace(frame, time_sec=0.25)], 0, "ally") == (5, 0.9)
    assert _debounced_roster_count([frame, replace(frame, time_sec=3)], 0, "ally") is None
    unknown = replace(frame, signals={"ally_liveness_candidates": [{"alive_candidate": None}] * 5})
    assert _debounced_roster_count([unknown, unknown], 0, "ally") is None


@pytest.mark.parametrize(
    "target,value", [("hp", 101), ("armor", 99), ("ally_alive", 6), ("hp", True)]
)
def test_invalid_reader_numbers_stay_unknown(target, value):
    assert _normalize_reader_value(target, "int", value) is None


def test_multi_death_or_missing_other_team_cannot_identify_kill_side():
    for after in (None, 3):
        result = resolve_kill_sides(
            kill_feed_row_added=True,
            ally_alive_before=5,
            ally_alive_after=4,
            enemy_alive_before=5,
            enemy_alive_after=after,
            killfeed_color_agrees=True,
        )
        assert result.victim_side == result.killer_side == "unknown"
