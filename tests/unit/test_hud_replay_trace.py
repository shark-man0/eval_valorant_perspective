from __future__ import annotations

import hashlib
from copy import deepcopy

import numpy as np

from valorant_ai_coach.hud.analyzers import RealHudAnalyzer
from valorant_ai_coach.hud.readers import FrameFeatureObservation, ReaderResult
from valorant_ai_coach.resources import resource_path


class SequenceReader:
    def __init__(self, values):
        self.values = iter(values)

    def read(self, image, roi):
        return ReaderResult(next(self.values), 0.95)


class FeatureReader:
    def observe_sequence(self, frames, **kwargs):
        return [
            FrameFeatureObservation(
                time_sec=float(index),
                metrics={},
                signals={"frame_width": 1920, "frame_height": 1080},
                roi_confidence={},
                calibration_anchor_presence={},
            )
            for index, _ in enumerate(frames)
        ]


def _analyzer(diagnostic_sink=None):
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
        diagnostic_sink=diagnostic_sink,
    )
    analyzer.feature_reader = FeatureReader()
    return analyzer


def _anchors(analyzer):
    return {
        name: analyzer.layout.normalized_roi(name)
        for name in ("round_timer", "top_match_bar", "player_hp_armor", "abilities")
    }


def test_optional_trace_is_deepcopied_and_keeps_runtime_outputs_identical(live_identity_signals):
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
    additions = [{**live_identity_signals, **signal} for signal in signals]
    frames = [np.full((1080, 1920, 3), 60, dtype=np.uint8) for _ in signals]
    plain_analyzer = _analyzer()
    plain = plain_analyzer.observe_frames(
        frames, anchor_detections=_anchors(plain_analyzer), additional_signals=additions
    )
    traces = []

    def mutate_diagnostic_copy(payload):
        traces.append(deepcopy(payload))
        payload["signals"]["kill_feed_row_added"] = True
        payload["raw_accepted_reader_values"]["player_hp_armor"]["hp"] = -500
        payload["reader_confidence"].clear()
        payload["classified_state"]["primary_state"] = "mutated"

    traced_analyzer = _analyzer(mutate_diagnostic_copy)
    traced = traced_analyzer.observe_frames(
        frames, anchor_detections=_anchors(traced_analyzer), additional_signals=additions
    )

    assert len(traces) == len(frames)
    assert [trace["frame_index"] for trace in traces] == list(range(len(frames)))
    assert [trace["source_pts_sec"] for trace in traces] == list(range(len(frames)))
    assert all(
        trace["source_pixel_sha256"] == hashlib.sha256(frame.tobytes()).hexdigest()
        for trace, frame in zip(traces, frames, strict=True)
    )
    assert all(trace["semantic_text_measurements"] == {} for trace in traces)
    assert all(trace["geometry_calibrated"] is True for trace in traces)
    assert traces[0]["raw_accepted_reader_values"]["player_hp_armor"] == {
        "hp": 100,
        "armor": 50,
    }
    assert traces[0]["reader_confidence"]["player_hp_armor"] == 0.95
    assert traces[0]["identity"] == {
        "live": False,
        "positive_count": 3,
        "reason": "competing_view_evidence",
    }
    assert traces[2]["identity"]["live"] is True
    assert traces[2]["classified_state"]["primary_state"] == "live_first_person"
    assert traced.observations == plain.observations
    assert traced.hud_events == plain.hud_events
    assert traced.change_times_sec == plain.change_times_sec
    assert any(event["type"] == "kill" for event in traced.hud_events)


def test_default_trace_sink_is_disabled_and_retains_no_frame_payload(live_identity_signals):
    analyzer = _analyzer()
    frame = np.full((1080, 1920, 3), 60, dtype=np.uint8)
    result = analyzer.observe_frames(
        [frame],
        anchor_detections=_anchors(analyzer),
        additional_signals=[live_identity_signals],
    )
    assert analyzer.diagnostic_sink is None
    assert len(result.observations) == 1
    assert not hasattr(analyzer, "last_diagnostic_trace")


def test_trace_reports_uncalibrated_geometry_as_used_for_classification(live_identity_signals):
    traces = []
    analyzer = _analyzer(traces.append)
    frame = np.full((1080, 1920, 3), 60, dtype=np.uint8)
    analyzer.observe_frames([frame], additional_signals=[live_identity_signals])
    assert traces[0]["geometry_calibrated"] is False
    assert traces[0]["identity"]["live"] is False
    assert traces[0]["identity"]["reason"] == "geometry_invalid"
    assert traces[0]["classified_state"]["primary_state"] == "unknown"
