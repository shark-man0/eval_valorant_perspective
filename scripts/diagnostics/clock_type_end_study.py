"""Isolated research contract. Never imported by a producer or returns a Formal End.

Synthetic callers may supply an assumed active context. Real saved-row replay must
not fabricate one. Caption absence is positive input, never a template nonmatch.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from fractions import Fraction
from math import isfinite


@dataclass(frozen=True)
class ActiveContext:
    source: str
    epoch: str
    start_tick: int
    evidence_sha256: str


@dataclass(frozen=True)
class Sample:
    source: str
    epoch: str
    tick: int
    base: Fraction
    pixel: str
    clock_kind: str
    clock_literal: str | None
    clock_confidence: float
    score: tuple[int, int] | None
    score_confidence: float
    caption: str  # complete / absent (positive evidence) / partial / unknown
    caption_confidence: float
    phase: str  # active (proven context plus valid scan) / buy / unknown
    view: str  # admissible global UI / spectator / unknown; not player identity
    source_break: bool = False
    occluded: bool = False


@dataclass(frozen=True)
class Pattern:
    boundary_tick: int
    confirmation_tick: int
    time_base: str
    formal_release: bool = False
    scope: str = "unqualified_clock_type_contract_study"


@dataclass
class Run:
    value: object
    first: int
    last: int
    count: int = 1

    def stable(self, base: Fraction) -> bool:
        return self.count >= 2 and (self.last - self.first) * base >= Fraction(1, 10)


def extend(run: Run | None, value: object, tick: int, step: int) -> Run:
    if run is not None and run.value == value and tick - run.last == step:
        return Run(value, run.first, tick, run.count + 1)
    return Run(value, tick, tick)


def accepted(confidence: float) -> bool:
    return type(confidence) in (int, float) and isfinite(confidence) and 0.9 <= confidence <= 1


class ClockTypeEndStudy:
    """One Spike→decimal hypothesis with strict abstention, not a release backend.

    Require stable adjacent accepted scores, stable prior Spike and positively
    absent caption. Decimal may be first observed at the score tick or its next
    native sample, never assigned an earlier timestamp. Deadline is one second
    from the actually observed score update, never extended or restarted.
    """

    def __init__(self, step: int, context: ActiveContext | None = None):
        if type(step) is not int or step <= 0:
            raise ValueError("positive integer native step required")
        self.step = step
        self.context = context
        self.previous: Sample | None = None
        self.scores: Run | None = None
        self.spike: Run | None = None
        self.absence: Run | None = None
        self.pending: int | None = None
        self.after: tuple[int, int] | None = None
        self.decimal: Run | None = None
        self.result: Run | None = None
        self.ended = False
        self.blocker = "no_active_context" if context is None else None

    def abort(self, reason: str) -> None:
        self.context = None
        self.scores = self.spike = self.absence = self.decimal = self.result = None
        self.pending = self.after = None
        self.blocker = reason

    def advance(self, row: Sample) -> Pattern | None:
        previous = self.previous
        self.previous = row
        if self.ended:
            return None
        if (
            type(row.tick) is not int
            or row.tick < 0
            or row.base <= 0
            or not re.fullmatch(r"[0-9a-f]{64}", row.pixel)
        ):
            self.abort("invalid_source_identity")
            return None
        if (
            row.source_break
            or previous is not None
            and (
                row.source != previous.source
                or row.epoch != previous.epoch
                or row.base != previous.base
                or row.tick - previous.tick != self.step
                or row.pixel == previous.pixel
            )
        ):
            self.abort("source_break")
            return None
        ctx = self.context
        if ctx is None:
            return None
        if (
            ctx.source != row.source
            or ctx.epoch != row.epoch
            or ctx.start_tick >= row.tick
            or not re.fullmatch(r"[0-9a-f]{64}", ctx.evidence_sha256)
        ):
            self.abort("active_context_mismatch")
            return None
        if row.phase != "active" or row.view != "global" or row.occluded:
            self.abort("unsafe_current_ui")
            return None
        if self.pending is not None and (row.tick - self.pending) * row.base > 1:
            self.abort("immutable_confirmation_deadline")
            return None
        old_score, old_spike, old_absence = self.scores, self.spike, self.absence
        valid_score = (
            row.score is not None
            and len(row.score) == 2
            and all(type(x) is int and x >= 0 for x in row.score)
            and accepted(row.score_confidence)
        )
        if not valid_score:
            if self.pending is not None:
                self.abort("unknown_score")
                return None
            self.scores = None
        else:
            self.scores = extend(self.scores, row.score, row.tick, self.step)
        if (
            self.pending is None
            and old_score is not None
            and valid_score
            and row.score != old_score.value
        ):
            delta = sorted(a - b for a, b in zip(row.score, old_score.value, strict=True))
            if (
                old_score.last == row.tick - self.step
                and old_score.stable(row.base)
                and delta == [0, 1]
                and old_spike is not None
                and old_spike.last == row.tick - self.step
                and old_spike.stable(row.base)
                and old_absence is not None
                and old_absence.last == row.tick - self.step
                and old_absence.stable(row.base)
            ):
                self.pending = row.tick
                self.after = row.score
        if self.pending is not None and row.score != self.after:
            self.abort("contradictory_score")
            return None
        self.spike = (
            extend(self.spike, "spike", row.tick, self.step)
            if row.clock_kind == "spike" and accepted(row.clock_confidence)
            else None
        )
        self.absence = (
            extend(self.absence, "absent", row.tick, self.step)
            if row.caption == "absent" and accepted(row.caption_confidence)
            else None
        )
        if self.pending is None:
            return None
        is_decimal = (
            row.clock_kind == "decimal"
            and accepted(row.clock_confidence)
            and isinstance(row.clock_literal, str)
            and re.fullmatch(r"[0-9]{2}\.[0-9]{2}", row.clock_literal)
        )
        if is_decimal:
            if self.decimal is not None and self.decimal.value != row.clock_literal:
                self.abort("contradictory_decimal")
                return None
            self.decimal = extend(self.decimal, row.clock_literal, row.tick, self.step)
        elif row.tick > self.pending or row.clock_kind not in {"unknown", "spike"}:
            self.abort("missing_or_contradictory_clock_type")
            return None
        if (
            self.decimal is None
            and row.tick - self.pending > self.step
            or self.decimal is not None
            and self.decimal.first - self.pending > self.step
        ):
            self.abort("clock_witness_outside_adjacent_bracket")
            return None
        self.result = (
            extend(self.result, "complete", row.tick, self.step)
            if row.caption == "complete" and accepted(row.caption_confidence)
            else None
        )
        if all(
            run is not None and run.stable(row.base)
            for run in (self.scores, self.decimal, self.result)
        ):
            pattern = Pattern(self.pending, row.tick, str(row.base))
            self.ended = True
            return pattern
        return None


def replay_samples(rows: list[Sample], step: int, context: ActiveContext | None = None) -> dict:
    from dataclasses import asdict

    study = ClockTypeEndStudy(step, context)
    patterns = [asdict(pattern) for row in rows if (pattern := study.advance(row)) is not None]
    return {
        "patterns": patterns,
        "last_blocker": study.blocker,
        "formal_events": 0,
        "qualification_issued": False,
    }
