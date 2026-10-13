"""Round affiliation stays visible without suppressing canonical negative checks."""

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_native_event_membership_is_schema_compatible_and_does_not_hide_cut_violation():
    adapter = load_module("membership_trace_adapter", ROOT / "tests/e2e/trace_adapter.py")
    pack = ROOT / "ValorantData/valorant_e2e_validation_pack_v3"
    evaluator = load_module("membership_evaluator", pack / "tests/reference_evaluator.py")
    schema = json.loads((pack / "schemas/e2e_output_trace_schema_v1.json").read_text())
    result = SimpleNamespace(round_packages=[{
        "events": [{"type": "status_effect", "time_sec": 100.4, "actor": "player",
                    "confidence": 0.91, "attributes": {"duration_sec": 0.8}}],
    }])
    trace = adapter.to_e2e_trace(result)
    Draft202012Validator(schema).validate(trace)
    assert trace["temporal_features"][0]["round_id"] == "sample_round_1"
    # A synthetic negative assertion uses the unchanged pack evaluator. It does
    # not alter the production pack, GT or any original assertion/threshold.
    assertions = {key: [] for key in (
        "required_point_events", "ordering_constraints", "required_state_intervals",
        "required_snapshots", "event_count_constraints", "negative_assertions",
    )}
    assertions["negative_assertions"] = [{
        "id": "synthetic-cut", "window": [100.5, 100.6],
        "must_not_span_temporal_features": ["status_effect.duration_sec"],
    }]
    assert evaluator.evaluate(assertions, trace) == [
        "discontinuity_span:synthetic-cut:status_effect.duration_sec",
    ]
