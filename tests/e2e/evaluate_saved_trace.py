"""Evaluation-only CLI; never imported by production analyzers."""

import argparse
import importlib.util
import json
from collections import Counter
from pathlib import Path

import jsonschema


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", required=True, type=Path)
    parser.add_argument("--trace", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    trace = json.loads(args.trace.read_text(encoding="utf-8"))
    schema = json.loads((args.pack / "schemas/e2e_output_trace_schema_v1.json").read_text())
    jsonschema.validate(trace, schema)
    assertions = json.loads((args.pack / "tests/generated/e2e_assertions_v3.json").read_text())
    spec = importlib.util.spec_from_file_location(
        "validation_reference_evaluator", args.pack / "tests/reference_evaluator.py"
    )
    assert spec is not None and spec.loader is not None
    evaluator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(evaluator)
    failures = evaluator.evaluate(assertions, trace)
    for group, rows in trace.items():
        for index, row in enumerate(rows):
            if not any(k == "confidence" or k.endswith("_confidence") for k in row):
                failures.append(f"missing_confidence:{group}:{index}")
    report = {
        "pass": not failures,
        "schema_valid": True,
        "trace_counts": {k: len(v) for k, v in trace.items()},
        "failure_count": len(failures),
        "failure_categories": dict(Counter(f.split(":", 1)[0] for f in failures)),
        "failures": failures,
        "negative_assertion_count": len(assertions["negative_assertions"]),
        "warning": (
            "Zero negative violations is not proof of detection: "
            "empty outputs can satisfy prohibitions."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
                           encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "failures"}, indent=2))
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(main())
