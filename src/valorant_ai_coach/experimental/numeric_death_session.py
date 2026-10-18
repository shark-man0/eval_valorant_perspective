"""Image-to-Event orchestration for an independently qualified candidate run.

This adapter grants no subject identity. Its frame provider must supply already
reviewed subject/continuity evidence; each numerical witness is checked against
the current image reading before the existing release consumer sees it. No
provider or qualification is installed by default, and no application caller is
enabled here.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from fractions import Fraction
from typing import Any

from .death_episode_fields import (
    DeathEpisodeFieldCollector,
    DeathEpisodeFields,
    ReportCandidateFrame,
)
from .numeric_death_release import NumericSelfDeathEventConsumer
from .report_fatal_row import FatalReportRowReader, FatalReportRowReading
from .self_death_image import SelfDeathImageReading, SelfDeathImageRecognizer
from .subject_death import DeathProbeDecision, ProbeFrame, SourceBinding, SubjectRole


@dataclass(frozen=True)
class NumericDeathSessionReading:
    image_reading: SelfDeathImageReading
    event: dict[str, Any] | None
    blocker: str | None
    episode_fields: DeathEpisodeFields | None = None
    field_blocker: str | None = None
    report_row: FatalReportRowReading | None = None


class NumericDeathImageSession:
    """Join actual image predictions to original, separately reviewed witnesses.

    A provider is not a Boolean permission or an image classifier: it must return
    a genuine qualified producer's ProbeFrame for this exact source. The adapter
    never replaces UNKNOWN/CANDIDATE with SELF/SOURCE_REVIEWED. Continuity hashes
    must come from the independently qualified source producer, not this adapter.
    """

    def __init__(
        self, recognizer: SelfDeathImageRecognizer, consumer: NumericSelfDeathEventConsumer,
        frame_provider: Callable[[SelfDeathImageReading], ProbeFrame] | None = None,
        *,
        report_provider: Callable[[Any, SourceBinding], ReportCandidateFrame | None] | None = None,
        report_row_reader: FatalReportRowReader | None = None,
    ) -> None:
        self.recognizer = recognizer
        self.consumer = consumer
        self.frame_provider = frame_provider
        self.report_provider = report_provider
        if report_row_reader is not None and report_provider is None:
            raise ValueError('fatal-row measurement needs the original Report provider')
        self.report_row_reader = report_row_reader
        self.field_collector = DeathEpisodeFieldCollector(recognizer.native_step_ticks)
        self.frames: list[ProbeFrame] = []
        self.failed = False

    def observe(self, image: Any, source: SourceBinding, *,
                qualified_new_round: bool = False) -> NumericDeathSessionReading:
        reading = self.recognizer.observe(image, source,
                                          qualified_new_round=qualified_new_round)
        if qualified_new_round:
            self.frames.clear()
            self.failed = False
            self.field_collector.reset()
        report = self.report_provider(image, source) if self.report_provider is not None else None
        report_row = (self.report_row_reader.read(image, report)
                      if report is not None and self.report_row_reader is not None else None)
        episode_fields = self.field_collector.observe(reading, report, report_row)

        def reject(reason: str, *, poison: bool = False) -> NumericDeathSessionReading:
            if poison:
                self.failed = True
                self.frames.clear()
            return NumericDeathSessionReading(reading, None, reason, episode_fields,
                                             self.field_collector.last_blocker, report_row)

        if reading.reason == 'source_invalid_or_discontinuous':
            return reject(reading.reason, poison=True)
        if self.failed:
            return reject('qualified_source_chain_requires_rearm')
        qualification = self.consumer.qualification
        if qualification is None:
            return reject('independent_numeric_qualification_missing')
        if self.frame_provider is None:
            return reject('qualified_frame_provider_missing')
        if (source.video_sha256 != qualification.source_sha256
                or source.code_fingerprint != qualification.code_fingerprint
                or source.profile_fingerprint != qualification.profile_fingerprint
                or source.dependencies_fingerprint != qualification.dependencies_fingerprint
                or self.recognizer.native_step_ticks != qualification.native_step_ticks):
            return reject('source_or_fingerprint_mismatch', poison=True)
        frame = self.frame_provider(reading)
        if not isinstance(frame, ProbeFrame) or frame.source != source:
            return reject('qualified_frame_source_mismatch', poison=True)
        if frame.discontinuity:
            return reject('qualified_frame_discontinuity', poison=True)
        previous = self.frames[-1] if self.frames else None
        if previous is not None and (
            source.context != previous.source.context
            or source.pts_ticks-previous.source.pts_ticks != qualification.native_step_ticks
            or frame.previous_pts_ticks != previous.source.pts_ticks
            or frame.continuity_proof_sha256 is None
            or source.pixel_sha256 == previous.source.pixel_sha256
        ):
            return reject('qualified_source_chain_gap_or_unproved_continuity', poison=True)
        if not self._measurements_match(reading, frame):
            return reject('qualified_witness_not_supported_by_current_image', poison=True)
        self.frames.append(frame)
        # The marker can precede the report edge by up to one second, and
        # confirmation can follow that edge by another second. Keep both
        # existing horizons plus the original native onset predecessor.
        keep = Fraction(2) + Fraction(qualification.native_step_ticks*source.time_base_num,
                                      source.time_base_den)
        self.frames = [f for f in self.frames if source.time-f.source.time <= keep]
        if reading.status != 'prediction':
            return reject('image_prediction_pending')
        if not set(reading.evidence_sources) <= {f.source for f in self.frames}:
            return reject('original_image_evidence_missing_from_source_chain', poison=True)
        onsets = [f for f in self.frames if float(f.source.time) == reading.onset_time_sec]
        if len(onsets) != 1:
            return reject('original_image_onset_missing_or_ambiguous', poison=True)
        selection = (
            (frame, SubjectRole.SOURCE_PLAYER_BINDING),
            (frame, SubjectRole.VICTIM),
            (onsets[0], SubjectRole.DEATH_TRANSITION),
        )
        witnesses = []
        for original, role in selection:
            found = [o for o in original.observations if o.role == role]
            if len(found) != 1:
                return reject('qualified_original_role_missing_or_ambiguous', poison=True)
            witnesses.append(found[0])
        decision = DeathProbeDecision('candidate', (
            'recognizer_qualification_missing', 'production_adoption_not_authorized',
        ), source, reading.onset_time_sec, reading.confirmation_time_sec,
            reading.support, tuple(witnesses))
        event = self.consumer.consume(decision, tuple(self.frames), episode_fields=episode_fields)
        return NumericDeathSessionReading(reading, event, self.consumer.last_blocker,
                                         episode_fields, self.field_collector.last_blocker,
                                         report_row)

    def _measurements_match(self, reading: SelfDeathImageReading, frame: ProbeFrame) -> bool:
        """A reviewed tag cannot invent support/ROI absent from this source image."""
        victims = [s for s in reading.subjects if s.role == 'victim']
        victim = victims[0] if len(victims) == 1 else None
        for observation in frame.observations:
            maximum: float | None = None
            roi: tuple[int, int, int, int] | None = self.recognizer.report_search_roi
            if observation.role == SubjectRole.SOURCE_PLAYER_BINDING:
                if victim is not None:
                    maximum = min(*victim.marker_support, victim.yellow_fraction)
                    roi = victim.marker_roi
                method = 'killfeed_highlight_shape_color_v1'
            elif observation.role == SubjectRole.VICTIM:
                if victim is not None and victim.weapon_roi is not None:
                    maximum = victim.weapon_support
                    roi = victim.weapon_roi
                method = 'killfeed_weapon_template_ncc_v1'
            elif observation.role == SubjectRole.DEATH_TRANSITION:
                if (self.recognizer.episode.pending_onset == frame.source
                        and self.recognizer.report_predecessor is not None):
                    maximum = reading.report_support
                roi = reading.report_match_roi
                method = 'fresh_self_referential_report_caption_ncc_v1'
            elif observation.role == SubjectRole.REPORT:
                if observation.method == 'self_referential_report_caption_ncc_v1':
                    maximum = reading.report_support
                    roi = reading.report_match_roi
                elif observation.method == 'independent_report_header_ncc_v1':
                    maximum = reading.report_presence_support
                    roi = (self.recognizer.report_presence_search_roi
                           or self.recognizer.report_search_roi)
                method = observation.method
            elif observation.role in {SubjectRole.RESPAWN, SubjectRole.SPECTATOR}:
                # These independently supplied vetoes cannot contribute positive
                # evidence or grant Self; the consumer still rejects respawn.
                continue
            else:
                return False
            if (maximum is None or maximum < .90 or observation.confidence is None
                    or observation.confidence > maximum or observation.roi != roi
                    or observation.method != method):
                return False
        return True
