from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from valorant_ai_coach.hud import (
    HudDirectEventBuilder,
    HudLayout,
    HudObservationV2,
    HudStateClassifier,
    NormalizedRoi,
    aggregate_observation_quality,
    empty_hud_quality,
    empty_hud_values,
    resolve_kill_sides,
)
from valorant_ai_coach.schema_validation import SchemaValidator

ROOT = Path(__file__).resolve().parents[2]
HUD_CASES = json.loads((ROOT / "tests" / "hud_logic_cases_v1.json").read_text(encoding="utf-8"))[
    "cases"
]


def _observation(
    time_sec: float,
    *,
    frame_index: int = 0,
    primary_state: str = "live_first_person",
    state_flags: tuple[str, ...] = (),
    hud_confidence: float = 0.9,
    values_override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    values = empty_hud_values()
    values["player_specific_hud_valid"] = primary_state == "live_first_person"
    values.update(values_override or {})
    quality = empty_hud_quality()
    quality["hud_confidence"] = hud_confidence
    quality["state_confidence"] = hud_confidence
    world_trustworthy = primary_state == "live_first_person" and not set(state_flags) & {
        "vision_obscured_smoke",
        "vision_obscured_flash",
        "visual_transition",
    }
    return HudObservationV2(
        time_sec=time_sec,
        frame_index=frame_index,
        primary_state=primary_state,
        state_flags=state_flags,
        values=values,
        quality=quality,
        remote_view_type="unknown" if primary_state == "remote_control_view" else "none",
        is_player_world_view_trustworthy=world_trustworthy,
    ).to_dict()


def _ability_slot(
    slot: int,
    available: bool,
    charges: int,
    *,
    confidence: float = 0.93,
) -> dict[str, Any]:
    roles = ("C", "Q", "E", "X")
    semantic_roles = ("ability_c", "ability_q", "ability_e", "ultimate")
    return {
        "slot": slot,
        "available": available,
        "charges": charges,
        "confidence": confidence,
        "keybind_role": roles[slot],
        "semantic_role": semantic_roles[slot],
        "ability_name": None,
    }


def _case(case_id: str) -> dict[str, Any]:
    return next(item for item in HUD_CASES if item["id"] == case_id)


@pytest.mark.parametrize("case", HUD_CASES, ids=lambda item: item["id"])
def test_authoritative_hud_logic_cases(case: dict[str, Any]) -> None:
    case_id = case["id"]
    signals = case["signals"]
    expected = case["expect"]

    if case_id in {"HL-001", "HL-002", "HL-003", "HL-004", "HL-008", "HL-009"}:
        result = HudStateClassifier().classify(signals)
        flags = set(result.state_flags)
        if "flag" in expected:
            assert expected["flag"] in flags
        if "not_flag" in expected:
            assert expected["not_flag"] not in flags
        if "primary_state" in expected:
            assert result.primary_state == expected["primary_state"]
        if "remote_view_type" in expected:
            assert result.remote_view_type == expected["remote_view_type"]
        if "player_specific_hud_valid" in expected:
            assert result.player_specific_hud_valid is expected["player_specific_hud_valid"]
        if "world_view_trustworthy" in expected:
            assert result.is_player_world_view_trustworthy is expected["world_view_trustworthy"]
        if "sensitive_visual_readers_suspended" in expected:
            assert (
                result.sensitive_visual_readers_suspended
                is expected["sensitive_visual_readers_suspended"]
            )
        return

    if case_id in {"HL-005", "HL-006", "HL-007"}:
        assigned = resolve_kill_sides(
            kill_feed_row_added=signals["kill_feed_row_added"],
            ally_alive_before=signals["ally_alive_before"],
            ally_alive_after=signals["ally_alive_after"],
            enemy_alive_before=signals["enemy_alive_before"],
            enemy_alive_after=signals["enemy_alive_after"],
            killfeed_color_agrees=signals.get("killfeed_color_agrees", False),
        )
        assert assigned.victim_side == expected["victim_side"]
        assert assigned.killer_side == expected["killer_side"]
        return

    if case_id == "HL-010":
        slot = _ability_slot(
            signals["slot"], signals["available"], 1, confidence=signals["confidence"]
        )
        observation = _observation(
            12.0, hud_confidence=signals["confidence"], values_override={"ability_slots": [slot]}
        )
        events = HudDirectEventBuilder().build([observation])
        ultimate = next(event for event in events if event["type"] == "ability_state")
        assert ultimate["attributes"]["semantic_role"] == "ultimate"
        assert ultimate["attributes"]["available"] is expected["ultimate_available"]
        assert ultimate["attributes"]["ability_name"] is None
        return

    if case_id == "HL-011":
        quality = aggregate_observation_quality(
            signals["frame_hud_confidences"], signals["valid_timeline_fraction"]
        )
        assert quality["hud_confidence"] == pytest.approx(expected["result_approx"])
        return

    if case_id == "HL-012":
        layout = HudLayout.load(ROOT / "config" / "hud_layout_1080p_v3.json")
        anchors = _scaled_shifted_anchors(layout)
        result = layout.validate_calibration(
            1920,
            1080,
            detected_anchors=anchors,
            letterboxed=False,
            crop_applied=False,
        )
        assert result.calibration_required is expected["calibration_required"]
        assert result.median_position_error_norm == pytest.approx(
            signals["median_position_error_norm"]
        )
        assert result.median_size_relative_error == pytest.approx(
            signals["median_size_relative_error"]
        )
        return

    raise AssertionError(f"Unimplemented authoritative HUD logic case: {case_id}")


def _scaled_shifted_anchors(layout: HudLayout) -> dict[str, NormalizedRoi]:
    names = ("round_timer", "top_match_bar", "player_hp_armor", "abilities")
    anchors: dict[str, NormalizedRoi] = {}
    for name in names:
        expected = layout.normalized_roi(name)
        width = expected.width * 1.15
        center_x = expected.x + expected.width / 2 + 0.05
        anchors[name] = NormalizedRoi(
            x=center_x - width / 2,
            y=expected.y,
            width=width,
            height=expected.height,
        )
    return anchors


def test_calibration_rejects_same_aspect_resolution_mismatch() -> None:
    layout = HudLayout.load(ROOT / "config" / "hud_layout_1080p_v3.json")
    anchors = {name: layout.normalized_roi(name) for name in (
        "round_timer",
        "top_match_bar",
        "player_hp_armor",
        "abilities",
    )}

    result = layout.validate_calibration(
        1280,
        720,
        detected_anchors=anchors,
        letterboxed=False,
        crop_applied=False,
    )

    assert result.calibration_required
    assert "resolution_mismatch" in result.reasons


def test_calibration_requires_three_anchor_inliers_not_only_a_good_median() -> None:
    layout = HudLayout.load(ROOT / "config" / "hud_layout_1080p_v3.json")
    anchors = {
        name: layout.normalized_roi(name)
        for name in ("round_timer", "top_match_bar", "player_hp_armor")
    }
    expected = anchors["player_hp_armor"]
    anchors["player_hp_armor"] = NormalizedRoi(
        expected.x + 0.10,
        expected.y,
        expected.width,
        expected.height,
    )

    result = layout.validate_calibration(
        1920,
        1080,
        detected_anchors=anchors,
        letterboxed=False,
        crop_applied=False,
    )

    assert result.calibration_required
    assert "insufficient_anchor_inliers" in result.reasons


def test_calibration_tolerates_one_outlier_when_three_anchors_agree() -> None:
    layout = HudLayout.load(ROOT / "config" / "hud_layout_1080p_v3.json")
    anchors = {
        name: layout.normalized_roi(name)
        for name in ("round_timer", "top_match_bar", "player_hp_armor", "abilities")
    }
    expected = anchors["abilities"]
    anchors["abilities"] = NormalizedRoi(
        expected.x + 0.10,
        expected.y,
        expected.width,
        expected.height,
    )

    result = layout.validate_calibration(
        1920,
        1080,
        detected_anchors=anchors,
        letterboxed=False,
        crop_applied=False,
    )

    assert result.calibrated


def test_model_serialization_matches_hud_schema_and_rejects_untrusted_values() -> None:
    observation = HudObservationV2.from_dict(_observation(1.0))
    SchemaValidator().validate_hud_observation(observation.to_dict())

    with pytest.raises(ValueError, match="player_specific_hud_valid=false"):
        HudObservationV2(
            time_sec=1.0,
            frame_index=1,
            primary_state="remote_control_view",
            remote_view_type="unknown",
            values={**empty_hud_values(), "player_specific_hud_valid": True, "hp": 100},
            quality=empty_hud_quality(),
        )


def test_classifier_never_trusts_obscured_or_unknown_world_view() -> None:
    classifier = HudStateClassifier()
    smoke = classifier.classify(
        {
            "live_first_person": True,
            "low_edge_density": True,
            "low_spatial_entropy": True,
            "broad_color_uniformity": True,
            "hud_anchors_stable": True,
        }
    )
    assert "vision_obscured_smoke" in smoke.state_flags
    assert not smoke.is_player_world_view_trustworthy

    map_transition = classifier.classify(
        {"partial_expanded_map": True, "transition_duration_sec": 0.18}
    )
    assert map_transition.primary_state == "unknown"
    assert map_transition.remote_view_type == "none"
    assert not map_transition.is_player_world_view_trustworthy

