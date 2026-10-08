from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from tests.e2e.trace_adapter import to_e2e_trace
from valorant_ai_coach.events import EventSourceContract
from valorant_ai_coach.hud.analyzers import RealHudAnalyzer
from valorant_ai_coach.hud.models import HudObservationV2, empty_hud_quality, empty_hud_values
from valorant_ai_coach.hud.readers import ReaderResult
from valorant_ai_coach.resources import resource_path
from valorant_ai_coach.rounds import RoundPackageBuilder
from valorant_ai_coach.schema_validation import SchemaValidator
from valorant_ai_coach.video import VideoMetadata


class TimerReader:
    def __init__(self, results):
        self.results = iter(results)

    def read(self, image, roi):
        return next(self.results)


def test_accepted_display_flows_from_reader_to_native_package_to_trace(live_identity_signals):
    analyzer = RealHudAnalyzer(
        resource_path("config/hud_layout_1080p_v3.json"),
        readers={"round_timer": TimerReader([
            ReaderResult("01:05", .95, ("digit_templates",)),
            ReaderResult("1:05", .95, ("digit_templates",)),
            ReaderResult(None, 0, ("unknown",)),
        ])},
    )
    analyzer.ocr_fallback_rois = ()
    anchors = {
        name: analyzer.layout.normalized_roi(name)
        for name in ("round_timer", "top_match_bar", "player_hp_armor", "abilities")
    }
    result = analyzer.observe_frames(
        [np.full((1080, 1920, 3), 60, dtype=np.uint8)] * 3,
        anchor_detections=anchors,
        additional_signals=[live_identity_signals] * 3,
    )
    assert [row["values"]["round_time_remaining_sec"] for row in result.observations] == [
        65, 65, None
    ]
    assert result.observations[0]["values"]["round_time_remaining_display"] == "01:05"
    assert result.observations[1]["values"]["round_time_remaining_display"] == "1:05"
    assert "round_time_remaining_display" not in result.observations[2]["values"]
    validator = SchemaValidator()
    for row in result.observations:
        validator.validate_hud_observation(row)
    builder = RoundPackageBuilder(
        contract=EventSourceContract.load(resource_path("config/event_source_contract_v1.json")),
        validator=validator,
    )
    packages = builder.build(
        match_id="timer_contract", video_metadata=VideoMetadata(
            Path("video.mp4"), 3, 1920, 1080, 60, "h264", None, False, 0,
        ), hud_observations=result.observations, hud_events=result.hud_events,
    )
    for package in packages:
        validator.validate_round_package(package)
    snapshots = packages[0]["state_snapshots"]
    assert [s.get("round_time_remaining_display") for s in snapshots] == ["01:05", "1:05", None]
    trace = to_e2e_trace(SimpleNamespace(round_packages=packages, observations=result.observations))
    assert [s.get("game_timer_display") for s in trace["snapshots"]] == ["01:05", "1:05", None]
    proof = trace["snapshots"][0]["game_timer_display_provenance"]
    assert proof == {"reader": "round_timer", "sources": ["digit_templates"],
                     "confidence": .95, "cross_checked": False, "source_pts_sec": 0}
    poisoned = deepcopy(packages)
    poisoned[0]["state_snapshots"][0]["round_time_remaining_display"] = "1:05"
    with pytest.raises(ValueError, match="timer source mismatch"):
        to_e2e_trace(SimpleNamespace(round_packages=poisoned, observations=result.observations))


def test_numeric_timer_alone_never_becomes_display():
    values = empty_hud_values()
    values.update(round_time_remaining_sec=65, player_specific_hud_valid=True)
    quality = empty_hud_quality()
    quality.update(hud_confidence=.95, state_confidence=.95)
    row = HudObservationV2(0, 0, "live_first_person", values=values, quality=quality).to_dict()
    snapshot = {"time_sec": 0, "round_time_remaining_sec": 65}
    trace = to_e2e_trace(SimpleNamespace(
        round_packages=[{"round_window": {"start_sec": 0, "end_sec": 1},
                         "state_snapshots": [snapshot]}], observations=[row],
    ))
    assert "game_timer_display" not in trace["snapshots"][0]


@pytest.mark.parametrize("reader_score,value_score,cross_checked", [
    (.75, .75, True), (.95, .89, False), (.95, None, False)
])
def test_shared_snapshot_requires_independent_accepted_timer_score(
    reader_score, value_score, cross_checked
):
    values = empty_hud_values()
    values.update(round_time_remaining_sec=65, round_time_remaining_display="1:05",
                  round_time_remaining_display_provenance={
                      "reader": "round_timer", "sources": ["ocr"],
                      "confidence": reader_score, "cross_checked": cross_checked})
    quality = empty_hud_quality()
    quality.update(hud_confidence=.95, state_confidence=.95)
    if value_score is not None:
        quality["roi_confidence"]["round_timer_value"] = value_score
    row = HudObservationV2(0, 0, "live_first_person", values=values, quality=quality).to_dict()
    builder = RoundPackageBuilder(
        contract=EventSourceContract.load(resource_path("config/event_source_contract_v1.json")),
        validator=SchemaValidator(),
    )
    snapshots = builder._state_snapshots([row])
    assert "round_time_remaining_display" not in snapshots[0]
    trace = to_e2e_trace(SimpleNamespace(
        round_packages=[{"round_window": {"start_sec": 0, "end_sec": 1},
                         "state_snapshots": snapshots}], observations=[row],
    ))
    assert "game_timer_display" not in trace["snapshots"][0]


@pytest.mark.parametrize("changes", [
    {"round_time_remaining_display": "1:66"},
    {"round_time_remaining_sec": 64},
    {"round_time_remaining_display_provenance": None},
    {"round_time_remaining_display_provenance": {
        "reader": "round_timer", "sources": [], "confidence": .95, "cross_checked": False}},
    {"round_time_remaining_display_provenance": {
        "reader": "round_timer", "sources": ["ocr"], "confidence": .84, "cross_checked": False}},
])
def test_display_contract_rejects_unaccepted_or_inconsistent_evidence(changes):
    values = empty_hud_values()
    values.update(round_time_remaining_sec=65, round_time_remaining_display="1:05",
                  round_time_remaining_display_provenance={
                      "reader": "round_timer", "sources": ["ocr"],
                      "confidence": .95, "cross_checked": False})
    good = HudObservationV2(0, 0, values=values).to_dict()
    values.update(changes)
    with pytest.raises(ValueError):
        HudObservationV2(0, 0, values=values)
    good["values"] = values
    with pytest.raises(ValueError):
        SchemaValidator().validate_hud_observation(good)
