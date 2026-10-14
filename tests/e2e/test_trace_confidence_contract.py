"""Native field support remains auditable under canonical scalar confidence rules."""

from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.e2e.evaluate_saved_trace import evaluate_trace
from tests.e2e.trace_adapter import to_e2e_trace


def source(fields):
    return SimpleNamespace(
        round_packages=[{
            "state_snapshots": [{"time_sec": 1, "hp": None, "source_confidence": fields}],
            "round_window": {"start_sec": 0, "end_sec": 2},
        }],
        observations=[{
            "time_sec": 1, "primary_state": "unknown", "state_flags": [],
            "values": {"player_specific_hud_valid": False},
            "quality": {"hud_confidence": .9, "visual_confidence": 0},
        }],
    )


def test_map_is_preserved_and_summary_cannot_raise_any_field_confidence():
    native = source({"hp": .94, "weapon": .83})
    original = deepcopy(native)
    row = to_e2e_trace(native)["snapshots"][0]
    assert row["source_confidence"] == .83
    assert row["source_confidence_by_field"] == {"hp": .94, "weapon": .83}
    assert row["player_hp"] is None and row["view_owner"] == "unknown"
    assert native == original
    row["source_confidence_by_field"]["hp"] = 1
    assert native == original


def test_empty_support_map_is_explicit_unknown_zero():
    row = to_e2e_trace(source({}))["snapshots"][0]
    assert row["source_confidence"] == 0
    assert row["source_confidence_by_field"] == {}


@pytest.mark.parametrize("value", [True, None, "0.9", -.1, 1.1, float("nan"), float("inf")])
def test_relocating_map_does_not_hide_invalid_leaves(value):
    with pytest.raises(ValueError, match="confidence"):
        to_e2e_trace(source({"hp": value}))


@pytest.mark.parametrize("name", ["", None, 3])
def test_invalid_source_field_names_are_rejected(name):
    with pytest.raises(ValueError, match="field name"):
        to_e2e_trace(source({name: .9}))


@pytest.mark.parametrize("fields", [.9, None, []])
def test_native_field_map_contract_is_not_replaced_by_a_scalar(fields):
    with pytest.raises(ValueError, match="field map"):
        to_e2e_trace(source(fields))


def test_unchanged_canonical_evaluator_validates_scalar_and_still_checks_bad_scalars():
    pack = Path(__file__).resolve().parents[2] / "ValorantData/valorant_e2e_validation_pack_v3"
    trace = to_e2e_trace(source({"hp": .94, "weapon": .83}))
    result = evaluate_trace(pack, trace)
    assert not any(error.startswith("confidence:") for error in result["failures"])
    assert result["schema_valid"]
    trace["snapshots"][0]["source_confidence"] = True
    failed = evaluate_trace(pack, trace)
    assert "confidence:snapshots:0:source_confidence" in failed["failures"]
