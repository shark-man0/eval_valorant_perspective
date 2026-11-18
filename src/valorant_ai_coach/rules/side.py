"""Attack/defense side per round (development only).

Evidence and knowledge used:

- Only attackers can carry the spike, so a round in which the recorder's own
  live view shows the spike header in the weapon inventory is an attack round.
- The round ordinal comes from the top-bar score (ally + enemy points before
  the round), so a missed or spurious round boundary cannot shift it.
- Teams switch sides once after ``regulation_rounds_per_half`` rounds (game
  knowledge). Within regulation, one observed attack round therefore fixes the
  side of every other regulation round, provided all observations agree.

Overtime rounds only get a side from direct observation: the knowledge base
does not record the overtime side order. When observations disagree, only the
directly observed rounds get a side. Nothing here is a formal Fact.
"""

from __future__ import annotations

import bisect
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

ATTACK = "attack"
DEFENSE = "defense"
SCORE_GAP_SEC = 30.0  # a score read older than this does not date a sample


def _other(side: str) -> str:
    return DEFENSE if side == ATTACK else ATTACK


@dataclass(frozen=True)
class SideObservation:
    ordinal: int  # 0-based round ordinal
    side: str  # the recorder's side in that round
    source: str  # "spike_carried" | "detonation_win" | "defuse_win" | ...


@dataclass(frozen=True)
class SideInference:
    observations: tuple[SideObservation, ...]
    status: str  # "half_structure" | "observed_only" | "conflict" | "unobserved"
    first_half_side: str | None
    rounds_per_half: int = 12

    @property
    def observed(self) -> tuple[int, ...]:
        """Ordinals observed as attack (kept for reports)."""
        return tuple(sorted({o.ordinal for o in self.observations if o.side == ATTACK}))

    def side(self, ordinal: int | None) -> tuple[str, str] | None:
        """(side, source) for a round ordinal, or None when unknown."""
        if ordinal is None:
            return None
        direct = [o for o in self.observations if o.ordinal == ordinal]
        if direct and len({o.side for o in direct}) == 1:
            return direct[0].side, direct[0].source
        if self.first_half_side is None or ordinal >= 2 * self.rounds_per_half:
            return None
        if ordinal < self.rounds_per_half:
            return self.first_half_side, "half_structure"
        return _other(self.first_half_side), "half_structure"


def infer_sides(observations: Iterable[SideObservation | int], *,
                rounds_per_half: int = 12) -> SideInference:
    """Combine per-round side observations with the half structure.

    Plain ints are attack observations from the spike carrier (older callers).
    """
    items = tuple(sorted(
        {o if isinstance(o, SideObservation) else SideObservation(o, ATTACK, "spike_carried")
         for o in observations if (o.ordinal if isinstance(o, SideObservation) else o) >= 0},
        key=lambda o: (o.ordinal, o.source)))
    if not items:
        return SideInference(items, "unobserved", None, rounds_per_half)
    regulation = [o for o in items if o.ordinal < 2 * rounds_per_half]
    if not regulation:
        return SideInference(items, "observed_only", None, rounds_per_half)
    implied = {o.side if o.ordinal < rounds_per_half else _other(o.side) for o in regulation}
    if len(implied) != 1:
        return SideInference(items, "conflict", None, rounds_per_half)
    return SideInference(items, "half_structure", implied.pop(), rounds_per_half)


def outcome_sides(rounds: Sequence[tuple[int, str | None, float | None, float | None,
                                         float | None, float | None, bool]],
                  *, detonation_sec: float = 45.0, tolerance_sec: float = 3.0
                  ) -> list[SideObservation]:
    """Sides from how planted rounds ended (top bar only; game knowledge timings).

    Each round: (ordinal, winner "ally"|"enemy"|None, plant_lo, plant_hi, end_lo,
    end_hi, both_teams_alive_at_end). Plant and end are known within
    [lo, hi] (sampling). Only attackers win by detonation, so with both teams
    still alive when the spike ends exactly ``detonation_sec`` after the plant,
    the winner attacked.

    Defuses (only defenders win by them) are not used: on the DEVELOPMENT
    matches the "spike ended early with both teams alive" pattern agreed with
    the spike-carrier sides in 1 of 2 checkable rounds, which is not good enough.
    """
    out: list[SideObservation] = []
    for ordinal, winner, p_lo, p_hi, e_lo, e_hi, both_alive in rounds:
        if winner is None or None in (p_lo, p_hi, e_lo, e_hi) or not both_alive:
            continue
        assert p_lo is not None and p_hi is not None and e_lo is not None and e_hi is not None
        shortest, longest = e_lo - p_hi, e_hi - p_lo
        if (detonation_sec - tolerance_sec <= shortest
                and longest <= detonation_sec + 2 * tolerance_sec):
            winner_side, source = ATTACK, "detonation_win"
        else:
            continue
        side = winner_side if winner == "ally" else _other(winner_side)
        out.append(SideObservation(ordinal, side, source))
    return out


class RoundOrdinal:
    """Round ordinal at a time from confirmed ally/enemy score tracks."""

    def __init__(self, ally: Sequence[tuple[float, int]],
                 enemy: Sequence[tuple[float, int]]) -> None:
        self.tracks = [list(ally), list(enemy)]
        self.times = [[sec for sec, _ in track] for track in self.tracks]

    def _value(self, side: int, sec: float) -> int | None:
        times, track = self.times[side], self.tracks[side]
        index = bisect.bisect_right(times, sec) - 1
        if index < 0:
            return None
        before_sec, before = track[index]
        if index + 1 < len(track):
            # Between two reads the score is known only if it did not change.
            if track[index + 1][1] == before:
                return before
            return before if sec - before_sec <= SCORE_GAP_SEC else None
        return before if sec - before_sec <= SCORE_GAP_SEC else None

    def at(self, sec: float) -> int | None:
        ally, enemy = self._value(0, sec), self._value(1, sec)
        if ally is None or enemy is None:
            return None
        return ally + enemy
