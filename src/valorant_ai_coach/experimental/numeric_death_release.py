"""Candidate-evaluation consumer of independently qualified numeric Self proof.

No production caller is installed. A reviewed qualification report is bound by
an expected digest separately from the file; loading a prediction or hashing
its file is not qualification. This module cannot turn
UNKNOWN/CANDIDATE observations into reviewed Self evidence.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from fractions import Fraction
from itertools import combinations
from pathlib import Path
from typing import Any

from .subject_death import (
    DeathProbeDecision,
    ProbeFrame,
    ReviewStatus,
    SubjectRelation,
    SubjectRole,
    _hash,
)

_ROLES = frozenset({SubjectRole.SOURCE_PLAYER_BINDING, SubjectRole.VICTIM,
                    SubjectRole.DEATH_TRANSITION})
_COMPONENTS = frozenset({'source_player_binding', 'victim_role', 'report_transition',
                         'native_temporal_continuity', 'negative_controls'})
_NUMERIC_METHODS = frozenset({
    (SubjectRole.SOURCE_PLAYER_BINDING, 'killfeed_highlight_shape_color_v1'),
    (SubjectRole.VICTIM, 'killfeed_weapon_template_ncc_v1'),
    (SubjectRole.DEATH_TRANSITION, 'fresh_self_referential_report_caption_ncc_v1'),
})
_REPORT_METHODS = frozenset({'self_referential_report_caption_ncc_v1',
                             'independent_report_header_ncc_v1'})
_EVALUATION_SCOPE = 'qualified_candidate_evaluation'


def _supported_method(role: SubjectRole, method: str) -> bool:
    if role == SubjectRole.REPORT:
        return method in _REPORT_METHODS
    return (role, method) in _NUMERIC_METHODS


def release_fingerprint() -> str:
    digest = hashlib.sha256()
    source = Path(__file__)
    for label, path in (
        ('numeric_death_release.py', source),
        ('facts/builder.py', source.parent.parent/'facts'/'builder.py'),
    ):
        digest.update(label.encode('utf-8'))
        digest.update(path.read_bytes().replace(b'\r\n', b'\n'))
    return digest.hexdigest()


@dataclass(frozen=True)
class QualifiedNumericDeathContract:
    """Reviewed, exact-fingerprint candidate qualification; not a metrics judge.

    Offline qualification and split independence must be verified before trusted
    candidate-run configuration supplies a report digest. This implements the
    user's existing authorization to evaluate independently qualified candidates;
    it does not request fresh production approval before candidate E2E. No real
    qualification report is included. The file cannot qualify itself by hash.
    """

    report_sha256: str
    source_sha256: str
    code_fingerprint: str
    profile_fingerprint: str
    dependencies_fingerprint: str
    native_step_ticks: int
    split_review_sha256: str
    qualification_review_sha256: str
    component_reviews: tuple[tuple[str, str], ...]
    release_code_fingerprint: str
    source_player_subject_token: str

    @classmethod
    def load(cls, path: Path, *, expected_report_sha256: str) -> QualifiedNumericDeathContract:
        _hash(expected_report_sha256)
        content = path.read_bytes()
        if hashlib.sha256(content).hexdigest() != expected_report_sha256:
            raise ValueError('expected reviewed qualification report digest required')
        data = json.loads(content)
        keys = {'schema_version', 'source_sha256', 'code_fingerprint', 'profile_fingerprint',
                'dependencies_fingerprint', 'native_step_ticks', 'split_review_sha256',
                'qualification_review_sha256', 'component_reviews', 'release_fingerprint',
                'source_player_subject_token', 'evaluation_scope'}
        if (not isinstance(data, dict) or set(data) != keys
                or data['schema_version'] != 'numeric_self_death_qualification_v1'
                or data['evaluation_scope'] != _EVALUATION_SCOPE
                or data['release_fingerprint'] != release_fingerprint()
                or type(data['native_step_ticks']) is not int or data['native_step_ticks'] < 1
                or not isinstance(data['component_reviews'], dict)
                or set(data['component_reviews']) != _COMPONENTS):
            raise ValueError('complete current numeric release contract required')
        for key in ('source_sha256', 'code_fingerprint', 'profile_fingerprint',
                    'dependencies_fingerprint', 'split_review_sha256',
                    'qualification_review_sha256'):
            _hash(data[key])
        for review in data['component_reviews'].values():
            _hash(review)
        _hash(data['source_player_subject_token'])
        return cls(expected_report_sha256, data['source_sha256'], data['code_fingerprint'],
                   data['profile_fingerprint'], data['dependencies_fingerprint'],
                   data['native_step_ticks'], data['split_review_sha256'],
                   data['qualification_review_sha256'],
                   tuple(sorted(data['component_reviews'].items())),
                   data['release_fingerprint'], data['source_player_subject_token'])


class NumericSelfDeathEventConsumer:
    """Consume reviewed Self proof without weakening the existing image/probe path.

    Native adjacency and retained continuity hashes are required, but are not
    themselves semantic continuity qualification. That producer and negative
    controls must be included in the independently reviewed report. Default
    construction has no qualification and emits nothing. The original observations
    and HUD identity/owned fields are never mutated.
    """

    def __init__(self, qualification: QualifiedNumericDeathContract | None = None) -> None:
        if (qualification is not None
                and not isinstance(qualification, QualifiedNumericDeathContract)):
            raise ValueError('typed reviewed numeric qualification required; no Boolean override')
        self.qualification = qualification
        self.released: set[str] = set()
        self.last_blocker: str | None = None

    def consume(self, decision: DeathProbeDecision,
                frames: tuple[ProbeFrame, ...]) -> dict[str, Any] | None:
        def reject(reason: str) -> None:
            self.last_blocker = reason

        qualification = self.qualification
        if qualification is None:
            reject('independent_numeric_qualification_missing')
            return None
        if qualification.release_code_fingerprint != release_fingerprint():
            reject('release_consumer_fingerprint_mismatch')
            return None
        source = decision.source
        if (source.video_sha256 != qualification.source_sha256
                or source.code_fingerprint != qualification.code_fingerprint
                or source.profile_fingerprint != qualification.profile_fingerprint
                or source.dependencies_fingerprint != qualification.dependencies_fingerprint):
            reject('source_or_fingerprint_mismatch')
            return None
        if (decision.status != 'candidate' or len(decision.evidence) != 3
                or set(decision.blockers) not in (
                    {'recognizer_qualification_missing', 'production_adoption_not_authorized'},
                    {'subject_role_transition_not_qualified', 'production_adoption_not_authorized'},
                )):
            reject('complete_numeric_candidate_required')
            return None
        witnesses = decision.evidence
        if {w.role for w in witnesses} != _ROLES or any(
            w.source.context != source.context
            or w.relation != SubjectRelation.SELF
            or w.review_status != ReviewStatus.SOURCE_REVIEWED
            or w.subject_token is None or w.review_sha256 is None
            or w.confidence is None or w.confidence < .90
            or not _supported_method(w.role, w.method) for w in witnesses
        ):
            reject('independent_reviewed_numeric_self_roles_required')
            return None
        if {w.subject_token for w in witnesses} != {qualification.source_player_subject_token}:
            reject('conflicting_subjects')
            return None
        for a, b in combinations(witnesses, 2):
            ax1, ay1, ax2, ay2 = a.roi
            bx1, by1, bx2, by2 = b.roi
            if a.method == b.method or not (
                ax2 <= bx1 or bx2 <= ax1 or ay2 <= by1 or by2 <= ay1
            ):
                reject('independent_source_roles_required')
                return None
        onset = next(w for w in witnesses if w.role == SubjectRole.DEATH_TRANSITION).source
        parent_score = decision.confidence
        if (type(decision.boundary_time_sec) not in (int, float)
                or type(decision.confirmation_time_sec) not in (int, float)
                or decision.boundary_time_sec != float(onset.time)
                or decision.confirmation_time_sec != float(source.time)
                or not 0 < source.time-onset.time <= 1
                or parent_score is None or type(parent_score) not in (int, float)
                or not math.isfinite(parent_score) or not .90 <= parent_score <= 1):
            reject('original_onset_and_confirmation_required')
            return None
        if (not isinstance(frames, tuple) or not frames or frames[-1].source != source
                or any(f.discontinuity or f.source.context != source.context for f in frames)
                or not {w.source for w in witnesses} <= {f.source for f in frames}):
            reject('complete_same_segment_source_chain_required')
            return None
        for previous, current in zip(frames, frames[1:], strict=False):
            if (current.source.pts_ticks-previous.source.pts_ticks
                    != qualification.native_step_ticks
                    or current.previous_pts_ticks != previous.source.pts_ticks
                    or current.continuity_proof_sha256 is None
                    or current.source.pixel_sha256 == previous.source.pixel_sha256):
                reject('gap_duplicate_or_unproved_source_continuity')
                return None
        if any(w not in f.observations for w in witnesses for f in frames
               if f.source == w.source):
            reject('source_chain_does_not_contain_original_witnesses')
            return None
        if any(o.role == SubjectRole.RESPAWN for f in frames if f.source.time >= onset.time
               for o in f.observations):
            reject('respawn_conflicts_with_death_episode')
            return None
        # Require the image recognizer's entire current-frame corroboration
        # duration, not just numeric support at the confirmation endpoint.
        token = witnesses[0].subject_token
        tail: list[ProbeFrame] = []
        tail_scores: list[float] = []
        for frame in reversed(frames):
            if frame.source.time < onset.time:
                break
            selected = []
            for role in (SubjectRole.SOURCE_PLAYER_BINDING, SubjectRole.VICTIM,
                         SubjectRole.REPORT):
                matches = [o for o in frame.observations if o.role == role]
                if (len(matches) != 1 or matches[0].review_status != ReviewStatus.SOURCE_REVIEWED
                        or matches[0].review_sha256 is None or matches[0].confidence is None
                        or matches[0].confidence < .90
                        or not _supported_method(role, matches[0].method)):
                    break
                if role != SubjectRole.REPORT and (
                    matches[0].relation != SubjectRelation.SELF or matches[0].subject_token != token
                ):
                    break
                selected.append(matches[0])
            if len(selected) != 3:
                break
            if any(a.method == b.method or not (
                a.roi[2] <= b.roi[0] or b.roi[2] <= a.roi[0]
                or a.roi[3] <= b.roi[1] or b.roi[3] <= a.roi[1]
            ) for a, b in combinations(selected, 2)):
                break
            tail.append(frame)
            tail_scores.extend(float(o.confidence) for o in selected if o.confidence is not None)
            if len(tail) >= 3 and source.time-frame.source.time >= Fraction(1, 20):
                break
        if len(tail) < 3 or source.time-tail[-1].source.time < Fraction(1, 20):
            reject('continuous_current_frame_corroboration_required')
            return None
        identity = (source.video_sha256, witnesses[0].subject_token,
                    onset.pts_ticks, onset.time_base_num, onset.time_base_den)
        event_id = 'SELF-DEATH-' + hashlib.sha256(json.dumps(identity).encode('utf-8')).hexdigest()
        if event_id in self.released:
            reject('episode_already_released')
            return None
        confidence = min(parent_score, *tail_scores,
                         *(float(w.confidence) for w in witnesses if w.confidence is not None))
        attributes = {
            'cause_known': False,
            'evidence_provenance': {
                'subject_policy': 'independently_qualified_numeric_self_v1',
                'evaluation_scope': _EVALUATION_SCOPE,
                'elimination_coverage': 'self_death_only',
                'native_event_id': event_id,
                'qualification_report_sha256': qualification.report_sha256,
                'qualification_review_sha256': qualification.qualification_review_sha256,
                'onset_source': asdict(onset), 'confirmation_source': asdict(source),
                'subject_evidence': [asdict(w) for w in witnesses],
                'source_chain': [asdict(f.source) for f in frames],
                'corroboration_evidence': [asdict(f) for f in reversed(tail)],
                'continuity_proofs': [f.continuity_proof_sha256 for f in frames[1:]],
            },
        }
        event = {'event_id': event_id, 'time_sec': float(onset.time),
                 'type': 'player_death', 'actor': 'player',
                 'attributes': attributes, 'confidence': confidence}
        self.released.add(event_id)
        self.last_blocker = None
        return event

    def checkpoint(self) -> dict[str, Any]:
        report_sha = self.qualification.report_sha256 if self.qualification else None
        return {'schema_version': 1, 'release_fingerprint': release_fingerprint(),
                'qualification_sha256': report_sha,
                'released_event_ids': sorted(self.released)}

    def restore(self, state: dict[str, Any]) -> None:
        expected = self.checkpoint()
        if (not isinstance(state, dict) or set(state) != set(expected)
                or type(state['schema_version']) is not int or state['schema_version'] != 1
                or state['release_fingerprint'] != expected['release_fingerprint']
                or state['qualification_sha256'] != expected['qualification_sha256']
                or not isinstance(state['released_event_ids'], list)
                or any(not isinstance(v, str) or not v.startswith('SELF-DEATH-')
                       or len(v) != 75 for v in state['released_event_ids'])
                or len(set(state['released_event_ids'])) != len(state['released_event_ids'])):
            raise ValueError('matching exact-release checkpoint required')
        for identity in state['released_event_ids']:
            _hash(identity.removeprefix('SELF-DEATH-'))
        self.released = set(state['released_event_ids'])
