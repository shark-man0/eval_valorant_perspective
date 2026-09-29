from pathlib import Path

import cv2
import numpy as np
import pytest

from valorant_ai_coach.events import EventSourceContract
from valorant_ai_coach.facts import FactBuilder
from valorant_ai_coach.hud.models import HudObservationV2, empty_hud_quality, empty_hud_values
from valorant_ai_coach.resources import resource_path
from valorant_ai_coach.rules import DeterministicRuleEngine
from valorant_ai_coach.schema_validation import SchemaValidator
from valorant_ai_coach.video import FrameSample, VideoMetadata
from valorant_ai_coach.visual.core import VisualEventEngine, shot_movement
from valorant_ai_coach.visual.models import VisualObservation
from valorant_ai_coach.visual.policy import project_candidate_to_v3_event
from valorant_ai_coach.visual.runtime import RealVisualAnalyzer


def enemy(identifier="a", x=0.52, head=True):
    return {
        "detection_id": identifier,
        "bbox_norm": [0.1, 0.1, 0.99, 0.9],
        "head_point_norm": [x, 0.5] if head else None,
        "outline_side": "enemy",
        "confidence": 0.95,
    }


def sample(index, enemies=(), *, stationary=0.95, fired=False):
    return VisualObservation.from_mapping(
        {
            "time_sec": index / 15,
            "frame_index": index,
            "hud_primary_state": "live_first_person",
            "analysis_eligibility": {"player_mechanics": True, "world_semantics": True},
            "motion": {
                "state": "stationary",
                "stationary_confidence": stationary,
                "evidence_sources": ["global_optical_flow"],
            },
            "aiming": {
                "crosshair_stable": True,
                "confidence": 0.95,
                "reference_mode": "static_corner_reference",
            },
            "entities": {"visible_enemies": list(enemies)},
            "weapon_action": {
                "weapon_text": "Vandal",
                "ammo_delta": -1 if fired else 0,
                "confidence": 0.95,
            },
        }
    ).to_dict()


def events_and_facts(candidates):
    validator = SchemaValidator()
    events = []
    for i, candidate in enumerate(candidates):
        validator.validate_visual_candidate(candidate.to_dict())
        event = project_candidate_to_v3_event(candidate, event_id=f"review-{i}")
        if event is not None:
            events.append(event)
    return events, FactBuilder().build({"events": events})


@pytest.mark.parametrize("confidence,expected", [(0.86, None), (0.95, "good")])
def test_movement_confidence_is_not_promoted_by_ammo(confidence, expected):
    engine = VisualEventEngine()
    candidates = engine.process([sample(0, stationary=confidence, fired=True)])
    events, facts = events_and_facts(candidates)
    shot = next(e for e in events if e["type"] == "shot")
    assert shot["confidence"] == confidence
    decision = DeterministicRuleEngine().evaluate("AIM-03", facts, events)
    assert (decision.label if decision else None) == expected
    assert shot_movement(sample(0), {"camera_rotation_rejected": False}) == ("unknown", 0)


@pytest.mark.parametrize("flag", ["vision_obscured_smoke", "vision_obscured_flash"])
def test_real_pixels_occluded_shot_has_no_stationary_fact(tmp_path, flag):
    # The only texture is HUD-like detail: a motionless image is not proof that
    # the player stopped when the world is hidden.
    image = np.full((180, 320, 3), 128, np.uint8)
    image[150:] = np.random.default_rng(8).integers(0, 255, (30, 320, 3), dtype=np.uint8)
    path = tmp_path / "occluded.png"
    cv2.imwrite(str(path), image)
    frames = [FrameSample(i / 15, path) for i in range(3)]
    hud = []
    for i, frame in enumerate(frames):
        values = empty_hud_values()
        values.update(
            player_specific_hud_valid=True, weapon_text="Vandal", ammo_current=25 if i == 0 else 24
        )
        quality = empty_hud_quality()
        quality.update(hud_confidence=0.95, state_confidence=0.95)
        hud.append(
            HudObservationV2(
                time_sec=frame.time_sec,
                frame_index=i,
                primary_state="live_first_person",
                state_flags=(flag,),
                values=values,
                quality=quality,
                is_player_world_view_trustworthy=False,
            ).to_dict()
        )
    runtime = RealVisualAnalyzer(
        EventSourceContract.load(resource_path("config/event_source_contract_v1.json"))
    )
    result = runtime.analyze(
        frames,
        hud,
        video_metadata=VideoMetadata(
            Path("source.mp4"),
            1,
            320,
            180,
            30,
            "h264",
            None,
            False,
            0,
        ),
    )
    shots = [e for e in result.events if e["type"] == "shot"]
    assert len(shots) == 1 and shots[0]["confidence"] == 0.95
    assert shots[0]["attributes"]["moving"] is None
    facts = FactBuilder().build({"events": list(result.events)})
    assert not any(f.key == "first_shot_stationary" for f in facts)
    for rule in ("AIM-03", "MOV-02"):
        assert DeterministicRuleEngine().evaluate(rule, facts, list(result.events)) is None


@pytest.mark.parametrize("head_x,expected", [(0.52, "good"), (0.9, None)])
def test_preaim_requires_alignment_with_the_exposed_target(head_x, expected):
    engine = VisualEventEngine()
    candidates = engine.process(
        [sample(i, [enemy(x=head_x)] if i >= 9 else [], fired=i == 10) for i in range(11)]
    )
    events, facts = events_and_facts(candidates)
    decision = DeterministicRuleEngine().evaluate("AIM-02", facts, events)
    assert (decision.label if decision else None) == expected
    if expected is None:
        assert not any(c.type == "preaim_started" for c in candidates)


@pytest.mark.parametrize(
    "targets",
    [
        [enemy(head=False)],
        [enemy("a", 0.48), enemy("b", 0.52)],
    ],
)
def test_static_corner_does_not_prove_alignment_to_an_unknown_exposed_head(targets):
    candidates = VisualEventEngine().process(
        [sample(i, targets if i >= 9 else [], fired=i == 10) for i in range(11)]
    )
    events, facts = events_and_facts(candidates)
    assert not any(c.type == "preaim_started" and c.status == "confirmed" for c in candidates)
    assert DeterministicRuleEngine().evaluate("AIM-02", facts, events) is None


@pytest.mark.parametrize(
    "known_before,semantic_new,expected,semantic_frame",
    [
        (True, None, False, 2),
        (False, False, False, 2),
        (False, True, True, 2),
        (False, False, False, 1),
    ],
)
def test_info_peek_requires_new_information_and_respects_negative_semantics(
    known_before,
    semantic_new,
    expected,
    semantic_frame,
):
    samples = [
        sample(0, [enemy()] if known_before else []),
        sample(1, [enemy()]),
        sample(2, [enemy()]),
    ]
    proof = {
        1: {
            "micro_motion_state": "moving",
            "micro_motion_confidence": 0.95,
            "camera_rotation_rejected": True,
            "cover_transition": True,
            "cover_transition_confidence": 0.95,
            "new_line_of_sight": True,
            "revealed_region_confidence": 0.95,
        },
        2: {
            "returned_to_cover": True,
            "returned_to_cover_confidence": 0.95,
            "brief_exposure_without_visible_combat": True,
            "brief_exposure_without_visible_combat_confidence": 0.95,
            "semantic_confirmed": [
                "returned_to_cover",
                "brief_exposure_without_visible_combat",
            ],
        },
    }
    proof[semantic_frame].update(
        new_information_observed=semantic_new,
        new_information_observed_confidence=0.95,
    )
    proof[semantic_frame].setdefault("semantic_confirmed", []).append("new_information_observed")
    candidates = VisualEventEngine().process(samples, proof)
    assert any(c.type == "peek" and c.status == "confirmed" for c in candidates)
    assert any(c.type == "info_peek" and c.status == "confirmed" for c in candidates) == expected


def test_primary_target_switch_loss_and_tie_are_reconsidered():
    engine = VisualEventEngine()
    candidates = engine.process(
        [
            sample(0, [enemy("a", 0.6), enemy("b", 0.8)]),
            sample(1, [enemy("a", 0.8), enemy("b", 0.51)]),
            sample(2, [enemy("a", 0.8), enemy("b", 0.51, head=False)]),
            sample(3, [enemy("a", 0.48), enemy("b", 0.52)]),
            sample(4, [enemy("a", head=False)]),
        ]
    )
    aiming = [s["aiming"] for s in engine.enriched_observations]
    assert [s["primary_target_ref"] for s in aiming] == ["a", "b", "a", None, None]
    assert aiming[1]["head_alignment_error_norm"] == pytest.approx(0.01)
    assert any(c.type == "engagement_start" and c.start_sec == 1 / 15 for c in candidates)
    assert aiming[-1]["head_alignment_error_norm"] is None
    for observation in engine.enriched_observations:
        SchemaValidator().validate_visual_observation(observation)
