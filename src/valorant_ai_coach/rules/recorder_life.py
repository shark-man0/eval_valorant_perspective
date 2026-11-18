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
recorder was already dead). A buy-phase clock restart between two deaths of one
round means the round source merged two rounds: the later death is kept as a
death of an unsplit round (``after_round_restart``), never as a revive, and the
revive evidence must lie before the restart. Nothing here is a formal Fact or Event.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field

MERGE_WINDOW_SEC = 8.0  # one death seen by several sources / consecutive samples
REVIVE_MIN_SAMPLES = 2
REVIVE_MIN_SPAN_SEC = 5.0  # own live view must last this long between two deaths
RESET_AFTER_SCORE_SEC = 20.0  # score shows the new point during the round-end screen
MIN_ROUND_SEC = 20.0  # two score rises closer than this are one boundary seen twice
MIN_ROUND_GAP_SEC = 45.0  # buy phase plus the shortest round


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
    after_round_restart: bool = False  # the round source missed a boundary before it


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


def rounds_from_scores(tracks: Sequence[Sequence[tuple[float, int]]],
                       resets: Sequence[float] = (),
                       buy_phase_starts: Sequence[float] = ()) -> list[Round]:
    """Rounds from the top-bar score: a round ends exactly when one team's
    score rises, so, unlike boundary counting, a missed or spurious 5 v 5 reset
    cannot add or drop rounds. ``tracks`` are confirmed (sec, score) reads per
    team; either team alone is enough to place a boundary, which matters when
    one score is unreadable for a while.

    The score changes on the round-end screen and its first new read can also
    come well into the next round, so ``resets`` (top-bar 5 v 5 resets) place
    the start: the first reset after the last read of the old score and at most
    ``RESET_AFTER_SCORE_SEC`` after the new read. Other resets are ignored,
    except ``buy_phase_starts`` (resets followed by a whole buy phase at 5 v 5),
    which add a boundary the score missed when no boundary is near.
    """
    first = min((track[0][0] for track in tracks if track), default=None)
    if first is None:
        return []
    boundaries: list[float] = []
    for track in tracks:
        for (old_sec, old), (sec, value) in zip(track, track[1:], strict=False):
            if value > old:
                # A rise by n (score unreadable for a while) closes n rounds; the
                # earliest n resets in the gap place them where they can.
                between = sorted(r for r in resets if old_sec < r <= sec + RESET_AFTER_SCORE_SEC)
                placed = between[:value - old]
                boundaries.extend(placed if placed else [sec])
    starts = [first]
    for boundary in sorted(boundaries):
        if boundary - starts[-1] >= MIN_ROUND_SEC:
            starts.append(boundary)
    for extra in buy_phase_starts:
        if extra > first and all(abs(extra - start) >= MIN_ROUND_GAP_SEC for start in starts):
            starts.append(extra)
    starts.sort()
    return [Round(start, starts[i + 1] if i + 1 < len(starts) else None)
            for i, start in enumerate(starts)]


def _round_of(rounds: Sequence[Round], sec: float) -> int | None:
    # Latest round first: a sample exactly at a boundary belongs to the round that
    # starts there (spans share their boundary with the next start).
    for index in range(len(rounds) - 1, -1, -1):
        if rounds[index].contains(sec):
            return index
    return None


BUY_RESTART_MAX_GAP_SEC = 15.0
BUY_RESTART_FROM_MAX = 12  # post-round countdown / end of the previous clock


def buy_phase_restarts(clock: Sequence[tuple[float, int | None]], *,
                       buy_lengths: tuple[int, ...] = (30, 45)) -> list[float]:
    """When combat of a new round can start, from buy countdowns: a low reading
    followed, within ``BUY_RESTART_MAX_GAP_SEC``, by a reading no longer than a buy
    phase that the next reading confirms by counting down; the time returned is
    the end of that countdown. A jump to the combat clock (about 100 s) is the
    same round and is not a restart."""
    readings = [(sec, value) for sec, value in clock if value is not None]
    longest = max(buy_lengths)
    out: list[float] = []
    for (t0, v0), (t1, v1), (t2, v2) in zip(readings, readings[1:], readings[2:], strict=False):
        if (v0 <= BUY_RESTART_FROM_MAX and v1 <= longest and v1 >= v0 + 10
                and t1 - t0 <= BUY_RESTART_MAX_GAP_SEC
                and 0 <= v1 - v2 <= (t2 - t1) + 2 and t2 - t1 <= BUY_RESTART_MAX_GAP_SEC):
            combat = t1 + v1  # no one can die before the buy countdown ends
            if not out or combat - out[-1] > 20:
                out.append(combat)
    return out


MAX_SCORE_STEP = 3
COMBAT_CLOCK_MIN = 90  # the combat clock starts at 1:40
COMBAT_START_FROM_MAX = 5
COMBAT_START_MAX_GAP_SEC = 8.0


def combat_starts(clock: Sequence[tuple[float, int | None]]) -> list[float]:
    """Times the combat clock starts (a buy countdown near zero, then about 100 s,
    confirmed by the next reading counting down). It starts once per round, so
    two deaths with a combat start between them are in different rounds."""
    readings = [(sec, value) for sec, value in clock if value is not None]
    out: list[float] = []
    for (t0, v0), (t1, v1), (t2, v2) in zip(readings, readings[1:], readings[2:], strict=False):
        if (v0 <= COMBAT_START_FROM_MAX and v1 >= COMBAT_CLOCK_MIN
                and t1 - t0 <= COMBAT_START_MAX_GAP_SEC
                and 0 <= v1 - v2 <= (t2 - t1) + 2 and t2 - t1 <= COMBAT_START_MAX_GAP_SEC):
            out.append(t1)
    return out


def score_rises(scores: Sequence[tuple[float, int | None, int | None]]) -> list[float]:
    """After each confirmed rise of the total score (a round ended), the earliest
    time the next round can be under way: the rise plus ``RESET_AFTER_SCORE_SEC``
    (round-end screen and buy phase). Unconfirmed misreads and drops are ignored."""
    readings = [(sec, a + e) for sec, a, e in scores if a is not None and e is not None]
    out: list[float] = []
    stable: int | None = None
    for (t0, v0), (_, v1) in zip(readings, readings[1:], strict=False):
        if v0 != v1:
            continue
        if stable is None:
            stable = v0
        elif 0 < v0 - stable <= MAX_SCORE_STEP:  # rounds whose end was not read count once
            out.append(t0 + RESET_AFTER_SCORE_SEC)
            stable = v0
    return out


ALLY_RISE_MAX_GAP_SEC = 6.0


def ally_revives(counts: Sequence[tuple[float, int | None]], team_size: int = 5) -> list[float]:
    """Times the allied alive count goes up mid-round (someone was revived); a
    reset to a full team is a new round. Used only between two death detections
    that already have the recorder's own live view in between, so a single
    reading suffices (another death may follow the revive within a second)."""
    readings = [(sec, value) for sec, value in counts if value is not None]
    return [t1 for (t0, v0), (t1, v1) in zip(readings, readings[1:], strict=False)
            if 0 < v0 < v1 < team_size and t1 - t0 <= ALLY_RISE_MAX_GAP_SEC]


def reconcile(rounds: Sequence[Round], candidates: Mapping[str, Sequence[float]],
              self_live_at: Callable[[float], bool] | None = None,
              spectating_at: Callable[[float], bool] | None = None,
              live_samples: Sequence[float] = (),
              restarts: Sequence[float] = (),
              revives: Sequence[float] | None = None) -> Reconciliation:
    """Merge per-source death times into at most one death per life per round.

    ``self_live_at``/``spectating_at`` come from the timeline when available.
    ``live_samples`` are sample times at which the recorder was seen in their
    own live view (used to recognise a revive inside a round); ``restarts`` are
    times a new round was under way (``buy_phase_restarts``, ``combat_starts``,
    ``score_rises``). ``revives`` (``ally_revives``), when given, must show a
    revive between two deaths of one round; without one, a recorder seen alive
    in their own view long after the first death was never dead then, so the
    later detection replaces it (``superseded``).
    """
    dropped = {"outside_round": 0, "while_spectating": 0, "duplicate": 0, "superseded": 0}
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
            restart = next((t for t in restarts if last.sec < t < sec), None)
            if restart is not None:
                deaths.append(RecorderDeath(index, sec, {source}, after_round_restart=True))
                continue
            alive_again = [t for t in live_samples
                           if last.sec + MERGE_WINDOW_SEC < t < sec
                           and (self_live_at is None or self_live_at(t))]
            # Time-based, so 1 s and 5 s sampling ask for the same evidence.
            if (len(alive_again) < REVIVE_MIN_SAMPLES
                    or alive_again[-1] - alive_again[0] < REVIVE_MIN_SPAN_SEC):
                dropped["duplicate"] += 1
                last.sources.add(source)
                continue
            if revives is not None and not any(last.sec < t < sec for t in revives):
                dropped["superseded"] += 1
                last.sec, last.sources = sec, {source}
                continue
            deaths.append(RecorderDeath(index, sec, {source}, after_revive=True))
            continue
        deaths.append(RecorderDeath(index, sec, {source}))
    return Reconciliation(deaths, dropped, len(rounds))
