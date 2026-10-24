"""Opt-in fixed-orientation outline calibration for development map textures.

SIFT remains the ordinary runtime path. This calibrator compares the whole
registered map canvas, with two-way edge support and spatial distribution,
without using marker positions, predicted zones, or previous transforms.
"""

from __future__ import annotations

import hashlib
from typing import Any

import cv2
import numpy as np
from numpy.typing import NDArray

from .calibration import CalibrationResult, MinimapCalibrator
from .registry import MapDefinition


class OutlineMinimapCalibrator(MinimapCalibrator):
    def __init__(
        self, *, cache_reference: bool = True, expected_reference_sha256: str | None = None,
    ) -> None:
        super().__init__()
        self.cache_reference = cache_reference
        self.expected_reference_sha256 = expected_reference_sha256
        self.clear_reference_cache()

    def clear_reference_cache(self) -> None:
        """Discard immutable preprocessing, never preserve a frame transform."""
        self._clear_alignment()
        self._outline_key: tuple[Any, ...] | None = None
        self._outline_reference: NDArray[Any] | None = None
        self._outline_features: dict[int, tuple[NDArray[Any], float]] = {}
        self._outline_feature_bytes = 0

    def reset_frame_alignment(self) -> None:
        """Forget the frame transform; retain only content-keyed static work.

        Source/epoch changes cannot carry an alignment across observations.
        Reference pixels/features depend only on the existing content, geometry
        and ROI-shape key, which analyze verifies again on every frame.
        """
        self._clear_alignment()

    def analyze(
        self,
        frame: NDArray[Any],
        minimap_roi_norm: list[float] | tuple[float, float, float, float],
        definition: MapDefinition,
        *,
        profile: dict[str, Any] | None = None,
    ) -> CalibrationResult:
        self._clear_alignment()
        data = definition.data
        version = definition.geometry_version
        options = profile or {}

        def failed(reason: str) -> CalibrationResult:
            return self._result("calibration_required", 0, None, version, [reason])

        violation = self._profile_failure(options, version)
        if violation:
            return failed(violation)
        box = self._mask_bbox(data)
        gray = self._as_gray(frame)
        if box is None or gray is None or definition.reference_asset is None:
            return failed("outline_reference_or_frame_invalid")
        bounds = self._pixel_roi(minimap_roi_norm, gray.shape[1], gray.shape[0])
        if bounds is None:
            return failed("invalid_minimap_roi")
        left, top, right, bottom = bounds
        target = gray[top:bottom, left:right]
        # Bound an explicitly enabled development search; no resizing of input
        # coordinates, dynamic rotation, or partial-map recovery is attempted.
        if not min(target.shape) >= 64 or max(target.shape) > 1024:
            return failed("outline_roi_size_unsupported")
        try:
            content = definition.reference_asset.read_bytes()
        except OSError:
            return failed("reference_asset_unavailable")
        digest = hashlib.sha256(content).hexdigest()
        if self.expected_reference_sha256 and digest != self.expected_reference_sha256:
            return failed("reference_asset_hash_mismatch")
        x0, y0, x1, y1 = map(int, box)
        key = (str(definition.reference_asset), digest, version, box, target.shape)
        if not self.cache_reference or key != self._outline_key:
            self.clear_reference_cache()
            reference = cv2.imdecode(np.frombuffer(content, np.uint8), cv2.IMREAD_GRAYSCALE)
            if reference is None:
                return failed("reference_asset_unavailable")
            if not (0 <= x0 < x1 <= reference.shape[1] and 0 <= y0 < y1 <= reference.shape[0]):
                return failed("invalid_reference_mask_bbox")
            self._outline_reference = reference[y0:y1, x0:x1]
            self._outline_key = key
        reference = self._outline_reference
        assert reference is not None
        edges = cv2.Canny(target, 60, 160)
        if np.count_nonzero(edges) < 100:
            return failed("outline_runtime_edges_missing")
        distance = np.minimum(cv2.distanceTransform(255-edges, cv2.DIST_L2, 3), 5)
        maximum = min(2.8, target.shape[1]/reference.shape[1],
                      target.shape[0]/reference.shape[0])
        if maximum < .35:
            return failed("full_static_map_mask_not_visible")
        # <= 92 image correlations per observation, including large ROIs.
        scales = np.linspace(.35, maximum, min(92, int((maximum-.35)/.002)+2))
        best: tuple[float, float, int, int, NDArray[Any]] | None = None
        alternatives: list[tuple[float, float, int, int]] = []
        for index, scale in enumerate(scales):
            w, h = round(reference.shape[1]*scale), round(reference.shape[0]*scale)
            if not (32 <= w <= target.shape[1] and 32 <= h <= target.shape[0]):
                continue
            feature = self._outline_features.get(index)
            if feature is None:
                resized = cv2.resize(reference, (w, h), interpolation=cv2.INTER_AREA)
                weights = (cv2.Canny(resized, 60, 160) > 0).astype(np.float32)
                population = float(weights.sum())
                # Bounded single-key cache; larger grids recompute the suffix.
                if self.cache_reference and self._outline_feature_bytes+weights.nbytes <= 64*2**20:
                    self._outline_features[index] = weights, population
                    self._outline_feature_bytes += weights.nbytes
            else:
                weights, population = feature
            if population < 100:
                continue
            costs = (cv2.matchTemplate(distance, weights, cv2.TM_CCORR)/population).astype(
                np.float32
            )
            cost, _, peak, _ = cv2.minMaxLoc(costs)
            alternatives.append((cost, float(scale), peak[0], peak[1]))
            excluded = costs.copy()
            radius = max(5, round(max(w, h)*.025))
            px, py = peak
            excluded[max(0, py-radius):py+radius+1,
                     max(0, px-radius):px+radius+1] = 5
            second, _, second_peak, _ = cv2.minMaxLoc(excluded)
            alternatives.append((second, float(scale), second_peak[0], second_peak[1]))
            if best is None or cost < best[0]:
                best = cost, float(scale), peak[0], peak[1], weights
        if best is None:
            return failed("outline_search_empty")
        cost, scale, x, y, weights = best
        h, w = weights.shape
        for other_cost, other_scale, ox, oy in alternatives:
            separation = np.hypot(ox-x, oy-y)
            if (separation > max(5, max(w, h)*.025) or abs(other_scale/scale-1) > .03) and (
                other_cost-cost < .15
            ):
                return failed("outline_alignment_ambiguous")
        observed = distance[y:y+h, x:x+w]
        support = observed[weights > 0] <= 1.5
        recall = float(support.mean())
        inverse_distance = cv2.distanceTransform((weights == 0).astype(np.uint8)*255,
                                                 cv2.DIST_L2, 3)
        target_edges = edges[y:y+h, x:x+w] > 0
        precision = float(np.mean(inverse_distance[target_edges] <= 1.5))
        quadrants = []
        for ys in (slice(0, h//2), slice(h//2, h)):
            for xs in (slice(0, w//2), slice(w//2, w)):
                selected = weights[ys, xs] > 0
                if np.count_nonzero(selected) < 20:
                    return failed("outline_spatial_support_missing")
                quadrants.append(float(np.mean(observed[ys, xs][selected] <= 1.5)))
        if cost > .8 or recall < .85 or precision < .45 or min(quadrants) < .75:
            return failed("outline_correspondence_insufficient")
        matrix = np.array([[scale, 0, x-x0*scale], [0, scale, y-y0*scale]], np.float64)
        confidence = min(self._geometry_confidence_cap(data), recall, 1-cost/5)
        diagnostics = ["development_outline_alignment",
                       f"outline_recall:{recall:.4f}", f"outline_precision:{precision:.4f}",
                       f"outline_mean_distance_px:{cost:.4f}",
                       f"outline_quadrant_min:{min(quadrants):.4f}"]
        if options.get("client_build") not in data.get("observed_client_builds", []):
            diagnostics.append("client_build_unverified")
        self._last_matrix = matrix.astype(np.float32)
        self._last_roi_size = target.shape[1], target.shape[0]
        self._last_mask_bbox = box
        self._last_geometry_version = version
        return self._result(
            "ok", confidence, (x/target.shape[1], y/target.shape[0],
                               (x+w)/target.shape[1], (y+h)/target.shape[0]),
            version, diagnostics, matrix=matrix,
            roi_size=(target.shape[1], target.shape[0]), mask_bbox=box,
        )
