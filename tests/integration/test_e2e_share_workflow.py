"""Report reconciliation uses the actual evaluator, not video perception fixtures."""

import importlib.util
import json
import os
from pathlib import Path

import pytest

from scripts.e2e.share_report import export_report

ROOT = Path(__file__).resolve().parents[2]


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_canonical_evaluator_and_shared_summary_reconcile(tmp_path):
    pack = Path(
        os.environ.get("VALORANT_E2E_PACK", ROOT.parent / "valorant_e2e_validation_pack_v3")
    )
    if not pack.is_dir():
        pytest.skip("Separate validation pack is not installed")
    evaluator = load(pack / "tests/reference_evaluator.py", "share_reference")
    adapter = load(ROOT / "tests/e2e/evaluate_saved_trace.py", "share_adapter")
    assertions = json.loads((pack / "tests/generated/e2e_assertions_v3.json").read_text())
    trace = {
        key: []
        for key in (
            "events",
            "state_intervals",
            "ownership_intervals",
            "snapshots",
            "visual_observations",
            "temporal_features",
        )
    }
    expected = evaluator.evaluate(assertions, trace)
    evaluated = adapter.evaluate_trace(pack, trace)
    assert evaluated["failures"] == expected
    assert expected  # Empty detections must never become a PASS.
    path = export_report(
        raw={},
        trace=trace,
        evaluation=evaluated,
        assertions=assertions,
        metadata={"video_id": "test", "git_is_dirty": True},
        output_dir=tmp_path,
    )
    result = json.loads(path.read_text())
    assert result["result"]["status"] == "fail"
    assert result["e2e"]["failure_message_count"] == len(expected)
    for status, key in (("pass", "passed"), ("fail", "failed"), ("not_evaluated", "not_evaluated")):
        assert result["e2e"][key] == sum(
            row["status"] == status for row in evaluated["assertion_results"]
        )
    assert sum(result["e2e"][key] for key in ("passed", "failed", "not_evaluated")) == len(
        evaluated["assertion_results"]
    )
    assert result["negative_assertions"]["failed"] == 0
    assert result["negative_assertions"]["passed"] == len(assertions["negative_assertions"])
    assert str(ROOT) not in path.read_text()


def test_inconsistent_evaluator_cannot_produce_false_pass(tmp_path):
    report = export_report(
        raw={},
        trace={},
        assertions={},
        evaluation={"pass": True, "schema_valid": True, "failures": ["missing_point:p1"]},
        metadata={},
        output_dir=tmp_path,
    )
    assert json.loads(report.read_text())["result"]["status"] == "fail"
