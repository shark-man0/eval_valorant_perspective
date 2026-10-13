"""Explain confidence shape conflicts without weakening canonical evaluation."""

import copy
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "confidence_evaluation_adapter", ROOT / "tests/e2e/evaluate_saved_trace.py"
)
assert SPEC is not None and SPEC.loader is not None
ADAPTER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ADAPTER)


@pytest.mark.parametrize("leaf", [True, None, "0.9", -0.1, 1.1, float("nan"), float("inf")])
def test_invalid_map_leaf_is_not_misclassified_as_valid(leaf):
    trace = {"snapshots": [{"source_confidence": {"hp": leaf}}]}
    result = ADAPTER.confidence_diagnostics(trace, ["confidence:snapshots:0:source_confidence"])
    assert result["invalid_source_confidence_leaf_count"] == 1
    assert not result.get("valid_source_confidence_maps_rejected_as_scalars", 0)


def test_empty_map_and_invalid_scalar_remain_distinct():
    trace = {"snapshots": [{"source_confidence": {}, "hud_confidence": False}]}
    result = ADAPTER.confidence_diagnostics(trace, [
        "confidence:snapshots:0:source_confidence", "confidence:snapshots:0:hud_confidence"
    ])
    assert result["empty_source_confidence_maps"] == 1
    assert result["other_confidence_failures"] == 1
    assert not result.get("valid_source_confidence_maps_rejected_as_scalars", 0)


def test_canonical_evaluator_still_fails_valid_native_confidence_map():
    pack = ROOT / "ValorantData/valorant_e2e_validation_pack_v3"
    trace = {group: [] for group in (
        "events", "state_intervals", "ownership_intervals", "snapshots",
        "visual_observations", "temporal_features"
    )}
    trace["snapshots"] = [{"round_id": "sample_round_1", "time_sec": 0,
                           "source_confidence": {"hp": .9}, "hud_confidence": .9}]
    original = copy.deepcopy(trace)
    result = ADAPTER.evaluate_trace(pack, trace)
    assert not result["pass"]
    assert "confidence:snapshots:0:source_confidence" in result["failures"]
    assert result["confidence_diagnostics"][
        "valid_source_confidence_maps_rejected_as_scalars"] == 1
    assert result["confidence_diagnostics"]["invalid_source_confidence_leaf_count"] == 0
    assert trace == original
    assert result["schema_valid"] is True
