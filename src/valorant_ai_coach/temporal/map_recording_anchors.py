"""Recover current-frame registration from two measured native Map anchors."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from itertools import combinations
from typing import Any, cast

import cv2
import numpy as np
from numpy.typing import NDArray

from .evidence import native_time, source_scope

EVIDENCE = "current_features_agree_with_two_recording_anchors"
_MIN_SPACING = 10


@dataclass(frozen=True)
class _Anchor:
    sample_id: str
    timestamp: Fraction
    pixel_digest: str
    points: list[Any]
    descriptors: NDArray[np.float32]
    reference: dict[str, Any]
    atlas_cell: tuple[int, int] | None = None


@dataclass(frozen=True)
class _Fit:
    anchor: _Anchor
    transform: NDArray[np.float64]
    locations: NDArray[np.float64]
    residual: float


class RecordingMapAnchors:
    """A bounded causal reference bank for one source, acquisition and layout."""

    def __init__(self, *, atlas_diverse: bool = False) -> None:
        self._sift = cast(Any, cv2).SIFT_create(nfeatures=800, contrastThreshold=.012)
        self._matcher = cv2.BFMatcher(cv2.NORM_L2)
        self._scope: tuple[Any, ...] | None = None
        self._latest: Fraction | None = None
        self._anchors: list[_Anchor] = []
        self._atlas_diverse = atlas_diverse

    def _features(self, image: NDArray[np.uint8], bounds: list[int]) -> tuple[Any, Any]:
        left, top, right, bottom = bounds
        crop = cv2.cvtColor(image[top:bottom, left:right], cv2.COLOR_BGR2GRAY)
        points, descriptors = self._sift.detectAndCompute(crop, None)
        return points, descriptors

    def observe(
        self, image: NDArray[np.uint8], sample: dict[str, Any], raw: dict[str, Any],
        map_uuid: str | None, center_frame: tuple[float, float], *, recover: bool = True,
    ) -> dict[str, Any]:
        """Remember strong direct fits and probe only otherwise missing registrations."""
        bounds = raw["roi_pixel_bounds"]
        scope = (*source_scope(sample), map_uuid, tuple(bounds))
        tick = native_time(sample)
        if scope != self._scope or (self._latest is not None and tick <= self._latest):
            self._anchors.clear()
        self._scope, self._latest = scope, tick
        if map_uuid is None:
            return raw
        ranks = raw["reference_ranking"]
        direct = raw["map_name_candidates"]
        if ranks and ranks[0]["map_id"] != map_uuid:
            return raw
        if direct:
            self._remember(image, sample, raw, tick, map_uuid)
            return raw
        if not recover:
            return raw
        eligible = [
            a for a in self._anchors
            if tick - a.timestamp >= _MIN_SPACING
            and a.pixel_digest != sample["native_pixel_sha256"]
        ]
        if len(eligible) < 2:
            return raw
        left, top, right, bottom = bounds
        marker = center_frame[0] - left, center_frame[1] - top
        width, height = right - left, bottom - top
        if not (0 <= marker[0] < width and 0 <= marker[1] < height):
            return raw
        probes = np.asarray(
            [[x * width, y * height, 1.] for x in (.32, .68) for y in (.32, .68)]
            + [[*marker, 1.]],
        ).T
        keypoints, desc = self._features(image, bounds)
        if desc is None or len(desc) < 2:
            return raw
        fits = [
            result for anchor in eligible
            if (result := self._fit(anchor, keypoints, desc, marker, width * height, probes))
            is not None
        ]
        choices = []
        for first, second in combinations(fits, 2):
            delta = self._distance(first.locations, second.locations)
            if delta <= 6:
                choices.append((delta, first, second))
        if not choices:
            return raw
        delta, best, second = min(choices, key=lambda choice: choice[0])
        if any(self._distance(best.locations, option.locations) > 10
               for _, a, b in choices for option in (a, b)):
            return raw
        reference = {
            **best.anchor.reference,
            "reference_to_roi_homography_candidate": best.transform.tolist(),
            "fit_residual_p95_reference_px": max(
                delta, best.residual, second.residual,
                best.anchor.reference["fit_residual_p95_reference_px"],
                second.anchor.reference["fit_residual_p95_reference_px"],
            ),
            "evidence": EVIDENCE,
        }
        return {**raw, "map_name_candidates": [reference], "alignment_recovery": EVIDENCE,
                "registration_anchor_sample_refs": [best.anchor.sample_id, second.anchor.sample_id]}

    @staticmethod
    def _distance(a: NDArray[np.float64], b: NDArray[np.float64]) -> float:
        return float(np.linalg.norm(a - b, axis=0).max())

    def _remember(
        self, image: NDArray[np.uint8], sample: dict[str, Any], raw: dict[str, Any],
        tick: Fraction, map_uuid: str,
    ) -> None:
        (ref, *other) = raw["map_name_candidates"]
        if (other or ref["map_id"] != map_uuid or ref["inliers"] < 25
                or raw.get("alignment_recovery") is not None
                or any(a.pixel_digest == sample["native_pixel_sha256"] for a in self._anchors)
                or (self._anchors and tick - self._anchors[-1].timestamp < _MIN_SPACING)):
            return
        points, descriptors = self._features(image, raw["roi_pixel_bounds"])
        if descriptors is None:
            return
        cell = None
        if self._atlas_diverse:
            left, top, right, bottom = raw["roi_pixel_bounds"]
            matrix = np.asarray(ref["reference_to_roi_homography_candidate"])
            try:
                center = [(right-left)/2, (bottom-top)/2, 1.]
                x, y, _ = np.linalg.solve(matrix, center)
            except np.linalg.LinAlgError:
                return
            if not (np.isfinite([x, y]).all()):
                return
            cell = (int(x//192), int(y//192))
            same = [i for i, a in enumerate(self._anchors) if a.atlas_cell == cell]
            if len(same) >= 2:
                del self._anchors[same[-1]]
        self._anchors.append(_Anchor(
            sample["sample_sha256"], tick, sample["native_pixel_sha256"], points,
            descriptors, ref, cell,
        ))
        if self._atlas_diverse:
            if len(self._anchors) > 24:
                self._anchors.pop(0)
            return
        if len(self._anchors) > 16:
            # Keep the first four separately from the rolling recent anchors.
            del self._anchors[4]

    def _fit(
        self, anchor: _Anchor, keypoints: list[Any], desc: NDArray[np.float32],
        marker: tuple[float, float], area: int, probes: NDArray[np.float64],
    ) -> _Fit | None:
        pairs = self._matcher.knnMatch(anchor.descriptors, desc, k=2)
        matches = [m for m, n in pairs if m.distance < .69 * n.distance]
        unique: dict[int, Any] = {}
        for match in sorted(matches, key=lambda m: (m.distance, m.queryIdx, m.trainIdx)):
            unique.setdefault(match.trainIdx, match)
        if len(unique) < 22:
            return None
        before = np.asarray([anchor.points[m.queryIdx].pt for m in unique.values()], np.float32)
        after = np.asarray([keypoints[m.trainIdx].pt for m in unique.values()], np.float32)
        fit, mask = cv2.estimateAffinePartial2D(
            before, after, method=cv2.RANSAC, ransacReprojThreshold=2.,
        )
        if fit is None or mask is None or not np.isfinite(fit).all():
            return None
        inliers = mask.ravel().astype(bool)
        if inliers.sum() < 18 or inliers.mean() < .6 or not .8 <= np.linalg.norm(fit[:, 0]) <= 1.2:
            return None
        hull = cv2.convexHull(after[inliers])
        if cv2.contourArea(hull) < .14 * area or cv2.pointPolygonTest(hull, marker, True) < -6:
            return None
        transform = np.vstack([fit, [0, 0, 1]]) @ anchor.reference[
            "reference_to_roi_homography_candidate"
        ]
        try:
            coordinates = np.linalg.solve(transform, probes)[:2]
        except np.linalg.LinAlgError:
            return None
        errors = before[inliers] @ fit[:, :2].T + fit[:, 2] - after[inliers]
        scale = np.linalg.norm(transform[:2, 0])
        residual = float(np.percentile(np.linalg.norm(errors, axis=1), 95) / scale)
        return _Fit(anchor, transform, coordinates, residual)
