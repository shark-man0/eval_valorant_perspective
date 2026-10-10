"""Execute the immutable 33 supplied cases against implementation components."""

import json
import math

import pytest
from shapely.geometry import Point, Polygon

from valorant_ai_coach.maps.registry import MapDefinition
from valorant_ai_coach.resources import resource_path
from valorant_ai_coach.schema_validation import SchemaValidator
from valorant_ai_coach.visual.core import VisualEventEngine, shot_movement
from valorant_ai_coach.visual.models import VisualObservation
from valorant_ai_coach.visual.policy import (
    evaluate_visual_confidence,
    project_spatial_context,
    semantic_fact,
)
from valorant_ai_coach.visual.remote import classify_remote_view
from valorant_ai_coach.visual.semantic import SemanticBudget

PATCH = "config/visual_v2/"
CASES = json.loads(resource_path(PATCH + "tests/visual_logic_cases_v2.json").read_text())["cases"]
MAP = json.loads(
    resource_path(PATCH + "tests/fixtures/coarse_zone_fixture_test_map.json").read_text()
)


def obs(t=0, index=0, **parts):
    return VisualObservation.from_mapping(
        {
            "time_sec": t,
            "frame_index": index,
            "hud_primary_state": "live_first_person",
            "analysis_eligibility": {
                "player_mechanics": True,
                "world_semantics": True,
                "reason_codes": ["live_first_person"],
            },
            **parts,
        }
    ).to_dict()


def enemy(identifier="e1", error=0.1):
    return {
        "detection_id": identifier,
        "bbox_norm": [0.4, 0.3, 0.7, 0.9],
        "head_point_norm": [0.5 + error, 0.5],
        "outline_side": "enemy",
        "confidence": 0.95,
    }


def test_world_detection_uses_canonical_source_vocabulary():
    samples = [obs(0, entities={"visible_enemies": [enemy()]}),
               obs(.2, index=1), obs(.4, index=2), obs(.6, index=3), obs(.8, index=4)]
    candidates = VisualEventEngine().process(samples)
    world_events = [c for c in candidates if c.type in {"enemy_spotted", "enemy_lost"}]
    assert {c.type for c in world_events} == {"enemy_spotted", "enemy_lost"}
    assert all(c.attributes["source"] == "world_view" for c in world_events)


def run(samples, proofs=None, map_data=None):
    # The v3 override moves geometry out of Visual. Preserve these original
    # consumer scenarios through explicit resolved inputs; real resolver paths
    # and the new debounce are tested in test_map_zone_v3.py.
    definition = None
    if map_data:
        proofs = {key: dict(value) for key, value in (proofs or {}).items()}
        zones = [
            {
                **zone,
                "kind": "site" if zone["zone_id"] == "B_SITE" else "site_approach",
                "site_id": "B" if zone["zone_id"] == "B_SITE" else None,
                "site_affinity": [zone["macro_group"]] if zone["macro_group"] != "MID" else [],
            }
            for zone in map_data["zones"]
        ]
        zones.append({"zone_id": "A_SITE", "kind": "site", "site_id": "A", "site_affinity": ["A"]})
        definition = MapDefinition(
            {
                "map_id": "TEST_MAP",
                "geometry_version": "resolved_visual_fixture_v3",
                "zones": zones,
                "topology_edges": [
                    {"from_zone_id": "A_MAIN", "to_zone_id": "B_SITE", "active_by_default": True}
                ],
                "sites": [
                    {"site_id": "A", "zone_ids": ["A_SITE"]},
                    {"site_id": "B", "zone_ids": ["B_SITE"]},
                ],
            },
            {},
            {},
            None,
            None,
        )

        def resolved(sample, zone):
            meta = definition.zone_index.get(zone, {})
            return {
                "time_sec": sample["time_sec"],
                "frame_index": sample["frame_index"],
                "map_id": definition.map_id,
                "geometry_version": definition.geometry_version,
                "zone_id": zone,
                "zone_kind": meta.get("kind"),
                "site_id": meta.get("site_id"),
                "site_affinity": meta.get("site_affinity", []),
                "zone_confidence": 0.94 if zone else 0,
                "resolution_scope": "exact_zone" if zone else "unknown",
                "resolution_source": "polygon" if zone else "unknown",
                "calibration_status": "ok",
                "boundary_state": "clear",
                "candidate_zone_ids": [zone] if zone else [],
                "held_from_previous": False,
                "diagnostics": [],
            }

        for sample in samples:
            m = sample["minimap"]
            point = (m["self_x_norm"], m["self_y_norm"])
            zone = next(
                (
                    z["zone_id"]
                    for z in map_data["zones"]
                    if point[0] is not None and Polygon(z["polygon_norm"]).covers(Point(point))
                ),
                None,
            )
            proof = proofs.setdefault(sample["frame_index"], {})
            proof["zone_resolution"] = resolved(sample, zone)
            proof["static_peek_exposure"] = next(
                (
                    a["exposed_directions_count"]
                    for a in map_data["peek_exposure_anchors"]
                    if point[0] is not None
                    and math.dist(point, (a["x_norm"], a["y_norm"])) <= a["radius_norm"]
                ),
                None,
            )
            proof["ally_zone_resolutions"] = [
                ("ally-1", resolved(sample, "A_SITE" if marker["x_norm"] >= 0.08 else "A_MAIN"))
                for marker in m["ally_markers"]
            ]
    engine = VisualEventEngine(map_definition=definition)
    candidates = engine.process(samples, proofs)
    validator = SchemaValidator()
    for sample in engine.enriched_observations:
        validator.validate_visual_observation(sample)
    for candidate in candidates:
        validator.validate_visual_candidate(candidate.to_dict())
    return candidates, engine.enriched_observations


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
def test_supplied_logic_case(case):
    number = int(case["id"].split("-")[1])
    data, expected = case["inputs"], case["expected"]
    if number in {1, 2, 17, 18, 19, 26}:
        series = data.get("ammo_series", [25, 25 + data.get("ammo_delta", 0)])
        samples = []
        proofs = {}
        for i, ammo in enumerate(series):
            smoke = data.get("vision_obscured_smoke", False)
            state = data["hud_state"]
            samples.append(
                obs(
                    i * 0.125,
                    i,
                    hud_primary_state=state,
                    analysis_eligibility={
                        "player_mechanics": state == "live_first_person",
                        "world_semantics": not smoke,
                    },
                    quality={"occluded": smoke},
                    weapon_action={
                        "weapon_text": "Vandal",
                        "ammo_current": ammo,
                        "ammo_delta": ammo - series[i - 1] if i else 0,
                        "recoil_score": data["recoil_score"] if i else 0,
                        "confidence": 0.95,
                    },
                )
            )
            proofs[i] = data
        candidates, enriched = run(samples, proofs)
        shots = [item for item in candidates if item.type == "shot" and item.status == "confirmed"]
        if number in {2, 17, 18}:
            assert not shots
        else:
            assert len(shots) == 1 and shots[0].attributes["first_shot"] is True
        if number == 19:
            assert enriched[-1]["weapon_action"]["burst_active"]
        return
    if number in {3, 4}:
        sample = obs(
            motion={
                "map_displacement_norm_per_sec": data["map_displacement"],
                "camera_motion_score": data["camera_motion_score"],
            },
            minimap={"track_confidence": 0.95},
        )
        candidates, enriched = run([sample])
        assert enriched[0]["motion"]["state"] == ("moving" if number == 4 else "stationary")
        assert candidates
        return
    if number in {5, 6}:
        first = obs(
            entities={"visible_enemies": [enemy()]},
            weapon_action={"weapon_text": "Vandal", "ammo_delta": -1, "confidence": 0.95},
        )
        samples = [first]
        if number == 6:
            samples.append(
                obs(
                    0.1,
                    1,
                    quality={"occluded": True},
                    analysis_eligibility={"player_mechanics": True, "world_semantics": False},
                )
            )
        candidates, _ = run(samples)
        assert any(item.type == "engagement_start" for item in candidates)
        assert not any(item.type == "engagement_end" for item in candidates)
        return
    if number in {7, 8}:
        candidates, _ = run(
            [
                obs(
                    hud_primary_state=data["hud_state"],
                    analysis_eligibility={"player_mechanics": False},
                    weapon_action={"ammo_delta": -1, "confidence": 1},
                )
            ]
        )
        assert not candidates
        return
    if number == 9:
        samples = [
            obs(
                10 + i * 0.05,
                i,
                motion={
                    "state": "stationary",
                    "stationary_confidence": 0.95,
                    "evidence_sources": ["global_optical_flow"],
                },
                aiming={
                    "crosshair_stable": True,
                    "reference_mode": data["reference_mode"],
                    "confidence": data["reference_confidence"],
                },
                entities={"visible_enemies": [enemy(error=0.02)] if i == 13 else []},
            )
            for i in range(14)
        ]
        candidates, _ = run(samples)
        preaim = next(item for item in candidates if item.type == "preaim_started")
        assert preaim.attributes["lead_sec"] == pytest.approx(expected["lead_sec_approx"])
        return
    if number in {10, 22, 23}:
        sample = obs(
            motion={"state": "moving"},
            minimap={"self_x_norm": 0.28, "self_y_norm": 0.5, "track_confidence": 0.94},
        )
        proof = {
            "micro_motion_state": "moving",
            "micro_motion_confidence": 0.95,
            "camera_rotation_rejected": True,
            "cover_transition": True,
            "cover_transition_confidence": 0.95,
            "new_line_of_sight": True,
            "revealed_region_confidence": 0.95,
            **data,
        }
        candidates, enriched = run([sample], {0: proof}, MAP if number == 23 else None)
        peek = next(item for item in candidates if item.type == "peek")
        assert peek.attributes["exposed_directions"] == (3 if number == 23 else None)
        assert enriched[0]["spatial"]["exposed_directions_count"] == (3 if number == 23 else None)
        return
    if number in {11, 33}:
        proof = {
            **data,
            "hud_confidence": 0.95,
            "cast_animation_score": data.get("cast_animation_score", 0.9),
            "slot_index": "E",
        }
        candidates, enriched = run([obs(utility={"slot": "E", "confidence": 0.95})], {0: proof})
        used = next(item for item in candidates if item.type == "utility_used")
        assert used.attributes["slot"] == "E"
        assert "MB4" not in json.dumps(used.to_dict())
        return
    if number == 12:
        candidates, _ = run(
            [
                obs(
                    i * 0.2,
                    i,
                    motion={"map_displacement_norm_per_sec": 0.1},
                    minimap={"track_confidence": 0.95},
                )
                for i in range(5)
            ]
        )
        assert not any(item.type.startswith("rotation_") for item in candidates)
        return
    if number == 13:
        samples = [
            obs(
                i * 0.2,
                i,
                motion={
                    "state": "stationary",
                    "stationary_confidence": 0.95,
                    "evidence_sources": ["global_optical_flow"],
                },
                aiming={"crosshair_stable": True, "confidence": 0.95},
            )
            for i in range(17)
        ]
        candidates, _ = run(samples, {i: {"weapon_ready": True} for i in range(17)})
        assert sum(item.type == "hold_angle" for item in candidates) == 1
        return
    if number == 14:
        samples = [
            obs(0, 0),
            obs(0.2, 1, entities={"visible_enemies": [enemy()]}),
            obs(0.4, 2),
            obs(0.7, 3),
        ]
        proof = {
            "micro_motion_state": "moving",
            "micro_motion_confidence": 0.95,
            "camera_rotation_rejected": True,
            "cover_transition": True,
            "cover_transition_confidence": 0.95,
            "new_line_of_sight": True,
            "revealed_region_confidence": 0.95,
        }
        candidates, _ = run(samples, {0: proof, 3: {"returned_to_cover_cv": True}})
        info = next(item for item in candidates if item.type == "info_peek")
        assert info.status == "candidate" and info.semantic_confirmation == "required"
        return
    if number == 15:
        candidates, _ = run([obs(utility={"world_effect_candidate": "unknown", "confidence": 0.9})])
        assert not any(
            item.type == "utility_effect_observed" and item.status == "confirmed"
            for item in candidates
        )
        return
    if number == 16:
        assert (
            semantic_fact(
                {
                    "cover_available": True,
                    "cover_available_confidence": data["semantic_confidence"],
                },
                "cover_available",
            )[0]
            is None
        )
        return
    if number == 20:
        assert shot_movement(obs(), data)[0] == expected["movement_state"]
        return
    if number == 21:
        proof = {
            **data,
            "micro_motion_state": "moving",
            "micro_motion_confidence": 0.95,
            "camera_rotation_rejected": True,
        }
        candidates, _ = run([obs()], {0: proof})
        preaim = next(item for item in candidates if item.type == "preaim_started")
        assert preaim.confidence <= expected["confidence_max"] and preaim.status != "confirmed"
        assert preaim.attributes["lead_sec"] is None
        return
    if number == 24:
        samples = [
            obs(
                i * 0.2,
                i,
                motion={"map_displacement_norm_per_sec": 0.1},
                minimap={
                    "self_x_norm": 0.2 if i < 4 else 0.8,
                    "self_y_norm": 0.5,
                    "track_confidence": 0.93,
                },
            )
            for i in range(5)
        ]
        candidates, _ = run(samples, map_data=MAP)
        rotation = next(item for item in candidates if item.type == "rotation_started")
        assert (
            rotation.attributes["from"] == expected["from"]
            and rotation.attributes["to"] == expected["to"]
        )
        return
    if number == 25:
        samples = [
            obs(
                i * 0.2,
                i,
                minimap={
                    "ally_markers": [
                        {
                            "x_norm": x,
                            "y_norm": 0.5,
                            "side": "ally",
                            "confidence": data["track_confidence"],
                        }
                    ]
                },
            )
            # New canonical dwell is 0.35s, not same-frame entry completion.
            for i, x in enumerate((0.05, 0.09, 0.09, 0.09))
        ]
        candidates, _ = run(samples, map_data=MAP)
        assert any(
            item.type == "ally_enter_site" and item.attributes["site"] == expected["site"]
            for item in candidates
        )
        return
    if number == 27:
        candidates, enriched = run(
            [
                obs(
                    entities={
                        "visible_enemies": [
                            enemy(name, error)
                            for name, error in data["head_alignment_errors"].items()
                        ]
                    }
                )
            ]
        )
        assert enriched[0]["aiming"]["primary_target_ref"] == expected["primary_target_ref"]
        assert enriched[0]["aiming"]["head_alignment_error_norm"] == pytest.approx(
            expected["head_alignment_error_norm"]
        )
        return
    if number in {28, 29}:
        decision = classify_remote_view(
            {"primary_state": "live_first_person"},
            {
                "normal_weapon_hud_missing": data["normal_weapon_hud_missing"],
                "ability_control_active": data["ability_slot_active_control"],
                "remote_overlay": data["remote_overlay_signature"],
            },
        )
        assert decision["primary_state"] == expected["hud_state"]
        assert not decision["player_mechanics_eligible"]
        return
    if number == 30:
        budget = SemanticBudget()
        for i in range(data["semantic_calls_this_match"]):
            assert budget.reserve("m", str(i // 8), str(i), 8, 96)
        assert not budget.reserve("m", "next", "next", 8, 96)
        return
    if number == 31:
        assert (
            evaluate_visual_confidence(
                data["tier"], data["confidence"], data["independent_sources"]
            ).status
            == expected["status"]
        )
        return
    if number == 32:
        projected = project_spatial_context(data["spatial"])
        assert set(projected) == set(expected["v3_spatial_keys"])
        return
    pytest.fail(f"Case has no implementation coverage: {case['id']}")


def test_engagement_end_hysteresis_and_reengagement():
    samples = []
    for i in range(9):
        visible = i in (0, 8)
        samples.append(
            obs(
                i * 0.2,
                i,
                entities={"visible_enemies": [enemy()] if visible else []},
                weapon_action={
                    "weapon_text": "Vandal",
                    "ammo_delta": -1 if visible else 0,
                    "confidence": 0.95,
                },
            )
        )
    events, _ = run(samples)
    kinds = [event.type for event in events]
    assert kinds.count("engagement_start") == 2
    assert kinds.count("engagement_end") == 1
    assert kinds.count("enemy_lost") == 1
    assert kinds.count("enemy_reengage") == 1


@pytest.mark.parametrize("boundary", ["gap", "spectator", "remote", "buy_menu"])
def test_reengagement_does_not_reuse_history_across_segment_boundary(boundary):
    samples = [obs(i * .2, i,
                   entities={"visible_enemies": [enemy()] if i == 0 else []},
                   weapon_action={"weapon_text": "Vandal", "ammo_delta": -1 if i == 0 else 0,
                                  "confidence": .95}) for i in range(6)]
    if boundary != "gap":
        state = {"spectator": "spectator_first_person", "remote": "remote_control_view",
                 "buy_menu": "buy_menu_open"}[boundary]
        samples.append(obs(1.2, 6, hud_primary_state=state,
                           analysis_eligibility={"player_mechanics": False,
                                                 "world_semantics": False,
                                                 "reason_codes": [{
                                                     "spectator": "spectating_other_player",
                                                     "remote": "remote_control_view",
                                                     "buy_menu": "buy_menu",
                                                 }[boundary]]}))
    samples.append(obs(1.8 if boundary == "gap" else 1.4, 7,
                       entities={"visible_enemies": [enemy()]},
                       weapon_action={"weapon_text": "Vandal", "ammo_delta": -1,
                                      "confidence": .95}))
    events, _ = run(samples)
    assert sum(e.type == "engagement_end" for e in events) == 1
    assert sum(e.type == "engagement_start" for e in events) == 2
    assert not any(e.type == "enemy_reengage" for e in events)


def test_rotation_completion_and_primary_target_ambiguity():
    samples = [
        obs(
            i * 0.2,
            i,
            motion={"map_displacement_norm_per_sec": 0.1 if i < 5 else 0},
            minimap={
                "self_x_norm": 0.2 if i < 4 else 0.8,
                "self_y_norm": 0.5,
                "track_confidence": 0.95,
            },
        )
        for i in range(11)
    ]
    events, _ = run(samples, map_data=MAP)
    assert sum(item.type == "rotation_completed" for item in events) == 1
    _, enriched = run([obs(entities={"visible_enemies": [enemy("a", 0.03), enemy("b", -0.03)]})])
    assert enriched[0]["aiming"]["head_alignment_error_norm"] is None


def test_unknown_weapon_does_not_confirm_visual_flash_as_shot():
    events, _ = run([obs(weapon_action={"muzzle_flash_score": 0.99, "confidence": 0.99})])
    assert all(item.status != "confirmed" for item in events if item.type == "shot")


def test_explicit_source_break_clears_enemy_hysteresis_without_fake_loss():
    samples = [obs(0, entities={'visible_enemies': [enemy()]}),
               obs(.1, index=1), obs(.3, index=2), obs(.5, index=3), obs(.7, index=4)]
    events = VisualEventEngine().process(
        samples, evidence_by_frame={1: {'source_discontinuity': True}},
    )
    assert any(e.type == 'enemy_spotted' for e in events)
    assert not any(e.type in {'enemy_lost', 'engagement_end'} for e in events)
