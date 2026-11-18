"""Source-bound Map identity and current-frame contrast-assisted registration."""

from __future__ import annotations

from fractions import Fraction
from typing import Any

import cv2
import numpy as np
from numpy.typing import NDArray

from .evidence import native_time, source_scope
from .public_map_pixels import PublicMapPixels


class RecordingMapAlignment:
    def __init__(self, reader: PublicMapPixels) -> None:
        self.reader = reader
        self.source = ""
        self.map_uuid: str | None = None
        self._votes: list[tuple[str, Fraction, str]] = []
        self._last: tuple[tuple[str, ...], Fraction, NDArray[np.float64]] | None = None

    def inspect(
        self, image: NDArray[np.uint8], sample: dict[str, Any], raw: dict[str, Any],
    ) -> dict[str, Any]:
        source = sample["source_sha256"]
        tick = native_time(sample)
        scope = source_scope(sample)
        if source != self.source:
            self.source = source
            self.map_uuid = None
            self._votes.clear()
            self._last = None
        hits = raw["map_name_candidates"]
        if hits:
            hit = hits[0]
            uid = hit["map_id"]
            if self.map_uuid is not None and uid != self.map_uuid:
                self._last = None
                return {**raw, "map_name_candidates": [], "alignment_recovery": "map_uuid_conflict"}
            if self.map_uuid is None:
                if self._votes and self._votes[-1][0] != uid:
                    self._votes.clear()
                pixels = sample["native_pixel_sha256"]
                if (not self._votes or tick - self._votes[-1][1] >= 2) and all(
                    entry[2] != pixels for entry in self._votes
                ):
                    self._votes.append((uid, tick, pixels))
                if len(self._votes) == 3:
                    self.map_uuid = uid
            self._last = scope, tick, np.asarray(hit["reference_to_roi_homography_candidate"])
            return raw
        ranks = raw["reference_ranking"]
        if not self.map_uuid or not ranks or ranks[0]["map_id"] != self.map_uuid:
            return raw
        weak = ranks[0]
        if weak["inliers"] < 10:
            return raw
        left, top, right, bottom = raw["roi_pixel_bounds"]
        enhanced = image.copy()
        crop = image[top:bottom, left:right]
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        enhanced[top:bottom, left:right] = cv2.cvtColor(
            cv2.createCLAHE(2., (6, 6)).apply(gray), cv2.COLOR_GRAY2BGR,
        )
        second = self.reader.inspect(enhanced)["raw"]["map_name_candidates"]
        if len(second) != 1 or second[0]["map_id"] != self.map_uuid:
            return raw
        candidate = second[0]
        matrix = np.asarray(candidate["reference_to_roi_homography_candidate"])
        probes = np.array([[x*(right-left), y*(bottom-top), 1.]
                           for x in (.25, .75) for y in (.25, .75)]).T
        original = np.linalg.solve(weak["reference_to_roi_homography_candidate"], probes)
        refined = np.linalg.solve(matrix, probes)
        if np.linalg.norm(original[:2] - refined[:2], axis=0).max() > 10:
            return raw
        if self._last is not None:
            prior_scope, prior_time, previous = self._last
            if prior_scope == scope and 0 < tick-prior_time <= Fraction(1, 4):
                a, bcol = previous[:2, 0], matrix[:2, 0]
                ratio = np.linalg.norm(bcol) / np.linalg.norm(a)
                cosine = np.dot(a, bcol) / (np.linalg.norm(a)*np.linalg.norm(bcol))
                if not .92 <= ratio <= 1.08 or cosine < .985:
                    return raw
        return {**raw, "map_name_candidates": [candidate],
                "alignment_recovery": "recording_uuid_contrast_agreement"}
