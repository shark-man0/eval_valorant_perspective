from __future__ import annotations

import math
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from heapq import merge
from itertools import groupby
from pathlib import Path
from threading import Event
from typing import Any

from .service import FrameSample, VideoMetadata


@dataclass(frozen=True, slots=True)
class SampleRequest:
    time_sec: float
    purposes: tuple[str, ...]


class HudFrameSampler:
    """Create bounded two-pass sampling requests for HUD analysis."""

    def __init__(
        self,
        *,
        general_fps: float = 2.0,
        change_fps: float = 4.0,
        burst_fps: float = 12.0,
        burst_radius_sec: float = 0.75,
        max_pass_a_frames: int = 2400,
        max_pass_b_frames: int = 2400,
    ) -> None:
        for value in (general_fps, change_fps, burst_fps, burst_radius_sec):
            if not math.isfinite(value) or value <= 0:
                raise ValueError("sampling rate/radiusは0より大きい有限値が必要です")
        self.general_fps = general_fps
        self.change_fps = change_fps
        self.burst_fps = burst_fps
        self.burst_radius_sec = burst_radius_sec
        self.max_pass_a_frames = max(1, int(max_pass_a_frames))
        self.max_pass_b_frames = max(1, int(max_pass_b_frames))

    def pass_a(self, duration_sec: float) -> tuple[SampleRequest, ...]:
        """Compatibility collector; use pass_a_batches for bounded planning."""
        return tuple(item for batch in self.pass_a_batches(duration_sec) for item in batch)

    def pass_a_batches(self, duration_sec: float) -> Iterator[tuple[SampleRequest, ...]]:
        """Keep native cadence for arbitrarily long recordings, bounded per batch.

        The global timestamp grid never restarts at a batch boundary, so samples
        are neither duplicated nor omitted and temporal analysis stays continuous.
        """
        duration = self._duration(duration_sec)
        points = merge(
            self._grid(duration, self.general_fps, "general_hud"),
            self._grid(duration, self.change_fps, "change_sensitive_hud"),
        )
        batch: list[SampleRequest] = []
        for timestamp, group in groupby(points, key=lambda item: item[0]):
            batch.append(SampleRequest(timestamp, tuple(sorted({tag for _, tag in group}))))
            if len(batch) == self.max_pass_a_frames:
                yield tuple(batch)
                batch = []
        if batch:
            yield tuple(batch)

    @staticmethod
    def _grid(duration: float, fps: float, purpose: str) -> Iterator[tuple[float, str]]:
        for index in range(max(1, math.ceil(duration * fps)) + 1):
            yield round(min(duration, index / fps), 6), purpose

    def pass_b(
        self, duration_sec: float, change_times_sec: Sequence[float]
    ) -> tuple[SampleRequest, ...]:
        duration = self._duration(duration_sec)
        purposes: dict[float, set[str]] = {}
        step = 1.0 / self.burst_fps
        for value in sorted(set(float(item) for item in change_times_sec)):
            if not math.isfinite(value) or value < 0 or value > duration:
                continue
            left = max(0.0, value - self.burst_radius_sec)
            right = min(duration, value + self.burst_radius_sec)
            count = max(1, math.ceil((right - left) / step))
            for index in range(count + 1):
                timestamp = min(right, left + index * step)
                purposes.setdefault(round(timestamp, 6), set()).add("hud_change_burst")
        requests = self._requests(purposes)
        if len(requests) > self.max_pass_b_frames:
            stride = len(requests) / self.max_pass_b_frames
            requests = tuple(
                requests[min(len(requests) - 1, int(index * stride))]
                for index in range(self.max_pass_b_frames)
            )
        return requests

    @staticmethod
    def merge(*request_sets: Sequence[SampleRequest]) -> tuple[SampleRequest, ...]:
        purposes: dict[float, set[str]] = {}
        for requests in request_sets:
            for request in requests:
                purposes.setdefault(round(request.time_sec, 6), set()).update(request.purposes)
        return HudFrameSampler._requests(purposes)

    @staticmethod
    def change_times(observations: Sequence[dict[str, Any]]) -> tuple[float, ...]:
        """Find transitions worth dense HUD re-analysis, without visual inference."""

        found: list[float] = []
        previous: tuple[object, ...] | None = None
        previous_timer: float | None = None
        for observation in sorted(observations, key=lambda item: float(item.get("time_sec", 0.0))):
            values = observation.get("values")
            value_map = values if isinstance(values, dict) else {}
            current = (
                observation.get("primary_state"),
                tuple(observation.get("state_flags", ())),
                value_map.get("ally_alive"),
                value_map.get("enemy_alive"),
                value_map.get("hp"),
                value_map.get("spike_state"),
                value_map.get("score_ally"),
                value_map.get("score_enemy"),
                repr(value_map.get("kill_feed_rows", [])),
                value_map.get("combat_report_visible"),
            )
            timer_value = value_map.get("round_time_remaining_sec")
            timer = float(timer_value) if isinstance(timer_value, (int, float)) else None
            reset = timer is not None and previous_timer is not None and timer > previous_timer + 1
            if previous is not None and (current != previous or reset):
                found.append(float(observation.get("time_sec", 0.0)))
            previous = current
            previous_timer = timer
        return tuple(found)

    @staticmethod
    def extract_in_batches(
        extractor: Callable[..., list[FrameSample]],
        *,
        path: Path,
        requests: Sequence[SampleRequest],
        output_dir: Path,
        metadata: VideoMetadata,
        cancel_event: Event | None = None,
        batch_size: int = 500,
    ) -> list[FrameSample]:
        if batch_size <= 0:
            raise ValueError("batch_sizeは1以上が必要です")
        samples: list[FrameSample] = []
        for offset in range(0, len(requests), batch_size):
            if cancel_event is not None and cancel_event.is_set():
                raise InterruptedError("HUDフレーム抽出がキャンセルされました")
            batch = requests[offset : offset + batch_size]
            samples.extend(
                extractor(
                    path,
                    [request.time_sec for request in batch],
                    output_dir / f"batch-{offset // batch_size:03d}",
                    max_frames=len(batch),
                    jpeg_quality=92,
                    max_dimension=None,
                    metadata=metadata,
                    cancel_event=cancel_event,
                )
            )
        return samples

    @staticmethod
    def _duration(value: float) -> float:
        duration = float(value)
        if not math.isfinite(duration) or duration <= 0:
            raise ValueError("動画時間は0より大きい有限値が必要です")
        return duration

    @staticmethod
    def _add_grid(
        purposes: dict[float, set[str]], duration: float, fps: float, purpose: str
    ) -> None:
        step = 1.0 / fps
        count = max(1, math.ceil(duration / step))
        for index in range(count + 1):
            timestamp = min(duration, index * step)
            purposes.setdefault(round(timestamp, 6), set()).add(purpose)

    @staticmethod
    def _requests(purposes: dict[float, set[str]]) -> tuple[SampleRequest, ...]:
        return tuple(
            SampleRequest(time_sec, tuple(sorted(tags)))
            for time_sec, tags in sorted(purposes.items())
        )
