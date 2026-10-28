"""Opt-in recording-owner life/view hypotheses; never production ownership proof.

Inputs are *already reviewed/reader-supported* UI transitions on exact source frames,
not raw OCR values or assumed death from a persistent combat report. The caller
verifies the source bytes, native frame provenance and continuity receipt.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Literal

Life = Literal["unknown", "alive", "dead", "downed"]
View = Literal["unknown", "self", "spectator", "remote"]


@dataclass(frozen=True)
class SelfFrameCues:
    source_sha256: str
    source_epoch: str
    pts_ticks: int
    time_base: Fraction
    continuous_from_previous: bool = False
    own_view_ui: bool = False
    self_death_transition: bool = False
    spectator_ui: bool = False
    remote_view_ui: bool = False
    downed_transition: bool = False
    revival_transition: bool = False
    ultimate_return: bool = False
    new_round_reentry: bool = False
    marker_id: str | None = None
    marker_is_self_ui: bool = False

    def __post_init__(self) -> None:
        if (len(self.source_sha256) != 64
                or any(ch not in "0123456789abcdef" for ch in self.source_sha256)):
            raise ValueError("validated lowercase source SHA-256 required")
        if not self.source_epoch or type(self.pts_ticks) is not int or self.pts_ticks < 0:
            raise ValueError("native source epoch and nonnegative integer PTS required")
        if not isinstance(self.time_base, Fraction) or self.time_base <= 0:
            raise ValueError("positive native rational time base required")
        if self.marker_is_self_ui and not self.marker_id:
            raise ValueError("verified self-marker UI needs an observed marker ID")
        if self.marker_id is not None and not self.marker_id:
            raise ValueError("empty marker ID")


@dataclass(frozen=True)
class SelfTimelineHypothesis:
    life: Life
    view: View
    self_marker_id: str | None
    reason: str
    # This is an unqualified research observation, not an event or ownership fact.
    qualified: bool = False


class DevelopmentSelfTimeline:
    """Small temporal ablation model for unedited owner-POV normal matches.

    A confirmed spectator UI implies a death *hypothesis* when the prior self
    state was alive; it never asserts a qualified self-death event. Real revive
    and special ability-return transitions must be positively observed. The
    caller may not manufacture continuity from an unreviewed time gap.
    """

    def __init__(self) -> None:
        self.life: Life = "unknown"
        self.view: View = "unknown"
        self.previous: SelfFrameCues | None = None

    def observe(self, cue: SelfFrameCues) -> SelfTimelineHypothesis:
        prior = self.previous
        reset = (
            prior is None
            or not cue.continuous_from_previous
            or cue.source_sha256 != prior.source_sha256
            or cue.source_epoch != prior.source_epoch
            or cue.time_base != prior.time_base
            or cue.pts_ticks <= prior.pts_ticks
        )
        if reset:
            self.life, self.view = "unknown", "unknown"
        self.previous = cue

        # Mutually exclusive visible camera presentations and incompatible life
        # transitions cannot be silently made consistent from one image.
        mode_count = sum((cue.own_view_ui, cue.spectator_ui, cue.remote_view_ui))
        edge_count = sum((cue.self_death_transition, cue.downed_transition,
                          cue.revival_transition, cue.new_round_reentry))
        if (mode_count > 1 or edge_count > 1
                or (cue.spectator_ui and (cue.revival_transition or cue.new_round_reentry))):
            self.life, self.view = "unknown", "unknown"
            return SelfTimelineHypothesis(self.life, self.view, None, "conflicting_evidence")

        reason = "source_reset" if reset else "temporal_carry"
        if cue.new_round_reentry:
            # Round transition alone is not proof of whose view is displayed.
            self.life = "alive" if cue.own_view_ui else "unknown"
            self.view = "self" if cue.own_view_ui else "unknown"
            reason = "round_reentry" if cue.own_view_ui else "round_reentry_unverified"
        elif cue.revival_transition:
            if self.life in {"dead", "downed"}:
                self.life, self.view = "alive", "self" if cue.own_view_ui else "unknown"
                reason = "observed_revival"
            else:
                self.life, self.view = "unknown", "unknown"
                reason = "unanchored_revival"
        elif cue.downed_transition:
            self.life, self.view = "downed", "unknown"
            reason = "observed_downed"
        elif cue.self_death_transition:
            self.life, self.view = "dead", "spectator" if cue.spectator_ui else "unknown"
            reason = "observed_death_transition"
        elif cue.spectator_ui:
            # For the user's ordinary unedited own gameplay recording, a
            # spectator UI is useful temporal evidence, but not qualified GT.
            if self.life in {"alive", "unknown"}:
                self.life = "dead"
            self.view = "spectator"
            reason = "spectator_death_hypothesis"
        elif cue.remote_view_ui:
            # Remote camera/agent ability is not death or spectator mode.
            self.view = "remote"
            reason = "remote_view"
        elif cue.ultimate_return:
            # Phoenix-like return-to-anchor is not necessarily a death/revive.
            if self.life == "alive" and cue.own_view_ui:
                self.view = "self"
                reason = "ability_return"
            else:
                self.life, self.view = "unknown", "unknown"
                reason = "unanchored_ability_return"
        elif cue.own_view_ui:
            if self.life == "dead" or self.life == "downed":
                # Never invent a revive from a possibly spectated HUD alone.
                self.life, self.view = "unknown", "unknown"
                reason = "missing_revival_or_round_edge"
            else:
                self.life, self.view = "alive", "self"
                reason = "owner_ui"

        marker = (
            cue.marker_id if cue.marker_is_self_ui
            and self.life == "alive" and self.view == "self" else None
        )
        return SelfTimelineHypothesis(self.life, self.view, marker, reason)
