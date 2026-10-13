"""match_002 policy v1: typed snapshot source confidence, unchanged v3 checks.

Installed beside a byte-identical reference_evaluator_v3_base.py in a private
match_002 Pack. No trace fields are removed, averaged, or rewritten.
"""
from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path
from types import FunctionType

from jsonschema import Draft202012Validator

POLICY_VERSION = "match_002.snapshot_source_confidence.v1"


def load_base(root: Path):
    spec = importlib.util.spec_from_file_location(
        "unchanged_v3_evaluator", root / "tests/reference_evaluator_v3_base.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def typed_confidence_failures(output, base, schema):
    """Only the exact native dictionary field receives its native typed check."""
    failures = base._finite_confidence_failures(output)
    validator = Draft202012Validator(schema["$defs"]["snapshot_source_confidence"])
    valid_maps = set()
    for index, snapshot in enumerate(output.get("snapshots", [])):
        value = snapshot.get("source_confidence")
        if (isinstance(value, dict) and validator.is_valid(value)
                and all(type(v) in (int, float) and math.isfinite(v) and 0 <= v <= 1
                        for v in value.values())):
            valid_maps.add(f"confidence:snapshots:{index}:source_confidence")
        elif "source_confidence" in snapshot:
            # Scalar values also violate the native object contract, even if
            # the original scalar-only confidence checker accepted them.
            failure = f"confidence:snapshots:{index}:source_confidence"
            if failure not in failures:
                failures.append(failure)
    return [failure for failure in failures if failure not in valid_maps]


def evaluate(assertions, output):
    root = Path(__file__).resolve().parents[1]
    base = load_base(root)
    schema = json.loads((root / "schemas/round_package_schema_v2.json").read_text(
        encoding="utf-8"))
    namespace = dict(base.evaluate.__globals__)
    namespace["_finite_confidence_failures"] = lambda trace: typed_confidence_failures(
        trace, base, schema)
    # The original evaluation function and every other check remain unchanged;
    # using separate globals avoids mutating the imported base evaluator.
    adapted = FunctionType(base.evaluate.__code__, namespace, "evaluate")
    return adapted(assertions, output)
