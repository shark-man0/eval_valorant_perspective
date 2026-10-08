"""Optional context-local stage timing for full and replay pipelines."""

from __future__ import annotations

import json
import threading
import time
from contextvars import ContextVar, Token
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class _Frame:
    collector: RuntimeTimingCollector
    name: str
    started: float
    child_seconds: float = 0.0


_stack: ContextVar[tuple[_Frame, ...]] = ContextVar("runtime_timing_stack", default=())
_active: ContextVar[RuntimeTimingCollector | None] = ContextVar(
    "runtime_timing_collector", default=None
)
_REQUIRED_STAGES = (
    "metadata_open",
    "decode",
    "hud_geometry",
    "hud_identity",
    "hud_spectator",
    "hud_menu",
    "hud_numeric_ocr",
    "hud_event_detection",
    "event_fusion",
    "round_package_build",
    "visual_trigger_scan",
    "visual_analysis",
    "trace_serialization",
    "evaluator",
    "report_generation",
)


class RuntimeTimingCollector:
    """Collect exclusive stage time; nested stages are subtracted from parents."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._started: float | None = None
        self._finished: float | None = None
        self._values: dict[str, tuple[int, float]] = {
            name: (0, 0.0) for name in _REQUIRED_STAGES
        }
        self._token: Token[tuple[_Frame, ...]] | None = None
        self._active_token: Token[RuntimeTimingCollector | None] | None = None

    def __enter__(self) -> RuntimeTimingCollector:
        if self._token is not None:
            raise RuntimeError("timing collector is already active")
        self._started = time.perf_counter()
        self._token = _stack.set(_stack.get())
        self._active_token = _active.set(self)
        return self

    def __exit__(self, *_exc: object) -> None:
        assert self._started is not None and self._token is not None
        self._finished = time.perf_counter()
        _stack.reset(self._token)
        assert self._active_token is not None
        _active.reset(self._active_token)
        self._token = None
        self._active_token = None

    def snapshot(self) -> dict[str, Any]:
        now = self._finished if self._finished is not None else time.perf_counter()
        wall = max(0.0, now - self._started) if self._started is not None else 0.0
        with self._lock:
            stages = {
                name: {
                    "calls": calls,
                    "total_sec": total,
                    "average_sec": total / calls if calls else 0.0,
                    "wall_share": total / wall if wall else 0.0,
                }
                for name, (calls, total) in sorted(self._values.items())
            }
        return {"wall_sec": wall, "stages": stages}

    def export(self, path: Path) -> dict[str, Any]:
        result = self.snapshot()
        Path(path).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        return result

    def _record(self, name: str, seconds: float) -> None:
        with self._lock:
            calls, total = self._values.get(name, (0, 0.0))
            self._values[name] = (calls + 1, total + max(0.0, seconds))


class timing_stage:
    """Context manager; does nothing when no collector is active."""

    def __init__(self, name: str) -> None:
        self.name = name
        self._frame: _Frame | None = None

    def __enter__(self) -> None:
        collector = _active.get()
        if collector is None:
            return None
        stack = _stack.get()
        self._frame = _Frame(collector, self.name, time.perf_counter())
        _stack.set((*stack, self._frame))
        return None

    def __exit__(self, *_exc: object) -> None:
        frame = self._frame
        if frame is None:
            return
        elapsed = time.perf_counter() - frame.started
        frame.collector._record(frame.name, elapsed - frame.child_seconds)
        stack = _stack.get()
        if len(stack) > 1:
            stack[-2].child_seconds += elapsed
        _stack.set(stack[:-1])
