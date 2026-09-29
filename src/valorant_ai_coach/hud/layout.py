from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from statistics import median
from typing import Any


@dataclass(frozen=True, slots=True)
class NormalizedRoi:
    """A normalized rectangle stored as x/y/width/height."""

    x: float
    y: float
    width: float
    height: float

    def __post_init__(self) -> None:
        values = (self.x, self.y, self.width, self.height)
        if not all(math.isfinite(value) and 0 <= value <= 1 for value in values):
            raise ValueError("HUD ROIは0〜1の正規化座標で指定してください")
        if self.width <= 0 or self.height <= 0:
            raise ValueError("HUD ROIの幅と高さは0より大きい必要があります")
        if self.x + self.width > 1 or self.y + self.height > 1:
            raise ValueError("HUD ROIが画面範囲を超えています")

    @property
    def right(self) -> float:
        return self.x + self.width

    @property
    def bottom(self) -> float:
        return self.y + self.height

    def pixel_bounds(self, image_width: int, image_height: int) -> tuple[int, int, int, int]:
        if image_width <= 0 or image_height <= 0:
            raise ValueError("画像解像度が不正です")
        left = round(self.x * image_width)
        top = round(self.y * image_height)
        right = round(self.right * image_width)
        bottom = round(self.bottom * image_height)
        return left, top, max(left + 1, right), max(top + 1, bottom)


@dataclass(frozen=True, slots=True)
class CalibrationResult:
    calibrated: bool
    reasons: tuple[str, ...]
    detected_anchor_count: int
    median_position_error_norm: float | None
    median_size_relative_error: float | None

    @property
    def calibration_required(self) -> bool:
        return not self.calibrated


@dataclass(frozen=True, slots=True)
class HudLayout:
    schema_version: str
    calibrated: bool
    reference_resolution: tuple[int, int] | None
    regions: dict[str, NormalizedRoi]
    note: str = ""
    layout_format: str = "legacy"
    profile_id: str | None = None
    calibration_policy: dict[str, Any] | None = None
    coordinate_policy: dict[str, Any] | None = None

    @classmethod
    def load(cls, path: Path) -> HudLayout:
        source = Path(path).expanduser().resolve()
        try:
            raw = json.loads(source.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"HUD layoutを読み込めません: {source}: {exc}") from exc
        if not isinstance(raw, dict):
            raise ValueError("HUD layoutのrootはobjectである必要があります")

        is_v3 = isinstance(raw.get("rois"), dict)
        if is_v3:
            regions_raw = raw["rois"]
            regions = {
                str(name): cls._parse_v3_roi(str(name), value)
                for name, value in regions_raw.items()
            }
            calibrated = True
            layout_format = "v3"
        else:
            if raw.get("roi_coordinate_system") != "normalized_0_to_1":
                raise ValueError("HUD layoutはnormalized_0_to_1座標である必要があります")
            regions_raw = raw.get("regions", {})
            if not isinstance(regions_raw, dict):
                raise ValueError("regionsはobjectである必要があります")
            regions = {}
            for name, value in regions_raw.items():
                if not isinstance(value, dict):
                    raise ValueError(f"HUD ROI {name} がobjectではありません")
                try:
                    regions[str(name)] = NormalizedRoi(
                        x=float(value["x"]),
                        y=float(value["y"]),
                        width=float(value["width"]),
                        height=float(value["height"]),
                    )
                except (KeyError, TypeError, ValueError) as exc:
                    raise ValueError(f"HUD ROI {name} が不正です: {exc}") from exc
            calibrated = bool(raw.get("calibrated", False))
            layout_format = "legacy"

        reference = raw.get("reference_resolution")
        parsed_reference: tuple[int, int] | None = None
        if reference is not None:
            if not isinstance(reference, dict):
                raise ValueError("reference_resolutionが不正です")
            try:
                width, height = int(reference["width"]), int(reference["height"])
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError("reference_resolutionが不正です") from exc
            if width <= 0 or height <= 0:
                raise ValueError("reference_resolutionが不正です")
            parsed_reference = (width, height)
        if calibrated and not regions:
            raise ValueError("calibrated=trueには1件以上のROIが必要です")

        calibration_policy = raw.get("calibration_policy")
        if calibration_policy is not None and not isinstance(calibration_policy, dict):
            raise ValueError("calibration_policyはobjectである必要があります")
        coordinate_policy = raw.get("coordinate_policy")
        if coordinate_policy is not None and not isinstance(coordinate_policy, dict):
            raise ValueError("coordinate_policyはobjectである必要があります")
        return cls(
            schema_version=str(raw.get("schema_version", "1.0")),
            calibrated=calibrated,
            reference_resolution=parsed_reference,
            regions=regions,
            note=str(raw.get("note", "")),
            layout_format=layout_format,
            profile_id=str(raw["profile_id"]) if raw.get("profile_id") else None,
            calibration_policy=dict(calibration_policy or {}),
            coordinate_policy=dict(coordinate_policy or {}),
        )

    @staticmethod
    def _parse_v3_roi(name: str, value: Any) -> NormalizedRoi:
        if not isinstance(value, dict):
            raise ValueError(f"HUD ROI {name} がobjectではありません")
        try:
            left, top, right, bottom = (float(part) for part in value["norm"])
            return NormalizedRoi(left, top, right - left, bottom - top)
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"HUD ROI {name} が不正です: {exc}") from exc

    def normalized_roi(self, name: str) -> NormalizedRoi:
        try:
            return self.regions[name]
        except KeyError as exc:
            raise KeyError(f"HUD layoutにROI {name} がありません") from exc

    def pixel_bounds(
        self,
        name: str,
        image_width: int,
        image_height: int,
        *,
        calibration: CalibrationResult | None = None,
    ) -> tuple[int, int, int, int]:
        if self.layout_format == "v3" and (calibration is None or not calibration.calibrated):
            raise ValueError("ROIを使う前にHUDアンカー校正が必要です")
        return self.normalized_roi(name).pixel_bounds(image_width, image_height)

    def validate_calibration(
        self,
        image_width: int,
        image_height: int,
        *,
        detected_anchors: Mapping[str, NormalizedRoi | Sequence[float]] | None,
        letterboxed: bool | None,
        crop_applied: bool | None,
    ) -> CalibrationResult:
        """Check capture geometry and anchor scale before any v3 ROI is used.

        Anchor boxes use normalized x1/y1/x2/y2 coordinates in the displayed
        frame. Missing geometry metadata is deliberately treated as unknown.
        """

        reasons: list[str] = []
        policy = self.calibration_policy or {}
        tolerance = float(policy.get("position_tolerance_norm", 0.03))
        size_tolerance = float(policy.get("size_relative_tolerance", 0.12))
        min_anchors = int(policy.get("min_detected_anchors", 3))
        required = policy.get(
            "required_anchors", ["round_timer", "top_match_bar", "player_hp_armor", "abilities"]
        )
        if not isinstance(required, list):
            required = ["round_timer", "top_match_bar", "player_hp_armor", "abilities"]

        if image_width <= 0 or image_height <= 0:
            reasons.append("invalid_resolution")
        elif self.reference_resolution:
            if (image_width, image_height) != self.reference_resolution:
                reasons.append("resolution_mismatch")
            reference_aspect = self.reference_resolution[0] / self.reference_resolution[1]
            actual_aspect = image_width / image_height
            if abs(actual_aspect - reference_aspect) > 0.005:
                reasons.append("aspect_ratio_mismatch")
        else:
            reasons.append("reference_resolution_missing")

        if letterboxed is not False:
            reasons.append("letterbox_present" if letterboxed else "letterbox_unknown")
        if crop_applied is not False:
            reasons.append("crop_present" if crop_applied else "crop_unknown")

        positions: list[float] = []
        sizes: list[float] = []
        for name in required:
            detected = (detected_anchors or {}).get(str(name))
            expected = self.regions.get(str(name))
            if detected is None or expected is None:
                continue
            try:
                observed = self._coerce_anchor(detected)
            except (TypeError, ValueError):
                continue
            dx = (observed.x + observed.width / 2) - (expected.x + expected.width / 2)
            dy = (observed.y + observed.height / 2) - (expected.y + expected.height / 2)
            positions.append(math.hypot(dx, dy))
            sizes.append(
                max(
                    abs(observed.width / expected.width - 1),
                    abs(observed.height / expected.height - 1),
                )
            )

        if len(positions) < min_anchors:
            reasons.append("insufficient_anchors")
        inliers = [
            index
            for index, (position, size) in enumerate(zip(positions, sizes, strict=True))
            if position <= tolerance and size <= size_tolerance
        ]
        if len(positions) >= min_anchors and len(inliers) < min_anchors:
            # A median can conceal a bad anchor when fewer than three anchors agree.
            reasons.append("insufficient_anchor_inliers")
        accepted_positions = (
            [positions[index] for index in inliers] if len(inliers) >= min_anchors else positions
        )
        accepted_sizes = (
            [sizes[index] for index in inliers] if len(inliers) >= min_anchors else sizes
        )
        position_error = median(accepted_positions) if accepted_positions else None
        size_error = median(accepted_sizes) if accepted_sizes else None
        if position_error is not None and position_error > tolerance:
            reasons.append("anchor_position_mismatch")
        if size_error is not None and size_error > size_tolerance:
            reasons.append("anchor_scale_mismatch")

        return CalibrationResult(
            calibrated=not reasons,
            reasons=tuple(dict.fromkeys(reasons)),
            detected_anchor_count=len(positions),
            median_position_error_norm=position_error,
            median_size_relative_error=size_error,
        )

    @staticmethod
    def _coerce_anchor(value: NormalizedRoi | Sequence[float]) -> NormalizedRoi:
        if isinstance(value, NormalizedRoi):
            return value
        parts = tuple(float(part) for part in value)
        if len(parts) != 4:
            raise ValueError("anchor bboxにはx1,y1,x2,y2が必要です")
        x1, y1, x2, y2 = parts
        return NormalizedRoi(x1, y1, x2 - x1, y2 - y1)

    def to_dict(self) -> dict[str, Any]:
        reference = None
        if self.reference_resolution is not None:
            reference = {
                "width": self.reference_resolution[0],
                "height": self.reference_resolution[1],
            }
        if self.layout_format == "v3":
            return {
                "schema_version": self.schema_version,
                "profile_id": self.profile_id,
                "reference_resolution": reference,
                "coordinate_policy": dict(self.coordinate_policy or {}),
                "rois": {
                    name: {
                        "norm": [roi.x, roi.y, roi.right, roi.bottom],
                        "px": list(roi.pixel_bounds(*self.reference_resolution))
                        if self.reference_resolution
                        else None,
                    }
                    for name, roi in self.regions.items()
                },
                "calibration_policy": dict(self.calibration_policy or {}),
                "notes": [self.note] if self.note else [],
            }
        return {
            "schema_version": self.schema_version,
            "calibrated": self.calibrated,
            "reference_resolution": reference,
            "roi_coordinate_system": "normalized_0_to_1",
            "regions": {
                name: {"x": roi.x, "y": roi.y, "width": roi.width, "height": roi.height}
                for name, roi in self.regions.items()
            },
            "note": self.note,
        }
