"""Opt-in, non-releasing temporal gate for two independent visual signals.

The scores are diagnostics, not qualified self identity, GT or native Death.
A qualified actual start from the lifecycle is the only rearm. Missing signals,
source changes, and report toggling alone cannot rearm the death episode.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .subject_death import SourceBinding


@dataclass(frozen=True)
class DualDeathCandidate:
    status: str
    source: SourceBinding
    reason: str
    confidence: float | None = None

    @property
    def qualified(self) -> bool:
        return False

    @property
    def formal_events(self) -> tuple[()]:
        return ()


class ReportVictimEpisodeProbe:
    """Never emits Death; studies report/victim co-occurrence and duplicate latches.

    The 0.80 victim image-similarity cutoff is a *diagnostic comparison*
    value, NOT the production confidence floor or a release condition.
    """

    def __init__(self, *, report_floor: float = 0.90, victim_floor: float = 0.80) -> None:
        for score in (report_floor, victim_floor):
            if (type(score) is not float or not math.isfinite(score)
                    or not 0 < score <= 1):
                raise ValueError("finite explicit diagnostic comparison floor required")
        self.report_floor = report_floor
        self.victim_floor = victim_floor
        self.last_source: SourceBinding | None = None
        self.latched = False
        self.blocked_after_source_change = False

    def observe(
        self, source: SourceBinding, *, report_score: float | None,
        victim_score: float | None, qualified_new_round: bool = False,
    ) -> DualDeathCandidate:
        """Consume measured scores; a GT round label is never an input.

        For independent source experiments, only a *producer-qualified* native
        round_start may be supplied as qualified_new_round. Treating arbitrary
        timestamps or reference windows as this signal would be invalid.
        """
        if type(qualified_new_round) is not bool:
            raise ValueError("typed lifecycle signal required")
        for score in (report_score, victim_score):
            if score is not None and (
                isinstance(score, bool) or not isinstance(score, (int, float))
                or not math.isfinite(score) or not -1 <= score <= 1
            ):
                raise ValueError("measured image-similarity score required")
        previous = self.last_source
        if previous is not None and (
            source.context != previous.context or source.time <= previous.time
            or source.pixel_sha256 == previous.pixel_sha256
        ):
            # Missing or conflicting source proof must not make repeated
            # persistent report pixels look like another death episode.
            self.blocked_after_source_change = True
        self.last_source = source
        if qualified_new_round:
            self.latched = False
            self.blocked_after_source_change = False
        if self.blocked_after_source_change:
            return DualDeathCandidate("unknown", source, "source_changed_or_duplicate")
        if self.latched:
            return DualDeathCandidate("duplicate", source, "episode_already_recorded")
        if report_score is None or report_score < self.report_floor:
            return DualDeathCandidate("unknown", source, "self_report_not_measured")
        if victim_score is None or victim_score < self.victim_floor:
            return DualDeathCandidate("unknown", source, "independent_victim_not_measured")
        self.latched = True
        return DualDeathCandidate(
            "unqualified_candidate", source, "independent_semantics_and_qualification_missing",
            min(float(report_score), float(victim_score)),
        )
