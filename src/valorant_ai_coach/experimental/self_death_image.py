"""Current-image Self Death predictions for qualification; no formal release.

Combines a source-player killfeed marker in the victim position with a fresh
self-referential report and native temporal corroboration. Never reads GT.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any, Literal

import cv2
import numpy as np

from valorant_ai_coach.hud.readers import HudReader

from . import report_victim_episode, subject_death
from .killfeed_subject import (
    Box,
    KillfeedSubjectProfile,
    KillfeedSubjectReader,
    KillfeedSubjectReading,
    _matches,
)
from .report_victim_episode import DualDeathCandidate, ReportVictimEpisodeProbe
from .subject_death import SourceBinding, _hash


@dataclass(frozen=True)
class SelfDeathImageReading:
    status: Literal['unknown', 'pending', 'prediction', 'duplicate']
    reason: str
    source: SourceBinding
    report_support: float | None
    subjects: tuple[KillfeedSubjectReading, ...]
    onset_time_sec: float | None = None
    confirmation_time_sec: float | None = None
    support: float | None = None
    evidence_sources: tuple[SourceBinding, ...] = ()

    @property
    def qualified(self) -> bool:
        return False

    @property
    def formal_events(self) -> tuple[()]:
        return ()


class SelfDeathImageRecognizer:
    """Non-releasing image recognizer, using PR #50's episode latch.

    A producer-qualified native start is the only explicit rearm input. Its
    truth cannot be inferred here from a timestamp, raw reset or reference GT.
    Qualification must independently verify the report/marker presence AND
    absence readers before these diagnostic predictions can be adopted.
    """

    def __init__(self, profile: KillfeedSubjectProfile, name_reader: HudReader[str],
                 report_reference: Any, report_search_roi: Box, *,
                 runtime_fingerprint: str, dependencies_fingerprint: str,
                 native_step_ticks: int) -> None:
        _hash(runtime_fingerprint)
        _hash(dependencies_fingerprint)
        self.dependencies_fingerprint = dependencies_fingerprint
        if type(native_step_ticks) is not int or native_step_ticks < 1:
            raise ValueError('explicit positive native source cadence required')
        if (report_reference.ndim != 2 or report_reference.dtype != np.uint8
                or float(report_reference.std()) < 5):
            raise ValueError('contrasting self-referential report reference required')
        x1, y1, x2, y2 = report_search_roi
        h, w = report_reference.shape
        if (any(type(v) is not int for v in report_search_roi)
                or not 0 <= x1 < x2 <= profile.frame_shape[1]
                or not 0 <= y1 < y2 <= profile.frame_shape[0]
                or h > y2-y1 or w > x2-x1):
            raise ValueError('source-bound report geometry required')
        report_reference.setflags(write=False)
        self.report_reference = report_reference
        self.report_search_roi = report_search_roi
        self.native_step_ticks = native_step_ticks
        digest = hashlib.sha256(Path(__file__).read_bytes().replace(b'\r\n', b'\n'))
        for module in (report_victim_episode, subject_death):
            assert module.__file__ is not None
            digest.update(Path(module.__file__).read_bytes().replace(b'\r\n', b'\n'))
        digest.update(runtime_fingerprint.encode('ascii'))
        digest.update(dependencies_fingerprint.encode('ascii'))
        digest.update(report_reference.tobytes())
        digest.update(json.dumps(report_search_roi).encode('utf-8'))
        digest.update(str(native_step_ticks).encode('ascii'))
        self.reader = KillfeedSubjectReader(profile, name_reader,
                                            runtime_fingerprint=digest.hexdigest())
        self.episode = ReportVictimEpisodeProbe(report_floor=.90, victim_floor=.90)
        self.previous: SourceBinding | None = None
        self.previous_victim_visible: bool | None = None
        self.marker_onset: SourceBinding | None = None
        self.marker_predecessor: SourceBinding | None = None
        self.report_predecessor: SourceBinding | None = None
        self.pending: DualDeathCandidate | None = None
        self.stable: list[tuple[SourceBinding, float]] = []
        self.evidence: list[SourceBinding] = []
        self.onset_evidence: tuple[SourceBinding, ...] = ()
        self.blocked = False
        self.emitted = False

    @property
    def code_fingerprint(self) -> str:
        return self.reader.code_fingerprint

    @property
    def profile_fingerprint(self) -> str:
        return self.reader.profile.fingerprint()

    def observe(self, image: Any, source: SourceBinding, *,
                qualified_new_round: bool = False) -> SelfDeathImageReading:
        if type(qualified_new_round) is not bool:
            raise ValueError('typed producer-qualified lifecycle signal required')
        p = self.reader.profile
        valid = (isinstance(image, np.ndarray) and image.dtype == np.uint8
                 and image.shape == (*p.frame_shape, 3)
                 and hashlib.sha256(image.tobytes()).hexdigest() == source.pixel_sha256
                 and source.video_sha256 == p.source_sha256
                 and source.code_fingerprint == self.code_fingerprint
                 and source.profile_fingerprint == self.profile_fingerprint
                 and source.dependencies_fingerprint == self.dependencies_fingerprint)
        previous = self.previous
        broken = previous is not None and (
            source.context != previous.context
            or source.pts_ticks-previous.pts_ticks != self.native_step_ticks
            or source.pixel_sha256 == previous.pixel_sha256)
        if not valid or broken:
            self.blocked = True
            self.pending = None
            self.marker_onset = None
            self.marker_predecessor = None
            self.report_predecessor = None
            self.stable.clear()
            self.evidence.clear()
            self.onset_evidence = ()
            self.previous_victim_visible = None
        if qualified_new_round and valid:
            self.episode = ReportVictimEpisodeProbe(report_floor=.90, victim_floor=.90)
            self.blocked, self.emitted = False, False
            self.pending = None
            self.marker_onset = None
            self.marker_predecessor = None
            self.report_predecessor = None
            self.previous_victim_visible = None
            self.stable.clear()
            self.evidence.clear()
            self.onset_evidence = ()
        self.previous = source
        if not valid or self.blocked:
            return SelfDeathImageReading('unknown', 'source_invalid_or_discontinuous',
                                         source, None, ())
        subjects = self.reader.read(image, source)
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        captions = _matches(gray, self.report_reference,
                            (np.full_like(self.report_reference, 255),), self.report_search_roi)
        report = min(captions[0][1]) if len(captions) == 1 else 0.0
        victims = [s for s in subjects if s.role == 'victim']
        visible = len(victims) == 1
        if visible and self.previous_victim_visible is False:
            self.marker_onset = source
            self.marker_predecessor = previous
        self.previous_victim_visible = visible
        support = None
        if visible:
            victim = victims[0]
            assert victim.weapon_support is not None
            support = min(*victim.marker_support, victim.yellow_fraction, victim.weapon_support)
        if report >= .90 and not self.episode.last_report_positive:
            self.report_predecessor = previous
        episode = self.episode.observe(source, report_score=report, victim_score=support)
        if self.emitted:
            return SelfDeathImageReading('duplicate', 'episode_already_predicted', source,
                                         report, subjects)
        if episode.status == 'unqualified_candidate':
            marker = self.marker_onset
            # Both rising edges must actually have been observed in this segment.
            if marker is not None and 0 <= source.time-marker.time <= Fraction(1):
                self.pending = episode
                self.evidence = [s for s in (self.report_predecessor,
                    self.episode.pending_onset, self.marker_predecessor, marker) if s is not None]
                self.onset_evidence = tuple(self.evidence)
        if self.pending is None:
            return SelfDeathImageReading('unknown', 'fresh_report_and_self_victim_unproved',
                                         source, report, subjects)
        onset = self.pending.onset_time_sec
        assert onset is not None
        if (report < .90 or source.time-Fraction(str(onset)) > 1
                or any(s.role == 'killer' for s in subjects)):
            self.pending = None
            self.stable.clear()
            self.evidence.clear()
            self.onset_evidence = ()
            return SelfDeathImageReading('unknown', 'corroboration_interrupted_or_expired',
                                         source, report, subjects)
        if support is None:
            # A reader dropout invalidates the corroboration run, not the
            # independently observed report edge. A later run must still meet
            # the entire native-frame duration before that original edge expires.
            self.stable.clear()
            self.evidence = list(self.onset_evidence)
            return SelfDeathImageReading('unknown', 'victim_corroboration_restart_required',
                                         source, report, subjects, onset_time_sec=onset)
        self.stable.append((source, min(report, support)))
        self.evidence.append(source)
        if len(self.stable) < 3 or source.time-self.stable[0][0].time < Fraction(1, 20):
            return SelfDeathImageReading('pending', 'native_corroboration_pending', source,
                                         report, subjects, onset_time_sec=onset)
        self.emitted = True
        return SelfDeathImageReading(
            'prediction', 'qualification_and_production_adoption_pending', source,
            report, subjects, onset, float(source.time), min(s for _, s in self.stable),
            tuple(dict.fromkeys(self.evidence)),
        )
