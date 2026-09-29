from collections import Counter

import numpy as np
import pytest

from valorant_ai_coach.hud.analyzers import RealHudAnalyzer
from valorant_ai_coach.hud.models import HudObservationV2, empty_hud_quality, empty_hud_values
from valorant_ai_coach.hud.readers import ReaderResult
from valorant_ai_coach.hud.temporal import HudDirectEventBuilder
from valorant_ai_coach.resources import resource_path
from valorant_ai_coach.schema_validation import SchemaValidator


def observation(index, *, time=None, score=0, enemy=5, ally=5, flags=(), timer=100):
    values = empty_hud_values()
    values.update(
        score_ally=score,
        score_enemy=0,
        ally_alive=ally,
        enemy_alive=enemy,
        player_specific_hud_valid=True,
        round_time_remaining_sec=timer,
    )
    quality = empty_hud_quality()
    quality.update(hud_confidence=0.95, state_confidence=0.95)
    return HudObservationV2(
        time_sec=index * 0.25 if time is None else time,
        frame_index=index,
        primary_state="live_first_person",
        values=values,
        quality=quality,
        state_flags=flags,
        is_player_world_view_trustworthy=not bool(flags),
    ).to_dict()


@pytest.mark.parametrize("banner_index,score_index", [(1, 2), (2, 1)])
def test_round_end_joins_score_and_banner_in_both_orders(banner_index, score_index):
    samples = [observation(i, score=int(i >= score_index)) for i in range(5)]
    evidence = {banner_index: {"round_end_template": True}}
    result = HudDirectEventBuilder().build(samples, evidence_by_frame=evidence)
    ends = [item for item in result if item["type"] == "round_end"]
    assert len(ends) == 1 and ends[0]["time_sec"] == banner_index * 0.25
    assert "round_end_banner" in samples[banner_index]["state_flags"]
    for sample in samples:
        SchemaValidator().validate_hud_observation(sample)


def test_unrelated_distant_score_does_not_confirm_banner():
    samples = [observation(0, time=0), observation(1, time=1), observation(2, time=5, score=1)]
    assert not HudDirectEventBuilder().build(
        samples, evidence_by_frame={1: {"round_end_template": True}}
    )


@pytest.mark.parametrize("row_index,drop_index", [(1, 2), (2, 1)])
def test_kill_joins_row_and_roster_in_both_orders_once(row_index, drop_index):
    samples = [observation(i, enemy=4 if i >= drop_index else 5) for i in range(5)]
    evidence = {
        row_index: {
            "kill_feed_row_added": True,
            "killfeed_color_agrees": True,
            "normal_kill_confirmed": True,
        }
    }
    events = HudDirectEventBuilder().build(samples, evidence_by_frame=evidence)
    kills = [item for item in events if item["type"] == "kill"]
    assert len(kills) == 1 and kills[0]["time_sec"] == row_index * 0.25
    assert kills[0]["attributes"]["victim_side"] == "enemy"
    assert kills[0]["attributes"]["killer_side"] == "ally"
    for sample in samples:
        SchemaValidator().validate_hud_observation(sample)


def test_ambiguous_multiple_rows_do_not_reuse_one_roster_death():
    samples = [observation(0), observation(1), observation(2, enemy=4)]
    events = HudDirectEventBuilder().build(
        samples,
        evidence_by_frame={
            1: {"kill_feed_row_added": True},
            2: {"kill_feed_row_added": True},
        },
    )
    assert not [event for event in events if event["type"] == "kill"]


def test_ambiguous_multi_team_death_stays_unassigned():
    samples = [observation(0), observation(1, ally=4, enemy=4), observation(2, ally=4, enemy=4)]
    assert not HudDirectEventBuilder().build(
        samples, evidence_by_frame={1: {"kill_feed_row_added": True}}
    )


def test_death_is_once_per_round_and_status_once_per_observed_episode():
    samples = [observation(i) for i in range(9)]
    evidence = {}
    for i in (0, 1, 2, 3, 7, 8):
        samples[i]["values"]["combat_report_visible"] = True
        evidence[i] = {"self_hud_identity_lost": True}
    for i in (0, 1, 2, 7, 8):
        evidence.setdefault(i, {}).update(
            confirmed_status_effect="smoke",
            status_confidence=0.95,
            status_cross_checked=True,
            affected_side="player",
        )
    samples[5]["state_flags"] = ["buy_phase_banner"]
    samples[5]["values"]["round_time_remaining_sec"] = 1
    samples[6]["values"]["round_time_remaining_sec"] = 100
    events = HudDirectEventBuilder().build(samples, evidence_by_frame=evidence)
    counts = Counter(item["type"] for item in events)
    assert counts["player_death"] == 2
    assert counts["status_effect"] == 2
    statuses = [item for item in events if item["type"] == "status_effect"]
    assert statuses[0]["attributes"]["duration_sec"] == 0.75
    assert statuses[1]["attributes"]["duration_sec"] is None


class SequenceReader:
    def __init__(self, values):
        self.values = iter(values)

    def read(self, image, roi):
        return ReaderResult(next(self.values), 0.95)


@pytest.mark.parametrize("text,expected", [
    ("1714", None), ("13", None), ("1:99", None), ("1:4", None),
    ("1:14", 74.0), ("0:04", 4.0), (74, 74.0),
])
def test_default_timer_ocr_validates_format_but_preserves_numeric_seconds(text, expected):
    class Reader:
        def read(self, image, roi):
            return ReaderResult(text, .95)

    analyzer = RealHudAnalyzer(resource_path("config/hud_layout_1080p_v3.json"),
                               ocr_reader=Reader())
    anchors = {name: analyzer.layout.normalized_roi(name)
               for name in ("round_timer", "top_match_bar", "player_hp_armor", "abilities")}
    result = analyzer.observe_frames([np.full((1080, 1920, 3), 60, dtype=np.uint8)],
                                      anchor_detections=anchors)
    assert result.observations[0]["values"]["round_time_remaining_sec"] == expected


def test_stale_combat_report_in_buy_phase_does_not_emit_death():
    samples = [observation(0, flags=("buy_phase_banner",), timer=1),
               observation(1, timer=100), observation(2, timer=99)]
    for sample in samples[:2]:
        sample["values"]["combat_report_visible"] = True
    evidence = {i: {"self_hud_identity_lost": True} for i in range(2)}
    events = HudDirectEventBuilder().build(samples, evidence_by_frame=evidence)
    assert not [event for event in events if event["type"] == "player_death"]
    assert len([event for event in events if event["type"] == "round_start"]) == 1


@pytest.mark.parametrize("signals,expected", [
    ({"buy_menu_grid_present": True, "astral_geometry": True}, "live_first_person"),
    ({"astral_geometry": True, "purple_palette": True,
      "astra_hand_interface": True}, "remote_control_view"),
    ({"spectated_player_panel": True}, "unknown"),
])
def test_partial_scene_geometry_does_not_override_confirmed_hud(signals, expected):
    analyzer = RealHudAnalyzer(resource_path("config/hud_layout_1080p_v3.json"))
    anchors = {name: analyzer.layout.normalized_roi(name)
               for name in ("round_timer", "top_match_bar", "player_hp_armor", "abilities")}
    neutral = dict.fromkeys((
        "buy_menu_grid_present", "buy_menu_close_anchor_present", "expanded_map_present",
        "expanded_map_stable", "astral_geometry", "purple_palette", "astra_hand_interface",
        "spectated_player_panel", "remote_control_candidate",
    ), False)
    result = analyzer.observe_frames(
        [np.full((1080, 1920, 3), 60, dtype=np.uint8)],
        anchor_detections=anchors, additional_signals=[{**neutral, **signals}],
    )
    assert result.observations[0]["primary_state"] == expected


def test_map_texture_score_alone_cannot_confirm_tactical_map(monkeypatch):
    analyzer = RealHudAnalyzer(resource_path("config/hud_layout_1080p_v3.json"))
    monkeypatch.setattr("valorant_ai_coach.hud.readers._map_score", lambda _: .99)
    feature = analyzer.feature_reader.observe(np.full((1080, 1920, 3), 60, dtype=np.uint8))
    assert feature.signals["expanded_map_candidate"] is True
    assert feature.signals["expanded_map_present"] is False
    assert feature.signals["expanded_map_stable"] is False


def test_letterbox_invalidates_cached_calibration_until_anchors_recover(monkeypatch):
    from unittest.mock import Mock

    analyzer = RealHudAnalyzer(resource_path("config/hud_layout_1080p_v3.json"))
    anchors = {name: analyzer.layout.normalized_roi(name)
               for name in ("round_timer", "top_match_bar", "player_hp_armor", "abilities")}
    scores = dict.fromkeys(anchors, .99)
    profile = Mock()
    profile.detect_anchors.side_effect = [
        (anchors, scores, ()), ({}, {}, ()), ({}, {}, ()), (anchors, scores, ()),
    ]
    profile.detect_signals.return_value = {}
    analyzer.template_profile = profile
    monkeypatch.setattr(
        "valorant_ai_coach.hud.analyzers._detect_letterbox",
        Mock(side_effect=[False, True, False, False]),
    )
    frames = [np.full((1080, 1920, 3), 60, dtype=np.uint8)] * 4
    analysis = analyzer.observe_frames(frames)
    assert analysis.observations[0]["values"]["player_specific_hud_valid"] is True
    for item in analysis.observations[1:3]:
        assert item["primary_state"] == "unknown"
        assert item["values"]["player_specific_hud_valid"] is False
        assert "calibration_required" in item["quality"]["notes"]
    assert analysis.observations[3]["values"]["player_specific_hud_valid"] is True
    assert analysis.calibration.calibrated


def test_real_analyzer_connects_delayed_signals_without_test_only_before_counts():
    analyzer = RealHudAnalyzer(
        resource_path("config/hud_layout_1080p_v3.json"),
        readers={
            "ally_score": SequenceReader([0, 1, 1, 1]),
            "enemy_score": SequenceReader([0] * 4),
            "round_timer": SequenceReader([100, 99, 98, 97]),
            "ally_roster": SequenceReader([5] * 4),
            "enemy_roster": SequenceReader([5, 5, 4, 4]),
        },
    )
    # Native sampled frames with explicit evidence adapters, not a FakeAnalyzer.
    from unittest.mock import patch

    image = np.full((1080, 1920, 3), 60, dtype=np.uint8)
    anchors = {
        name: analyzer.layout.normalized_roi(name)
        for name in ("round_timer", "top_match_bar", "player_hp_armor", "abilities")
    }
    with patch(
        "valorant_ai_coach.hud.analyzers._frame_time", side_effect=lambda _, index: index * 0.25
    ):
        result = analyzer.observe_frames(
            [image] * 4,
            anchor_detections=anchors,
            additional_signals=[
                {},
                {"kill_feed_row_added": True},
                {"round_end_template": True},
                {},
            ],
        )
    assert Counter(item["type"] for item in result.hud_events) == {"kill": 1, "round_end": 1}
