"""Round phase events from the top bar: score update, buy phase start, combat
start and round end, kept apart (development only).

The four moments are different and are reported separately:

- ``score_update``: the first confirmed read of a new score. It is an
  observation time, a few seconds after the round actually ended.
- ``buy_phase_start``: from the buy countdown (``buy_phase_sec``, or
  ``buy_phase_half_start_sec`` for the first round of a half and overtime).
- ``combat_start``: from the round timer (``round_time_limit_sec``): a reading
  of ``t`` seconds at ``sec`` means combat started at ``sec - (limit - t)``.
- ``round_end``: the earliest observed end condition (a team eliminated on the
  top bar, or the combat timer running out before a plant); without one, the
  score update is only an upper bound and is labelled as such.

Timings come from game knowledge; the per-sample readings are the score
tracks, the timer, the top-bar alive counts and the spike indicator. Nothing
here is a formal Event.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

COMBAT_TIMER_MIN = 46  # above the longest buy countdown: only the combat timer shows it
MAX_READ_GAP_SEC = 20.0


@dataclass(frozen=True)
class PhaseSample:
    sec: float
    timer: int | None
    ordinal: int | None  # ally + enemy score points before this round
    ally_alive: int | None
    enemy_alive: int | None
    spike_planted: bool | None


@dataclass
class RoundPhases:
    ordinal: int
    score_update: float | None = None  # first read of this round's score
    buy_phase_start: float | None = None
    combat_start: float | None = None
    round_end: float | None = None
    bases: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class PhaseRules:
    round_time_limit_sec: int = 100
    buy_phase_sec: int = 30
    buy_phase_half_start_sec: int = 45
    regulation_rounds_per_half: int = 12

    def buy_length(self, ordinal: int) -> int:
        half = self.regulation_rounds_per_half
        if ordinal in (0, half) or ordinal >= 2 * half:
            return self.buy_phase_half_start_sec
        return self.buy_phase_sec


def round_phases(samples: Sequence[PhaseSample], rules: PhaseRules | None = None
                 ) -> list[RoundPhases]:
    rules = rules or PhaseRules()
    by_ordinal: dict[int, list[PhaseSample]] = {}
    for sample in samples:
        if sample.ordinal is not None:
            by_ordinal.setdefault(sample.ordinal, []).append(sample)
    out: list[RoundPhases] = []
    for ordinal in sorted(by_ordinal):
        rows = by_ordinal[ordinal]
        phases = RoundPhases(ordinal)
        if ordinal > 0:
            phases.score_update = rows[0].sec
            phases.bases["score_update"] = "first_confirmed_score_read"
        timed = [s for s in rows if s.timer is not None]
        combat = next((s for s in timed if s.timer is not None
                       and s.timer >= COMBAT_TIMER_MIN), None)
        if combat is not None and combat.timer is not None:
            phases.combat_start = combat.sec - (rules.round_time_limit_sec - combat.timer)
            phases.bases["combat_start"] = "round_timer"
        buy_len = rules.buy_length(ordinal)
        limit = phases.combat_start if phases.combat_start is not None else float("inf")
        buy = next((s for s in timed if s.timer is not None and s.timer <= buy_len
                    and s.sec < limit), None)
        if buy is not None and buy.timer is not None:
            phases.buy_phase_start = buy.sec - (buy_len - buy.timer)
            phases.bases["buy_phase_start"] = "buy_countdown"
        elif phases.combat_start is not None:
            phases.buy_phase_start = phases.combat_start - buy_len
            phases.bases["buy_phase_start"] = "combat_start_minus_buy_length"
        out.append(phases)
    # Round end: earliest end condition after combat start, before the next score.
    for index, phases in enumerate(out):
        nxt = out[index + 1] if index + 1 < len(out) else None
        upper = nxt.score_update if nxt is not None else None
        start = phases.combat_start
        if start is None:
            if upper is not None:
                phases.round_end = upper
                phases.bases["round_end"] = "score_update_upper_bound"
            continue
        window = [s for s in samples if start <= s.sec and (upper is None or s.sec <= upper)]
        eliminated = next((s.sec for s in window
                           if s.ally_alive == 0 or s.enemy_alive == 0), None)
        planted = any(s.spike_planted for s in window)
        expiry = start + rules.round_time_limit_sec
        candidates: list[tuple[float, str]] = []
        if eliminated is not None:
            candidates.append((eliminated, "team_eliminated"))
        if not planted and (upper is None or expiry <= upper):
            candidates.append((expiry, "timer_expired"))
        if candidates:
            phases.round_end, phases.bases["round_end"] = min(candidates)
        elif upper is not None:
            phases.round_end = upper
            phases.bases["round_end"] = "score_update_upper_bound"
    return out
