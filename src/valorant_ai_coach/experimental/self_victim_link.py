"""Offline, never-releasing source-player/killfeed-victim candidate link.

A structural scoreboard owner marker plus two OCR strings can suggest a Self
victim. Neither string agreement nor user-reviewed marker semantics is a
qualification, current-frame player-HUD identity, or a formal Death event.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from fractions import Fraction

from .subject_death import (
    ReviewStatus,
    SubjectObservation,
    SubjectRole,
)


@dataclass(frozen=True)
class SelfVictimLink:
    status: str
    blockers: tuple[str, ...]
    owner: SubjectObservation | None = None
    victim: SubjectObservation | None = None
    confidence: float | None = None

    @property
    def formal_events(self) -> tuple[()]:
        return ()

    @property
    def qualified(self) -> bool:
        return False


def link_source_player_to_victim(
    owner: SubjectObservation | None,
    victim: SubjectObservation | None,
    *,
    max_age_sec: float = 1.0,
) -> SelfVictimLink:
    """Return an *unqualified* text-agreement candidate, never an identity grant.

    Call with independently measured scoreboard-owner-row and *victim-position*
    text. A killfeed killer, sticky report or spectator name cannot substitute.
    The source owner row is only a candidate until its fixed-marker semantics
    and its positive/negative detector have independent qualification.
    """
    if (isinstance(max_age_sec, bool)
            or not isinstance(max_age_sec, (int, float))
            or not math.isfinite(max_age_sec)
            or not 0 < max_age_sec <= 1):
        raise ValueError("bounded positive source time horizon required")
    if owner is None or victim is None:
        return SelfVictimLink("unknown", ("missing_owner_or_victim",), owner, victim)
    if owner.role != SubjectRole.SOURCE_PLAYER_BINDING:
        return SelfVictimLink("unknown", ("not_source_player_marker",), owner, victim)
    if victim.role != SubjectRole.VICTIM:
        return SelfVictimLink("unknown", ("not_victim_role",), owner, victim)
    if (owner.method != "scoreboard_border_and_name_candidate"
            or victim.method != "killfeed_victim_text"):
        return SelfVictimLink("unknown", ("unqualified_role_method",), owner, victim)
    if owner.source.context != victim.source.context:
        return SelfVictimLink("unknown", ("source_context_mismatch",), owner, victim)
    if (not 0 <= abs(owner.source.time - victim.source.time)
            <= Fraction(str(max_age_sec))):
        return SelfVictimLink("unknown", ("stale_or_ambiguous_source_time",), owner, victim)
    if (owner.source.time == victim.source.time
            or owner.source.pixel_sha256 == victim.source.pixel_sha256):
        return SelfVictimLink("unknown", ("no_independent_source_frames",), owner, victim)
    ax1, ay1, ax2, ay2 = owner.roi
    bx1, by1, bx2, by2 = victim.roi
    if ax1 < bx2 and bx1 < ax2 and ay1 < by2 and by1 < ay2:
        return SelfVictimLink("unknown", ("overlapping_evidence_rois",), owner, victim)
    if owner.subject_token is None or victim.subject_token is None:
        return SelfVictimLink("unknown", ("name_evidence_missing",), owner, victim)
    if owner.subject_token != victim.subject_token:
        return SelfVictimLink("unknown", ("victim_is_not_recording_player",), owner, victim)
    scores = (owner.confidence, victim.confidence)
    if any(score is None or score < .90 for score in scores):
        return SelfVictimLink("unknown", ("text_or_marker_support_insufficient",), owner, victim)
    confidence = min(float(score) for score in scores if score is not None)
    # A visual review is not independently qualified recognition. No relation,
    # ownership, Alive or formal Death event is inferred from this diagnostic.
    review = all(
        o.review_status == ReviewStatus.SOURCE_REVIEWED
        for o in (owner, victim)
    )
    blockers = (
        "semantic_role_qualification_missing",
        "death_transition_corroboration_missing",
        "production_adoption_not_authorized",
    )
    if not review:
        blockers = (*blockers, "independent_review_missing")
    return SelfVictimLink("unqualified_self_victim_candidate", blockers,
                          owner, victim, confidence)
