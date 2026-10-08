from __future__ import annotations

import json

import pytest

from valorant_ai_coach.diagnostics import runtime_timing
from valorant_ai_coach.diagnostics.runtime_timing import RuntimeTimingCollector, timing_stage


def test_nested_stages_report_exclusive_time_and_calls(monkeypatch) -> None:
    clock = [0.0]
    monkeypatch.setattr(runtime_timing.time, "perf_counter", lambda: clock[0])
    with RuntimeTimingCollector() as timing:  # noqa: SIM117
        # Nested scopes are required to test exclusive parent accounting.
        with timing_stage("parent"):
            with timing_stage("child"):
                clock[0] += 3.0
            with timing_stage("child"):
                clock[0] += 2.0
            clock[0] += 4.0

    result = timing.snapshot()
    assert result["stages"]["child"]["calls"] == 2
    assert result["stages"]["child"]["total_sec"] == 5.0
    assert result["stages"]["parent"]["calls"] == 1
    assert result["stages"]["parent"]["total_sec"] == 4.0
    assert result["stages"]["child"]["average_sec"] == 2.5
    assert result["stages"]["child"]["wall_share"] > 0
    assert result["stages"]["parent"]["wall_share"] > 0


def test_timing_is_noop_without_collector_and_export_is_json(tmp_path) -> None:
    with timing_stage("ignored"):
        pass

    with RuntimeTimingCollector() as timing, timing_stage("work"):
        pass
    destination = tmp_path / "timing.json"
    exported = timing.export(destination)
    assert json.loads(destination.read_text(encoding="utf-8")) == exported
    assert exported["stages"]["work"]["calls"] == 1
    assert "ignored" not in exported["stages"]
    assert exported["stages"]["evaluator"] == {
        "calls": 0,
        "total_sec": 0.0,
        "average_sec": 0.0,
        "wall_share": 0.0,
    }


def test_repeated_calls_are_aggregated_without_retaining_samples(monkeypatch) -> None:
    clock = [0.0]
    monkeypatch.setattr(runtime_timing.time, "perf_counter", lambda: clock[0])
    with RuntimeTimingCollector() as timing:
        for _ in range(500):
            with timing_stage("decode"):
                clock[0] += 0.002

    stage = timing.snapshot()["stages"]["decode"]
    assert stage["calls"] == 500
    assert stage["total_sec"] == pytest.approx(1.0)
    assert stage["average_sec"] == pytest.approx(0.002)
