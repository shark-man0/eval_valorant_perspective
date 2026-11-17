"""Read-only view of the shared development timeline for knowledge consumers.

The shared timeline (``DevelopmentGameTimeline``) owns round, life and camera
state. Knowledge readers use this view to restrict per-frame evidence to the
moments the timeline calls ``SELF`` + ``ALIVE`` (the recorder's own live view),
to skip ``SPECTATOR`` intervals, and to bound inferences by round. They never
write timeline state, and nothing here becomes a formal Fact or Event.

Two inputs are accepted: the timeline's replay export
(``events_and_states_PRIVATE.json`` with ``native_states``/``events``), and a
compact JSON with ``states`` rows ``[sec, round, life, camera, round_number,
round_number_status]`` and ``events`` rows ``[kind, lower_sec, upper_sec]``.
"""

from __future__ import annotations

import bisect
import json
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any

MAX_STATE_GAP_SEC = 2.5  # a state older than this is treated as unknown


@dataclass(frozen=True)
class TimelineState:
    sec: float
    round: str
    life: str
    camera: str
    round_number: int | None

    @property
    def self_live(self) -> bool:
        return self.life == "ALIVE" and self.camera == "SELF"

    @property
    def spectating(self) -> bool:
        return self.camera == "SPECTATOR"


@dataclass(frozen=True)
class RoundSpan:
    start: float
    end: float | None


class TimelineView:
    def __init__(self, states: list[TimelineState], events: list[tuple[str, float, float]],
                 *, source_sha256: str = "") -> None:
        self.states = sorted(states, key=lambda s: s.sec)
        self._secs = [s.sec for s in self.states]
        self.events = sorted(events, key=lambda e: e[1])
        self.source_sha256 = source_sha256

    # Loading -----------------------------------------------------------------
    @classmethod
    def from_compact(cls, data: dict[str, Any]) -> TimelineView:
        states = [TimelineState(float(r[0]), str(r[1]), str(r[2]), str(r[3]),
                                None if r[4] is None else int(r[4])) for r in data["states"]]
        events = [(str(k), float(lo), float(hi)) for k, lo, hi in data["events"]
                  if lo is not None and hi is not None]
        return cls(states, events, source_sha256=str(data.get("source_sha256", "")))

    @classmethod
    def from_replay_export(cls, data: dict[str, Any]) -> TimelineView:
        def sec(sample: dict[str, Any]) -> float:
            return float(Fraction(sample["native_pts_tick"]) * Fraction(sample["native_time_base"]))

        states = []
        for row in data["native_states"]:
            number = (row.get("round_number") or {}).get("value")
            states.append(TimelineState(sec(row["sample"]), row["round"]["value"],
                                        row["life"]["value"], row["camera"]["value"],
                                        None if number is None else int(number)))
        events = [(e["kind"], float(e["lower_timestamp"]), float(e["upper_timestamp"]))
                  for e in data["events"]
                  if e["kind"] != "state_change" and e.get("lower_timestamp") is not None]
        sha = data["native_states"][0]["sample"].get("source_sha256", "") if states else ""
        return cls(states, events, source_sha256=sha)

    @classmethod
    def load(cls, path: Path) -> TimelineView:
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls.from_replay_export(data) if "native_states" in data else cls.from_compact(data)

    # Queries -------------------------------------------------------------------
    def state_at(self, sec: float) -> TimelineState | None:
        index = bisect.bisect_right(self._secs, sec) - 1
        if index < 0:
            return None
        state = self.states[index]
        return state if sec - state.sec <= MAX_STATE_GAP_SEC else None

    def self_live(self, sec: float) -> bool:
        state = self.state_at(sec)
        return bool(state and state.self_live)

    def spectating(self, sec: float) -> bool:
        state = self.state_at(sec)
        return bool(state and state.spectating)

    def rounds(self) -> list[RoundSpan]:
        """Round spans from round_start/round_end events.

        A round whose end was not seen is bounded by the next round start; only
        the last round can stay open (end None).
        """
        starts = [lo for kind, lo, _ in self.events if kind == "round_start"]
        ends = [hi for kind, _, hi in self.events if kind == "round_end"]
        spans = []
        for index, start in enumerate(starts):
            following = starts[index + 1] if index + 1 < len(starts) else None
            limit = following if following is not None else float("inf")
            end = next((e for e in ends if start < e <= limit), following)
            spans.append(RoundSpan(start, end))
        return spans

    def round_index(self, sec: float) -> int | None:
        """Index of the round span containing ``sec`` (start <= sec <= end)."""
        for index, span in enumerate(self.rounds()):
            if span.start <= sec and (span.end is None or sec <= span.end):
                return index
        return None

    def death_times(self) -> list[float]:
        """Timeline death hypotheses (upper bracket time)."""
        return [hi for kind, _, hi in self.events if kind == "death_hypothesis"]
