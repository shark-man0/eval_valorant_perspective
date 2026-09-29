from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from valorant_ai_coach.models import RuleCandidate


@dataclass(frozen=True, slots=True)
class PlannedFrame:
    time_sec: float
    purpose: str


class FramePlanner:
    """Plan sparse round context separately from dense candidate evidence."""

    _DENSE_OFFSETS: dict[str, tuple[float, ...]] = {
        "micro": (-2.0, -1.0, 0.0, 1.0, 2.0),
        "local": (-8.0, -4.0, 0.0, 4.0, 8.0),
        "phase": (-15.0, -7.5, 0.0, 7.5, 15.0),
        "round": (-10.0, 0.0, 10.0),
        "cross_round": (-10.0, 0.0, 10.0),
        "match": (-3.0, 0.0, 3.0),
    }

    def __init__(self, *, max_sparse: int = 10, max_dense: int = 22) -> None:
        if max_sparse < 0 or max_dense < 0:
            raise ValueError("フレーム上限は0以上である必要があります")
        self.max_sparse = max_sparse
        self.max_dense = max_dense

    def plan(
        self, round_package: dict[str, Any], candidates: list[RuleCandidate]
    ) -> list[PlannedFrame]:
        start = float(round_package["round_window"]["start_sec"])
        end = float(round_package["round_window"]["end_sec"])
        if end <= start:
            raise ValueError("round_windowの終了時刻は開始時刻より後である必要があります")
        dense_times: set[float] = set()
        dense_centers: set[float] = set()
        events = round_package.get("events", [])
        for candidate in candidates:
            relevant = [
                float(event["time_sec"])
                for event in events
                if event["type"] in candidate.matched_event_types
            ]
            if not relevant:
                continue
            offsets = self._DENSE_OFFSETS.get(
                candidate.temporal_level, self._DENSE_OFFSETS["local"]
            )
            for center in relevant:
                dense_centers.add(self._clamp(round(center, 3), start, end))
                for offset in offsets:
                    dense_times.add(self._clamp(round(center + offset, 3), start, end))
        centers = self._evenly_limit(sorted(dense_centers), self.max_dense)
        remaining = max(0, self.max_dense - len(centers))
        surrounding = sorted(dense_times - set(centers))
        dense = sorted(centers + self._evenly_limit(surrounding, remaining))
        sparse = self._sparse_times(start, end, self.max_sparse)

        # Keep candidate evidence when a sparse point lands on the same timestamp.
        result = [PlannedFrame(value, "dense_candidate_context") for value in dense]
        dense_keys = {round(value, 3) for value in dense}
        result.extend(
            PlannedFrame(value, "sparse_round_context")
            for value in sparse
            if round(value, 3) not in dense_keys
        )
        return sorted(result, key=lambda frame: frame.time_sec)

    @staticmethod
    def _sparse_times(start: float, end: float, limit: int) -> list[float]:
        if limit <= 0:
            return []
        if limit == 1:
            return [round((start + end) / 2, 3)]
        return [round(start + (end - start) * index / (limit - 1), 3) for index in range(limit)]

    @staticmethod
    def _evenly_limit(values: list[float], limit: int) -> list[float]:
        if limit <= 0:
            return []
        if len(values) <= limit:
            return values
        if limit == 1:
            return [values[len(values) // 2]]
        indexes = [round(index * (len(values) - 1) / (limit - 1)) for index in range(limit)]
        return [values[index] for index in indexes]

    @staticmethod
    def _clamp(value: float, start: float, end: float) -> float:
        return max(start, min(end, value))
