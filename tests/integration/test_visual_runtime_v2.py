from pathlib import Path
from threading import Event

import cv2
import numpy as np
import pytest

from valorant_ai_coach.events import EventSourceContract
from valorant_ai_coach.hud.models import HudObservationV2, empty_hud_quality, empty_hud_values
from valorant_ai_coach.resources import resource_path
from valorant_ai_coach.rounds import RoundPackageBuilder
from valorant_ai_coach.schema_validation import SchemaValidator
from valorant_ai_coach.storage import SQLiteRepository
from valorant_ai_coach.video import FrameSample, VideoMetadata
from valorant_ai_coach.visual.analyzer import WorldViewGate
from valorant_ai_coach.visual.models import VisualObservation
from valorant_ai_coach.visual.runtime import RealVisualAnalyzer
from valorant_ai_coach.visual.semantic import FACT_FIELDS, SemanticBudget, SemanticVisualAdapter


def metadata(path, duration=3):
    return VideoMetadata(path, duration, 960, 540, 30, "h264", None, False, 0)


def observation(time, index, *, state="unknown", ammo=25, flags=()):
    values = empty_hud_values()
    values.update(
        ammo_current=ammo if state == "live_first_person" else None,
        player_specific_hud_valid=state == "live_first_person",
    )
    quality = empty_hud_quality()
    quality.update(hud_confidence=0.95, state_confidence=0.95)
    return HudObservationV2(
        time_sec=time,
        frame_index=index,
        primary_state=state,
        values=values,
        quality=quality,
        state_flags=flags,
        is_player_world_view_trustworthy=state == "live_first_person" and not flags,
    ).to_dict()


def analyzer():
    return RealVisualAnalyzer(
        EventSourceContract.load(resource_path("config/event_source_contract_v1.json"))
    )


def test_supplied_stills_decode_but_do_not_invent_temporal_mechanics():
    frames = [
        FrameSample(float(t), resource_path(f"config/visual_v2/assets/t{t:03d}.jpg"))
        for t in (5, 20, 80, 112, 118, 128, 136, 165)
    ]
    hud = [observation(frame.time_sec, i) for i, frame in enumerate(frames)]
    result = analyzer().analyze(frames, hud, video_metadata=metadata(Path("unavailable.mp4"), 171))
    assert len(result.observations) == 8
    assert not result.events
    validator = SchemaValidator()
    for sample in result.observations:
        validator.validate_visual_observation(sample)


def test_ammo_alone_opens_micro_pass_even_without_recoil_or_visible_enemy(tmp_path):
    path = tmp_path / "blank.jpg"
    cv2.imwrite(str(path), np.zeros((540, 960, 3), dtype=np.uint8))
    frames = [FrameSample(i / 5, path) for i in range(4)]
    hud = [
        observation(frame.time_sec, i, state="live_first_person", ammo=25 if i == 0 else 24)
        for i, frame in enumerate(frames)
    ]
    triggers = analyzer().trigger_windows(frames, hud, video_metadata=metadata(path))
    assert (0.2, "shot") in triggers
    # A HUD discontinuity schedules refinement; it is not automatically a confirmed event.


def test_stale_hud_is_not_reused_for_new_visual_frames(tmp_path):
    path = tmp_path / "frame.jpg"
    cv2.imwrite(str(path), np.zeros((540, 960, 3), dtype=np.uint8))
    result = analyzer().analyze(
        [FrameSample(2, path)],
        [observation(0, 0, state="live_first_person")],
        video_metadata=metadata(path),
    )
    assert not result.observations[0]["analysis_eligibility"]["player_mechanics"]
    assert not result.events


def test_smoke_keeps_factual_shot_but_not_peek_gate():
    hud = [observation(0, 0, state="live_first_person", flags=("vision_obscured_smoke",))]
    assert WorldViewGate.allows_event({"type": "shot", "time_sec": 0}, hud)
    assert not WorldViewGate.allows_event({"type": "peek", "time_sec": 0}, hud)
    hud[0]["primary_state"] = "remote_control_view"
    assert not WorldViewGate.allows_event({"type": "shot", "time_sec": 0}, hud)


def test_visual_cancellation_before_frame_decode(tmp_path):
    instance = analyzer()
    event = Event()
    event.set()
    instance.set_cancel_event(event)
    with pytest.raises(InterruptedError):
        instance.analyze(
            [FrameSample(0, tmp_path / "not_read.jpg")],
            [],
            video_metadata=metadata(tmp_path / "source.mp4"),
        )


def test_actual_cv_and_hud_ammo_through_round_package_and_sqlite(tmp_path):
    path = tmp_path / "texture.jpg"
    rng = np.random.default_rng(555)
    cv2.imwrite(str(path), rng.integers(30, 200, (540, 960, 3), dtype=np.uint8))
    frames = [FrameSample(i / 15, path) for i in range(16)]
    hud = [
        observation(frame.time_sec, i, state="live_first_person", ammo=25 if i < 5 else 24)
        for i, frame in enumerate(frames)
    ]
    for sample in hud:
        sample["values"]["weapon_text"] = "Vandal"
    visual = analyzer().analyze(frames, hud, video_metadata=metadata(path))
    shots = [item for item in visual.events if item["type"] == "shot"]
    assert len(shots) == 1 and shots[0]["attributes"]["moving"] is False
    contract = EventSourceContract.load(resource_path("config/event_source_contract_v1.json"))

    def boundary(kind, t):
        return {
            "event_id": kind,
            "type": kind,
            "time_sec": t,
            "actor": "system",
            "attributes": {},
            "confidence": 0.95,
        }

    packages = RoundPackageBuilder(contract=contract, validator=SchemaValidator()).build(
        match_id="visual-pixels",
        video_metadata=metadata(path),
        hud_observations=hud,
        hud_events=[boundary("round_start", 0), boundary("round_end", 1)],
        visual_events=visual.events,
        visual_observations=visual.observations,
    )
    store = SQLiteRepository(tmp_path / "test.sqlite")
    store.create_match("visual-pixels", str(path), {"duration_sec": 3}, "completed")
    store.save_round_package(packages[0])
    saved = store.list_round_packages("visual-pixels")[0]
    assert any(item["type"] == "shot" for item in saved["events"])
    SchemaValidator().validate_round_package(saved)


def test_semantic_candidate_is_confirmed_in_isolated_adapter_and_reused_on_resume(
    tmp_path, monkeypatch
):
    path = tmp_path / "frame.jpg"
    cv2.imwrite(str(path), np.zeros((50, 50, 3), np.uint8))
    calls = []

    def transport(content, schema):
        calls.append(content)
        return {**dict.fromkeys(FACT_FIELDS), "affected_side": "enemy", "confidence": 0.95}

    ledger_path = tmp_path / "budget.sqlite"
    semantic = SemanticVisualAdapter(transport=transport, budget=SemanticBudget(ledger_path))
    contract = EventSourceContract.load(resource_path("config/event_source_contract_v1.json"))
    sample = VisualObservation.from_mapping(
        {
            "time_sec": 1,
            "frame_index": 0,
            "hud_primary_state": "live_first_person",
            "analysis_eligibility": {"player_mechanics": True, "world_semantics": True},
            "utility": {"world_effect_candidate": "visible_effect", "confidence": 0.95},
        }
    ).to_dict()
    instance = RealVisualAnalyzer(contract, semantic=semantic)
    monkeypatch.setattr(
        instance, "_measure", lambda *_: ([sample], {0: {"frame_ref": str(path)}}, [])
    )
    instance.begin_match("m", [{"type": "round_start", "time_sec": 0}])
    for _ in range(2):
        result = instance.analyze([FrameSample(1, path)], [], video_metadata=metadata(path))
        assert any(
            item["type"] == "utility_effect_observed"
            and item["attributes"]["affected_side"] == "enemy"
            for item in result.events
        )
        # Reopening the persisted ledger simulates a resumed process.
        semantic.budget = SemanticBudget(ledger_path)
    assert len(calls) == 1


def test_spatial_snapshot_projection_drops_intermediate_fields(tmp_path):
    h = [observation(i / 5, i, state="live_first_person") for i in range(6)]
    v = VisualObservation.from_mapping(
        {
            "time_sec": 0.4,
            "frame_index": 2,
            "hud_primary_state": "live_first_person",
            "analysis_eligibility": {"player_mechanics": True},
            "spatial": {"cover_available": True, "confidence": 0.95, "cover_edge_score": 0.9},
        }
    ).to_dict()
    contract = EventSourceContract.load(resource_path("config/event_source_contract_v1.json"))
    builder = RoundPackageBuilder(contract=contract, validator=SchemaValidator())
    packages = builder.build(
        match_id="spatial",
        video_metadata=metadata(tmp_path / "x.mp4"),
        hud_observations=h,
        hud_events=[],
        visual_observations=[v],
    )
    snapshot = next(item for item in packages[0]["state_snapshots"] if item["time_sec"] == 0.4)
    assert snapshot["spatial_context"]["cover_available"] is True
    assert "cover_edge_score" not in snapshot["spatial_context"]
