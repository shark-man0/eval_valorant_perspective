from __future__ import annotations

import json
from pathlib import Path

import pytest

from valorant_ai_coach.events import EventSourceContract, EventSourceContractError
from valorant_ai_coach.video import VideoMetadata
from valorant_ai_coach.visual import NullVisualAnalyzer, WorldViewGate

ROOT = Path(__file__).resolve().parents[2]


def test_event_source_contract_covers_registry_and_blocks_wrong_producer() -> None:
    contract = EventSourceContract.load(ROOT / "config" / "event_source_contract_v1.json")
    registry = json.loads(
        (ROOT / "schemas" / "event_type_registry_v2.json").read_text(encoding="utf-8")
    )
    contract.validate_registry(registry)
    contract.validate_event(
        {
            "event_id": "E1",
            "time_sec": 1.0,
            "type": "kill",
            "actor": "unknown",
            "attributes": {},
            "confidence": 0.9,
        },
        "hud_analyzer",
    )
    with pytest.raises(EventSourceContractError, match="生成できません"):
        contract.validate_event(
            {
                "event_id": "E2",
                "time_sec": 1.0,
                "type": "peek",
                "actor": "player",
                "attributes": {},
                "confidence": 0.9,
            },
            "hud_analyzer",
        )


@pytest.mark.parametrize(
    ("state", "flags", "trusted", "expected"),
    [
        ("live_first_person", [], True, True),
        ("live_first_person", ["vision_obscured_smoke"], True, False),
        ("live_first_person", ["vision_obscured_flash"], True, False),
        ("live_first_person", ["visual_transition"], True, False),
        ("remote_control_view", [], True, False),
        ("spectator_first_person", [], True, False),
        ("expanded_tactical_map", [], True, False),
    ],
)
def test_world_view_gate_suspends_invalid_visual_inference(
    state: str, flags: list[str], trusted: bool, expected: bool
) -> None:
    observation = {
        "primary_state": state,
        "state_flags": flags,
        "view_context": {"is_player_world_view_trustworthy": trusted},
    }
    assert WorldViewGate.is_trustworthy(observation) is expected


def test_null_visual_analyzer_is_explicit_and_emits_nothing(tmp_path: Path) -> None:
    contract = EventSourceContract.load(ROOT / "config" / "event_source_contract_v1.json")
    metadata = VideoMetadata(
        path=tmp_path / "match.mp4",
        duration_sec=10,
        width=1920,
        height=1080,
        fps=60,
        video_codec="h264",
        audio_codec=None,
        has_audio=False,
        file_size=0,
    )
    result = NullVisualAnalyzer(contract).analyze(
        [],
        [
            {
                "primary_state": "live_first_person",
                "state_flags": [],
                "view_context": {"is_player_world_view_trustworthy": True},
            }
        ],
        video_metadata=metadata,
    )
    assert result.events == ()
    assert "未接続" in result.diagnostics[0]


def test_map_transition_protects_nearby_events_and_spectator_cannot_shoot() -> None:
    observations = [
        {
            "time_sec": time_sec,
            "primary_state": state,
            "state_flags": flags,
            "view_context": {"is_player_world_view_trustworthy": trusted},
        }
        for time_sec, state, flags, trusted in [
            (1.0, "live_first_person", [], True),
            (2.0, "unknown", ["visual_transition"], False),
            (2.1, "live_first_person", [], True),
            (3.0, "spectator_first_person", [], False),
        ]
    ]
    assert WorldViewGate.allows_event({"type": "shot", "time_sec": 1.5}, observations)
    assert not WorldViewGate.allows_event({"type": "shot", "time_sec": 1.8}, observations)
    assert not WorldViewGate.allows_event({"type": "peek", "time_sec": 2.1}, observations)
    assert not WorldViewGate.allows_event({"type": "shot", "time_sec": 3.0}, observations)


def test_derived_events_suppress_low_confidence_facts() -> None:
    from valorant_ai_coach.events import DerivedEventBuilder

    contract = EventSourceContract.load(ROOT / "config" / "event_source_contract_v1.json")
    events = DerivedEventBuilder(contract).build(
        [
            {
                "time_sec": 1.0,
                "values": {"spike_state": "planted"},
                "quality": {"hud_confidence": 0.5},
            },
        ]
    )
    assert events == []
