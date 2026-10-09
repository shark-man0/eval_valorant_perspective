from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from threading import Event
from typing import Any, Protocol

import cv2
import numpy as np

from .layout import CalibrationResult, HudLayout, NormalizedRoi

FrameInput = np.ndarray | str | Path | Any


@dataclass(frozen=True, slots=True)
class ReaderResult[T]:
    value: T | None
    confidence: float
    sources: tuple[str, ...] = ()
    cross_checked: bool = False


class HudReader[T](Protocol):
    def read(self, image: np.ndarray, roi: np.ndarray) -> ReaderResult[T]: ...


class DigitTemplateReader(HudReader[str], Protocol):
    """Replaceable template matcher for digits-only HUD values."""


class DigitsOcrReader(HudReader[str], Protocol):
    """Optional OCR adapter. The core does not require an OCR package."""


class TextOcrReader(HudReader[str], Protocol):
    """Optional reader for short labels and kill-feed text."""


class IconStateReader(HudReader[str], Protocol):
    """Replaceable template reader for spike, ability, and status icons."""


@dataclass(frozen=True, slots=True)
class RoiMetrics:
    mean_luminance: float
    luminance_std: float
    mean_saturation: float
    edge_density: float
    spatial_entropy: float
    broad_color_uniformity: float
    bright_fraction: float
    dark_fraction: float
    width: int
    height: int


@dataclass(frozen=True, slots=True)
class FrameFeatureObservation:
    time_sec: float | None
    metrics: dict[str, RoiMetrics]
    signals: dict[str, Any]
    roi_confidence: dict[str, float]
    calibration_anchor_presence: dict[str, float]
    kill_feed_row_signature: tuple[tuple[float, float, float, float], ...] = ()


class OpenCvHudFeatureReader:
    """OCR-free, replaceable pixel feature reader driven entirely by HUD layout ROIs.

    These are conservative feature candidates, not semantic claims. A deployment
    can inject template/OCR readers for stronger UI classification.
    """

    ANCHOR_NAMES = ("round_timer", "top_match_bar", "player_hp_armor", "abilities")

    def __init__(self, layout: HudLayout) -> None:
        self.layout = layout

    def observe(
        self,
        frame: FrameInput,
        *,
        time_sec: float | None = None,
        previous: FrameFeatureObservation | None = None,
        following: FrameFeatureObservation | None = None,
    ) -> FrameFeatureObservation:
        image = load_frame(frame)
        height, width = image.shape[:2]
        crops: dict[str, np.ndarray] = {}
        metrics: dict[str, RoiMetrics] = {}
        for name, roi in self.layout.regions.items():
            crop = _crop(image, roi)
            if crop.size:
                crops[name] = crop
                metrics[name] = measure_roi(crop)

        anchors = {name: _anchor_presence(metrics.get(name)) for name in self.ANCHOR_NAMES}
        center = metrics.get("center_crosshair_area")
        buy_menu_grid = _region_candidate(metrics.get("buy_menu_grid"), min_edge=0.055)
        close_x_score = _cross_lines_score(crops.get("buy_menu_close_anchor"))
        report_score = _panel_score(crops.get("combat_report"))
        map_score = _map_score(metrics.get("expanded_tactical_map"))
        astral = _astra_scores(crops.get("center_crosshair_area"))
        banner_score = _region_candidate(metrics.get("center_phase_banner"), min_edge=0.025)
        smoke_features = _obscuration_features(center)
        flash_features = _flash_features(
            previous, FrameFeatureObservation(time_sec, metrics, {}, {}, anchors), following
        )
        roster = {
            "ally": _roster_liveness(crops.get("ally_roster")),
            "enemy": _roster_liveness(crops.get("enemy_roster")),
        }
        kill_change = _change_score(
            crops.get("kill_feed"),
            None if previous is None else _extract_crop_from_metrics_source(previous, "kill_feed"),
        )

        stable_anchors = previous is not None and all(
            previous.calibration_anchor_presence.get(name, 0.0) >= 0.55
            and anchors.get(name, 0.0) >= 0.55
            for name in self.ANCHOR_NAMES
        )
        signals: dict[str, Any] = {
            "buy_menu_grid_present": buy_menu_grid >= 0.72,
            "buy_menu_grid_confidence": buy_menu_grid,
            "buy_menu_close_anchor_present": close_x_score >= 0.78,
            "buy_menu_close_anchor_confidence": close_x_score,
            "combat_report_visible": report_score >= 0.78,
            "combat_report_confidence": report_score,
            # World geometry can have the same edge/color distribution as a
            # tactical map. Keep this as a candidate until a configured map UI
            # detector confirms it; aggregate texture alone is not identity.
            "expanded_map_candidate": map_score >= 0.82,
            "expanded_map_present": False,
            "map_confidence": map_score,
            "expanded_map_stable": False,
            "astral_geometry": astral["geometry"] >= 0.9,
            "purple_palette": astral["palette"] >= 0.9,
            "astra_hand_interface": astral["interface"] >= 0.9,
            "remote_confidence": min(astral.values()),
            # Aggregate texture can exclude live attribution but cannot verify
            # a remote-operation interface. Preserve that provenance explicitly.
            "remote_texture_candidate": all(score >= 0.90 for score in astral.values()),
            # World texture can have the same edge/contrast distribution as
            # text. It is not a semantic purchase/result banner, even when a
            # score changes. Configured semantic detectors promote separately.
            "phase_banner_candidate": banner_score >= 0.8,
            "phase_banner_candidate_confidence": banner_score,
            **smoke_features,
            **flash_features,
            "hud_anchors_stable": stable_anchors,
            "kill_feed_change_score": kill_change,
            "kill_feed_row_added": kill_change >= 0.08,
            "ally_liveness_candidates": roster["ally"],
            "enemy_liveness_candidates": roster["enemy"],
            "anchor_presence": anchors,
            "frame_width": width,
            "frame_height": height,
        }
        roi_confidence = {
            name: min(1.0, max(0.0, _region_signal_confidence(item)))
            for name, item in metrics.items()
        }
        return FrameFeatureObservation(
            time_sec,
            metrics,
            signals,
            roi_confidence,
            anchors,
            _feed_signature(crops.get("kill_feed")),
        )

    def observe_sequence(
        self,
        frames: Sequence[FrameInput],
        *,
        times: Sequence[float] | None = None,
        cancel_event: Event | None = None,
    ) -> tuple[FrameFeatureObservation, ...]:
        initial: list[FrameFeatureObservation] = []
        for index, frame in enumerate(frames):
            if cancel_event is not None and cancel_event.is_set():
                raise InterruptedError("HUD frame analysis was cancelled")
            initial.append(
                self.observe(frame, time_sec=None if times is None else float(times[index]))
            )
        observed: list[FrameFeatureObservation] = []
        for index, item in enumerate(initial):
            previous = initial[index - 1] if index else None
            following = initial[index + 1] if index + 1 < len(initial) else None
            flash = _flash_features(previous, item, following)
            signals = dict(item.signals)
            signals.update(flash)
            signals["hud_anchors_stable"] = previous is not None and all(
                previous.calibration_anchor_presence.get(name, 0.0) >= 0.55
                and item.calibration_anchor_presence.get(name, 0.0) >= 0.55
                for name in self.ANCHOR_NAMES
            )
            changed_rows, change_score, row_added = _feed_row_changes(
                () if previous is None else previous.kill_feed_row_signature,
                item.kill_feed_row_signature,
            )
            signals["kill_feed_change_score"] = change_score
            signals["kill_feed_changed_rows"] = list(changed_rows)
            signals["kill_feed_added_rows"] = [0] if row_added else []
            signals["kill_feed_row_added"] = row_added
            observed.append(
                FrameFeatureObservation(
                    item.time_sec,
                    item.metrics,
                    signals,
                    item.roi_confidence,
                    item.calibration_anchor_presence,
                    item.kill_feed_row_signature,
                )
            )
        return tuple(observed)


def load_frame(frame: FrameInput) -> np.ndarray:
    image: Any
    if isinstance(frame, np.ndarray):
        image = frame
    else:
        path_value = getattr(frame, "path", frame)
        image = cv2.imread(str(Path(path_value)), cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError(f"HUD frameをOpenCVで読み込めません: {path_value}")
    if not isinstance(image, np.ndarray) or image.ndim not in {2, 3} or image.size == 0:
        raise ValueError("HUD frameは空でないOpenCV互換画像である必要があります")
    if image.ndim == 2:
        image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    if image.shape[2] == 4:
        image = cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)
    return np.asarray(image)


def crop_roi(
    frame: FrameInput,
    layout: HudLayout,
    name: str,
    *,
    calibration: CalibrationResult | None = None,
) -> np.ndarray:
    image = load_frame(frame)
    left, top, right, bottom = layout.pixel_bounds(
        name,
        image.shape[1],
        image.shape[0],
        calibration=calibration,
    )
    return image[top:bottom, left:right]


def measure_roi(image: np.ndarray) -> RoiMetrics:
    if image.size == 0:
        raise ValueError("ROI crop is empty")
    bgr = image if image.ndim == 3 else cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    edges = cv2.Canny(gray, 60, 140)
    edge_density = float(np.count_nonzero(edges)) / float(edges.size)
    hist = cv2.calcHist([gray], [0], None, [16], [0, 256]).ravel().astype(np.float64)
    total = float(hist.sum())
    probabilities = hist / total if total else hist
    nonzero = probabilities[probabilities > 0]
    entropy = float(-(nonzero * np.log2(nonzero)).sum() / 4.0) if nonzero.size else 0.0
    hue_sat = cv2.calcHist([hsv], [0, 1], None, [12, 8], [0, 180, 0, 256]).ravel()
    color_total = float(hue_sat.sum())
    color_entropy = 0.0
    if color_total:
        color_prob = hue_sat.astype(np.float64) / color_total
        color_prob = color_prob[color_prob > 0]
        color_entropy = float(-(color_prob * np.log2(color_prob)).sum() / np.log2(96))
    return RoiMetrics(
        mean_luminance=float(gray.mean()),
        luminance_std=float(gray.std()),
        mean_saturation=float(hsv[:, :, 1].mean()),
        edge_density=edge_density,
        spatial_entropy=min(1.0, max(0.0, entropy)),
        broad_color_uniformity=min(1.0, max(0.0, 1.0 - color_entropy)),
        bright_fraction=float(np.count_nonzero(gray >= 235)) / float(gray.size),
        dark_fraction=float(np.count_nonzero(gray <= 20)) / float(gray.size),
        width=int(gray.shape[1]),
        height=int(gray.shape[0]),
    )


def _crop(image: np.ndarray, roi: NormalizedRoi) -> np.ndarray:
    left, top, right, bottom = roi.pixel_bounds(image.shape[1], image.shape[0])
    return image[top:bottom, left:right]


def _crop_all_configured(image: np.ndarray, layout: HudLayout, name: str) -> np.ndarray | None:
    region = layout.regions.get(name)
    return None if region is None else _crop(image, region)


def _anchor_presence(metrics: RoiMetrics | None) -> float:
    if metrics is None:
        return 0.0
    contrast = min(1.0, metrics.luminance_std / 28.0)
    structure = min(1.0, metrics.edge_density / 0.06)
    return round(0.55 * contrast + 0.45 * structure, 4)


def _region_signal_confidence(metrics: RoiMetrics) -> float:
    return min(1.0, metrics.edge_density / 0.12) * min(1.0, metrics.luminance_std / 40.0)


def _region_candidate(metrics: RoiMetrics | None, *, min_edge: float) -> float:
    if metrics is None:
        return 0.0
    edge = min(1.0, metrics.edge_density / max(min_edge * 2, 0.001))
    contrast = min(1.0, metrics.luminance_std / 45.0)
    return round(0.5 * edge + 0.5 * contrast, 4)


def _cross_lines_score(image: np.ndarray | None) -> float:
    if image is None or image.size == 0:
        return 0.0
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    lines = cv2.HoughLinesP(
        cv2.Canny(gray, 50, 130),
        1,
        np.pi / 180,
        threshold=max(8, min(gray.shape) // 3),
        minLineLength=max(5, min(gray.shape) // 4),
        maxLineGap=4,
    )
    if lines is None:
        return 0.0
    # Binding versions expose either (N, 1, 4) or (N, 4); keep all coordinates.
    diagonal_signs: set[int] = set()
    for line in lines.reshape(-1, 4):
        x1, y1, x2, y2 = (int(part) for part in line)
        dx, dy = x2 - x1, y2 - y1
        if abs(dx) < 3 or abs(dy) < 3 or abs(abs(dy / dx) - 1) > 0.45:
            continue
        diagonal_signs.add(1 if dx * dy > 0 else -1)
    return 0.82 if len(diagonal_signs) == 2 else 0.0


def _panel_score(image: np.ndarray | None) -> float:
    if image is None or image.size == 0:
        return 0.0
    metrics = measure_roi(image)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    border_width = max(1, gray.shape[1] // 16)
    left_delta = abs(
        float(gray[:, :border_width].mean())
        - float(gray[:, border_width : 2 * border_width].mean())
    )
    right_delta = abs(
        float(gray[:, -border_width:].mean())
        - float(gray[:, -2 * border_width : -border_width].mean())
    )
    boundary = min(1.0, max(left_delta, right_delta) / 42.0)
    content = min(1.0, metrics.edge_density / 0.075) * min(1.0, metrics.luminance_std / 32.0)
    return round(0.55 * boundary + 0.45 * content, 4)


def _map_score(metrics: RoiMetrics | None) -> float:
    if metrics is None:
        return 0.0
    line_structure = min(1.0, metrics.edge_density / 0.07)
    tonal_range = min(1.0, metrics.luminance_std / 52.0)
    return round(0.6 * line_structure + 0.4 * tonal_range, 4)


def _astra_scores(image: np.ndarray | None) -> dict[str, float]:
    if image is None or image.size == 0:
        return {"geometry": 0.0, "palette": 0.0, "interface": 0.0}
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    purple = cv2.inRange(hsv, np.array([125, 55, 55]), np.array([175, 255, 255]))
    palette_ratio = float(np.count_nonzero(purple)) / float(purple.size)
    palette_score = min(1.0, palette_ratio / 0.24)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    circles = cv2.HoughCircles(
        gray,
        cv2.HOUGH_GRADIENT,
        dp=1.4,
        minDist=max(8, min(gray.shape) // 8),
        param1=90,
        param2=24,
        minRadius=4,
        maxRadius=max(8, min(gray.shape) // 3),
    )
    geometry_score = 0.92 if circles is not None and len(circles.reshape(-1, 3)) >= 2 else 0.0
    lower = gray[int(gray.shape[0] * 0.58) :, :]
    lower_edges = cv2.Canny(lower, 55, 130)
    interface_ratio = float(np.count_nonzero(lower_edges)) / float(lower_edges.size)
    interface_score = min(1.0, interface_ratio / 0.07) * min(1.0, float(lower.std()) / 38.0)
    return {
        "geometry": round(geometry_score, 4),
        "palette": round(palette_score, 4),
        "interface": round(interface_score, 4),
    }


def _obscuration_features(metrics: RoiMetrics | None) -> dict[str, bool | float]:
    if metrics is None:
        return {
            "low_edge_density": False,
            "low_spatial_entropy": False,
            "broad_color_uniformity": False,
            "smoke_confidence": 0.0,
            "smoke_ambiguous": False,
        }
    return {
        "low_edge_density": metrics.edge_density <= 0.025,
        "low_spatial_entropy": metrics.spatial_entropy <= 0.62,
        "broad_color_uniformity": metrics.broad_color_uniformity >= 0.55,
        # These features cannot distinguish smoke from a nearby blank wall or
        # darkness. Keep a candidate, not a high-confidence semantic assertion.
        "smoke_ambiguous": True,
        "smoke_confidence": min(
            0.64,
            round(
                max(0.0, min(1.0, (0.03 - metrics.edge_density) / 0.03))
                * max(0.0, min(1.0, (0.75 - metrics.spatial_entropy) / 0.75))
                * metrics.broad_color_uniformity,
                4,
            ),
        ),
    }


def _flash_features(
    previous: FrameFeatureObservation | None,
    current: FrameFeatureObservation,
    following: FrameFeatureObservation | None,
) -> dict[str, bool | float]:
    key = "center_crosshair_area"
    before = None if previous is None else previous.metrics.get(key)
    now = current.metrics.get(key)
    after = None if following is None else following.metrics.get(key)
    if before is None or now is None or after is None:
        return {
            "abrupt_luminance_spike": False,
            "scene_detail_collapse": False,
            "rapid_decay": False,
            "flash_confidence": 0.0,
        }
    spike = now.mean_luminance - before.mean_luminance >= 55
    detail_collapse = now.edge_density <= max(0.025, before.edge_density * 0.4)
    decay = after.mean_luminance - now.mean_luminance <= -35
    score = 0.92 if spike and detail_collapse and decay else 0.0
    return {
        "abrupt_luminance_spike": spike,
        "scene_detail_collapse": detail_collapse,
        "rapid_decay": decay,
        "flash_confidence": score,
    }


def _roster_liveness(image: np.ndarray | None) -> list[dict[str, float | bool | None]]:
    if image is None or image.size == 0:
        return []
    width = image.shape[1]
    slots: list[dict[str, float | bool | None]] = []
    for index in range(5):
        left = round(index * width / 5)
        right = max(left + 1, round((index + 1) * width / 5))
        crop = image[:, left:right]
        hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
        saturation = float(hsv[:, :, 1].mean())
        contrast = float(cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY).std())
        if saturation >= 92 and contrast >= 22:
            alive: bool | None = True
            confidence = min(1.0, saturation / 110) * min(1.0, contrast / 38)
        elif saturation <= 3 and contrast >= 18:
            alive = False
            confidence = min(1.0, max(0.0, (5 - saturation) / 5)) * min(1.0, contrast / 32)
        else:
            alive = None
            confidence = 0.0
        slots.append(
            {
                "alive_candidate": alive,
                "confidence": round(confidence, 4),
            }
        )
    return slots


def _change_score(current: np.ndarray | None, previous: np.ndarray | None) -> float:
    if current is None or previous is None or current.size == 0 or previous.size == 0:
        return 0.0
    height, width = (
        min(current.shape[0], previous.shape[0]),
        min(current.shape[1], previous.shape[1]),
    )
    current_gray = cv2.cvtColor(current[:height, :width], cv2.COLOR_BGR2GRAY)
    previous_gray = cv2.cvtColor(previous[:height, :width], cv2.COLOR_BGR2GRAY)
    difference = cv2.absdiff(current_gray, previous_gray)
    return float(np.count_nonzero(difference >= 35)) / float(difference.size)


def _feed_signature(
    image: np.ndarray | None,
) -> tuple[tuple[float, float, float, float], ...]:
    """Describe feed rows by occupancy and pixels without retaining frame crops."""

    if image is None or image.size == 0:
        return ()
    row_count = max(3, min(8, round(image.shape[0] / 23)))
    signature: list[tuple[float, float, float, float]] = []
    for index in range(row_count):
        top = round(index * image.shape[0] / row_count)
        bottom = max(top + 1, round((index + 1) * image.shape[0] / row_count))
        row = image[top:bottom]
        gray = cv2.cvtColor(row, cv2.COLOR_BGR2GRAY)
        hsv = cv2.cvtColor(row, cv2.COLOR_BGR2HSV)
        edge = float(np.count_nonzero(cv2.Canny(gray, 55, 135))) / float(gray.size)
        saturation = float(hsv[:, :, 1].mean()) / 255.0
        luminance = float(gray.std()) / 128.0
        occupied = float(edge >= 0.018 or (saturation >= 0.12 and luminance >= 0.08))
        signature.append((occupied, min(1.0, edge), saturation, min(1.0, luminance)))
    return tuple(signature)


def _feed_row_changes(
    previous: tuple[tuple[float, float, float, float], ...],
    current: tuple[tuple[float, float, float, float], ...],
) -> tuple[tuple[int, ...], float, bool]:
    if not current:
        return (), 0.0, False
    if not previous or len(previous) != len(current):
        changed = tuple(index for index, row in enumerate(current) if row[0] > 0)
        return changed, 0.0, False
    differences = [
        sum(abs(left - right) for left, right in zip(old, new, strict=True)) / 4.0
        for old, new in zip(previous, current, strict=True)
    ]
    changed = tuple(index for index, difference in enumerate(differences) if difference >= 0.12)
    score = sum(differences) / len(differences)
    first_changed = differences[0] >= 0.20 and current[0][0] > 0
    shift_matches = 0
    if first_changed:
        for old, new in zip(previous[:-1], current[1:], strict=False):
            distance = sum(abs(left - right) for left, right in zip(old, new, strict=True)) / 4.0
            if distance <= 0.10:
                shift_matches += 1
    added = first_changed and (previous[0][0] == 0.0 or shift_matches >= max(2, len(previous) // 3))
    return changed, min(1.0, score), added


def _extract_crop_from_metrics_source(
    observation: FrameFeatureObservation, name: str
) -> np.ndarray | None:
    # The single-frame interface cannot retain source pixels; sequence observation
    # performs the actual feed comparison from its adjacent source frames.
    del observation, name
    return None
