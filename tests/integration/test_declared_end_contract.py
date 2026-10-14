import copy
import importlib.util
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from scripts.e2e.declared_end_contract import constraint

PACK = Path(__file__).resolve().parents[2] / "ValorantData/valorant_e2e_validation_pack_v3"


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def marker():
    return {"round_id": "sample_round_7", "boundary_kind": "round_end", "approved_time_sec": 750,
            "approved_record": {"event_type": "round_end", "event_time_sec": 750,
                                "time_origin": "explicit_human_supplied_time_not_backcalculation",
                                "first_native_onset_verified": False, "last_absent_sec": None},
            "review_provenance": {"reviewer": "human user in current chat",
                                  "approval_quote": "synthetic approval"}}


def assertions():
    policy = json.loads((PACK / "ground_truth/evaluation_policy_v3.json").read_text(
        encoding="utf-8",
    ))
    value = constraint(marker(), policy)
    schema = json.loads((PACK / "schemas/e2e_ground_truth_schema_v3.json").read_text(
        encoding="utf-8",
    ))
    Draft202012Validator({"$ref": "#/$defs/count_constraint", "$defs": schema["$defs"]}).validate(
        value)
    builder = load_module("declared_end_assertion_builder", PACK / "tests/build_assertions.py")
    # Exercise the unchanged compiler on synthetic GT, not change the original
    # pack or use expected values in a production recognizer.
    gt = {"known_discontinuities": [], "continuous_segments": [], "rounds": [{
        "round_id": "sample_round_7", "round_package_expectations": {
            "event_count_constraints": [value]},
    }]}
    data = {"ground_truth/timeline_ground_truth_v3.json": gt,
            "ground_truth/negative_assertions_v3.json": {"assertions": []},
            "contracts/event_attribute_vocab_v1.json": {"events": {}}}
    builder.load = data.__getitem__
    compiled = builder.build()
    assert compiled["required_point_events"] == []  # no invented onset bracket
    assert compiled["event_count_constraints"] == [{**value, "round_id": "sample_round_7"}]
    assert value["window"] == [749.9, 750.1]
    assert "confidence" not in value
    return compiled


@pytest.mark.parametrize("fault", [None, "missing", "duplicate", "actor", "round",
                                  "too_early", "too_late", "confidence"])
def test_unchanged_v3_compiler_and_evaluator_enforce_declared_end(fault):
    compiled = assertions()
    event = {"round_id": "sample_round_7", "type": "round_end", "actor": "system",
             "time_sec": 750.0, "confidence": .9}
    events = [event]
    if fault == "missing":
        events = []
    elif fault == "duplicate":
        events.append(copy.deepcopy(event))
    elif fault == "actor":
        event["actor"] = "player"
    elif fault == "round":
        event["round_id"] = "sample_round_8"
    elif fault in {"too_early", "too_late"}:
        event["time_sec"] = 749.89 if fault == "too_early" else 750.11
    elif fault == "confidence":
        event["confidence"] = float("nan")
    evaluator = load_module(
        "declared_end_reference_evaluator", PACK / "tests/reference_evaluator.py")
    failures = evaluator.evaluate(compiled, {"events": events})
    if fault is None:
        assert failures == []
    elif fault == "confidence":
        assert "confidence:events:0:confidence" in failures
    else:
        assert "count:sample_round_7:round_end" in failures


@pytest.mark.parametrize("fault", ["not_human", "derived_time", "time_mismatch", "nan", "bool"])
def test_unapproved_or_derived_inputs_cannot_become_positive_constraints(fault):
    value = marker()
    if fault == "not_human":
        value["review_provenance"]["reviewer"] = "Codex"
    elif fault == "derived_time":
        value["approved_record"]["time_origin"] = "score_reset_inference"
    elif fault == "time_mismatch":
        value["approved_time_sec"] = 751
    elif fault == "nan":
        value["approved_time_sec"] = float("nan")
    else:
        value["approved_time_sec"] = True
    policy = json.loads((PACK / "ground_truth/evaluation_policy_v3.json").read_text(
        encoding="utf-8",
    ))
    with pytest.raises(ValueError):
        constraint(value, policy)
