"""Evaluation-only CLI; never imported by production analyzers."""

import argparse
import importlib.util
import json
from collections import Counter
from pathlib import Path

import jsonschema


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
