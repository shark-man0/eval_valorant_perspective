from __future__ import annotations

from pathlib import Path

import pytest

from valorant_ai_coach.events import EventSourceContract
from valorant_ai_coach.rounds import RoundPackageBuilder, aggregate_observation_quality
from valorant_ai_coach.schema_validation import SchemaValidator
from valorant_ai_coach.video import VideoMetadata

ROOT = Path(__file__).resolve().parents[2]


def observation(
    time_sec: float,
    *,
    hud_confidence: float = 0.9,
    ally_alive: int = 5,
    enemy_alive: int = 5,
    spike_state: str = "unknown",
) -> dict[str, object]:
    return {
        "schema_version": "2.0",
        "time_sec": time_sec,
        "frame_index": round(time_sec * 60),
        "primary_state": "live_first_person",
        "state_flags": [],
        "view_context": {
            "remote_view_type": "none",
            "is_player_world_view_trustworthy": True,
        },
        "values": {
            "round_time_remaining_sec": max(0, 100 - time_sec),
            "score_ally": 1,
            "score_enemy": 2,
            "ally_alive": ally_alive,
            "enemy_alive": enemy_alive,
            "hp": 100,
            "armor": 50,
            "ammo_current": 25,
            "ammo_reserve": 50,
            "weapon_text": None,
            "spike_state": spike_state,
            "location_text": None,
            "kill_feed_rows": [],
            "ability_slots": [],
            "combat_report_visible": False,
            "buy_phase_visible": False,
            "round_end_text": None,
            "zone_id": None,
            "player_specific_hud_valid": True,
        },
        "quality": {
            "hud_confidence": hud_confidence,
            "visual_confidence": 0.0,
            "occluded_rois": [],
            "notes": [],
            "state_confidence": hud_confidence,
            "roi_confidence": {},
        },
    }


def event(event_id: str, time_sec: float, event_type: str) -> dict[str, object]:
    return {
        "event_id": event_id,
        "time_sec": time_sec,
        "type": event_type,
        "actor": "system",
        "attributes": {},
        "confidence": 0.9,
    }


def test_hud_observation_schema_and_cross_field_contract() -> None:
    validator = SchemaValidator()
    validator.validate_hud_observation(observation(1.0))
    invalid = observation(1.0)
    invalid["primary_state"] = "spectator_first_person"
    invalid["view_context"]["is_player_world_view_trustworthy"] = True  # type: ignore[index]
    with pytest.raises(ValueError, match="world view"):
        validator.validate_hud_observation(invalid)


def test_quality_formula_matches_patch_logic_case() -> None:
    samples = [
        observation(2 / 3, hud_confidence=0.95),
        observation(2.0, hud_confidence=0.9),
        observation(10 / 3, hud_confidence=0.8),
    ]
    quality = aggregate_observation_quality(
        samples, 0.0, 5.0, coverage_radius_sec=2 / 3
    )
    assert quality["timeline_completeness"] == pytest.approx(0.8, abs=0.001)
    assert quality["hud_confidence"] == pytest.approx(0.72, abs=0.001)
    assert quality["missing_intervals"] == pytest.approx(
        [{"start_sec": 4.0, "end_sec": 5.0}], abs=0.001
    )


def test_builder_produces_schema_valid_round_package_without_visual_fabrication(
    tmp_path: Path,
) -> None:
    validator = SchemaValidator()
    contract = EventSourceContract.load(ROOT / "config" / "event_source_contract_v1.json")
    builder = RoundPackageBuilder(contract=contract, validator=validator)
    metadata = VideoMetadata(
        path=tmp_path / "match.mp4",
        duration_sec=5.0,
        width=1920,
        height=1080,
        fps=60,
        video_codec="h264",
        audio_codec=None,
        has_audio=False,
        file_size=0,
    )
    observations = [
        observation(1.0),
        observation(2.0, enemy_alive=4),
        observation(3.0, enemy_alive=4, spike_state="planted"),
    ]
    packages = builder.build(
        match_id="M-HUD",
        video_metadata=metadata,
        hud_observations=observations,
        hud_events=[event("H-START", 1.0, "round_start"), event("H-END", 3.0, "round_end")],
    )
    assert len(packages) == 1
    package = packages[0]
    validator.validate_round_package(package)
    assert package["round_meta"]["round_result"] == "unknown"
    assert package["state_snapshots"]
    assert {item["type"] for item in package["events"]}.isdisjoint(
        {"shot", "peek", "movement_state", "utility_used"}
    )
    assert "objective_state" in {item["type"] for item in package["events"]}
