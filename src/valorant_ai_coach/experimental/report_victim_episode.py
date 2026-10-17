"""Non-releasing observed report-onset plus independently measured victim probe.

A report header can persist or be reopened. A candidate therefore requires a
locally observed absent-to-present transition and victim name support shortly
after it. This diagnostic never grants subject identity, Alive or Death.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from fractions import Fraction

from .subject_death import SourceBinding


@dataclass(frozen=True)
class DualDeathCandidate:
    status: str
    source: SourceBinding
    reason: str
    confidence: float | None = None
    onset_time_sec: float | None = None
    confirmation_time_sec: float | None = None

    @property
    def qualified(self) -> bool:
        return False

    @property
    def formal_events(self) -> tuple[()]:
        return ()


class ReportVictimEpisodeProbe:
    """Report onset + victim similarity; one candidate per qualified round.

    Floors are *diagnostic image similarity*, not production confidence or
    qualified identity. In particular 0.80 victim comparison is never valid
    formal event evidence. No GT timestamp enters this state machine.
    """

    def __init__(self, *, report_floor: float = 0.90, victim_floor: float = 0.80) -> None:
        for score in (report_floor, victim_floor):
            if (type(score) is not float or not math.isfinite(score)
                    or not 0 < score <= 1):
                raise ValueError("finite explicit diagnostic comparison floor required")
        self.report_floor = report_floor
        self.victim_floor = victim_floor
        self.last_source: SourceBinding | None = None
        self.last_report_positive = False
        self.pending_onset: SourceBinding | None = None
        self.latched = False
        self.blocked_after_source_change = False

    def observe(
        self, source: SourceBinding, *, report_score: float | None,
        victim_score: float | None, qualified_new_round: bool = False,
    ) -> DualDeathCandidate:
        """Use measured signals only; caller must provide a *genuine* native start.

        A user-entered GT boundary, raw clock reset or a false boolean is
        not a qualified_new_round. Such values must never be wired here.
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
        changed = previous is not None and (
            source.context != previous.context or source.time <= previous.time
            or source.pixel_sha256 == previous.pixel_sha256
        )
        self.last_source = source
        if changed:
            self.blocked_after_source_change = True
            self.pending_onset = None
            self.last_report_positive = False
        if qualified_new_round:
            self.latched = False
            self.blocked_after_source_change = False
            self.pending_onset = None
            self.last_report_positive = False
        if self.blocked_after_source_change:
            return DualDeathCandidate("unknown", source, "source_changed_or_duplicate")
        if self.latched:
            return DualDeathCandidate("duplicate", source, "episode_already_recorded")

        # A below-threshold NCC is only a *diagnostic* negative, never a
        # qualified proof of report absence. Explicit confirmation remains
        # required before any production event or Death timing.
        report_positive = report_score is not None and report_score >= self.report_floor
        if (
            previous is not None and not self.last_report_positive
            and report_positive and previous.context == source.context
            and 0 < source.time - previous.time <= Fraction(1, 2)
        ):
            self.pending_onset = source
        if not report_positive:
            self.pending_onset = None
        self.last_report_positive = report_positive

        onset = self.pending_onset
        if onset is None or not report_positive:
            return DualDeathCandidate("unknown", source, "new_report_onset_unproved")
        if source.time - onset.time > Fraction(1):
            self.pending_onset = None
            return DualDeathCandidate("unknown", source, "onset_expired")
        if victim_score is None or victim_score < self.victim_floor:
            return DualDeathCandidate("unknown", source, "independent_victim_not_measured")

        # Preserve the observed onset separately from the later text witness.
        # The sampled scan is not a native-timing qualification.
        # Guarding the paired witness also narrows the optional score types.
        if report_score is None or victim_score is None:
            return DualDeathCandidate("unknown", source, "paired_signal_missing")
        self.latched = True
        return DualDeathCandidate(
            "unqualified_candidate", source,
            "subject_role_continuity_and_qualification_missing",
            min(float(report_score), float(victim_score)),
            float(onset.time), float(source.time),
        )
