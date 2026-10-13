"""Evaluation-only CLI; never imported by production analyzers."""

import argparse
import importlib.util
import json
import math
from collections import Counter
from pathlib import Path

import jsonschema


def confidence_diagnostics(trace, failures):
    """Explain canonical failures without removing them or repairing the trace.

    Native per-field confidence maps are not scalar confidences. The reference
    evaluator currently checks every *_confidence key as a scalar. Keep its
    verdict intact and report this distinct shape mismatch for contract review.
    No raw values, source paths or arbitrary field names are exported here.
    """
    counts = Counter()

    def valid_scalar(value):
        return (isinstance(value, (int, float)) and not isinstance(value, bool)
                and math.isfinite(value) and 0 <= value <= 1)

    for code in failures:
        if not code.startswith("confidence:"):
            continue
        _, group, index, field = code.split(":", 3)
        value = trace[group][int(index)][field]
        if field == "source_confidence" and isinstance(value, dict):
            counts["source_confidence_map_failures"] += 1
            counts["source_confidence_leaf_count"] += len(value)
            invalid = sum(not valid_scalar(leaf) for leaf in value.values())
            counts["invalid_source_confidence_leaf_count"] += invalid
            if not value:
                counts["empty_source_confidence_maps"] += 1
            elif not invalid:
                counts["valid_source_confidence_maps_rejected_as_scalars"] += 1
        else:
            counts["other_confidence_failures"] += 1
    return dict(counts)


def evaluate_trace(pack, trace):
    """Reuse the canonical evaluator, including isolated assertion outcomes for reports."""
    schema = json.loads(
        (pack / "schemas/e2e_output_trace_schema_v1.json").read_text(encoding="utf-8")
    )
    jsonschema.validate(trace, schema)
    assertions = json.loads(
        (pack / "tests/generated/e2e_assertions_v3.json").read_text(encoding="utf-8")
    )
    spec = importlib.util.spec_from_file_location(
        "validation_reference_evaluator", pack / "tests/reference_evaluator.py"
    )
    assert spec is not None and spec.loader is not None
    evaluator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(evaluator)
    failures = evaluator.evaluate(assertions, trace)
    for group, rows in trace.items():
        for index, row in enumerate(rows):
            if not any(k == "confidence" or k.endswith("_confidence") for k in row):
                failures.append(f"missing_confidence:{group}:{index}")
    groups = (
        "required_point_events",
        "ordering_constraints",
        "required_state_intervals",
        "required_ownership_intervals",
        "required_snapshots",
        "derived_assertions",
        "required_visual_observations",
        "event_count_constraints",
        "negative_assertions",
    )
    outcomes = []
    for group in groups:
        for index, req in enumerate(assertions.get(group, [])):
            isolated = {key: [] for key in groups}
            isolated[group] = [req]
            if group == "ordering_constraints":
                isolated["required_point_events"] = assertions["required_point_events"]
            errors = [
                code
                for code in evaluator.evaluate(isolated, trace)
                if not code.startswith("confidence:")
                and not (group == "ordering_constraints" and code.startswith("missing_point:"))
            ]
            missing_dependency = group == "ordering_constraints" and any(
                "missing_point:" + req[side] in failures for side in ("before", "after")
            )
            outcomes.append(
                {
                    "assertion_id": req.get("id", f"{group}-{index:03d}"),
                    "group": group,
                    "index": index,
                    "status": "not_evaluated"
                    if missing_dependency
                    else ("fail" if errors else "pass"),
                    "failures": errors,
                }
            )
    return {
        "pass": not failures,
        "schema_valid": True,
        "trace_counts": {k: len(v) for k, v in trace.items()},
        "failure_count": len(failures),
        "failure_categories": dict(Counter(f.split(":", 1)[0] for f in failures)),
        "confidence_diagnostics": confidence_diagnostics(trace, failures),
        "failures": failures,
        "negative_assertion_count": len(assertions["negative_assertions"]),
        "assertion_results": outcomes,
        "warning": (
            "Zero negative violations is not proof of detection: "
            "empty outputs can satisfy prohibitions."
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", required=True, type=Path)
    parser.add_argument("--trace", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    trace = json.loads(args.trace.read_text(encoding="utf-8"))
    report = evaluate_trace(args.pack, trace)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {k: v for k, v in report.items() if k not in {"failures", "assertion_results"}},
            indent=2,
        )
    )
    return int(not report["pass"])


if __name__ == "__main__":
    raise SystemExit(main())
