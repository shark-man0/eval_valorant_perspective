from __future__ import annotations

import json
import time
from pathlib import Path

from scripts.e2e.runtime_summary import export_runtime_summary


def _write_run(output: Path, shared: Path, *, previous_path=None, run_metadata=None):
    output.mkdir(parents=True, exist_ok=True)
    shared.mkdir(parents=True, exist_ok=True)
    raw = {
        "status": "complete",
        "sampled_frame_count": 2,
        "observations": [
            {"primary_state": "live_first_person"},
            {"primary_state": "buy_phase"},
        ],
    }
    evaluation = {
        "pass": True,
        "schema_valid": True,
        "counts": {"passed": 1, "failed": 0, "not_evaluated": 1},
    }
    frame_input = {
        "input_scope": "isolated_points",
        "pts_sec": [4.0, 8.0],
        "calibration_prefix": [0.0, 1.0],
    }
    for name, value in (
        ("raw_processing.json", raw),
        ("e2e_trace.json", {"events": []}),
        ("evaluation_report.json", evaluation),
        ("frame_input.json", frame_input),
        ("stage_timings.json", {"stages": {"decode": {"calls": 1, "total_sec": 4.0}}}),
        ("command_results.json", [{"command": "analyzer", "exit_code": 0}]),
        (
            "run_metadata.json",
            run_metadata or {"exit_code": 0, "input_hashes": {}},
        ),
    ):
        (output / name).write_text(json.dumps(value), encoding="utf-8")
    return export_runtime_summary(
        output=output,
        shared=shared,
        mode="sampled",
        raw=raw,
        evaluation=evaluation,
        suite={
            "suite_sha256": "d" * 64,
            "selected_categories": ["state"],
            "video_id": "match_001",
            "source_sha256": "a" * 64,
        },
        frame_input=frame_input,
        metadata={
            "video_id": "match_001",
            "source_sha256": "a" * 64,
            "validation_pack_sha256": "b" * 64,
        },
        assertions_hash="c" * 64,
        stages={"evaluator": {"calls": 1, "total_sec": 2.0}},
        started=time.perf_counter() - 10,
        initial_code="e" * 64,
        initial_settings="f" * 64,
        previous_path=previous_path,
        root=output,
    )


def test_export_merges_stages_writes_local_summary_and_provenance(tmp_path: Path) -> None:
    output = tmp_path / "run"
    summary = _write_run(output, tmp_path / "shared")

    assert summary["frame_count"] == 2
    assert summary["metrics"]["passed"] == 1
    assert summary["metrics"]["state_live_first_person"] == 1
    assert summary["timing"]["stages"]["decode"]["total_sec"] == 4.0
    assert summary["timing"]["stages"]["evaluator"]["total_sec"] == 2.0
    assert summary["timing"]["stages"]["decode"]["wall_share"] < 0.5
    assert summary["current_previous_delta"]["comparable"] is False
    assert summary["terminal_context"]["exit_code"] == 0
    assert {
        "stage_timings.json",
        "frame_input.json",
        "command_results.json",
        "raw_processing.json",
        "evaluation_report.json",
    }.issubset(summary["terminal_context"]["input_hashes"])
    assert summary["terminal_context"]["result_artifact"]["path"] == "evaluation_report.json"
    assert json.loads((output / "runtime_summary.json").read_text())["mode"] == "sampled"
    markdown = (output / "runtime_summary.md").read_text()
    assert "| Stage | Total s | Calls | Average s | Wall % |" in markdown
    assert "| wall_sec |" in markdown
    assert "Observed runtime deltas describe run-to-run variation" in markdown
    assert "| passed |" in markdown


def test_export_loads_previous_summary_and_compares_matching_inputs(tmp_path: Path) -> None:
    old_dir = tmp_path / "old"
    _write_run(old_dir, tmp_path / "old_shared")
    current = _write_run(tmp_path / "current", tmp_path / "current_shared", previous_path=old_dir)
    assert current["current_previous_delta"]["comparable"] is True


def test_failed_preflight_is_diagnostic_and_ineligible(tmp_path: Path) -> None:
    output = tmp_path / "failed"
    output.mkdir()
    (output / "frame_input.json").write_text(
        json.dumps({"pts_sec": [1.0, 2.0]}), encoding="utf-8"
    )
    summary = export_runtime_summary(
        output=output,
        shared=tmp_path / "shared",
        mode="full",
        raw={"status": "error", "observations": []},
        evaluation={},
        suite=None,
        frame_input=None,
        metadata={"video_id": "match_001"},
        assertions_hash=None,
        stages={},
        started=time.perf_counter() - 1,
        initial_code="a" * 64,
        initial_settings=None,
        previous_path=None,
        root=tmp_path,
    )
    assert summary["comparison_eligible"] is False
    assert summary["frame_count"] == 0
    assert summary["current_previous_delta"]["comparable"] is False
    assert (output / "runtime_summary.json").is_file()


def test_complete_data_with_bad_terminal_status_or_error_is_ineligible(tmp_path: Path) -> None:
    output = tmp_path / "failed-terminal"
    summary = _write_run(
        output,
        tmp_path / "shared",
        run_metadata={"exit_code": 2, "input_hashes": {}},
    )
    assert summary["comparison_eligible"] is False

    summary = _write_run(
        output,
        tmp_path / "shared",
        run_metadata={
            "exit_code": 0,
            "input_hashes": {},
            "metadata": {"error_code": "PREFLIGHT_FAILED"},
        },
    )
    assert summary["comparison_eligible"] is False
