"""Development portrait evidence from previously confirmed native frames."""

from dataclasses import dataclass
from typing import Any

import cv2
import numpy as np

from valorant_ai_coach.temporal.evidence import native_time, source_scope
from valorant_ai_coach.temporal.map_direct_recorder import (
    DirectPeak,
    DirectRecorderTracker,
    _rim_evidence,
)


@dataclass(frozen=True)
class RecordingPeak(DirectPeak):
    anchor_refs: tuple[str, str]


class RecordingPortraitBank:
    """Find measured new centers supported by two earlier distinct portrait crops."""

    def __init__(self):
        self.scope = None
        self.tick = None
        self.entries: list[tuple[Any, str, np.ndarray]] = []

    def visit(self, sample, bounds):
        scope = (*source_scope(sample), tuple(bounds))
        tick = native_time(sample)
        if scope != self.scope or (self.tick is not None and tick < self.tick):
            self.entries.clear()
        self.scope, self.tick = scope, tick

    def remember(self, image, sample, center):
        if self.tick != native_time(sample):
            raise ValueError("Current exact observation required")
        if self.entries and self.tick - self.entries[-1][0] < 3:
            return
        scale = image.shape[1] / 1920
        half = max(4, round(4 * scale))
        x, y = map(round, center)
        crop = image[y - half:y + half + 1, x - half:x + half + 1]
        if crop.shape[:2] != (2 * half + 1, 2 * half + 1):
            return
        chip = cv2.cvtColor(cv2.resize(crop, (9, 9)), cv2.COLOR_BGR2GRAY)
        if chip.std() < 12 or any(np.array_equal(chip, old[2]) for old in self.entries):
            return
        self.entries.append((self.tick, sample["sample_sha256"], chip))
        if len(self.entries) > 9:
            del self.entries[3]

    def peaks(self, roi, uuid, *, scale, count=14):
        height, width = roi.shape[:2]
        if not 0.8 <= scale <= 1.2 or min(height, width) < 32:
            return []
        sources = [(ref, patch) for tick, ref, patch in self.entries if tick < self.tick]
        if len(sources) < 2:
            return []
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        small = gray if scale == 1 else cv2.resize(
            gray, None, fx=1 / scale, fy=1 / scale, interpolation=cv2.INTER_AREA,
        )
        chip_scores = np.stack([
            cv2.matchTemplate(small, patch, cv2.TM_CCOEFF_NORMED) for _, patch in sources
        ])
        np.nan_to_num(chip_scores, copy=False, nan=-1., posinf=-1., neginf=-1.)
        decision = np.partition(chip_scores, -2, axis=0)[-2]
        candidates = np.argwhere(
            (decision == cv2.dilate(decision, np.ones((7, 7), np.uint8))) & (decision >= .85)
        )
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        result = []
        for y, x in sorted(candidates, key=lambda p: (-decision[*p], *p))[:count]:
            center = (round(scale * (int(x) + 4)), round(scale * (int(y) + 4)))
            if not (12 * scale < center[0] < width - 12 * scale
                    and 12 * scale < center[1] < height - 12 * scale):
                continue
            warm, pairs, rivals = _rim_evidence(hsv, *center, scale)
            if warm < 6 or pairs < 2 or rivals > 4:
                continue
            refs = np.argsort(-chip_scores[:, y, x], kind="stable")[:2]
            result.append(RecordingPeak(
                center, float(decision[y, x]), warm, pairs, rivals,
                (sources[refs[0]][0], sources[refs[1]][0]),
            ))
        return result


class RecordingPortraitTracker(DirectRecorderTracker):
    """Confirm recording-specific detections against the reference Agent bank."""

    def _confirmed_peaks(self, image, peaks, left, top):
        self._anchor_refs = {}
        eligible = []
        target = self.portrait_reader._uuids.index(self.identity.uuid)
        for index, peak in enumerate(peaks):
            if not isinstance(peak, RecordingPeak):
                continue
            center = (peak.center[0] + left, peak.center[1] + top)
            scores = self.portrait_reader._portrait_scores(image, center)
            if scores is None:
                continue
            own = float(scores[target])
            margin = own - float(np.delete(scores, target).max())
            if own >= .68 and margin >= .012:
                eligible.append((index, peak.response, margin))
                self._anchor_refs[index] = peak.anchor_refs
        return eligible

    def _observe_measured(self, image, roi, sample, frame, camera):
        self.search.visit(sample, roi)
        pool, result = super()._observe_measured(image, roi, sample, frame, camera)
        if result["support_count"] > 0:
            result["portrait_identity_evidence"] = "recording_portrait_reference_agreement"
            result["portrait_anchor_sample_refs"] = list(
                self._anchor_refs[result["support_candidate_index"]]
            )
        return pool, result
