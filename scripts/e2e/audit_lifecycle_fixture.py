"""Audit evaluator sensitivity using synthetic traces, never Analyzer inputs.

The positive oracle is constructed solely to test the private evaluation
contract. A PASS here cannot prove any real-video boundary or promote a Pack.
"""
from __future__ import annotations

import argparse
import copy
import importlib.util
import json
from pathlib import Path

from jsonschema import Draft202012Validator

from scripts.e2e.validate_fixture import load, validate

GROUPS = ("events", "state_intervals", "ownership_intervals", "snapshots",
          "visual_observations", "temporal_features")


def oracle(assertions: dict) -> dict:
    if any(assertions.get(key) for key in (
            "required_snapshots", "required_visual_observations", "derived_assertions")):
        raise ValueError("this lifecycle audit does not cover additional observation assertions")
    trace = {key: [] for key in GROUPS}
    for row in assertions["required_point_events"]:
        trace["events"].append({
            "round_id": row["round_id"], "type": row["type"], "actor": row["actor"],
            "time_sec": sum(row["acceptance_window"]) / 2,
            "attributes": copy.deepcopy(row.get("required_event_attributes", {})),
            "confidence": .9})
    for row in assertions["event_count_constraints"]:
        def matches(event, requirement=row):
            return (all(event[key] == requirement[key] for key in ("round_id", "type", "actor"))
                    and ("window" not in requirement
                         or requirement["window"][0] <= event["time_sec"]
                         <= requirement["window"][1]))

        count = sum(matches(event) for event in trace["events"])
        if count < row["min"]:
            if "window" not in row:
                raise ValueError("missing independently time-bounded lifecycle requirement")
            trace["events"].extend({
                "round_id": row["round_id"], "type": row["type"], "actor": row["actor"],
                "time_sec": sum(row["window"]) / 2, "attributes": {}, "confidence": .9}
                for _ in range(row["min"] - count))
    for key, dest, field in (("required_state_intervals", "state_intervals", "state"),
                             ("required_ownership_intervals", "ownership_intervals", "owner")):
        for row in assertions.get(key, []):
            if row.get("edge_brackets"):
                edges = row["edge_brackets"]
                interval = [edges["start"]["first_present_sec"],
                            edges["end"]["last_present_sec"]]
            else:
                interval = row["core_interval"]
            item = {"round_id": row["round_id"], field: row[field],
                    "interval": copy.deepcopy(interval), "confidence": .9}
            if field == "state":
                item["subtype"] = row.get("subtype")
            trace[dest].append(item)
    return trace


def negative_mutations(trace: dict, negative: dict):
    """Exercise every prohibited value, not just one representative per array."""
    supported = {"id", "window", "reason", "must_not_emit_matching",
                 "must_not_emit_player_event_types", "must_not_state_match",
                 "must_not_match_snapshot_subset", "must_not_span_temporal_features"}
    if set(negative) - supported:
        raise ValueError("unsupported negative fields must not be silently skipped")
    window = negative["window"]
    time = sum(window) / 2
    rid = trace["events"][0]["round_id"]
    variants = []
    if "must_not_emit_matching" in negative:
        event = {"round_id": rid, "type": "round_start", "actor": "system",
                 "time_sec": time, "attributes": {}, "confidence": .9}
        event.update(copy.deepcopy(negative["must_not_emit_matching"]))
        variants.append(("events", event, "negative_match"))
    for kind in negative.get("must_not_emit_player_event_types", []):
        variants.append(("events", {"round_id": rid, "type": kind, "actor": "player",
                                   "time_sec": time, "attributes": {}, "confidence": .9},
                         "negative_event"))
    if "must_not_state_match" in negative:
        state = {"round_id": rid, "interval": list(window), "confidence": .9}
        state.update(copy.deepcopy(negative["must_not_state_match"]))
        variants.append(("state_intervals", state, "negative_state"))
    if "must_not_match_snapshot_subset" in negative:
        snapshot = {"round_id": rid, "time_sec": time, "confidence": .9}
        snapshot.update(copy.deepcopy(negative["must_not_match_snapshot_subset"]))
        variants.append(("snapshots", snapshot, "poison_subset"))
    for feature in negative.get("must_not_span_temporal_features", []):
        variants.append(("temporal_features", {
            "round_id": rid, "feature": feature, "interval": list(window),
            "value": window[1] - window[0], "confidence": .9}, "discontinuity_span"))
    if not variants:
        raise ValueError("unsupported or empty negative assertion")
    for group, row, prefix in variants:
        changed = copy.deepcopy(trace)
        changed[group].append(row)
        yield changed, f"{prefix}:{negative['id']}"


def audit(assertions: dict, evaluate, schema: dict) -> dict:
    trace = oracle(assertions)
    validator = Draft202012Validator(schema)
    validator.validate(trace)
    if evaluate(assertions, trace):
        raise ValueError("positive synthetic oracle rejected")
    empty = {key: [] for key in GROUPS}
    if not evaluate(assertions, empty):
        raise ValueError("empty Analyzer trace incorrectly accepted")
    checks = {"missing_boundary": 0, "duplicate_boundary": 0, "wrong_round": 0,
              "late_boundary": 0, "negative_mutations": 0, "missing_state": 0}
    for index, row in enumerate(trace["events"]):
        for kind in ("missing_boundary", "duplicate_boundary", "wrong_round", "late_boundary"):
            changed = copy.deepcopy(trace)
            if kind == "missing_boundary":
                changed["events"].pop(index)
            elif kind == "duplicate_boundary":
                changed["events"].append(copy.deepcopy(row))
            elif kind == "wrong_round":
                changed["events"][index]["round_id"] = "unannotated_corrupt_round"
            else:
                changed["events"][index]["time_sec"] += 10
            validator.validate(changed)
            if not evaluate(assertions, changed):
                raise ValueError(f"evaluator missed {kind}")
            checks[kind] += 1
    for index in range(len(trace["state_intervals"])):
        changed = copy.deepcopy(trace)
        changed["state_intervals"].pop(index)
        if not evaluate(assertions, changed):
            raise ValueError("evaluator missed missing state")
        checks["missing_state"] += 1
    for negative in assertions["negative_assertions"]:
        for changed, expected in negative_mutations(trace, negative):
            validator.validate(changed)
            if not any(failure == expected or failure.startswith(expected + ":")
                       for failure in evaluate(assertions, changed)):
                raise ValueError("evaluator missed specific negative assertion: " + expected)
            checks["negative_mutations"] += 1
    return {"synthetic_only": True, "positive_oracle_passed": True,
            "empty_trace_rejected": True, "boundaries": len(trace["events"]),
            "checks": checks, "real_video_detection_verified": False,
            "formal_pack_completed": False}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path, required=True)
    parser.add_argument("--canonical-pack", type=Path, required=True)
    args = parser.parse_args()
    validate(args.pack, args.canonical_pack)
    path = args.pack / "tests/reference_evaluator.py"
    spec = importlib.util.spec_from_file_location("audited_pack_evaluator", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    report = audit(load(args.pack / "tests/generated/e2e_assertions_v3.json"), module.evaluate,
                   load(args.pack / "schemas/e2e_output_trace_schema_v1.json"))
    print(json.dumps(report, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
