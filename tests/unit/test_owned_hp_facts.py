"""Ownership and current accepted-reader provenance for direct HP point facts."""

from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest
from test_round_package_builder import observation

import valorant_ai_coach.hud.analyzers as analyzers_module
from valorant_ai_coach.events import EventSourceContract
from valorant_ai_coach.facts.builder import FactBuilder
from valorant_ai_coach.hud.analyzers import RealHudAnalyzer
from valorant_ai_coach.hud.classifier import StateClassification
from valorant_ai_coach.hud.identity import IdentityEvidence
from valorant_ai_coach.hud.layout import CalibrationResult, HudLayout
from valorant_ai_coach.hud.readers import FrameFeatureObservation, ReaderResult
from valorant_ai_coach.resources import resource_path
from valorant_ai_coach.rounds import RoundPackageBuilder
from valorant_ai_coach.rounds.builder import _owned_hp_facts
from valorant_ai_coach.schema_validation import SchemaValidator
from valorant_ai_coach.video import VideoMetadata


def _owned_row(time_sec=1.0, hp=80, confidence=0.95):
    row = observation(time_sec, hud_confidence=0.0)
    row["quality"]["roi_confidence"] = {"player_hp_armor": confidence, "hp_value": confidence}
    row["values"]["hp"] = hp
    return row


def test_owned_hp_facts_keep_current_point_confidence_and_deduplicate_exact_replay():
    rows = [_owned_row(1.0, 80, 0.90), _owned_row(2.0, 76, 0.95)]
    before = deepcopy(rows)
    facts = _owned_hp_facts(rows + [rows[0]])
    assert rows == before
    assert [(f["time_sec"], f["value"], f["confidence"]) for f in facts] == [
        (1.0, 80, 0.90),
        (2.0, 76, 0.95),
    ]
    assert all(f["key"] == "hp" and f["source"] == "hud" for f in facts)
    assert all(f["fact_id"].startswith("HH") for f in facts)
    assert len({f["fact_id"] for f in facts}) == len(facts)


@pytest.mark.parametrize("state", ["unknown", "spectator_first_person", "remote_control_view"])
def test_nonlive_state_rejects_adversarial_owned_hp_even_when_value_is_present(state):
    row = _owned_row()
    row["primary_state"] = state
    row["view_context"]["remote_view_type"] = "other" if state == "remote_control_view" else "none"
    row["view_context"]["is_player_world_view_trustworthy"] = False
    # Deliberately violate the observation cross-field schema: the fact helper
    # must still independently enforce both gates rather than trust the flag.
    assert not _owned_hp_facts([row])


@pytest.mark.parametrize("owned", [False, 1, "true", None])
def test_live_hp_requires_explicit_boolean_ownership(owned):
    row = _owned_row()
    if owned is None:
        row["values"].pop("player_specific_hud_valid")
    else:
        row["values"]["player_specific_hud_valid"] = owned
    assert not _owned_hp_facts([row])


def test_live_owned_hp_fact_does_not_require_world_view_confidence():
    row = _owned_row()
    row["view_context"]["is_player_world_view_trustworthy"] = False
    assert [(fact["key"], fact["value"]) for fact in _owned_hp_facts([row])] == [("hp", 80)]


@pytest.mark.parametrize("hp", [None, True, -1, 101, 80.0, "80"])
def test_invalid_or_missing_hp_values_do_not_seed_facts(hp):
    assert not _owned_hp_facts([_owned_row(hp=hp)])


@pytest.mark.parametrize(
    "confidence", [None, True, 0.89, 0.8, 1.01, float("nan"), float("inf"), "0.95"]
)
def test_weak_or_malformed_reader_confidence_does_not_seed_facts(confidence):
    row = _owned_row(confidence=0.95)
    row["quality"]["roi_confidence"]["hp_value"] = confidence
    assert not _owned_hp_facts([row])


def test_geometry_confidence_armor_only_and_missing_reserved_signal_do_not_seed_hp():
    geometry_only = _owned_row()
    geometry_only["quality"]["roi_confidence"] = {"player_hp_armor": 0.99}
    armor_only = _owned_row(hp=None)
    armor_only["values"]["armor"] = 50
    missing = _owned_row()
    missing["quality"]["roi_confidence"].pop("hp_value")
    assert not _owned_hp_facts([geometry_only, armor_only, missing])


def test_uncalibrated_or_bad_timestamp_rows_do_not_seed_facts():
    uncalibrated = _owned_row()
    uncalibrated["quality"]["notes"] = ["calibration_required"]
    malformed_notes = _owned_row(time_sec=2)
    malformed_notes["quality"]["notes"] = "calibrated"
    missing_notes = _owned_row(time_sec=3)
    missing_notes["quality"].pop("notes")
    bad_timestamp = _owned_row()
    bad_timestamp["time_sec"] = float("nan")
    assert not _owned_hp_facts([uncalibrated, malformed_notes, missing_notes, bad_timestamp])


def test_analyzer_emits_reader_only_current_hp_provenance_and_zeros_rejected_or_unowned(
    monkeypatch,
):
    class SequenceReader:
        def __init__(self):
            self.results = iter(
                [
                    ReaderResult({"hp": 80}, 0.95),
                    ReaderResult({"armor": 50}, 0.99),
                    ReaderResult({"hp": 72}, 0.80, cross_checked=True),
                    ReaderResult({"hp": 60}, 0.95),
                    ReaderResult(None, 0.99),
                    ReaderResult({"hp": True}, 0.99),
                    ReaderResult({"hp": "not-an-int"}, 0.99),
                ]
            )

        def read(self, image, roi):
            return next(self.results)

    class FakeFeatures:
        def observe_sequence(self, frames, **kwargs):
            return [
                FrameFeatureObservation(
                    time_sec=float(index),
                    metrics={},
                    signals={"frame_width": 1920, "frame_height": 1080},
                    roi_confidence={"player_hp_armor": 0.99, "hp_value": 0.99},
                    calibration_anchor_presence={},
                )
                for index, _ in enumerate(frames)
            ]

    class FixedClassifier:
        states = ["live_first_person"] * 3 + ["spectator_first_person"] + ["live_first_person"] * 3

        def __init__(self):
            self.index = 0

        def classify(self, signals):
            del signals
            state = self.states[self.index]
            self.index += 1
            live = state == "live_first_person"
            return StateClassification(
                primary_state=state,
                state_flags=(),
                remote_view_type="none",
                player_specific_hud_valid=live,
                is_player_world_view_trustworthy=live,
                confidence=0.95,
                flag_confidence={},
            )

    monkeypatch.setattr(
        analyzers_module,
        "live_identity",
        lambda *args, **kwargs: IdentityEvidence(True, 3, "test"),
    )
    monkeypatch.setattr(
        HudLayout,
        "validate_calibration",
        lambda *args, **kwargs: CalibrationResult(True, (), 4, 0.0, 0.0),
    )
    analyzer = RealHudAnalyzer(
        resource_path("config/hud_layout_1080p_v3.json"),
        readers={"player_hp_armor": SequenceReader()},
    )
    analyzer.feature_reader = FakeFeatures()
    analyzer.state_classifier = FixedClassifier()
    anchors = {
        name: analyzer.layout.normalized_roi(name)
        for name in ("round_timer", "top_match_bar", "player_hp_armor", "abilities")
    }
    frames = [np.full((1080, 1920, 3), 60, np.uint8) for _ in range(7)]
    rows = analyzer.observe_frames(frames, anchor_detections=anchors).observations
    assert [row["values"]["hp"] for row in rows] == [80, None, 72, None, None, None, None]
    assert [row["quality"]["roi_confidence"]["hp_value"] for row in rows] == [
        0.95,
        0.0,
        0.80,
        0.0,
        0.0,
        0.0,
        0.0,
    ]
    assert rows[1]["quality"]["roi_confidence"]["player_hp_armor"] == 0.99
    assert rows[3]["values"]["player_specific_hud_valid"] is False
    assert all(row["quality"]["roi_confidence"]["hp_value"] == 0 for row in rows[3:4])
    assert [(fact["value"], fact["confidence"]) for fact in _owned_hp_facts(list(rows))] == [
        (80, 0.95)
    ]


def test_no_reader_and_uncalibrated_feature_hp_scores_cannot_authorize_hp_value(monkeypatch):
    class FakeFeatures:
        def observe_sequence(self, frames, **kwargs):
            return [
                FrameFeatureObservation(
                    time_sec=0.0,
                    metrics={},
                    signals={"frame_width": 1920, "frame_height": 1080},
                    roi_confidence={"player_hp_armor": 0.99, "hp_value": 0.99},
                    calibration_anchor_presence={},
                )
                for _ in frames
            ]

    monkeypatch.setattr(
        HudLayout,
        "validate_calibration",
        lambda *args, **kwargs: CalibrationResult(True, (), 4, 0.0, 0.0),
    )
    analyzer = RealHudAnalyzer(resource_path("config/hud_layout_1080p_v3.json"))
    analyzer.feature_reader = FakeFeatures()
    anchors = {
        name: analyzer.layout.normalized_roi(name)
        for name in ("round_timer", "top_match_bar", "player_hp_armor", "abilities")
    }
    frame = np.full((1080, 1920, 3), 60, np.uint8)
    no_reader = analyzer.observe_frames([frame], anchor_detections=anchors).observations[0]
    assert no_reader["values"]["hp"] is None
    assert no_reader["quality"]["roi_confidence"]["hp_value"] == 0.0

    monkeypatch.setattr(
        HudLayout,
        "validate_calibration",
        lambda *args, **kwargs: CalibrationResult(False, ("insufficient_anchors",), 0, None, None),
    )
    uncalibrated_analyzer = RealHudAnalyzer(resource_path("config/hud_layout_1080p_v3.json"))
    uncalibrated_analyzer.feature_reader = FakeFeatures()
    uncalibrated = uncalibrated_analyzer.observe_frames([frame], anchor_detections={}).observations[
        0
    ]
    assert uncalibrated["values"]["hp"] is None
    assert uncalibrated["quality"]["roi_confidence"]["hp_value"] == 0.0


def test_round_builder_adds_direct_hp_facts_without_changing_snapshots_events_or_quality(tmp_path):
    rows = [observation(0), _owned_row(1, 80), _owned_row(2, 72), observation(3)]
    for row in rows[1:3]:
        row["quality"]["roi_confidence"]["round_timer_value"] = 0.95
    for row in (rows[0], rows[-1]):
        row["values"]["round_time_remaining_sec"] = None
    legacy = deepcopy(rows)
    legacy[1]["quality"]["roi_confidence"].pop("hp_value")
    legacy[2]["quality"]["roi_confidence"].pop("hp_value")
    builder = RoundPackageBuilder(
        contract=EventSourceContract.load(resource_path("config/event_source_contract_v1.json")),
        validator=SchemaValidator(),
    )
    metadata = VideoMetadata(
        path=Path(tmp_path) / "synthetic.mp4",
        duration_sec=4.0,
        width=1920,
        height=1080,
        fps=60,
        video_codec="h264",
        audio_codec=None,
        has_audio=False,
        file_size=0,
    )
    package = builder.build(
        match_id="M", video_metadata=metadata, hud_observations=rows, hud_events=[]
    )[0]
    baseline = builder.build(
        match_id="M", video_metadata=metadata, hud_observations=legacy, hud_events=[]
    )[0]
    for key in ("events", "state_snapshots", "round_window", "observation_quality"):
        assert package[key] == baseline[key]
    hp_facts = [fact for fact in package["deterministic_facts"] if fact["key"] == "hp"]
    assert [(fact["time_sec"], fact["value"]) for fact in hp_facts] == [(1, 80), (2, 72)]
    assert all(fact["confidence"] == 0.95 for fact in hp_facts)
    timer_facts = [
        fact for fact in package["deterministic_facts"] if fact["key"] == "round_time_remaining_sec"
    ]
    assert [(fact["time_sec"], fact["value"]) for fact in timer_facts] == [(1, 99), (2, 98)]
    assert [fact["fact_id"] for fact in timer_facts] == ["HT0001", "HT0002"]
    assert [fact["fact_id"] for fact in hp_facts] == ["HH0001", "HH0002"]
    assert not {fact["fact_id"] for fact in hp_facts} & {fact["fact_id"] for fact in timer_facts}
    assert not any(
        event["type"] in {"player_death", "damage", "hp_loss"} for event in package["events"]
    )
    SchemaValidator().validate_round_package(package)


def test_fact_enrichment_preserves_hp_confidence_and_is_idempotent(tmp_path):
    row = _owned_row(1.0, 80, 0.95)
    builder = RoundPackageBuilder(
        contract=EventSourceContract.load(resource_path("config/event_source_contract_v1.json")),
        validator=SchemaValidator(),
    )
    metadata = VideoMetadata(
        path=Path(tmp_path) / "synthetic.mp4",
        duration_sec=2.0,
        width=1920,
        height=1080,
        fps=60,
        video_codec="h264",
        audio_codec=None,
        has_audio=False,
        file_size=0,
    )
    package = builder.build(
        match_id="M",
        video_metadata=metadata,
        hud_observations=[observation(0), row, observation(2)],
        hud_events=[],
    )[0]
    enriched = FactBuilder().enrich(package)
    enriched_again = FactBuilder().enrich(enriched)
    hp_facts = [fact for fact in enriched["deterministic_facts"] if fact["key"] == "hp"]
    assert len(hp_facts) == 1
    assert hp_facts[0]["confidence"] == 0.95
    assert [
        fact for fact in enriched_again["deterministic_facts"] if fact["key"] == "hp"
    ] == hp_facts
    assert len({fact["fact_id"] for fact in enriched_again["deterministic_facts"]}) == len(
        enriched_again["deterministic_facts"]
    )
