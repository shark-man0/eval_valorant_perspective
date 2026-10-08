from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.e2e.run_metrics import (
    FullRunLock,
    build_runtime_summary,
    code_fingerprint,
    load_previous,
)


def test_code_fingerprint_tracks_only_selected_python_sources(tmp_path: Path) -> None:
    source = tmp_path / "src/pkg"
    source.mkdir(parents=True)
    (source / "app.py").write_text("a = 1\n", encoding="utf-8")
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "readme.md").write_text("one", encoding="utf-8")
    first = code_fingerprint(tmp_path)
    (docs / "readme.md").write_text("two", encoding="utf-8")
    assert code_fingerprint(tmp_path) == first
    (source / "app.py").write_text("a = 2\n", encoding="utf-8")
    assert code_fingerprint(tmp_path) != first


def test_summary_recomputes_stage_shares_and_compares_same_inputs() -> None:
    previous = build_runtime_summary(
        "full", 10, 5.0, {"stages": {"decode": {"calls": 2, "total_sec": 4}}},
        {"raw": "a", "profile_fingerprint": "old", "code_fingerprint": "old"},
        "b" * 64,
        {"passed": 8, "rate": 0.5},
    )
    current = build_runtime_summary(
        "full", 20, 4.0, {"decode": {"calls": 4, "total_sec": 2}},
        {"raw": "a", "profile_fingerprint": "new", "code_fingerprint": "new"},
        "b" * 64,
        {"passed": 9, "rate": 0.75, "added": 3},
        previous,
    )
    assert current["fps"] == 5.0
    assert current["timing"]["stages"]["decode"]["wall_share"] == 0.5
    comparison = current["current_previous_delta"]
    assert comparison["comparable"] is True
    assert comparison["deltas"]["wall_sec"]["delta"] == -1.0
    assert comparison["deltas"]["wall_sec"]["percent_change"] == -20.0
    assert comparison["deltas"]["passed"]["delta"] == 1.0
    assert comparison["deltas"]["rate"]["percent_change"] == 50.0


@pytest.mark.parametrize(
    ("field", "value"),
    (("mode", "replay"), ("source_sha256", "c" * 64), ("input_fingerprint", {"raw": "other"})),
)
def test_summary_refuses_incomparable_runs(field: str, value: object) -> None:
    old = build_runtime_summary("full", 1, 1, {}, {"raw": "x"}, "b" * 64, {})
    current = build_runtime_summary("full", 2, 2, {}, {"raw": "x"}, "b" * 64, {}, old)
    old[field] = value
    current = build_runtime_summary(
        "full", 2, 2, {}, {"raw": "x"}, "b" * 64, {}, old
    )
    assert current["current_previous_delta"]["comparable"] is False


def test_load_previous_verifies_terminal_inputs_and_result_artifact(tmp_path: Path) -> None:
    raw = tmp_path / "raw_processing.json"
    evaluation = tmp_path / "evaluation_report.json"
    result = tmp_path / "runtime_result.json"
    frame_input = tmp_path / "frame_input.json"
    raw.write_text('{"status": "complete"}', encoding="utf-8")
    evaluation.write_text('{"pass": true}', encoding="utf-8")
    result.write_text('{"mode": "full"}', encoding="utf-8")
    frame_input.write_text('{"frames": 1}', encoding="utf-8")

    def digest(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    summary_path = tmp_path / "runtime_summary.json"
    summary_path.write_text(
        json.dumps(
            {
                "mode": "full",
                "terminal_context": {
                    "exit_code": 0,
                    "input_hashes": {
                        "raw_processing.json": digest(raw),
                        "evaluation_report.json": digest(evaluation),
                        "frame_input.json": digest(frame_input),
                    },
                    "result_artifact": {
                        "path": result.name,
                        "sha256": digest(result),
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    assert load_previous(tmp_path)["mode"] == "full"

    evaluation.write_text('{"pass": false}', encoding="utf-8")
    assert load_previous(summary_path) is None


def test_load_previous_rejects_missing_context_exit_code_and_result_hash(tmp_path: Path) -> None:
    summary = tmp_path / "runtime_summary.json"
    raw = tmp_path / "raw_processing.json"
    evaluation = tmp_path / "evaluation_report.json"
    result_artifact = tmp_path / "result.json"
    raw.write_text("{}", encoding="utf-8")
    evaluation.write_text("{}", encoding="utf-8")
    result_artifact.write_text("{}", encoding="utf-8")
    input_hashes = {
        name: hashlib.sha256((tmp_path / name).read_bytes()).hexdigest()
        for name in ("raw_processing.json", "evaluation_report.json")
    }
    summary.write_text('{"mode": "full"}', encoding="utf-8")
    assert load_previous(summary) is None
    context = {
        "input_hashes": input_hashes,
        "result_artifact": {
            "path": result_artifact.name,
            "sha256": hashlib.sha256(result_artifact.read_bytes()).hexdigest(),
        },
    }
    summary.write_text(json.dumps({"terminal_context": context}), encoding="utf-8")
    assert load_previous(summary) is None  # Missing terminal exit status.
    context["exit_code"] = 0
    context["result_artifact"] = {"path": result_artifact.name}
    summary.write_text(json.dumps({"terminal_context": context}), encoding="utf-8")
    assert load_previous(summary) is None  # Result artifact lacks a verified digest.


def test_load_previous_requires_comparison_eligibility_and_valid_raw_result(tmp_path: Path) -> None:
    summary = tmp_path / "runtime_summary.json"
    raw = tmp_path / "raw_processing.json"
    evaluation = tmp_path / "evaluation_report.json"
    raw.write_text('{"status": "complete"}', encoding="utf-8")
    evaluation.write_text('{"pass": true}', encoding="utf-8")
    result = tmp_path / "result.json"
    result.write_text("{}", encoding="utf-8")

    def digest(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    runtime_summary = {
        "comparison_eligible": True,
        "terminal_context": {
            "exit_code": 0,
            "input_hashes": {
                "raw_processing.json": digest(raw),
                "evaluation_report.json": digest(evaluation),
            },
            "result_artifact": {"path": "result.json", "sha256": digest(result)},
        },
    }
    summary.write_text(json.dumps(runtime_summary), encoding="utf-8")
    assert load_previous(summary) is not None

    runtime_summary["comparison_eligible"] = False
    summary.write_text(json.dumps(runtime_summary), encoding="utf-8")
    assert load_previous(summary) is None

    runtime_summary.pop("comparison_eligible")
    raw.write_text('{"status": "error"}', encoding="utf-8")
    runtime_summary["terminal_context"]["input_hashes"]["raw_processing.json"] = digest(raw)
    summary.write_text(json.dumps(runtime_summary), encoding="utf-8")
    assert load_previous(summary) is None


def test_explicit_identity_keys_only_are_ignored_in_fingerprint_comparison() -> None:
    old = build_runtime_summary(
        "full", 1, 2, {},
        {"raw": "x", "profile_fingerprint": "p1", "code_fingerprint": "c1"},
        "b" * 64,
        {},
    )
    current = build_runtime_summary(
        "full", 1, 2, {},
        {"raw": "x", "profile_name": "p2", "code_sha": "c2"},
        "b" * 64,
        {},
        old,
    )
    assert current["current_previous_delta"]["comparable"] is False


def test_full_run_lock_rejects_a_second_process_and_releases(tmp_path: Path) -> None:
    child = (
        "from scripts.e2e.run_metrics import FullRunLock; "
        "from pathlib import Path; import sys; "
        "\ntry:\n with FullRunLock(Path(sys.argv[1])): pass\n"
        "except ValueError:\n print('busy')\n"
    )
    with FullRunLock(tmp_path):
        result = subprocess.run(
            [sys.executable, "-c", child, str(tmp_path)],
            check=True,
            capture_output=True,
            text=True,
        )
        assert result.stdout.strip() == "busy"
    with FullRunLock(tmp_path):
        pass
