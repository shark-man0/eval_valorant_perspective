"""Associate original field readings with an image-predicted death episode.

This is transport, not semantic qualification. In particular a Report portrait
is not relabeled as a killer and the episode never grants Self ownership. The
formal release consumer must not consume these candidates as qualified fields.
"""
from __future__ import annotations

import copy
import math
from dataclasses import dataclass, replace
from fractions import Fraction
from typing import TYPE_CHECKING, Any

from valorant_ai_coach.hud.models import _validate_report_readings

from .self_death_image import SelfDeathImageReading
from .subject_death import SourceBinding

if TYPE_CHECKING:
    from .report_fatal_row import FatalReportRowReading


def _accepted(value: Any) -> bool:
    return type(value) in (int, float) and math.isfinite(value) and .90 <= value <= 1


def _physical(source: SourceBinding) -> tuple[Any, ...]:
    # Different readers legitimately have different code/profile/dependencies.
    # Their physical frame and source segment must nevertheless match exactly.
    return (source.video_sha256, source.segment_id, source.pts_ticks,
            source.time_base_num, source.time_base_den, source.pixel_sha256)


@dataclass(frozen=True)
class EpisodeField:
    name: str
    value: str | int
    display: str
    source: SourceBinding
    source_confidence: float
    roi: tuple[int, int, int, int]
    methods: tuple[str, ...]
    cross_checked: bool
    association_support: float
    # Original marker/role/Report observations, including their own producer.
    image_witness: SelfDeathImageReading
    fatal_row: FatalReportRowReading | None = None


@dataclass(frozen=True)
class ReportCandidateFrame:
    source: SourceBinding
    report_roi: tuple[int, int, int, int]
    # Serialized immutable payload prevents a provider mutating retained values.
    payload_json: str

    @classmethod
    def from_fields(cls, source: SourceBinding, report_roi: tuple[int, int, int, int],
                    fields: dict[str, dict[str, Any]]) -> ReportCandidateFrame:
        import json

        if (not isinstance(source, SourceBinding) or not isinstance(report_roi, tuple)
                or len(report_roi) != 4
                or any(type(v) is not int or v < 0 for v in report_roi)
                or not report_roi[0] < report_roi[2] or not report_roi[1] < report_roi[3]):
            raise ValueError('original Report frame and nonempty pixel ROI required')
        payload = {
            'status': 'candidate', 'reader': 'combat_report',
            'source_pts_sec': float(source.time), 'source_pixel_sha256': source.pixel_sha256,
            'profile_fingerprint': source.profile_fingerprint, 'fields': copy.deepcopy(fields),
        }
        # Reuse the existing producer's field-specific acceptance/provenance
        # contract; malformed/low-confidence fields are not made acceptable here.
        _validate_report_readings({'combat_report_visible': True,
                                   'combat_report_readings': payload})
        return cls(source, report_roi, json.dumps(payload, sort_keys=True, allow_nan=False))

    def fields_for(self, image: SelfDeathImageReading, support: float) -> tuple[EpisodeField, ...]:
        import json

        if _physical(self.source) != _physical(image.source):
            raise ValueError('Report fields and current image must be the same physical frame')
        payload = json.loads(self.payload_json)
        # Also validate direct construction / deserialized instances.
        checked = self.from_fields(self.source, self.report_roi, payload['fields'])
        if checked.payload_json != self.payload_json:
            raise ValueError('Report payload does not match its original source binding')
        x, y, right, bottom = self.report_roi
        w, h = right-x, bottom-y
        result = []
        for name, field in payload['fields'].items():
            left, top, r, b = field['roi_bounds_norm']
            roi = (x+round(left*w), y+round(top*h), x+round(r*w), y+round(b*h))
            if roi[0] >= roi[2] or roi[1] >= roi[3]:
                raise ValueError('Report field has an empty physical ROI')
            value = field['label'] if name == 'report_portrait_label' else field['value']
            display = field['label'] if name == 'report_portrait_label' else field['display']
            result.append(EpisodeField(name, value, display, self.source, field['confidence'],
                roi, tuple(field['sources']), field['cross_checked'],
                min(support, field['confidence']), image))
        return tuple(result)


@dataclass(frozen=True)
class DeathEpisodeFields:
    onset_source: SourceBinding
    confirmation_source: SourceBinding
    fields: tuple[EpisodeField, ...]
    conflicting_fields: tuple[str, ...]

    @property
    def qualified(self) -> bool:
        return False

    @property
    def formal_events(self) -> tuple[()]:
        return ()


class DeathEpisodeFieldCollector:
    """Bounded native-frame join; no carry-forward or cross-episode fill.

    Only original readings between the existing detector's onset and confirmation
    can contribute. Conflicts suppress that entire field, not unrelated fields.
    A source/producer change or malformed Report poisons this collector until an
    explicit qualified rearm. None of these checks qualifies the image detector.
    """

    def __init__(self, native_step_ticks: int) -> None:
        if type(native_step_ticks) is not int or native_step_ticks < 1:
            raise ValueError('positive native cadence required')
        self.native_step_ticks = native_step_ticks
        self.reset()

    def reset(self) -> None:
        self.frames: list[tuple[SelfDeathImageReading, tuple[EpisodeField, ...]]] = []
        self.failed = False
        self.last_blocker: str | None = None
        self.report_context: tuple[Any, ...] | None = None

    def observe(self, image: SelfDeathImageReading,
                report: ReportCandidateFrame | None = None,
                fatal_row: FatalReportRowReading | None = None) -> DeathEpisodeFields | None:
        def reject(reason: str) -> None:
            self.failed = True
            self.frames.clear()
            self.last_blocker = reason

        if self.failed:
            return None
        source = image.source
        previous = self.frames[-1][0].source if self.frames else None
        if (image.reason == 'source_invalid_or_discontinuous'
                or previous is not None and (
                    source.context != previous.context
                    or source.pts_ticks-previous.pts_ticks != self.native_step_ticks
                    or source.pixel_sha256 == previous.pixel_sha256)):
            reject('episode_field_source_chain_broken')
            return None
        victims = [v for v in image.subjects if v.role == 'victim']
        fields: list[EpisodeField] = []
        current_report = (image.report_support if _accepted(image.report_support)
                          else image.report_presence_support)
        if report is not None:
            if (_physical(report.source) != _physical(source)
                    or self.report_context is not None
                    and report.source.context != self.report_context):
                reject('episode_report_source_or_producer_mismatch')
                return None
            self.report_context = report.source.context
        if fatal_row is not None and (
            report is None or fatal_row.fields_source != report.source
            or _physical(fatal_row.source) != _physical(source)
        ):
            reject('fatal_row_source_mismatch')
            return None
        if len(victims) == 1 and _accepted(current_report):
            victim = victims[0]
            if victim.weapon_roi is not None:
                role_scores = [victim.weapon_support]
                # Legacy weapon profiles do not measure plate support. Preserve
                # that absence, as the image recognizer does; never synthesize 1.
                if victim.weapon_plate_fraction is not None:
                    role_scores.append(victim.weapon_plate_fraction)
            else:
                role_scores = [victim.ability_support, victim.ability_plate_fraction]
            scores = [*victim.marker_support, victim.yellow_fraction, *role_scores,
                      current_report]
            if (victim.source == source and len(victim.marker_support) == 3
                    and all(_accepted(s) for s in scores)):
                support = min(float(s) for s in scores if s is not None)
                if (victim.normalized_name and victim.name_roi is not None
                        and _accepted(victim.name_confidence)):
                    assert victim.name_confidence is not None
                    fields.append(EpisodeField('victim_name', victim.normalized_name,
                        victim.name_text or '', source, victim.name_confidence, victim.name_roi,
                        ('killfeed_victim_name_reader',), False,
                        min(support, victim.name_confidence), image))
                if report is not None:
                    try:
                        for field in report.fields_for(image, support):
                            if (field.name == 'damage_received' and fatal_row is not None
                                    and fatal_row.reason == 'unqualified_fatal_damage_row'
                                    and fatal_row.damage_roi == field.roi
                                    and _accepted(fatal_row.association_support)
                                    and _accepted(fatal_row.marker_support)
                                    and _accepted(fatal_row.header_support)):
                                assert fatal_row.association_support is not None
                                assert fatal_row.marker_support is not None
                                assert fatal_row.header_support is not None
                                field = replace(field, fatal_row=fatal_row,
                                    association_support=min(field.association_support,
                                                            fatal_row.association_support,
                                                            fatal_row.marker_support,
                                                            fatal_row.header_support))
                            fields.append(field)
                    except (ValueError, TypeError, KeyError):
                        reject('episode_report_payload_invalid')
                        return None
        self.frames.append((image, tuple(fields)))
        keep = Fraction(2) + Fraction(self.native_step_ticks*source.time_base_num,
                                      source.time_base_den)
        self.frames = [(r, f) for r, f in self.frames if source.time-r.source.time <= keep]
        if image.status != 'prediction':
            return None
        originals = {r.source for r, _ in self.frames}
        onsets = [r.source for r, _ in self.frames if float(r.source.time) == image.onset_time_sec]
        if (len(onsets) != 1 or image.confirmation_time_sec != float(source.time)
                or not image.evidence_sources or source not in image.evidence_sources
                or not set(image.evidence_sources) <= originals
                or onsets[0] not in image.evidence_sources
                or not 0 < source.time-onsets[0].time <= 1
                or not _accepted(image.support)):
            reject('original_episode_evidence_missing')
            return None
        onset = onsets[0]
        candidates = [f for r, fields_at_frame in self.frames
                      if onset.time <= r.source.time <= source.time for f in fields_at_frame]
        names = sorted({f.name for f in candidates})
        conflicts = tuple(name for name in names
                          if len({f.value for f in candidates if f.name == name}) != 1)
        self.last_blocker = 'conflicting_episode_fields' if conflicts else None
        retained = tuple(f for f in candidates if f.name not in conflicts)
        return DeathEpisodeFields(onset, source, retained, conflicts)
