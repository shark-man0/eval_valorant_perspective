"""Round-level reconciliation of the recorder's deaths (development only).

Sources, in order of authority:

1. ``timeline``: the shared ``DevelopmentGameTimeline`` (death hypotheses and
   ALIVE/DEAD + SELF/SPECTATOR state). It owns life state; nothing here
   overrides it.
2. ``kill_feed``: an entry whose victim end carries the game's local-player
   highlight.
3. ``hud``: the recorder's own ability HUD replaced by a teammate's (only when
   no timeline is available).

Deaths are assigned to rounds and reconciled: at most one death per round
unless the recorder is seen alive and in their own view again inside the same
round (a revive), detections that would span a round boundary are dropped, and
HUD-based detections inside a timeline SPECTATOR interval are dropped (the
recorder was already dead). Nothing here is a formal Fact or Event.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field

MERGE_WINDOW_SEC = 8.0  # one death seen by several sources / consecutive samples
REVIVE_MIN_SAMPLES = 2


@dataclass(frozen=True)
class Round:
    start: float
    end: float | None

    def contains(self, sec: float) -> bool:
        return self.start <= sec and (self.end is None or sec <= self.end)


@dataclass
class RecorderDeath:
    round_index: int
    sec: float
    sources: set[str] = field(default_factory=set)
    after_revive: bool = False


@dataclass
class Reconciliation:
    deaths: list[RecorderDeath]
    dropped: dict[str, int]
    rounds: int


def rounds_from_alive_counts(samples: Sequence[tuple[float, int | None, int | None]]
                             ) -> list[Round]:
    """Round starts where the top bar resets to 5 v 5 after a lower count.

    Used only when no timeline is available. ``samples`` are (sec, ally, enemy).
    """
    starts: list[float] = []
    previous_total: int | None = None
    for sec, ally, enemy in samples:
        if ally is None or enemy is None:
            continue
        total = ally + enemy
        if total == 10 and (previous_total is None or previous_total < 10):
            starts.append(sec)
        previous_total = total
    return [Round(start, starts[i + 1] if i + 1 < len(starts) else None)
            for i, start in enumerate(starts)]


def _round_of(rounds: Sequence[Round], sec: float) -> int | None:
    for index, span in enumerate(rounds):
        if span.contains(sec):
            return index
    return None


def reconcile(rounds: Sequence[Round], candidates: Mapping[str, Sequence[float]],
              self_live_at: Callable[[float], bool] | None = None,
              spectating_at: Callable[[float], bool] | None = None,
              live_samples: Sequence[float] = ()) -> Reconciliation:
    """Merge per-source death times into at most one death per life per round.

    ``self_live_at``/``spectating_at`` come from the timeline when available.
    ``live_samples`` are sample times at which the recorder was seen in their
    own live view (used to recognise a revive inside a round).
    """
    dropped = {"outside_round": 0, "while_spectating": 0, "duplicate": 0}
    events: list[tuple[float, str, int]] = []
    for source, times in candidates.items():
        for sec in times:
            index = _round_of(rounds, sec)
            if index is None:
                dropped["outside_round"] += 1
                continue
            if source == "hud" and spectating_at is not None and spectating_at(sec - 5.0):
                dropped["while_spectating"] += 1
                continue
            events.append((sec, source, index))
    events.sort()
    deaths: list[RecorderDeath] = []
    for sec, source, index in events:
        last = next((d for d in reversed(deaths) if d.round_index == index), None)
        if last is not None and sec - last.sec <= MERGE_WINDOW_SEC:
            last.sources.add(source)
            continue
        if last is not None:
            alive_again = [t for t in live_samples
                           if last.sec + MERGE_WINDOW_SEC < t < sec
                           and (self_live_at is None or self_live_at(t))]
            if len(alive_again) < REVIVE_MIN_SAMPLES:
                dropped["duplicate"] += 1
                last.sources.add(source)
                continue
            deaths.append(RecorderDeath(index, sec, {source}, after_revive=True))
            continue
        deaths.append(RecorderDeath(index, sec, {source}))
    return Reconciliation(deaths, dropped, len(rounds))
