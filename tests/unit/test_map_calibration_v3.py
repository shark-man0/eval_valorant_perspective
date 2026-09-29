from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from valorant_ai_coach.maps.calibration import MinimapCalibrator

ROOT = Path(__file__).resolve().parents[2]
MAP_CONFIG = ROOT / "config/map_zone_v3/config/maps/summit_map_v3.json"
REFERENCE = ROOT / "config/map_zone_v3/assets/summit_minimap_reference.png"


@pytest.fixture
def definition() -> SimpleNamespace:
    data = json.loads(MAP_CONFIG.read_text(encoding="utf-8"))
    return SimpleNamespace(
        data=data,
        geometry_version=data["geometry_version"],
        reference_asset=REFERENCE,
    )


def _put_in_frame(
    image: np.ndarray,
    *,
    frame_size: tuple[int, int] = (800, 600),
    origin: tuple[int, int] = (70, 55),
) -> tuple[np.ndarray, list[float]]:
    height, width = frame_size[1], frame_size[0]
    x, y = origin
    canvas = np.zeros((height, width, 3), dtype=np.uint8)
    h, w = image.shape[:2]
    canvas[y : y + h, x : x + w] = image
    return canvas, [x / width, y / height, (x + w) / width, (y + h) / height]


def _bbox(data: dict) -> tuple[float, float, float, float]:
    raw = data["coordinate_system"]["reference_map_mask_bbox_within_roi_px"]
    return tuple(float(value) for value in raw)  # type: ignore[return-value]


def test_reference_asset_calibrates_and_transforms_to_map_mask(definition: SimpleNamespace) -> None:
    reference = cv2.imread(str(REFERENCE), cv2.IMREAD_COLOR)
    assert reference is not None
    frame, roi = _put_in_frame(reference)
    calibrator = MinimapCalibrator()

    result = calibrator.analyze(frame, roi, definition)

    assert result.status == "ok"
    assert result.geometry_version == definition.geometry_version
    assert result.confidence == pytest.approx(0.9)
    assert result.bbox_norm is not None
    x0, y0, x1, y1 = _bbox(definition.data)
    ref_h, ref_w = reference.shape[:2]
    # Subpixel RANSAC fits can vary; 0.001 here is less than half a pixel.
    assert result.bbox_norm == pytest.approx(
        (x0 / ref_w, y0 / ref_h, x1 / ref_w, y1 / ref_h), abs=0.001
    )
    point = calibrator.transform((x0 + (x1 - x0) * 0.37) / ref_w, (y0 + (y1 - y0) * 0.62) / ref_h)
    assert point == pytest.approx((0.37, 0.62), abs=0.01)


def test_uniformly_scaled_and_translated_full_map_is_recovered(definition: SimpleNamespace) -> None:
    reference = cv2.imread(str(REFERENCE), cv2.IMREAD_COLOR)
    assert reference is not None
    scale = 0.8
    scaled = cv2.resize(reference, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    pad_x, pad_y = 17, 13
    roi_image = np.zeros((scaled.shape[0] + 24, scaled.shape[1] + 34, 3), dtype=np.uint8)
    roi_image[pad_y : pad_y + scaled.shape[0], pad_x : pad_x + scaled.shape[1]] = scaled
    frame, roi = _put_in_frame(roi_image, frame_size=(720, 560), origin=(103, 61))
    calibrator = MinimapCalibrator()

    result = calibrator.analyze(frame, roi, definition)

    assert result.status == "ok"
    assert result.bbox_norm is not None
    x0, y0, x1, y1 = _bbox(definition.data)
    roi_h, roi_w = roi_image.shape[:2]
    expected_bbox = (
        (pad_x + scale * x0) / roi_w,
        (pad_y + scale * y0) / roi_h,
        (pad_x + scale * x1) / roi_w,
        (pad_y + scale * y1) / roi_h,
    )
    assert result.bbox_norm == pytest.approx(expected_bbox, abs=0.01)
    point = calibrator.transform(
        (pad_x + scale * (x0 + (x1 - x0) * 0.21)) / roi_w,
        (pad_y + scale * (y0 + (y1 - y0) * 0.79)) / roi_h,
    )
    assert point == pytest.approx((0.21, 0.79), abs=0.02)


@pytest.mark.parametrize("failure_kind", ["rotated", "cropped", "noise"])
def test_unsupported_or_unrecoverable_minimap_is_rejected(
    definition: SimpleNamespace, failure_kind: str
) -> None:
    reference = cv2.imread(str(REFERENCE), cv2.IMREAD_COLOR)
    assert reference is not None
    if failure_kind == "rotated":
        height, width = reference.shape[:2]
        matrix = cv2.getRotationMatrix2D((width / 2, height / 2), 8.0, 1.0)
        matrix[0, 2] += 22.5
        matrix[1, 2] += 36.5
        observed = cv2.warpAffine(reference, matrix, (width + 45, height + 73))
    elif failure_kind == "cropped":
        observed = reference[:, 90:]
    else:
        rng = np.random.default_rng(43)
        observed = rng.integers(0, 256, reference.shape, dtype=np.uint8)

    frame, roi = _put_in_frame(observed)
    calibrator = MinimapCalibrator()
    result = calibrator.analyze(frame, roi, definition)

    assert result.status == "calibration_required"
    assert result.bbox_norm is None
    assert calibrator.transform(0.5, 0.5) is None


@pytest.mark.parametrize(
    ("profile", "expected"),
    [
        ({"dynamic_rotation": True}, "dynamic_rotation_unsupported"),
        ({"player_centered": True}, "player_centered_crop_unsupported"),
        ({"known_geometry_change": True}, "known_geometry_change_requires_reauthoring"),
        ({"geometry_version": "older_geometry"}, "geometry_version_mismatch"),
    ],
)
def test_unsupported_profile_or_geometry_version_fails_before_alignment(
    definition: SimpleNamespace, profile: dict[str, object], expected: str
) -> None:
    calibrator = MinimapCalibrator()
    frame = np.zeros((100, 100, 3), dtype=np.uint8)

    result = calibrator.analyze(frame, [0.0, 0.0, 1.0, 1.0], definition, profile=profile)

    assert result.status == "calibration_required"
    assert result.diagnostics == (expected,)
    assert calibrator.transform(0.5, 0.5) is None


def test_unknown_client_build_is_reported_as_unverified(definition: SimpleNamespace) -> None:
    reference = cv2.imread(str(REFERENCE), cv2.IMREAD_COLOR)
    assert reference is not None
    frame, roi = _put_in_frame(reference)

    result = MinimapCalibrator().analyze(
        frame, roi, definition, profile={"client_build": "future-build"}
    )

    assert result.status == "ok"
    assert "client_build_unverified" in result.diagnostics
