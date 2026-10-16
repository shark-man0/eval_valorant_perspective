"""Image reader for a source-player highlight and its killfeed role.

Measures current pixels, not names/times supplied by GT. Output stays an
unqualified diagnostic: no HUD identity, player Fact or Death event is granted.
"""
from __future__ import annotations

import hashlib
import json
import math
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import cv2
import numpy as np

from valorant_ai_coach.hud.readers import HudReader
from valorant_ai_coach.hud.weapon_identity import masked_score

from .subject_death import SourceBinding, _hash

Box = tuple[int, int, int, int]


@dataclass(frozen=True)
class KillfeedSubjectProfile:
    source_sha256: str
    owner_marker_review_sha256: str
    frame_shape: tuple[int, int]
    search_roi: Box
    marker_reference: Any
    marker_masks: tuple[Any, Any, Any]
    yellow_mask: Any
    weapon_reference: Any
    headshot_reference: Any
    name_y_offsets: tuple[int, int] = (9, 31)
    additional_weapon_references: tuple[Any, ...] = ()

    def __post_init__(self) -> None:
        _hash(self.source_sha256)
        _hash(self.owner_marker_review_sha256)
        x1, y1, x2, y2 = self.search_roi
        if (any(type(v) is not int for v in (*self.frame_shape, *self.search_roi))
                or not 0 <= x1 < x2 <= self.frame_shape[1]
                or not 0 <= y1 < y2 <= self.frame_shape[0]):
            raise ValueError('source-bound search geometry required')
        occupied = np.zeros(self.marker_reference.shape, dtype=bool)
        if not set(np.unique(self.marker_reference)) <= {0, 255}:
            raise ValueError('binary highlight-shape reference required')
        for mask in self.marker_masks:
            if (mask.shape != self.marker_reference.shape or np.count_nonzero(mask) < 32
                    or np.any(occupied & (mask > 0))
                    or float(self.marker_reference[mask > 0].std()) < 5):
                raise ValueError('three disjoint structural supports required')
            occupied |= mask > 0
        if (len(self.marker_masks) != 3 or self.yellow_mask.shape != occupied.shape
                or np.count_nonzero(self.yellow_mask) < 32
                or np.any((self.yellow_mask > 0) & ~occupied)):
            raise ValueError('highlight color must be supported by the structural border')
        h, w = self.marker_reference.shape
        if (any(type(v) is not int for v in self.name_y_offsets)
                or not 0 <= self.name_y_offsets[0] < self.name_y_offsets[1] <= h):
            raise ValueError('name crop must remain inside the row height')
        for array in (self.marker_reference, *self.marker_masks, self.yellow_mask,
                      self.weapon_reference, self.headshot_reference,
                      *self.additional_weapon_references):
            if array.ndim != 2 or array.dtype != np.uint8 or float(array.std()) < 5:
                raise ValueError('contrasting uint8 structural raster required')
            array.setflags(write=False)
        if h > y2-y1 or w > x2-x1:
            raise ValueError('marker exceeds source search region')

    def fingerprint(self) -> str:
        digest = hashlib.sha256(json.dumps({
            'source': self.source_sha256, 'review': self.owner_marker_review_sha256,
            'frame_shape': self.frame_shape, 'search': self.search_roi,
            'name_y_offsets': self.name_y_offsets,
            'marker_feature': 'hsv_yellow_outline_v1',
        }, sort_keys=True).encode('utf-8'))
        for array in (self.marker_reference, *self.marker_masks, self.yellow_mask,
                      self.weapon_reference, self.headshot_reference,
                      *self.additional_weapon_references):
            digest.update(str(array.shape).encode('ascii'))
            digest.update(array.tobytes())
        return digest.hexdigest()


@dataclass(frozen=True)
class KillfeedSubjectReading:
    source: SourceBinding
    role: Literal['killer', 'victim', 'unknown']
    marker_roi: Box
    weapon_roi: Box | None
    name_roi: Box | None
    marker_support: tuple[float, ...]
    yellow_fraction: float
    name_text: str | None
    name_confidence: float | None
    reason: str
    weapon_support: float | None = None

    @property
    def qualified(self) -> bool:
        return False

    @property
    def formal_events(self) -> tuple[()]:
        return ()

    @property
    def normalized_name(self) -> str | None:
        return unicodedata.normalize('NFKC', self.name_text).strip() if self.name_text else None


def _iou(a: Box, b: Box) -> float:
    intersection = max(0, min(a[2], b[2])-max(a[0], b[0])) * max(
        0, min(a[3], b[3])-max(a[1], b[1]))
    union = (a[2]-a[0])*(a[3]-a[1])+(b[2]-b[0])*(b[3]-b[1])-intersection
    return intersection / union


def _matches(gray: Any, reference: Any, masks: tuple[Any, ...],
             region: Box) -> list[tuple[Box, tuple[float, ...]]]:
    left, top, right, bottom = region
    h, w = reference.shape
    if bottom-top < h or right-left < w:
        return []
    crop = gray[top:bottom, left:right]
    scores = np.stack([np.nan_to_num(cv2.matchTemplate(
        crop, reference, cv2.TM_CCOEFF_NORMED, mask=m), nan=-1, posinf=-1, neginf=-1)
        for m in masks])
    ys, xs = np.where(scores.min(axis=0) >= .90)
    if len(ys) > 128:
        return []  # ambiguous repeated structure cannot qualify a unique slot
    accepted: list[tuple[Box, tuple[float, ...]]] = []
    for y, x in sorted(zip(ys.tolist(), xs.tolist(), strict=True),
                       key=lambda p: -float(scores[:, p[0], p[1]].min())):
        box = (left+x, top+y, left+x+w, top+y+h)
        if any(_iou(box, old) > .5 for old, _ in accepted):
            continue
        actual = gray[box[1]:box[3], box[0]:box[2]]
        support = tuple(masked_score(reference, actual, m) for m in masks)
        if min(support) >= .90:
            accepted.append((box, support))
    return accepted


class KillfeedSubjectReader:
    """Locate highlighted portrait and independent weapon separator in one row.

    The weapon must lie wholly left (victim) or right (killer) of the marker.
    Names are read from that measured gap, never compared to expected strings.
    """

    def __init__(self, profile: KillfeedSubjectProfile, reader: HudReader[str],
                 *, runtime_fingerprint: str) -> None:
        _hash(runtime_fingerprint)
        self.profile, self.reader = profile, reader
        digest = hashlib.sha256(Path(__file__).read_bytes().replace(b'\r\n', b'\n'))
        digest.update(runtime_fingerprint.encode('ascii'))
        self.code_fingerprint = digest.hexdigest()

    def read(self, image: Any, source: SourceBinding) -> tuple[KillfeedSubjectReading, ...]:
        p = self.profile
        if (image.shape != (*p.frame_shape, 3) or image.dtype != np.uint8
                or hashlib.sha256(image.tobytes()).hexdigest() != source.pixel_sha256
                or source.video_sha256 != p.source_sha256
                or source.profile_fingerprint != p.fingerprint()
                or source.code_fingerprint != self.code_fingerprint):
            return ()
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        hsv_image = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        marker_feature = (((hsv_image[:, :, 0] >= 18) & (hsv_image[:, :, 0] <= 40)
                           & (hsv_image[:, :, 1] >= 60)
                           & (hsv_image[:, :, 2] >= 150)).astype(np.uint8) * 255)
        markers = _matches(marker_feature, p.marker_reference, p.marker_masks, p.search_roi)
        mirrored = _matches(marker_feature, np.fliplr(p.marker_reference).copy(),
                            tuple(np.fliplr(m).copy() for m in p.marker_masks), p.search_roi)
        all_markers = [(box, scores, False) for box, scores in markers]
        for box, scores in mirrored:
            if not any(_iou(box, old) > .5 for old, _, _ in all_markers):
                all_markers.append((box, scores, True))
        result = []
        for box, support, flip in all_markers:
            x1, y1, x2, y2 = box
            hsv = cv2.cvtColor(image[y1:y2, x1:x2], cv2.COLOR_BGR2HSV)
            yellow = ((hsv[:, :, 0] >= 18) & (hsv[:, :, 0] <= 40)
                      & (hsv[:, :, 1] >= 60) & (hsv[:, :, 2] >= 150))
            selected = np.fliplr(p.yellow_mask) if flip else p.yellow_mask
            fraction = float(yellow[selected > 0].mean())
            if fraction < .90:
                continue
            region = (p.search_roi[0], max(p.search_roi[1], y1-4),
                      p.search_roi[2], min(p.search_roi[3], y2+4))
            weapons: list[tuple[Box, tuple[float, ...]]] = []
            for reference in (p.weapon_reference, *p.additional_weapon_references):
                weapons.extend(_matches(gray, reference, (np.full_like(reference, 255),), region))
            # Multiple references for the same physical separator are one
            # witness, never independent corroboration or increased confidence.
            unique: list[tuple[Box, tuple[float, ...]]] = []
            for candidate in sorted(weapons, key=lambda item: -min(item[1])):
                if not any(_iou(candidate[0], old[0]) > .5 for old in unique):
                    unique.append(candidate)
            weapons = unique
            valid = [(b, s) for b, s in weapons if b[2] <= x1-4 or b[0] >= x2+4]
            if len(valid) != 1:
                result.append(KillfeedSubjectReading(source, 'unknown', box, None, None,
                              support, fraction, None, None, 'weapon_separator_unavailable'))
                continue
            weapon, weapon_scores = valid[0]
            role: Literal['killer', 'victim', 'unknown'] = (
                'victim' if weapon[2] < x1 else 'killer')
            left, right = (weapon[2]+4, x1-1) if role == 'victim' else (x2+1, weapon[0]-4)
            # Headshot glyphs are role evidence, not a part of the player's name.
            if role == 'victim' and right-left >= p.headshot_reference.shape[1]:
                heads = _matches(gray, p.headshot_reference,
                                 (np.full_like(p.headshot_reference, 255),),
                                 (left, region[1], right, region[3]))
                if len(heads) == 1:
                    left = heads[0][0][2]+4
            name_box = (left, y1+p.name_y_offsets[0], right, y1+p.name_y_offsets[1])
            text, confidence = None, None
            if left < right:
                name_crop = image[name_box[1]:name_box[3], left:right]
                reading = self.reader.read(image, name_crop)
                hsv_name = cv2.cvtColor(name_crop, cv2.COLOR_BGR2HSV)
                ink = (hsv_name[:, :, 1] < 50) & (hsv_name[:, :, 2] > 200)
                clipped = bool(np.any(ink[:, :2]) or np.any(ink[:, -2:]))
                if (isinstance(reading.value, str) and reading.value.strip()
                        and not clipped
                        and type(reading.confidence) in (float, int)
                        and math.isfinite(reading.confidence) and .90 <= reading.confidence <= 1):
                    text = reading.value
                    confidence = float(reading.confidence)
            result.append(KillfeedSubjectReading(
                source, role, box, weapon, name_box if left < right else None,
                support, fraction, text, confidence, 'unqualified_source_player_role_candidate',
                min(weapon_scores)))
        return tuple(result)
