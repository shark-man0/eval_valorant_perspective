"""Qualified image measurements to event-subject proof, without HUD identity.

This producer requires both independently qualified numeric recognition and the
existing qualified native scene entrance. No certificate/default caller is
installed. It creates new producer observations; it never relabels archived
UNKNOWN/CANDIDATE records or uses evaluation labels as runtime input.
"""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from dataclasses import dataclass
from fractions import Fraction

from valorant_ai_coach.hud.global_lifecycle import (
    _scene_attested,
    global_recognizer_fingerprint,
)
from valorant_ai_coach.hud.native_lifecycle import NativeLifecycleAnalysis
from valorant_ai_coach.hud.round_lifecycle import is_discontinuous
from valorant_ai_coach.video.native import NativeSourceFrame
from valorant_ai_coach.video.service import VideoProbeError

from .death_episode_fields import _accepted
from .numeric_death_release import QualifiedNumericDeathContract, release_fingerprint
from .self_death_image import SelfDeathImageReading, SelfDeathImageRecognizer
from .subject_death import (
    ProbeFrame,
    ReviewStatus,
    SourceBinding,
    SubjectObservation,
    SubjectRelation,
    SubjectRole,
)


@dataclass(frozen=True)
class _NativeWitness:
    frame: NativeSourceFrame
    proof_json: str | None
    declared_break: bool


class QualifiedNumericImageProvider:
    """Candidate-only producer under the existing numeric qualification contract.

    Component review hashes refer to independently reviewed producer semantics,
    not a claim that each runtime frame was manually labeled. Known Subject
    observations are created only under that exact external qualification.
    Native scene proof supplies continuity only, never Self, HP or Alive.
    """

    def __init__(self, recognizer: SelfDeathImageRecognizer,
                 qualification: QualifiedNumericDeathContract, *,
                 frames: tuple[NativeSourceFrame, ...],
                 lifecycle: NativeLifecycleAnalysis) -> None:
        if (not isinstance(qualification, QualifiedNumericDeathContract)
                or qualification.release_code_fingerprint != release_fingerprint()
                or qualification.code_fingerprint != recognizer.code_fingerprint
                or qualification.profile_fingerprint != recognizer.profile_fingerprint
                or qualification.dependencies_fingerprint != recognizer.dependencies_fingerprint
                or qualification.native_step_ticks != recognizer.native_step_ticks
                or qualification.source_sha256 != recognizer.reader.profile.source_sha256):
            raise ValueError('exact independently reviewed numeric producer required')
        scene = lifecycle.qualification
        if (scene is None or 'scene_continuity' not in scene.components
                or scene.recognizer_fingerprint != global_recognizer_fingerprint()
                or dict(qualification.component_reviews).get('native_temporal_continuity')
                != scene.report_sha256
                or not isinstance(frames, tuple) or not frames
                or any(not isinstance(f, NativeSourceFrame) for f in frames)
                or len(frames) != len(lifecycle.source_rows)):
            raise ValueError('current qualified native scene coverage required')
        self.recognizer, self.qualification = recognizer, qualification
        self.scene_qualification = scene
        witnesses = []
        for native, original in zip(frames, lifecycle.source_rows, strict=True):
            row = deepcopy(original)
            binding = {
                'source_video_sha256': native.source_video_sha256,
                'source_epoch': native.source_epoch, 'source_pts_ticks': native.pts_ticks,
                'source_time_base': str(native.time_base), 'source_pts_sec': native.time_sec,
                'source_pixel_sha256': native.pixel_sha256,
            }
            if (not isinstance(native, NativeSourceFrame)
                    or any(row.get(key) != value for key, value in binding.items())
                    or native.source_video_sha256 != qualification.source_sha256):
                raise ValueError('native scene and image source bindings must agree')
            proof = row.get('system_evidence', {}).get('global_scene_continuity')
            witnesses.append(_NativeWitness(native, json.dumps(proof, sort_keys=True,
                allow_nan=False) if proof is not None else None,
                is_discontinuous(None, row.get('system_observation', {}),
                                 row.get('system_evidence', {}))))
        self._witnesses = tuple(witnesses)
        self.index = 0
        self.previous: SourceBinding | None = None
        self.scene_segment: str | None = None
        self.failed = False
        self.last_blocker: str | None = None

    def __call__(self, reading: SelfDeathImageReading) -> ProbeFrame:
        source = reading.source

        def reject(reason: str) -> ProbeFrame:
            self.failed = True
            self.last_blocker = reason
            return ProbeFrame(source, (), discontinuity=True)

        if self.failed:
            return reject('qualified_provider_requires_new_source_session')
        if self.index >= len(self._witnesses):
            return reject('native_source_coverage_exhausted')
        witness = self._witnesses[self.index]
        native = witness.frame
        qualification = self.qualification
        if (qualification.release_code_fingerprint != release_fingerprint()
                or self.scene_qualification.recognizer_fingerprint
                != global_recognizer_fingerprint()
                or source.video_sha256 != qualification.source_sha256
                or source.code_fingerprint != qualification.code_fingerprint
                or source.profile_fingerprint != qualification.profile_fingerprint
                or source.dependencies_fingerprint != qualification.dependencies_fingerprint
                or source.pts_ticks != native.pts_ticks
                or source.time_base_num != native.time_base.numerator
                or source.time_base_den != native.time_base.denominator
                or source.time != native.pts_ticks*native.time_base
                or source.segment_id != native.source_epoch
                or source.pixel_sha256 != native.pixel_sha256):
            return reject('current_image_and_qualified_source_mismatch')
        if witness.declared_break:
            return reject('declared_native_source_discontinuity')
        # Actual encoded/pixel verification, not a hash manufactured from a label.
        try:
            native.read_image()
        except (VideoProbeError, OSError):
            return reject('native_encoded_or_pixel_hash_mismatch')
        previous = self.previous
        proof_hash = None
        source_support = None
        if previous is not None:
            if (source.context != previous.context
                    or source.pts_ticks-previous.pts_ticks != qualification.native_step_ticks
                    or source.pixel_sha256 == previous.pixel_sha256 or witness.proof_json is None):
                return reject('native_source_gap_repeat_or_missing_scene_proof')
            proof = json.loads(witness.proof_json)
            token = proof.get('segment') if isinstance(proof, dict) else None
            if (not isinstance(proof, dict) or not isinstance(token, str) or not token.strip()
                    or not _accepted(proof.get('confidence'))
                    or proof.get('qualification_sha256') != self.scene_qualification.report_sha256
                    or not _scene_attested(proof, {'time_sec': float(previous.time)},
                                           self.scene_qualification)
                    or proof.get('source_video_sha256') != source.video_sha256
                    or proof.get('source_epoch') != source.segment_id
                    or type(proof.get('source_pts_ticks')) is not int
                    or proof.get('source_pts_ticks') != source.pts_ticks
                    or proof.get('source_time_base') != str(Fraction(source.time_base_num,
                                                                   source.time_base_den))
                    or proof.get('source_pts_sec') != float(source.time)
                    or proof.get('source_pixel_sha256') != source.pixel_sha256
                    or type(proof.get('previous_source_pts_ticks')) is not int
                    or proof.get('previous_source_pts_ticks') != previous.pts_ticks
                    or proof.get('previous_source_pixel_sha256') != previous.pixel_sha256
                    or self.scene_segment is not None and token != self.scene_segment):
                return reject('qualified_scene_pair_missing_conflicting_or_discontinuous')
            if proof['confidence'] > min(proof['witness_ncc']):
                return reject('scene_confidence_exceeds_original_witness_support')
            source_support = float(proof['confidence'])
            self.scene_segment = token
            proof_hash = hashlib.sha256(witness.proof_json.encode('utf-8')).hexdigest()
        observations = []
        reviews = dict(qualification.component_reviews)

        def add(role: SubjectRole, score: float, method: str,
                roi: tuple[int, int, int, int], component: str) -> None:
            if not _accepted(score):
                return
            if source_support is not None:
                score = min(score, source_support)
            relation = (SubjectRelation.UNKNOWN if role == SubjectRole.REPORT
                        else SubjectRelation.SELF)
            token = (None if relation == SubjectRelation.UNKNOWN
                     else qualification.source_player_subject_token)
            identity = (source.pixel_sha256, source.pts_ticks, role, method)
            observations.append(SubjectObservation(
                hashlib.sha256(json.dumps(identity).encode('utf-8')).hexdigest(),
                source, role, relation, token, score, method, roi,
                ReviewStatus.SOURCE_REVIEWED, reviews[component]))

        victims = [s for s in reading.subjects if s.role == 'victim' and s.source == source]
        if len(victims) == 1:
            victim = victims[0]
            if len(victim.marker_support) == 3 and all(_accepted(s) for s in (
                *victim.marker_support, victim.yellow_fraction,
            )):
                add(SubjectRole.SOURCE_PLAYER_BINDING,
                    min(*victim.marker_support, victim.yellow_fraction),
                    'killfeed_highlight_shape_color_v1', victim.marker_roi, 'source_player_binding')
            # Structural/ability predicates never masquerade as numeric weapon NCC.
            if victim.weapon_roi is not None and _accepted(victim.weapon_support):
                assert victim.weapon_support is not None
                support = victim.weapon_support
                if (victim.weapon_plate_fraction is not None
                        and not _accepted(victim.weapon_plate_fraction)):
                    support = 0.0
                elif victim.weapon_plate_fraction is not None:
                    support = min(support, victim.weapon_plate_fraction)
                add(SubjectRole.VICTIM, support, 'killfeed_weapon_template_ncc_v1',
                    victim.weapon_roi, 'victim_role')
        if _accepted(reading.report_support) and reading.report_match_roi is not None:
            assert reading.report_support is not None
            add(SubjectRole.REPORT, reading.report_support,
                'self_referential_report_caption_ncc_v1', reading.report_match_roi,
                'report_transition')
            if (self.recognizer.episode.pending_onset == source
                    and self.recognizer.report_predecessor is not None):
                add(SubjectRole.DEATH_TRANSITION, reading.report_support,
                    'fresh_self_referential_report_caption_ncc_v1', reading.report_match_roi,
                    'report_transition')
        elif _accepted(reading.report_presence_support):
            assert reading.report_presence_support is not None
            add(SubjectRole.REPORT, reading.report_presence_support,
                'independent_report_header_ncc_v1', self.recognizer.report_presence_search_roi
                or self.recognizer.report_search_roi, 'report_transition')
        self.index += 1
        self.previous = source
        self.last_blocker = None
        return ProbeFrame(source, tuple(observations),
                          previous.pts_ticks if previous is not None else None, proof_hash)

    def continuity_provenance(self) -> dict[str, object]:
        """Export original accepted scene proof bodies for private artifact storage.

        Event proof hashes can be resolved against these original records. This
        is not a checkpoint, evidence loader or qualification generator.
        """
        proofs = {}
        for witness in self._witnesses[1:self.index]:
            assert witness.proof_json is not None
            digest = hashlib.sha256(witness.proof_json.encode('utf-8')).hexdigest()
            proofs[digest] = json.loads(witness.proof_json)
        return {'scene_qualification_sha256': self.scene_qualification.report_sha256,
                'numeric_qualification_sha256': self.qualification.report_sha256,
                'scene_proofs': proofs}
