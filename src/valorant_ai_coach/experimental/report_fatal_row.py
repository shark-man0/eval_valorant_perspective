"""Measure a fatal-damage row label without declaring a Death or Self owner.

The static label is independent of the damage digits. Persistent Reports can
pass this reader; only the separate qualified lifecycle may establish a new
death. This module has no formal Event/Fact constructor or application default.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from valorant_ai_coach.hud.report_header import ReportFieldLocator

from .death_episode_fields import ReportCandidateFrame
from .killfeed_subject import Box, _matches
from .subject_death import SourceBinding, _hash


@dataclass(frozen=True)
class FatalReportRowReading:
    source: SourceBinding
    fields_source: SourceBinding
    reason: str
    marker_roi: Box | None = None
    damage_roi: Box | None = None
    marker_support: float | None = None
    header_support: float | None = None
    association_support: float | None = None

    @property
    def qualified(self) -> bool:
        return False


class FatalReportRowReader:
    """Require the original value slot plus a separately measured fatal label.

    Search/field bounds are explicit source-calibrated profile data. They are
    translated only by the existing current Report header locator. Neither GT
    values nor a death timestamp/name/agent is an input.
    """

    def __init__(self, *, reference: Any, search_box: Box, locator: ReportFieldLocator,
                 damage_bounds: tuple[float, float, float, float],
                 field_producer: tuple[str, str, str], dependencies_fingerprint: str) -> None:
        if (not isinstance(reference, np.ndarray) or reference.dtype != np.uint8
                or reference.ndim != 2 or min(reference.shape) < 2 or reference.std() == 0):
            raise ValueError('nonconstant original grayscale label reference required')
        locator.validate()
        h, w = locator.header.input_shape
        if (len(search_box) != 4 or any(type(v) is not int for v in search_box)
                or not 0 <= search_box[0] < search_box[2] <= w
                or not 0 <= search_box[1] < search_box[3] <= h
                or search_box[2]-search_box[0] < reference.shape[1]
                or search_box[3]-search_box[1] < reference.shape[0]
                or len(damage_bounds) != 4
                or any(type(v) not in (int, float) or not math.isfinite(v)
                       for v in damage_bounds)
                or not 0 <= damage_bounds[0] < damage_bounds[2] <= 1
                or not 0 <= damage_bounds[1] < damage_bounds[3] <= 1
                or len(field_producer) != 3):
            raise ValueError('source-calibrated Report row profile required')
        for value in (*field_producer, dependencies_fingerprint):
            _hash(value)
        self.reference = reference.copy()
        self.reference.flags.writeable = False
        self.search_box = search_box
        header_arrays = [a.copy() for a in (
            locator.header.reference, locator.header.mask, locator.header.regions)]
        for array in header_arrays:
            array.flags.writeable = False
        self.locator = replace(locator, header=replace(locator.header,
            reference=header_arrays[0], mask=header_arrays[1], regions=header_arrays[2]))
        self.damage_bounds = damage_bounds
        self.field_producer = field_producer
        self.dependencies_fingerprint = dependencies_fingerprint
        metadata = {'search_box': search_box, 'damage_bounds': damage_bounds,
                    'field_producer': field_producer,
                    'reference_shape': reference.shape,
                    'reference_sha256': hashlib.sha256(reference.tobytes()).hexdigest(),
                    'header_origin': locator.reference_origin_norm,
                    'header_shape': locator.header.input_shape,
                    'header_threshold': locator.header.threshold,
                    'header_reference_x': locator.header.reference_x,
                    'header_mask_sha256': hashlib.sha256(locator.header.mask.tobytes()).hexdigest(),
                    'header_regions_sha256': hashlib.sha256(
                        locator.header.regions.tobytes()).hexdigest(),
                    'header_reference_sha256': hashlib.sha256(
                        locator.header.reference.tobytes()).hexdigest()}
        self.profile_fingerprint = hashlib.sha256(json.dumps(
            metadata, sort_keys=True).encode()).hexdigest()
        self.code_fingerprint = hashlib.sha256(
            Path(__file__).read_bytes().replace(b'\r\n', b'\n')
            + Path(__file__).with_name('killfeed_subject.py').read_bytes().replace(b'\r\n', b'\n')
            + Path(__file__).with_name('death_episode_fields.py').read_bytes().replace(
                b'\r\n', b'\n')
            + field_producer[0].encode()).hexdigest()

    def read(self, image: Any, fields: ReportCandidateFrame) -> FatalReportRowReading:
        original = fields.source
        measured = replace(original, code_fingerprint=self.code_fingerprint,
                           profile_fingerprint=self.profile_fingerprint,
                           dependencies_fingerprint=self.dependencies_fingerprint)

        def rejected(reason: str) -> FatalReportRowReading:
            return FatalReportRowReading(measured, original, reason)

        if ((original.code_fingerprint, original.profile_fingerprint,
             original.dependencies_fingerprint) != self.field_producer
                or not isinstance(image, np.ndarray) or image.dtype != np.uint8
                or image.ndim != 3 or image.shape[2] != 3
                or hashlib.sha256(image.tobytes()).hexdigest() != original.pixel_sha256):
            return rejected('original_field_producer_or_pixels_mismatch')
        left, top, right, bottom = fields.report_roi
        if not (0 <= left < right <= image.shape[1] and 0 <= top < bottom <= image.shape[0]):
            return rejected('report_roi_outside_current_frame')
        crop = image[top:bottom, left:right]
        if crop.shape[:2] != self.locator.header.input_shape:
            return rejected('report_calibration_shape_mismatch')
        offset = self.locator.offset(crop)
        if offset is None:
            return rejected('current_report_header_missing')
        dx, dy, header_score = offset
        x1, y1, x2, y2 = self.search_box
        region = (x1+dx, y1+dy, x2+dx, y2+dy)
        if not (0 <= region[0] < region[2] <= crop.shape[1]
                and 0 <= region[1] < region[3] <= crop.shape[0]):
            return rejected('translated_label_search_outside_report')
        matches = _matches(cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY), self.reference,
                           (np.full_like(self.reference, 255),), region)
        if len(matches) != 1:
            return rejected('fatal_row_label_missing_or_ambiguous')
        marker, scores = matches[0]
        payload = json.loads(fields.payload_json)
        checked = ReportCandidateFrame.from_fields(original, fields.report_roi, payload['fields'])
        if checked != fields:
            return rejected('original_report_payload_mismatch')
        damage = payload['fields'].get('damage_received')
        if damage is None:
            return rejected('accepted_damage_value_missing')
        h, w = crop.shape[:2]
        a, b, c, d = self.damage_bounds
        expected = (round(a*w)+dx, round(b*h)+dy, round(c*w)+dx, round(d*h)+dy)
        a, b, c, d = damage['roi_bounds_norm']
        actual = (round(a*w), round(b*h), round(c*w), round(d*h))
        marker_center = ((marker[0]+marker[2])/2, (marker[1]+marker[3])/2)
        if (actual != expected or not actual[0] < marker_center[0] < actual[2]
                or not (actual[1]+actual[3])/2 < marker_center[1]
                <= actual[3]+self.reference.shape[0]):
            return rejected('fatal_marker_does_not_identify_original_damage_slot')
        return FatalReportRowReading(measured, original, 'unqualified_fatal_damage_row',
            (marker[0]+left, marker[1]+top, marker[2]+left, marker[3]+top),
            (actual[0]+left, actual[1]+top, actual[2]+left, actual[3]+top),
            min(scores), header_score, min(*scores, header_score, damage['confidence']))
