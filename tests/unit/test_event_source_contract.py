from __future__ import annotations

import json
from pathlib import Path

import pytest

from valorant_ai_coach.events import EventSourceContract, EventSourceContractError
from valorant_ai_coach.resources import resource_path


def event(event_type: str, actor: str) -> dict[str, object]:
    return {"type": event_type, "actor": actor}


@pytest.mark.parametrize("event_type", ["round_start", "round_end"])
def test_round_lifecycle_actor_contract_requires_system(event_type: str) -> None:
    contract = EventSourceContract.load(resource_path("config/event_source_contract_v1.json"))
    contract.validate_event(event(event_type, "system"), "hud_analyzer")
    with pytest.raises(EventSourceContractError, match="actor"):
        contract.validate_event(event(event_type, "team"), "hud_analyzer")


def test_round_actor_check_does_not_replace_producer_check() -> None:
    contract = EventSourceContract.load(resource_path("config/event_source_contract_v1.json"))
    with pytest.raises(EventSourceContractError, match="生成できません"):
        contract.validate_event(event("round_start", "system"), "visual_analyzer")


def test_actor_metadata_is_optional_for_legacy_contract(tmp_path: Path) -> None:
    path = tmp_path / "legacy-contract.json"
    path.write_text(
        json.dumps(
            {
                "events": {
                    "round_start": {
                        "primary_producer": "hud_analyzer",
                        "mvp_status": "mvp_direct",
                    },
                    "kill": {"primary_producer": "hud_analyzer"},
                }
            }
        ),
        encoding="utf-8",
    )
    contract = EventSourceContract.load(path)
    contract.validate_event(event("round_start", "team"), "hud_analyzer")
    contract.validate_event(event("kill", "unknown"), "hud_analyzer")


def test_actor_metadata_is_only_enforced_for_round_lifecycle() -> None:
    contract = EventSourceContract.load(resource_path("config/event_source_contract_v1.json"))
    # Other actor semantics remain governed by their current producers.
    contract.validate_event(event("player_death", "unknown"), "hud_analyzer")


@pytest.mark.parametrize("allowed_actors", [[], ["bogus"], ["system", "system"], "system", [1]])
def test_invalid_allowed_actor_metadata_is_rejected(tmp_path: Path, allowed_actors: object) -> None:
    path = tmp_path / "invalid-contract.json"
    path.write_text(
        json.dumps(
            {
                "events": {
                    "round_start": {
                        "primary_producer": "hud_analyzer",
                        "allowed_actors": allowed_actors,
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(EventSourceContractError, match="allowed_actors"):
        EventSourceContract.load(path)
