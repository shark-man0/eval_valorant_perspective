"""Represent a human-declared approximate end using existing v3 count semantics.

This evaluator-only preparation never fabricates last-absent/first-present
evidence or changes a recognizer, confidence, Schema or existing assertion.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from jsonschema import Draft202012Validator

from scripts.e2e.run_dataset_case import sha256_file
from valorant_ai_coach.hud.calibrate_temporal import _check_output_privacy


def constraint(marker: dict, policy: dict) -> dict:
    record = marker["approved_record"]
    provenance = marker["review_provenance"]
    if (marker["boundary_kind"] != "round_end"
            or record.get("event_type") != "round_end"
            or record.get("time_origin") != "explicit_human_supplied_time_not_backcalculation"
            or provenance.get("reviewer") != "human user in current chat"
            or not provenance.get("approval_quote")
            or record.get("first_native_onset_verified") is not False
            or record.get("last_absent_sec") is not None):
        raise ValueError("scoped human-declared end without a certified onset bracket required")
    time = marker["approved_time_sec"]
    before = policy["defaults"]["point_event_before_sec"]
    after = policy["defaults"]["point_event_after_sec"]
    if (any(type(x) not in (int, float) or not math.isfinite(x) for x in (time, before, after))
            or time != record.get("event_time_sec") or not 0 <= before <= 2
            or not 0 <= after <= 2 or time < before):
        raise ValueError("explicit time and canonical finite nonnegative tolerances required")
    return {"type": "round_end", "actor": "system", "min": 1, "max": 1,
            "window": [time - before, time + after]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--canonical-pack", type=Path, required=True)
    parser.add_argument("--round-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    _check_output_privacy(args.output.resolve())
    if args.output.exists():
        raise FileExistsError("use a new private fragment path")
    policy_path = args.canonical_pack / "ground_truth/evaluation_policy_v3.json"
    schema_path = args.canonical_pack / "schemas/e2e_ground_truth_schema_v3.json"
    hashes = {p: sha256_file(p) for p in (args.ledger, policy_path, schema_path)}
    ledger = json.loads(args.ledger.read_text(encoding="utf-8"))
    if (ledger.get("kind") != "private_approved_boundary_ledger_not_validation_pack"
            or ledger.get("production_input") is not False):
        raise ValueError("private approved ledger required")
    markers = [row for row in ledger["boundaries"]
               if row["round_id"] == args.round_id and row["boundary_kind"] == "round_end"]
    if len(markers) != 1:
        raise ValueError("one explicit approved end required")
    value = constraint(markers[0], json.loads(policy_path.read_text(encoding="utf-8")))
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator({"$ref": "#/$defs/count_constraint", "$defs": schema["$defs"]}).validate(
        value)
    if any(sha256_file(p) != digest for p, digest in hashes.items()):
        raise ValueError("evaluation inputs changed during preparation")
    report = {"kind": "private_v3_round_expectation_fragment_not_complete_pack",
              "video_id": ledger["video_id"], "source_video_sha256": ledger["source_video_sha256"],
              "round_id": args.round_id, "approved_time_sec": markers[0]["approved_time_sec"],
              "round_package_expectations": {"event_count_constraints": [value]},
              "ledger_sha256": hashes[args.ledger], "policy_sha256": hashes[policy_path],
              "schema_sha256": hashes[schema_path],
              "first_native_onset_verified": False, "last_absent_sec": None,
              "production_input": False, "formal_pack_completed": False}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print("Prepared schema-valid declared-end count constraint; no pack/manifest registered")


if __name__ == "__main__":
    main()
