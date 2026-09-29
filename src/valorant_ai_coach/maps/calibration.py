"""Conservative alignment of a static minimap reference to a video frame."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from math import atan2, degrees, hypot, isfinite, sqrt
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import cv2
import numpy as np
from numpy.typing import NDArray

from valorant_ai_coach.video.geometry import normalized_roi_bounds

if TYPE_CHECKING:
    from valorant_ai_coach.maps.registry import MapDefinition


FloatArray = NDArray[np.float32]
ImageArray = NDArray[np.uint8]


@dataclass(frozen=True, slots=True)
class CalibrationResult:
    """Result of an attempted map-mask alignment.

    ``bbox_norm`` is XYXY relative to the supplied minimap ROI. ``transform``
    returns coordinates normalized to the detected static map-mask canvas.
    """

    status: str
    confidence: float
    bbox_norm: tuple[float, float, float, float] | None
    geometry_version: str
    diagnostics: tuple[str, ...]
    _matrix: tuple[float, float, float, float, float, float] | None = field(
        default=None, repr=False, compare=False
    )
    _roi_size: tuple[int, int] | None = field(default=None, repr=False, compare=False)
    _mask_bbox: tuple[float, float, float, float] | None = field(
        default=None, repr=False, compare=False
    )

    def transform(self, x_roi_norm: float, y_roi_norm: float) -> tuple[float, float] | None:
        """Map ROI-normalized XY into this result's normalized map-mask canvas."""

        if (
            self.status != "ok"
            or self._matrix is None
            or self._roi_size is None
            or self._mask_bbox is None
            or not isfinite(x_roi_norm)
            or not isfinite(y_roi_norm)
            or not 0.0 <= x_roi_norm <= 1.0
            or not 0.0 <= y_roi_norm <= 1.0
        ):
            return None
        roi_w, roi_h = self._roi_size
        m00, m01, m02, m10, m11, m12 = self._matrix
        dx = x_roi_norm * roi_w - m02
        dy = y_roi_norm * roi_h - m12
        determinant = m00 * m00 + m10 * m10
        if determinant <= 1e-8:
            return None
        ref_x = (m00 * dx + m10 * dy) / determinant
        ref_y = (-m10 * dx + m00 * dy) / determinant
        x0, y0, x1, y1 = self._mask_bbox
        map_x = (ref_x - x0) / (x1 - x0)
        map_y = (ref_y - y0) / (y1 - y0)
        if not (-1e-4 <= map_x <= 1.0001 and -1e-4 <= map_y <= 1.0001):
            return None
        return min(1.0, max(0.0, map_x)), min(1.0, max(0.0, map_y))


class MinimapCalibrator:
    """Recover a fixed-orientation, full static map mask from a reference.

    The reference asset is treated as a source of visual evidence only. An
    affine similarity alignment must be supported by spatially distributed
    feature matches and the entire authored map-mask box must remain visible.
    """

    _ROTATION_LIMIT_DEGREES = 1.5
    _MIN_GOOD_MATCHES = 14
    _MIN_INLIERS = 11
    _MIN_INLIER_RATIO = 0.42
    _MIN_MAP_COVERAGE_X = 0.34
    _MIN_MAP_COVERAGE_Y = 0.42
    _MIN_QUADRANTS = 3
    _MAX_REPROJECTION_RMS = 2.5
    _MIN_SCALE = 0.35
    _MAX_SCALE = 2.8

    def __init__(self) -> None:
        opencv_module = cast(Any, cv2)
        sift_create = opencv_module.SIFT_create
        self._detector: Any = sift_create(nfeatures=2400, contrastThreshold=0.018)
        self._matcher = cv2.BFMatcher(cv2.NORM_L2, crossCheck=False)
        self._reference_cache_key: tuple[str, int, int, tuple[float, ...]] | None = None
        self._reference_gray: NDArray[np.uint8] | None = None
        self._reference_keypoints: list[cv2.KeyPoint] = []
        self._reference_descriptors: NDArray[np.float32] | None = None
        self._last_matrix: FloatArray | None = None
        self._last_roi_size: tuple[int, int] | None = None
        self._last_mask_bbox: tuple[float, float, float, float] | None = None
        self._last_geometry_version = ""

    def analyze(
        self,
        frame: ImageArray,
        minimap_roi_norm: list[float] | tuple[float, float, float, float],
        definition: MapDefinition,
        *,
        profile: dict[str, Any] | None = None,
    ) -> CalibrationResult:
        """Align ``definition``'s reference asset inside a normalized XYXY ROI."""

        self._clear_alignment()
        data = self._definition_data(definition)
        geometry_version = self._geometry_version(definition, data)
        profile = profile or {}
        failure = self._profile_failure(profile, geometry_version)
        if failure is not None:
            return self._result("calibration_required", 0.0, None, geometry_version, [failure])
        if not geometry_version:
            return self._result("calibration_required", 0.0, None, "", ["unknown_geometry_version"])

        mask_bbox = self._mask_bbox(data)
        if mask_bbox is None:
            return self._result(
                "calibration_required", 0.0, None, geometry_version, ["invalid_reference_mask_bbox"]
            )

        frame_gray = self._as_gray(frame)
        if frame_gray is None:
            return self._result(
                "calibration_required", 0.0, None, geometry_version, ["unsupported_frame"]
            )
        roi_bounds = self._pixel_roi(minimap_roi_norm, frame_gray.shape[1], frame_gray.shape[0])
        if roi_bounds is None:
            return self._result(
                "calibration_required", 0.0, None, geometry_version, ["invalid_minimap_roi"]
            )
        left, top, right, bottom = roi_bounds
        roi_gray = frame_gray[top:bottom, left:right]
        roi_h, roi_w = roi_gray.shape[:2]
        if roi_w < 32 or roi_h < 32:
            return self._result(
                "calibration_required", 0.0, None, geometry_version, ["minimap_roi_too_small"]
            )

        asset = self._reference_path(definition)
        if asset is None or not asset.is_file():
            return self._result(
                "calibration_required", 0.0, None, geometry_version, ["reference_asset_unavailable"]
            )
        loaded = self._load_reference(asset, mask_bbox)
        if loaded is None:
            return self._result(
                "calibration_required", 0.0, None, geometry_version, ["reference_asset_invalid"]
            )
        reference_gray, reference_keypoints, reference_descriptors = loaded
        if reference_descriptors is None or len(reference_keypoints) < self._MIN_GOOD_MATCHES:
            return self._result(
                "calibration_required",
                0.0,
                None,
                geometry_version,
                ["reference_features_unavailable"],
            )

        roi_keypoints, roi_descriptors = self._detector.detectAndCompute(roi_gray, None)
        if roi_descriptors is None or len(roi_keypoints) < self._MIN_GOOD_MATCHES:
            return self._result(
                "calibration_required",
                0.0,
                None,
                geometry_version,
                ["runtime_features_unavailable"],
            )

        try:
            pairs = self._matcher.knnMatch(reference_descriptors, roi_descriptors, k=2)
        except cv2.error:
            return self._result(
                "calibration_required", 0.0, None, geometry_version, ["feature_matching_failed"]
            )
        good = [
            pair[0]
            for pair in pairs
            if len(pair) == 2 and pair[0].distance < 0.72 * pair[1].distance
        ]
        # A descriptor appearing more than once in the target inflates support
        # and makes repetitive corridors look more certain than they are.
        unique_good: list[cv2.DMatch] = []
        seen_targets: set[int] = set()
        for match in sorted(good, key=lambda item: item.distance):
            if match.trainIdx not in seen_targets:
                seen_targets.add(match.trainIdx)
                unique_good.append(match)
        if len(unique_good) < self._MIN_GOOD_MATCHES:
            return self._result(
                "calibration_required",
                0.0,
                None,
                geometry_version,
                ["insufficient_feature_matches"],
            )

        source_points = np.asarray(
            [reference_keypoints[match.queryIdx].pt for match in unique_good], dtype=np.float32
        )
        target_points = np.asarray(
            [roi_keypoints[match.trainIdx].pt for match in unique_good], dtype=np.float32
        )
        matrix_raw, inlier_mask_raw = cv2.estimateAffinePartial2D(
            source_points,
            target_points,
            method=cv2.RANSAC,
            ransacReprojThreshold=2.8,
            maxIters=4000,
            confidence=0.995,
            refineIters=25,
        )
        if matrix_raw is None or inlier_mask_raw is None:
            return self._result(
                "calibration_required", 0.0, None, geometry_version, ["map_alignment_not_recovered"]
            )
        matrix = cast(NDArray[np.float64], np.asarray(matrix_raw, dtype=np.float64))
        inlier_mask = np.asarray(inlier_mask_raw)
        inliers = inlier_mask.reshape(-1).astype(bool)
        inlier_count = int(inliers.sum())
        inlier_ratio = inlier_count / len(unique_good)
        if inlier_count < self._MIN_INLIERS or inlier_ratio < self._MIN_INLIER_RATIO:
            return self._result(
                "calibration_required", 0.0, None, geometry_version, ["weak_feature_consensus"]
            )

        reference_points = source_points[inliers]
        observed_points = target_points[inliers]
        x0, y0, x1, y1 = mask_bbox
        coverage_x = self._span(reference_points[:, 0], x0, x1)
        coverage_y = self._span(reference_points[:, 1], y0, y1)
        quadrants = self._occupied_quadrants(reference_points, mask_bbox)
        if (
            coverage_x < self._MIN_MAP_COVERAGE_X
            or coverage_y < self._MIN_MAP_COVERAGE_Y
            or quadrants < self._MIN_QUADRANTS
        ):
            return self._result(
                "calibration_required", 0.0, None, geometry_version, ["full_map_evidence_missing"]
            )

        a, b = float(matrix[0, 0]), float(matrix[1, 0])
        scale = hypot(a, b)
        rotation = degrees(atan2(b, a))
        if scale < self._MIN_SCALE or scale > self._MAX_SCALE:
            return self._result(
                "calibration_required", 0.0, None, geometry_version, ["unsupported_map_scale"]
            )
        if abs(rotation) > self._ROTATION_LIMIT_DEGREES:
            return self._result(
                "calibration_required",
                0.0,
                None,
                geometry_version,
                ["dynamic_rotation_unsupported"],
            )

        projected = self._map_bbox_in_roi(matrix, mask_bbox)
        if (
            projected[0] < -2.0
            or projected[1] < -2.0
            or projected[2] > roi_w + 2.0
            or projected[3] > roi_h + 2.0
        ):
            return self._result(
                "calibration_required",
                0.0,
                None,
                geometry_version,
                ["full_static_map_mask_not_visible"],
            )

        predicted = cv2.transform(reference_points.reshape(1, -1, 2), matrix).reshape(-1, 2)
        errors = np.linalg.norm(predicted - observed_points, axis=1)
        reprojection_rms = float(sqrt(float(np.mean(np.square(errors)))))
        if not isfinite(reprojection_rms) or reprojection_rms > self._MAX_REPROJECTION_RMS:
            return self._result(
                "calibration_required",
                0.0,
                None,
                geometry_version,
                ["alignment_residual_too_large"],
            )

        # Reject aspect/skew changes explicitly. estimateAffine2D is only used
        # as a diagnostic model; the accepted transform remains a similarity.
        affine, affine_inliers = cv2.estimateAffine2D(
            reference_points,
            observed_points,
            method=cv2.RANSAC,
            ransacReprojThreshold=2.8,
            maxIters=3000,
            confidence=0.995,
            refineIters=20,
        )
        if affine is not None and affine_inliers is not None:
            singular_values = np.linalg.svd(affine[:, :2], compute_uv=False)
            if singular_values[-1] <= 0 or singular_values[0] / singular_values[-1] > 1.025:
                return self._result(
                    "calibration_required", 0.0, None, geometry_version, ["nonuniform_map_scale"]
                )

        bbox_norm = (
            projected[0] / roi_w,
            projected[1] / roi_h,
            projected[2] / roi_w,
            projected[3] / roi_h,
        )
        geometry_cap = self._geometry_confidence_cap(data)
        coverage_score = min(1.0, coverage_x / 0.70, coverage_y / 0.75)
        match_score = min(1.0, inlier_count / 45.0)
        residual_score = max(0.0, 1.0 - reprojection_rms / (self._MAX_REPROJECTION_RMS * 1.4))
        confidence = min(geometry_cap, inlier_ratio * coverage_score * match_score * residual_score)
        if confidence < 0.55:
            return self._result(
                "calibration_required",
                0.0,
                None,
                geometry_version,
                ["alignment_confidence_below_threshold"],
            )

        diagnostics = [
            f"aligned_inliers:{inlier_count}",
            f"map_coverage:{coverage_x:.2f}x{coverage_y:.2f}",
        ]
        observed_builds = data.get("observed_client_builds", [])
        client_build = profile.get("client_build")
        if (
            not isinstance(client_build, str)
            or not client_build
            or isinstance(observed_builds, list)
            and client_build not in observed_builds
        ):
            diagnostics.append("client_build_unverified")

        self._last_matrix = np.asarray(matrix, dtype=np.float32)
        self._last_roi_size = (roi_w, roi_h)
        self._last_mask_bbox = mask_bbox
        self._last_geometry_version = geometry_version
        return self._result(
            "ok",
            confidence,
            bbox_norm,
            geometry_version,
            diagnostics,
            matrix=matrix,
            roi_size=(roi_w, roi_h),
            mask_bbox=mask_bbox,
        )

    def transform(self, x_roi_norm: float, y_roi_norm: float) -> tuple[float, float] | None:
        """Map ROI-normalized XY into normalized static map-mask coordinates."""

        if (
            self._last_matrix is None
            or self._last_roi_size is None
            or self._last_mask_bbox is None
            or not isfinite(x_roi_norm)
            or not isfinite(y_roi_norm)
            or not 0.0 <= x_roi_norm <= 1.0
            or not 0.0 <= y_roi_norm <= 1.0
        ):
            return None
        roi_w, roi_h = self._last_roi_size
        matrix = self._last_matrix
        dx = x_roi_norm * roi_w - float(matrix[0, 2])
        dy = y_roi_norm * roi_h - float(matrix[1, 2])
        a, b = float(matrix[0, 0]), float(matrix[1, 0])
        determinant = a * a + b * b
        if determinant <= 1e-8:
            return None
        ref_x = (a * dx + b * dy) / determinant
        ref_y = (-b * dx + a * dy) / determinant
        x0, y0, x1, y1 = self._last_mask_bbox
        map_x = (ref_x - x0) / (x1 - x0)
        map_y = (ref_y - y0) / (y1 - y0)
        if not (-1e-4 <= map_x <= 1.0001 and -1e-4 <= map_y <= 1.0001):
            return None
        return min(1.0, max(0.0, map_x)), min(1.0, max(0.0, map_y))

    def _clear_alignment(self) -> None:
        self._last_matrix = None
        self._last_roi_size = None
        self._last_mask_bbox = None
        self._last_geometry_version = ""

    def _load_reference(
        self, path: Path, mask_bbox: tuple[float, float, float, float]
    ) -> tuple[NDArray[np.uint8], list[cv2.KeyPoint], NDArray[np.float32] | None] | None:
        try:
            stat = path.stat()
        except OSError:
            return None
        cache_key = (str(path.resolve()), stat.st_mtime_ns, stat.st_size, mask_bbox)
        if cache_key != self._reference_cache_key:
            gray_raw = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
            color_raw = cv2.imread(str(path), cv2.IMREAD_COLOR)
            if gray_raw is None or color_raw is None:
                return None
            gray = cast(NDArray[np.uint8], gray_raw)
            color = cast(NDArray[np.uint8], color_raw)
            x0, y0, x1, y1 = mask_bbox
            height, width = gray.shape
            if x0 < 0 or y0 < 0 or x1 > width or y1 > height or x1 <= x0 or y1 <= y0:
                return None
            hsv = cv2.cvtColor(color, cv2.COLOR_BGR2HSV)
            # Keep features on the neutral gray/white map rendering and walls;
            # colored player markers and the surrounding world are not anchors.
            static_pixels = cv2.inRange(hsv, np.array([0, 0, 42]), np.array([179, 62, 248]))
            region = np.zeros_like(gray)
            region[int(y0) : int(y1), int(x0) : int(x1)] = 255
            feature_mask = cv2.bitwise_and(static_pixels, region)
            keypoints, descriptors = self._detector.detectAndCompute(gray, feature_mask)
            if descriptors is None or len(keypoints) < self._MIN_GOOD_MATCHES:
                return None
            self._reference_cache_key = cache_key
            self._reference_gray = gray
            self._reference_keypoints = keypoints
            self._reference_descriptors = descriptors
        if self._reference_gray is None:
            return None
        return self._reference_gray, self._reference_keypoints, self._reference_descriptors

    @staticmethod
    def _as_gray(frame: ImageArray) -> NDArray[np.uint8] | None:
        if not isinstance(frame, np.ndarray) or frame.ndim not in (2, 3):
            return None
        if frame.ndim == 3 and frame.shape[2] not in (3, 4):
            return None
        if frame.size == 0 or frame.dtype != np.uint8:
            return None
        if frame.ndim == 2:
            return frame
        code = cv2.COLOR_BGR2GRAY if frame.shape[2] == 3 else cv2.COLOR_BGRA2GRAY
        return cast(NDArray[np.uint8], cv2.cvtColor(frame, code))

    @staticmethod
    def _pixel_roi(
        roi: list[float] | tuple[float, float, float, float], width: int, height: int
    ) -> tuple[int, int, int, int] | None:
        return normalized_roi_bounds(roi, width, height)

    @staticmethod
    def _definition_data(definition: MapDefinition) -> Mapping[str, Any]:
        data = getattr(definition, "data", None)
        return data if isinstance(data, Mapping) else {}

    @staticmethod
    def _geometry_version(definition: MapDefinition, data: Mapping[str, Any]) -> str:
        value = getattr(definition, "geometry_version", None) or data.get("geometry_version")
        return value if isinstance(value, str) else ""

    @staticmethod
    def _reference_path(definition: MapDefinition) -> Path | None:
        value = getattr(definition, "reference_asset", None)
        return Path(value) if isinstance(value, (str, Path)) else None

    @staticmethod
    def _mask_bbox(data: Mapping[str, Any]) -> tuple[float, float, float, float] | None:
        coordinate_system = data.get("coordinate_system")
        raw = (
            coordinate_system.get("reference_map_mask_bbox_within_roi_px")
            if isinstance(coordinate_system, Mapping)
            else None
        )
        if not isinstance(raw, (list, tuple)) or len(raw) != 4:
            return None
        try:
            bbox = tuple(float(value) for value in raw)
        except (TypeError, ValueError):
            return None
        if not all(isfinite(value) for value in bbox):
            return None
        x0, y0, x1, y1 = bbox
        if x0 < 0 or y0 < 0 or x1 <= x0 or y1 <= y0:
            return None
        return x0, y0, x1, y1

    @staticmethod
    def _profile_failure(profile: Mapping[str, Any], geometry_version: str) -> str | None:
        if profile.get("dynamic_rotation") is True:
            return "dynamic_rotation_unsupported"
        if profile.get("player_centered") is True:
            return "player_centered_crop_unsupported"
        if profile.get("known_geometry_change") is True:
            return "known_geometry_change_requires_reauthoring"
        profiled_version = profile.get("geometry_version")
        if (
            isinstance(profiled_version, str)
            and profiled_version
            and profiled_version != geometry_version
        ):
            return "geometry_version_mismatch"
        return None

    @staticmethod
    def _geometry_confidence_cap(data: Mapping[str, Any]) -> float:
        value = data.get("geometry_confidence_cap", 0.9)
        try:
            cap = float(value)
        except (TypeError, ValueError):
            return 0.85
        if not isfinite(cap):
            return 0.85
        return min(0.9, max(0.0, cap))

    @staticmethod
    def _span(values: NDArray[np.float32], lower: float, upper: float) -> float:
        if upper <= lower or values.size == 0:
            return 0.0
        return float((float(values.max()) - float(values.min())) / (upper - lower))

    @staticmethod
    def _occupied_quadrants(
        points: NDArray[np.float32], bbox: tuple[float, float, float, float]
    ) -> int:
        x0, y0, x1, y1 = bbox
        midpoint_x, midpoint_y = (x0 + x1) / 2, (y0 + y1) / 2
        occupied = set()
        for x, y in points:
            occupied.add((int(x >= midpoint_x), int(y >= midpoint_y)))
        return len(occupied)

    @staticmethod
    def _map_bbox_in_roi(
        matrix: NDArray[np.float64], bbox: tuple[float, float, float, float]
    ) -> tuple[float, float, float, float]:
        x0, y0, x1, y1 = bbox
        corners = np.asarray([[[x0, y0], [x1, y0], [x1, y1], [x0, y1]]], dtype=np.float32)
        points = np.asarray(cv2.transform(corners, matrix)).reshape(-1, 2)
        return (
            float(points[:, 0].min()),
            float(points[:, 1].min()),
            float(points[:, 0].max()),
            float(points[:, 1].max()),
        )

    @staticmethod
    def _result(
        status: str,
        confidence: float,
        bbox_norm: tuple[float, float, float, float] | None,
        geometry_version: str,
        diagnostics: list[str],
        *,
        matrix: NDArray[np.float64] | None = None,
        roi_size: tuple[int, int] | None = None,
        mask_bbox: tuple[float, float, float, float] | None = None,
    ) -> CalibrationResult:
        packed_matrix = (
            (
                float(matrix[0, 0]),
                float(matrix[0, 1]),
                float(matrix[0, 2]),
                float(matrix[1, 0]),
                float(matrix[1, 1]),
                float(matrix[1, 2]),
            )
            if matrix is not None
            else None
        )
        return CalibrationResult(
            status=status,
            confidence=float(confidence),
            bbox_norm=bbox_norm,
            geometry_version=geometry_version,
            diagnostics=tuple(diagnostics),
            _matrix=packed_matrix,
            _roi_size=roi_size,
            _mask_bbox=mask_bbox,
        )
