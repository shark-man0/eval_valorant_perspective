"""Unqualified, source-scoped scoreboard marker/name probe; no ownership grant."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from valorant_ai_coach.hud.readers import HudReader
from valorant_ai_coach.hud.weapon_identity import masked_score

from .subject_death import (
    SourceBinding,
    SubjectObservation,
    SubjectRelation,
    SubjectRole,
    _hash,
    probe_fingerprint,
)


def scoreboard_probe_fingerprint(runtime_fingerprint: str) -> str:
    digest = hashlib.sha256(Path(__file__).read_bytes().replace(b'\r\n', b'\n'))
    digest.update(probe_fingerprint(runtime_fingerprint=runtime_fingerprint).encode('ascii'))
    return digest.hexdigest()


@dataclass(frozen=True)
class ScoreboardProfile:
    source_sha256: str
    owner_review_sha256: str
    frame_shape: tuple[int, int]
    search: tuple[int, int, int]  # left, first top, exclusive last bottom
    reference: Any  # private grayscale structural raster
    masks: tuple[Any, Any, Any]
    name_roi: tuple[int, int, int, int]  # relative to matched row

    def __post_init__(self) -> None:
        _hash(self.source_sha256)
        _hash(self.owner_review_sha256)
        h, w = self.reference.shape
        left, top, bottom = self.search
        x1, y1, x2, y2 = self.name_roi
        coords = (*self.frame_shape, *self.search, *self.name_roi)
        if (any(type(v) is not int for v in coords)
                or not (left >= 0 and top >= 0 and top+h <= bottom <= self.frame_shape[0])
                or left+w > self.frame_shape[1] or not (0 <= x1 < x2 <= w and 0 <= y1 < y2 <= h)
                or self.reference.dtype != np.uint8 or len(self.masks) != 3):
            raise ValueError('invalid source geometry or structural assets')
        occupied = np.zeros((h, w), dtype=bool)
        for mask in self.masks:
            if (mask.shape != (h, w) or np.count_nonzero(mask) < 32
                    or np.any(occupied & (mask > 0)) or np.any(mask[y1:y2, x1:x2])):
                raise ValueError('independent structure masks must exclude name pixels')
            if float(self.reference[mask > 0].std()) < 5:
                raise ValueError('insufficient structural contrast')
            occupied |= mask > 0
            mask.setflags(write=False)
        self.reference.setflags(write=False)

    def fingerprint(self) -> str:
        data = {'source_sha256': self.source_sha256, 'review': self.owner_review_sha256,
                'frame_shape': self.frame_shape, 'search': self.search, 'name_roi': self.name_roi}
        digest = hashlib.sha256(json.dumps(data, sort_keys=True).encode('utf-8'))
        for array in (self.reference, *self.masks):
            digest.update(array.tobytes())
        return digest.hexdigest()


@dataclass(frozen=True)
class ScoreboardCandidate:
    reason: str
    support_scores: tuple[float, ...]
    row_top: int | None = None
    observation: SubjectObservation | None = None


class ScoreboardSubjectProbe:
    """Match three value-invariant border supports before reading the row name.

    Even a successful result keeps relation UNKNOWN and review CANDIDATE. The
    source owner's marker-semantics review is not detector qualification.
    """

    def __init__(self, profile: ScoreboardProfile, reader: HudReader[str],
                 *, runtime_fingerprint: str) -> None:
        self.profile = profile
        self.reader = reader
        self.code_fingerprint = scoreboard_probe_fingerprint(runtime_fingerprint)

    def read(self, image: Any, source: SourceBinding) -> ScoreboardCandidate:
        profile = self.profile
        if (image.shape[:2] != profile.frame_shape
                or hashlib.sha256(image.tobytes()).hexdigest() != source.pixel_sha256
                or source.video_sha256 != profile.source_sha256
                or source.profile_fingerprint != profile.fingerprint()
                or source.code_fingerprint != self.code_fingerprint):
            return ScoreboardCandidate('source_or_profile_mismatch', ())
        left, top, bottom = profile.search
        h, w = profile.reference.shape
        matches = []
        best: tuple[float, ...] = (0.0, 0.0, 0.0)
        for y in range(top, bottom-h+1):
            crop = image[y:y+h, left:left+w]
            scores = tuple(masked_score(profile.reference, crop, mask) for mask in profile.masks)
            if min(scores) > min(best):
                best = scores
            if min(scores) >= .90:
                matches.append((y, scores))
        if not matches:
            return ScoreboardCandidate('marker_not_matched', best)
        # Adjacent pixel alignments are one row; distinct marked rows are ambiguous.
        if matches[-1][0]-matches[0][0] >= h:
            return ScoreboardCandidate('ambiguous_marked_rows', best)
        y, scores = max(matches, key=lambda item: min(item[1]))
        x1, y1, x2, y2 = profile.name_roi
        reading = self.reader.read(image, image[y+y1:y+y2, left+x1:left+x2])
        if (not isinstance(reading.value, str) or not reading.value.strip()
                or isinstance(reading.confidence, bool)
                or not isinstance(reading.confidence, (int, float))
                or not np.isfinite(reading.confidence)
                or not .90 <= reading.confidence <= 1):
            return ScoreboardCandidate('name_not_accepted', scores, y)
        token = hashlib.sha256(reading.value.encode('utf-8')).hexdigest()
        observed = SubjectObservation(
            f'scoreboard-source-binding-{source.pts_ticks}', source,
            SubjectRole.SOURCE_PLAYER_BINDING, SubjectRelation.UNKNOWN, token,
            min(*scores, reading.confidence), 'scoreboard_border_and_name_candidate',
            (left, y, left+w, y+h),
        )
        return ScoreboardCandidate('unqualified_source_binding_candidate', scores, y, observed)
