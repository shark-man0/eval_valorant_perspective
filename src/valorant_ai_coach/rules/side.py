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
class SideInference:
    observed: tuple[int, ...]  # round ordinals (0-based) seen as attack
    status: str  # "half_structure" | "observed_only" | "conflict" | "unobserved"
    first_half_side: str | None
    rounds_per_half: int = 12

    def side(self, ordinal: int | None) -> tuple[str, str] | None:
        """(side, source) for a round ordinal, or None when unknown."""
        if ordinal is None:
            return None
        if ordinal in self.observed:
            return ATTACK, "spike_carried"
        if self.first_half_side is None or ordinal >= 2 * self.rounds_per_half:
            return None
        if ordinal < self.rounds_per_half:
            return self.first_half_side, "half_structure"
        return _other(self.first_half_side), "half_structure"


def infer_sides(attack_ordinals: Iterable[int], *, rounds_per_half: int = 12) -> SideInference:
    observed = tuple(sorted({o for o in attack_ordinals if o >= 0}))
    if not observed:
        return SideInference(observed, "unobserved", None, rounds_per_half)
    regulation = [o for o in observed if o < 2 * rounds_per_half]
    if not regulation:
        return SideInference(observed, "observed_only", None, rounds_per_half)
    implied = {ATTACK if o < rounds_per_half else DEFENSE for o in regulation}
    if len(implied) != 1:
        return SideInference(observed, "conflict", None, rounds_per_half)
    return SideInference(observed, "half_structure", implied.pop(), rounds_per_half)


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
