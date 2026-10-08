"""Write a concise, provenance-bound summary for one full or bounded E2E run."""

from __future__ import annotations

import hashlib
import json
import math
import os
import time
from collections import Counter
from collections.abc import Mapping
from pathlib import Path, PureWindowsPath
from typing import Any

from scripts.e2e.run_metrics import (
    build_runtime_summary,
    code_fingerprint,
    load_previous,
)


def export_runtime_summary(
    *,
    output: Path,
    shared: Path,
    mode: str,
    raw: Mapping[str, Any],
    evaluation: Mapping[str, Any],
    suite: Mapping[str, Any] | None,
    frame_input: Mapping[str, Any] | Path | None,
    metadata: Mapping[str, Any],
    assertions_hash: str | None,
    stages: Mapping[str, Any],
    started: float,
    initial_code: str | None,
    initial_settings: str | None,
    previous_path: str | Path | None,
    root: Path,
) -> dict[str, Any]:
    """Merge child and orchestration timing and export local JSON/Markdown results."""
    output = Path(output).expanduser().resolve()
    shared = Path(shared).expanduser().resolve()
    root = Path(root).expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    frame_spec = _frame_input(frame_input, output)
    stage_totals = _merge_stages(stages, _read_json(output / "stage_timings.json"))
    wall_sec = max(0.0, time.perf_counter() - started)

    shared_summary = _read_json(shared / "summary.json") if mode == "full" else {}
    metrics = _metrics(mode, raw, evaluation, shared_summary)
    processed_frames = _frame_count(mode, raw, evaluation, frame_spec)
    source_sha = _first_string(
        metadata.get("source_sha256"),
        raw.get("source_sha256"),
        suite.get("source_sha256") if suite else None,
        frame_spec.get("source_sha256"),
    )
    input_fingerprint: dict[str, Any] = {
        "video_id": metadata.get("video_id") or (suite or {}).get("video_id"),
        "source_sha256": source_sha,
        "validation_pack_sha256": metadata.get("validation_pack_sha256"),
        "assertions_sha256": assertions_hash,
        "input_scope": frame_spec.get("input_scope", "full_recording"),
        "profile_fingerprint": initial_settings,
        "code_fingerprint": initial_code or code_fingerprint(root),
    }
    if mode != "full":
        pts = frame_spec.get("pts_sec", [])
        prefix = frame_spec.get("calibration_prefix", [])
        input_fingerprint.update(
            suite_sha256=(suite or {}).get("suite_sha256"),
            selected_categories=(suite or {}).get("selected_categories", []),
            pts_sec=pts,
            calibration_prefix=prefix,
        )

    previous = None
    previous_resolved: Path | None = None
    if previous_path is not None:
        previous_resolved = _native_path(previous_path, root)
        previous = load_previous(previous_resolved)
    terminal_context = _terminal_context(output, metadata, assertions_hash)
    terminal_metadata = terminal_context.get("metadata", {})
    exit_code = terminal_context.get("exit_code")
    metadata_error = (
        terminal_metadata.get("error_code")
        if isinstance(terminal_metadata, Mapping)
        else None
    ) or metadata.get("error_code")
    # Failed preflight/runtime results are diagnostic artifacts only.
    successful_result = (
        raw.get("status") == "complete"
        and _has_result(evaluation)
        and type(exit_code) is int
        and exit_code in (0, 1)
        and not metadata_error
    )
    if not successful_result:
        previous = None

    summary = build_runtime_summary(
        mode=mode,
        processed_frames=processed_frames,
        wall_sec=wall_sec,
        timing={"stages": stage_totals},
        input_fingerprint=input_fingerprint,
        source_sha256=source_sha,
        metrics=metrics,
        previous=previous,
    )
    summary.update(
        code_fingerprint=initial_code or code_fingerprint(root),
        profile_fingerprint=initial_settings,
        comparison_eligible=successful_result,
        previous_path=str(previous_resolved) if previous_resolved else None,
    )
    summary["state_counts"] = _state_counts(raw)
    summary["terminal_context"] = terminal_context

    json_path = output / "runtime_summary.json"
    json_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    (output / "runtime_summary.md").write_text(
        _markdown(summary), encoding="utf-8"
    )
    return summary


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _merge_stages(
    orchestration: Mapping[str, Any], child: Mapping[str, Any]
) -> dict[str, dict[str, float | int]]:
    merged: dict[str, dict[str, float | int]] = {}
    child_stages = child.get("stages", {})
    for collection in (child_stages, orchestration):
        if not isinstance(collection, Mapping):
            continue
        for name, row in collection.items():
            if not isinstance(name, str) or not isinstance(row, Mapping):
                continue
            current = merged.setdefault(name, {"calls": 0, "total_sec": 0.0})
            current["calls"] = int(current["calls"]) + _as_int(row.get("calls"))
            current["total_sec"] = float(current["total_sec"]) + _as_float(
                row.get("total_sec")
            )
    return merged


def _metrics(
    mode: str,
    raw: Mapping[str, Any],
    evaluation: Mapping[str, Any],
    shared: Mapping[str, Any],
) -> dict[str, Any]:
    counts = (
        shared.get("e2e")
        if mode == "full" and raw.get("status") == "complete"
        else evaluation.get("counts")
    )
    result: dict[str, Any] = {}
    if isinstance(counts, Mapping):
        for name, value in counts.items():
            if isinstance(name, str) and _is_number(value):
                result[name] = value
    if mode == "full":
        result["assertions_pass"] = counts.get("passed") if isinstance(counts, Mapping) else None
        result["assertions_fail"] = counts.get("failed") if isinstance(counts, Mapping) else None
        result["assertions_not_evaluated"] = (
            counts.get("not_evaluated") if isinstance(counts, Mapping) else None
        )
    result["evaluation_pass"] = 1 if evaluation.get("pass") is True else 0
    result["schema_valid"] = 1 if evaluation.get("schema_valid") is True else 0
    for state, count in _state_counts(raw).items():
        result[f"state_{state}"] = count
    return result


def _state_counts(raw: Mapping[str, Any]) -> dict[str, int]:
    observations = raw.get("observations", [])
    if not isinstance(observations, list):
        return {}
    return dict(
        sorted(
            Counter(
                str(row.get("primary_state", "unknown"))
                for row in observations
                if isinstance(row, Mapping)
            ).items()
        )
    )


def _frame_count(
    mode: str,
    raw: Mapping[str, Any],
    evaluation: Mapping[str, Any],
    frame_spec: Mapping[str, Any],
) -> int:
    del mode, evaluation, frame_spec
    sampled = raw.get("sampled_frame_count")
    if isinstance(sampled, (int, float)) and not isinstance(sampled, bool) and sampled > 0:
        return int(sampled)
    observations = raw.get("observations", [])
    return len(observations) if isinstance(observations, list) else 0


def _frame_input(value: Mapping[str, Any] | Path | None, output: Path) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if isinstance(value, Path):
        candidate = value.expanduser().resolve()
        return _read_json(candidate)
    return _read_json(output / "frame_input.json")


def _terminal_context(
    output: Path, metadata: Mapping[str, Any], assertions_hash: str | None
) -> dict[str, Any]:
    run_metadata = _read_json(output / "run_metadata.json")
    context = dict(run_metadata)
    existing_hashes = context.get("input_hashes", {})
    hashes = dict(existing_hashes) if isinstance(existing_hashes, Mapping) else {}
    for name in (
        "raw_processing.json",
        "e2e_trace.json",
        "evaluation_report.json",
        "stage_timings.json",
        "frame_input.json",
        "command_results.json",
    ):
        candidate = output / name
        if candidate.is_file():
            hashes[name] = _sha256(candidate)
    context["input_hashes"] = hashes
    context["exit_code"] = run_metadata.get("exit_code")
    if assertions_hash is not None:
        context["assertions_sha256"] = assertions_hash
    result_path = output / "evaluation_report.json"
    context["result_artifact"] = (
        {"path": result_path.name, "sha256": _sha256(result_path)}
        if result_path.is_file()
        else None
    )
    context.setdefault("metadata", dict(metadata))
    return context


def _markdown(summary: Mapping[str, Any]) -> str:
    comparison = summary.get("current_previous_delta", {})
    deltas = comparison.get("deltas", {}) if isinstance(comparison, Mapping) else {}
    lines = [
        "# E2E runtime summary",
        "",
        f"Mode: `{summary.get('mode')}`  ",
        f"Frames: {summary.get('frame_count')}  ",
        f"Wall time: {_fmt(summary.get('wall_sec'))} s  ",
        f"Throughput: {_fmt(summary.get('fps'))} frames/s",
        "",
        _comparison_note(comparison),
        "",
        "Observed runtime deltas describe run-to-run variation; they do not by themselves "
        "establish an improvement.",
        "",
        "## Runtime and metrics",
        "",
        "| Metric | Current | Previous | Delta | Change |",
        "|---|---:|---:|---:|---:|",
        _delta_row("wall_sec", summary.get("wall_sec"), deltas.get("wall_sec")),
    ]
    metrics = summary.get("metrics", {})
    if isinstance(metrics, Mapping):
        for name, value in sorted(metrics.items()):
            if _is_number(value):
                lines.append(_delta_row(str(name), value, deltas.get(name)))
    lines.extend(
        [
            "",
            "## Stages",
            "",
            "| Stage | Total s | Calls | Average s | Wall % |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    timing = summary.get("timing", {})
    stage_rows = timing.get("stages", {}) if isinstance(timing, Mapping) else {}
    if isinstance(stage_rows, Mapping):
        for name, row in sorted(stage_rows.items()):
            if isinstance(row, Mapping):
                wall_percent = _fmt(100 * _as_float(row.get("wall_share")))
                lines.append(
                    f"| {name} | {_fmt(row.get('total_sec'))} | {row.get('calls', 0)} | "
                    f"{_fmt(row.get('average_sec'))} | {wall_percent}% |"
                )
    return "\n".join(lines) + "\n"


def _delta_row(name: str, current: Any, delta: Any) -> str:
    if isinstance(delta, Mapping):
        previous = _fmt(delta.get("previous"))
        difference = _fmt(delta.get("delta"))
        change = _fmt(delta.get("percent_change")) + "%"
    else:
        previous = difference = change = "—"
    return f"| {name} | {_fmt(current)} | {previous} | {difference} | {change} |"


def _comparison_note(comparison: Any) -> str:
    if not isinstance(comparison, Mapping):
        return "Comparison: unavailable."
    if comparison.get("comparable") is True:
        return "Comparison: same mode, video, and input fingerprint."
    reason = comparison.get("reason") or "ineligible_run"
    return f"Comparison: not comparable ({reason})."


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _first_string(*values: Any) -> str | None:
    return next((value for value in values if isinstance(value, str) and value), None)


def _native_path(value: str | Path, root: Path) -> Path:
    text = str(value)
    if os.name != "nt" and PureWindowsPath(text).drive:
        raise ValueError("previous summary path uses a foreign Windows drive")
    path = Path(value).expanduser()
    return (path if path.is_absolute() else root / path).resolve()


def _as_float(value: Any) -> float:
    if not _is_number(value):
        return 0.0
    parsed = float(value)
    return parsed if math.isfinite(parsed) and parsed >= 0 else 0.0


def _as_int(value: Any) -> int:
    if not _is_number(value):
        return 0
    return max(0, int(value))


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _has_result(evaluation: Mapping[str, Any]) -> bool:
    return type(evaluation.get("pass")) is bool


def _fmt(value: Any) -> str:
    return f"{float(value):.3f}" if _is_number(value) else "—"
