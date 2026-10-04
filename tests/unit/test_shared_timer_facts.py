from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest
from test_round_package_builder import observation

from valorant_ai_coach.events import EventSourceContract
from valorant_ai_coach.facts.builder import FactBuilder
from valorant_ai_coach.hud.analyzers import RealHudAnalyzer
from valorant_ai_coach.hud.readers import ReaderResult
from valorant_ai_coach.resources import resource_path
from valorant_ai_coach.rounds import RoundPackageBuilder
from valorant_ai_coach.rounds.builder import _shared_timer_facts
from valorant_ai_coach.schema_validation import SchemaValidator
from valorant_ai_coach.video import VideoMetadata


def _unknown_timer(time_sec=1.0, value=74, confidence=0.95):
    row = observation(time_sec, hud_confidence=0.0)
    row["primary_state"] = "unknown"
    row["view_context"]["is_player_world_view_trustworthy"] = False
    row["values"]["player_specific_hud_valid"] = False
    for key in ("hp", "armor", "ammo_current", "ammo_reserve", "weapon_text"):
        row["values"][key] = None
    row["values"]["round_time_remaining_sec"] = value
    row["quality"]["roi_confidence"] = {"round_timer": 0.99, "round_timer_value": confidence}
    return row


def test_shared_timer_facts_preserve_unknown_actor_and_current_point_provenance():
    rows = [_unknown_timer(1, 74, 0.90), _unknown_timer(2, 74, 0.95)]
    before = deepcopy(rows)
    facts = _shared_timer_facts(rows + [rows[0]])
    assert rows == before
    assert [f["time_sec"] for f in facts] == [1.0, 2.0]
    assert [f["confidence"] for f in facts] == [0.90, 0.95]
    assert {f["key"] for f in facts} == {"round_time_remaining_sec"}
    assert all(f["source"] == "hud" and f["provenance_event_ids"] == [] for f in facts)
    assert len({f["fact_id"] for f in facts}) == 2


@pytest.mark.parametrize("value", [None, True, -1, float("nan"), float("inf"), "74"])
def test_invalid_shared_timer_values_do_not_seed_facts(value):
    assert not _shared_timer_facts([_unknown_timer(value=value)])


@pytest.mark.parametrize("confidence", [None, True, 0, 0.8, 0.89, 1.01, float("nan"), "0.95"])
def test_invalid_or_weak_reader_confidence_cannot_authorize_shared_timer(confidence):
    assert not _shared_timer_facts([_unknown_timer(confidence=confidence)])


def test_geometry_confidence_and_uncalibrated_or_missing_reader_do_not_authorize_facts():
    row = _unknown_timer()
    row["quality"]["roi_confidence"].pop("round_timer_value")
    assert not _shared_timer_facts([row])
    row = _unknown_timer()
    row["quality"]["notes"] = ["calibration_required"]
    assert not _shared_timer_facts([row])


def test_shared_timer_builder_keeps_windows_events_snapshots_and_fact_confidence(tmp_path):
    rows = [observation(0), _unknown_timer(1), observation(3)]
    rows[0]["values"]["round_time_remaining_sec"] = None
    rows[2]["values"]["round_time_remaining_sec"] = None
    legacy = deepcopy(rows)
    legacy[1]["quality"]["roi_confidence"].pop("round_timer_value")
    validator = SchemaValidator()
    builder = RoundPackageBuilder(
        contract=EventSourceContract.load(resource_path("config/event_source_contract_v1.json")),
        validator=validator,
    )
    metadata = VideoMetadata(
        path=Path(tmp_path) / "synthetic.mp4", duration_sec=4.0, width=1920, height=1080,
        fps=60, video_codec="h264", audio_codec=None, has_audio=False, file_size=0,
    )
    package = builder.build(match_id="M", video_metadata=metadata, hud_observations=rows,
                            hud_events=[])[0]
    baseline = builder.build(match_id="M", video_metadata=metadata, hud_observations=legacy,
                             hud_events=[])[0]
    for key in ("events", "state_snapshots", "round_window", "observation_quality"):
        assert package[key] == baseline[key]
    validator.validate_round_package(package)
    fact = package["deterministic_facts"][0]
    assert fact["time_sec"] == 1 and fact["value"] == 74 and fact["confidence"] == 0.95
    # Enrichment must not replace the direct confidence with aggregate HUD quality.
    package["state_snapshots"].append({**package["state_snapshots"][0],
                                      "time_sec": 1.0, "round_time_remaining_sec": 74})
    enriched = FactBuilder().enrich(package)
    matching = [f for f in enriched["deterministic_facts"]
                if f["key"] == "round_time_remaining_sec" and f["time_sec"] == 1]
    assert matching == [fact]
    assert len({f["fact_id"] for f in enriched["deterministic_facts"]}) == len(
        enriched["deterministic_facts"])
    validator.validate_round_package(enriched)


def test_analyzer_emits_only_accepted_current_reader_provenance_without_identity():
    class TimerReader:
        def __init__(self):
            self.results = iter([ReaderResult("1:14", 0.95), ReaderResult(None, 0.99),
                                 ReaderResult("1:13", 0.8, cross_checked=True)])
            self.calls = 0

        def read(self, image, roi):
            self.calls += 1
            return next(self.results)

    timer = TimerReader()
    analyzer = RealHudAnalyzer(resource_path("config/hud_layout_1080p_v3.json"),
                               readers={"round_timer": timer})
    anchors = {name: analyzer.layout.normalized_roi(name)
               for name in ("round_timer", "top_match_bar", "player_hp_armor", "abilities")}
    frame = np.full((1080, 1920, 3), 60, dtype=np.uint8)
    result = analyzer.observe_frames([frame] * 3, anchor_detections=anchors)
    rows = result.observations
    assert [r["quality"]["roi_confidence"]["round_timer_value"] for r in rows] == [0.95, 0, 0.8]
    assert [r["values"]["round_time_remaining_sec"] for r in rows] == [74, None, 73]
    assert all(r["primary_state"] == "unknown" for r in rows)
    assert all(r["values"]["player_specific_hud_valid"] is False for r in rows)
    assert not {e["type"] for e in result.hud_events} & {"round_start", "round_end", "player_death"}
    assert len(_shared_timer_facts(list(rows))) == 1
    for row in rows:
        SchemaValidator().validate_hud_observation(row)

    not_calibrated_timer = TimerReader()
    uncalibrated = RealHudAnalyzer(resource_path("config/hud_layout_1080p_v3.json"),
                                  readers={"round_timer": not_calibrated_timer})
    missing = uncalibrated.observe_frames([frame], anchor_detections={}).observations[0]
    assert missing["values"]["round_time_remaining_sec"] is None
    assert missing["quality"]["roi_confidence"]["round_timer_value"] == 0
    assert not_calibrated_timer.calls == 0
    assert not _shared_timer_facts([missing])
