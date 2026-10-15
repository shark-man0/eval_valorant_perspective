"""Typed source/subject evidence and a non-releasing Death qualification probe.

This module has no production caller, qualification grant or Event constructor.
A source review is not recognizer qualification. Even a complete synthetic or
reviewed candidate remains unqualified and cannot emit a formal Death event.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import asdict, dataclass
from enum import StrEnum
from fractions import Fraction
from itertools import combinations
from typing import Any


class SubjectRole(StrEnum):
    SOURCE_PLAYER_BINDING = "source_player_binding"
    VICTIM = "victim"
    KILLER = "killer"
    DEATH_TRANSITION = "death_transition"
    REPORT = "report_visible"
    SPECTATOR = "spectator_view"
    RESPAWN = "respawn"


class SubjectRelation(StrEnum):
    UNKNOWN = "unknown"
    SELF = "self"
    NONSELF = "nonself"
    TEAMMATE = "teammate"
    ENEMY = "enemy"


class ReviewStatus(StrEnum):
    CANDIDATE = "candidate"
    SOURCE_REVIEWED = "source_reviewed_not_qualified"


def _hash(value: str) -> None:
    if not isinstance(value, str) or re.fullmatch("[0-9a-f]{64}", value) is None:
        raise ValueError("SHA-256 must be lowercase hexadecimal")


def _text(value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("nonempty provenance is required")


def _integer(value: int, minimum: int) -> None:
    if type(value) is not int or value < minimum:
        raise ValueError("invalid integer source coordinate")


@dataclass(frozen=True)
class SourceBinding:
    video_sha256: str
    pts_ticks: int
    time_base_num: int
    time_base_den: int
    segment_id: str
    pixel_sha256: str
    code_fingerprint: str
    profile_fingerprint: str
    dependencies_fingerprint: str

    def __post_init__(self) -> None:
        for value in (self.video_sha256, self.pixel_sha256, self.code_fingerprint,
                      self.profile_fingerprint, self.dependencies_fingerprint):
            _hash(value)
        _integer(self.pts_ticks, 0)
        _integer(self.time_base_num, 1)
        _integer(self.time_base_den, 1)
        _text(self.segment_id)

    @property
    def time(self) -> Fraction:
        return Fraction(self.pts_ticks * self.time_base_num, self.time_base_den)

    @property
    def context(self) -> tuple[str, str, int, int, str, str, str]:
        return (self.video_sha256, self.segment_id, self.time_base_num, self.time_base_den,
                self.code_fingerprint, self.profile_fingerprint, self.dependencies_fingerprint)


@dataclass(frozen=True)
class SubjectObservation:
    evidence_id: str
    source: SourceBinding
    role: SubjectRole
    relation: SubjectRelation
    subject_token: str | None
    confidence: float | None
    method: str
    roi: tuple[int, int, int, int]
    review_status: ReviewStatus = ReviewStatus.CANDIDATE
    review_sha256: str | None = None

    def __post_init__(self) -> None:
        _text(self.evidence_id)
        _text(self.method)
        if not isinstance(self.source, SourceBinding):
            raise ValueError("typed source binding required")
        if not isinstance(self.role, SubjectRole) or not isinstance(self.relation, SubjectRelation):
            raise ValueError("typed role and relation required")
        if not isinstance(self.review_status, ReviewStatus):
            raise ValueError("typed source-review state required")
        if self.subject_token is not None:
            _hash(self.subject_token)
        if self.relation != SubjectRelation.UNKNOWN and self.subject_token is None:
            raise ValueError("known relation needs an observed subject token")
        if self.confidence is not None and (
            isinstance(self.confidence, bool) or not isinstance(self.confidence, (int, float))
            or not math.isfinite(self.confidence) or not 0 <= self.confidence <= 1
        ):
            raise ValueError("confidence must be finite source support in [0,1] or absent")
        if not isinstance(self.roi, tuple) or len(self.roi) != 4:
            raise ValueError("immutable source ROI required")
        for value in self.roi:
            _integer(value, 0)
        x1, y1, x2, y2 = self.roi
        if not (x1 < x2 and y1 < y2):
            raise ValueError("nonempty source ROI required")
        if self.review_sha256 is not None:
            _hash(self.review_sha256)
        if self.review_status == ReviewStatus.SOURCE_REVIEWED and self.review_sha256 is None:
            raise ValueError("reviewed evidence needs its review provenance")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SubjectObservation:
        """Strict standalone round-trip, not a migration of public HUD schemas."""
        copied = dict(data)
        copied["source"] = SourceBinding(**copied["source"])
        copied["role"] = SubjectRole(copied["role"])
        copied["relation"] = SubjectRelation(copied["relation"])
        copied["review_status"] = ReviewStatus(copied["review_status"])
        copied["roi"] = tuple(copied["roi"])
        return cls(**copied)


def _review_supported(observation: SubjectObservation) -> bool:
    return (observation.review_status == ReviewStatus.SOURCE_REVIEWED
            and observation.confidence is not None and observation.confidence >= 0.90)


@dataclass(frozen=True)
class ProbeFrame:
    source: SourceBinding
    observations: tuple[SubjectObservation, ...]
    previous_pts_ticks: int | None = None
    continuity_proof_sha256: str | None = None
    discontinuity: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.source, SourceBinding) or not isinstance(self.observations, tuple):
            raise ValueError("immutable typed source observations required")
        if type(self.discontinuity) is not bool:
            raise ValueError("explicit discontinuity state required")
        if self.previous_pts_ticks is not None:
            _integer(self.previous_pts_ticks, 0)
        if self.continuity_proof_sha256 is not None:
            _hash(self.continuity_proof_sha256)
        if any(not isinstance(o, SubjectObservation) for o in self.observations):
            raise ValueError("typed subject observations required")
        if any(o.source != self.source for o in self.observations):
            raise ValueError("evidence belongs to another physical source frame")
        ids = [o.evidence_id for o in self.observations]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate evidence ID in frame")


@dataclass(frozen=True)
class DeathProbeDecision:
    status: str
    blockers: tuple[str, ...]
    source: SourceBinding
    boundary_time_sec: float | None = None
    confirmation_time_sec: float | None = None
    confidence: float | None = None
    evidence: tuple[SubjectObservation, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "qualified": False, "formal_events": []}


class SubjectDeathProbe:
    """Bounded, offline candidate assembly; never a production Event producer.

    Native adjacency is necessary but insufficient: callers must also retain a
    source-continuity proof. That diagnostic proof confers no event authority.
    """

    def __init__(self, *, native_step_ticks: int, max_corroboration_sec: float) -> None:
        _integer(native_step_ticks, 1)
        if (isinstance(max_corroboration_sec, bool)
                or not isinstance(max_corroboration_sec, (int, float))
                or not math.isfinite(max_corroboration_sec) or max_corroboration_sec <= 0):
            raise ValueError("explicit finite experimental corroboration horizon required")
        self.step = native_step_ticks
        self.horizon = Fraction(str(max_corroboration_sec))
        self.previous: SourceBinding | None = None
        self.pending: dict[SubjectRole, SubjectObservation] = {}
        self.latched = False
        self.latched_token: str | None = None

    def observe(self, frame: ProbeFrame) -> DeathProbeDecision:
        source = frame.source
        previous = self.previous
        reset = frame.discontinuity or previous is not None and (
            source.context != previous.context
            or source.pts_ticks - previous.pts_ticks != self.step
            or frame.previous_pts_ticks != previous.pts_ticks
            or frame.continuity_proof_sha256 is None
        )
        if reset:
            self.pending.clear()
            self.latched = False
            self.latched_token = None
        self.previous = source
        self.pending = {k: v for k, v in self.pending.items()
                        if 0 <= source.time - v.source.time <= self.horizon}
        if any(o.role == SubjectRole.RESPAWN for o in frame.observations):
            # Conservative reset: even ambiguous respawn breaks a pending join.
            self.pending.clear()
            if any(o.role == SubjectRole.RESPAWN and _review_supported(o)
                   and o.relation == SubjectRelation.SELF
                   and o.subject_token == self.latched_token for o in frame.observations):
                self.latched = False
            return DeathProbeDecision("unknown", ("respawn_resets_pending",), source)
        relevant = (SubjectRole.SOURCE_PLAYER_BINDING, SubjectRole.VICTIM,
                    SubjectRole.DEATH_TRANSITION)
        for observation in frame.observations:
            if observation.role not in relevant:
                continue  # Report, spectator and killer cannot substitute for victim.
            old = self.pending.get(observation.role)
            if (old is not None and old.subject_token is not None
                    and observation.subject_token is not None
                    and (old.subject_token != observation.subject_token
                         or old.relation != SubjectRelation.UNKNOWN
                         and observation.relation != SubjectRelation.UNKNOWN
                         and old.relation != observation.relation)):
                self.pending.clear()
                return DeathProbeDecision("unknown", ("conflicting_subjects",), source)
            # Keep the first observed support/time, not a later confirmation PTS.
            if old is None or not _review_supported(old) and _review_supported(observation):
                self.pending[observation.role] = observation
        support = tuple(self.pending[k] for k in relevant if k in self.pending)
        blockers = []
        for role in relevant:
            o = self.pending.get(role)
            if o is None:
                blockers.append("missing_" + role)
            elif o.relation != SubjectRelation.SELF:
                blockers.append("unproved_self_" + role)
            elif o.review_status != ReviewStatus.SOURCE_REVIEWED:
                blockers.append("unreviewed_" + role)
            elif o.confidence is None:
                blockers.append("missing_confidence_" + role)
            elif o.confidence < 0.90:
                blockers.append("below_source_evidence_floor_" + role)
        if not blockers:
            tokens = {o.subject_token for o in support}
            if len(tokens) != 1:
                blockers.append("conflicting_subjects")
            if len({o.source.pts_ticks for o in support}) < 2:
                blockers.append("no_temporal_corroboration")
            for a, b in combinations(support, 2):
                ax1, ay1, ax2, ay2 = a.roi
                bx1, by1, bx2, by2 = b.roi
                disjoint = ax2 <= bx1 or bx2 <= ax1 or ay2 <= by1 or by2 <= ay1
                if a.method == b.method or not disjoint:
                    blockers.append("independence_unproved")
        if blockers:
            return DeathProbeDecision("unknown", tuple(sorted(set(blockers))), source,
                                      evidence=support)
        if self.latched:
            return DeathProbeDecision("duplicate", ("episode_already_observed",), source,
                                      evidence=support)
        self.latched = True
        self.latched_token = support[0].subject_token
        transition = self.pending[SubjectRole.DEATH_TRANSITION]
        confidence = min(float(o.confidence) for o in support if o.confidence is not None)
        return DeathProbeDecision(
            "candidate", ("recognizer_qualification_missing", "production_adoption_not_authorized"),
            source, float(transition.source.time), float(source.time), confidence, support,
        )


def probe_fingerprint(*, runtime_fingerprint: str) -> str:
    """Bind experiment bytes plus existing runtime; never reuse a global grant."""
    from pathlib import Path

    _hash(runtime_fingerprint)
    digest = hashlib.sha256(Path(__file__).read_bytes().replace(b"\r\n", b"\n"))
    digest.update(runtime_fingerprint.encode("ascii"))
    return digest.hexdigest()


def serialize_observation(observation: SubjectObservation) -> str:
    return json.dumps(observation.to_dict(), sort_keys=True, allow_nan=False)
