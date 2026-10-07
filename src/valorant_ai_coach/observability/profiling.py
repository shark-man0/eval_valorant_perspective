from __future__ import annotations

import json
import os
import platform
import sys
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from .context import bind_context
from .environment import package_versions, repository_state, tool_version
from .pi import raspberry_pi_metrics
from .sanitize import sanitize_value

PERFORMANCE_SCHEMA_VERSION = "1.0"


@dataclass(slots=True)
class _PhaseStats:
    duration_sec: float = 0.0
    calls: int = 0
    failures: int = 0


def _peak_rss_bytes() -> int | None:
    try:
        import resource

        usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    except (ImportError, OSError, ValueError):
        return None
    if usage <= 0:
        return None
    # Linux reports KiB, macOS reports bytes.
    return int(usage if sys.platform == "darwin" else usage * 1024)


def _resident_memory_bytes() -> int | None:
    if not sys.platform.startswith("linux"):
        return None
    try:
        fields = Path("/proc/self/statm").read_text(encoding="ascii").split()
        if len(fields) < 2:
            return None
        return int(fields[1]) * int(os.sysconf("SC_PAGE_SIZE"))
    except (OSError, ValueError):
        return None


class PerformanceRecorder:
    def __init__(
        self,
        run_id: str,
        *,
        repository_root: Path | None = None,
        include_pi_metrics: bool = True,
    ) -> None:
        self.run_id = str(run_id)
        self.repository_root = repository_root
        self.include_pi_metrics = include_pi_metrics
        self._started_perf = time.perf_counter()
        self._started_cpu = time.process_time()
        self._finished_perf: float | None = None
        self._phases: dict[str, _PhaseStats] = {}
        self.status = "running"
        self.failure_category: str | None = None

    @contextmanager
    def phase(self, name: str, *, round_no: int | str | None = None) -> Iterator[None]:
        started = time.perf_counter()
        failed = False
        with bind_context(run_id=self.run_id, phase=name, round_no=round_no):
            try:
                yield
            except BaseException:
                failed = True
                raise
            finally:
                duration = max(0.0, time.perf_counter() - started)
                stats = self._phases.setdefault(name, _PhaseStats())
                stats.duration_sec += duration
                stats.calls += 1
                if failed:
                    stats.failures += 1

    def finish(self, status: str, *, failure_category: str | None = None) -> None:
        if self._finished_perf is None:
            self._finished_perf = time.perf_counter()
        self.status = str(status)
        self.failure_category = failure_category

    def report(self) -> dict[str, Any]:
        finished = self._finished_perf or time.perf_counter()
        state = repository_state(self.repository_root)
        resource_metrics: dict[str, Any] = {
            "process_cpu_time_sec": max(0.0, time.process_time() - self._started_cpu),
            "peak_memory_bytes": _peak_rss_bytes(),
            "resident_memory_bytes": _resident_memory_bytes(),
            "thread_count": threading.active_count(),
        }
        if self.include_pi_metrics:
            resource_metrics["raspberry_pi"] = raspberry_pi_metrics()
        payload = {
            "schema_version": PERFORMANCE_SCHEMA_VERSION,
            "run_id": self.run_id,
            "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "repository": state,
            "python": {
                "implementation": platform.python_implementation(),
                "version": platform.python_version(),
            },
            "platform": {
                "os": platform.system(),
                "release": platform.release(),
                "architecture": platform.machine(),
            },
            "phase_durations": {
                name: {
                    "duration_sec": round(stats.duration_sec, 6),
                    "calls": stats.calls,
                    "failures": stats.failures,
                }
                for name, stats in sorted(self._phases.items())
            },
            "total_elapsed_sec": round(max(0.0, finished - self._started_perf), 6),
            "resources": resource_metrics,
            "tools": {
                "ffmpeg": tool_version("ffmpeg", "-version"),
                "ffprobe": tool_version("ffprobe", "-version"),
            },
            "packages": package_versions(("numpy", "opencv-python")),
            "status": self.status,
            "failure_category": self.failure_category,
        }
        return cast(dict[str, Any], sanitize_value(payload))

    def write_json(self, target: Path) -> Path:
        destination = Path(target)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(self.report(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return destination
