from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]


def load(relative: str) -> dict[str, object]:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def test_hud_observation_schema_is_valid_draft_2020_12() -> None:
    Draft202012Validator.check_schema(load("schemas/hud_observation_schema_v2.json"))


def test_event_source_contract_exactly_covers_existing_registry() -> None:
    contract = load("config/event_source_contract_v1.json")
    registry = load("schemas/event_type_registry_v2.json")
    assert set(contract["events"]) == set(registry["event_types"])  # type: ignore[arg-type]


def test_patch_logic_cases_and_state_anchors_are_preserved() -> None:
    logic = load("tests/hud_logic_cases_v1.json")
    ids = [item["id"] for item in logic["cases"]]  # type: ignore[index]
    assert ids == [f"HL-{index:03d}" for index in range(1, 13)]
    anchors = load("tests/hud_state_samples_v2.json")
    assert len(anchors["samples"]) == 13  # type: ignore[arg-type]
    assert anchors["tolerance_sec"] == 0.25


def test_normalized_rois_are_bounded_and_not_source_code_constants() -> None:
    layout = load("config/hud_layout_1080p_v3.json")
    rois = layout["rois"]
    assert isinstance(rois, dict) and rois
    for name, value in rois.items():
        assert isinstance(name, str) and isinstance(value, dict)
        norm = value["norm"]
        assert isinstance(norm, list) and len(norm) == 4
        left, top, right, bottom = (float(item) for item in norm)
        assert 0 <= left < right <= 1, name
        assert 0 <= top < bottom <= 1, name


def test_ability_contract_keeps_x_as_agent_independent_ultimate() -> None:
    contract = load("config/ability_slot_contract_v1.json")
    slots = contract["slots"]
    assert isinstance(slots, list)
    x_slot = next(item for item in slots if item["keybind_role"] == "X")
    assert x_slot["slot"] == 3
    assert x_slot["semantic_role"] == "ultimate"
