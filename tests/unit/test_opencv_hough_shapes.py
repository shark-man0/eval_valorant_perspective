"""OpenCV bindings may return flat or singleton-axis Hough coordinate arrays."""

from pathlib import Path

import cv2
import numpy as np
import pytest

from valorant_ai_coach.hud.layout import HudLayout
from valorant_ai_coach.hud.readers import OpenCvHudFeatureReader, _astra_scores, _cross_lines_score
from valorant_ai_coach.hud.spectator_icon import menu_overlay_candidate
from valorant_ai_coach.hud.weapon_identity import frame_edges, structural_layout
from valorant_ai_coach.resources import resource_path


@pytest.mark.parametrize("flat", [False, True])
def test_hough_line_shapes_preserve_coordinates_and_gates(monkeypatch, flat):
    coordinates = np.array([[5, 5, 35, 35], [35, 5, 5, 35]], dtype=np.int32)
    lines = coordinates if flat else coordinates[:, None, :]
    monkeypatch.setattr(cv2, "HoughLinesP", lambda *args, **kwargs: lines.copy())
    image = np.zeros((40, 40, 3), np.uint8)
    assert _cross_lines_score(image) == 0.82
    assert menu_overlay_candidate(image) is True
    edges = np.zeros((40, 40), np.uint8)
    for x1, y1, x2, y2 in coordinates:
        cv2.line(edges, (int(x1), int(y1)), (int(x2), int(y2)), 1, 1)
    assert np.array_equal(frame_edges(edges > 0), edges > 0)
    arrangement = structural_layout(edges > 0, np.zeros_like(edges), lines)
    assert arrangement["structural_gates"]["arrangement"] is True


@pytest.mark.parametrize("flat", [False, True])
@pytest.mark.parametrize("count", [1, 2])
def test_circle_shape_preserves_minimum_count(monkeypatch, flat, count):
    coordinates = np.array([[10, 10, 5], [30, 30, 5]], dtype=np.float32)[:count]
    circles = coordinates if flat else coordinates[None, :, :]
    monkeypatch.setattr(cv2, "HoughCircles", lambda *args, **kwargs: circles.copy())
    assert _astra_scores(np.zeros((40, 40, 3), np.uint8))["geometry"] == (
        0.92 if count >= 2 else 0.0
    )


def test_feature_reader_accepts_both_hough_binding_shapes(monkeypatch):
    layout = HudLayout.load(Path(resource_path("config/hud_layout_1080p_v3.json")))
    image = np.random.default_rng(7).integers(0, 256, (360, 640, 3), dtype=np.uint8)
    original_lines, original_circles = cv2.HoughLinesP, cv2.HoughCircles

    def bind(flat):
        def lines(*args, **kwargs):
            result = original_lines(*args, **kwargs)
            if result is None:
                return None
            return result.reshape(-1, 4) if flat else result.reshape(-1, 1, 4)

        def circles(*args, **kwargs):
            result = original_circles(*args, **kwargs)
            if result is None:
                return None
            return result.reshape(-1, 3) if flat else result.reshape(1, -1, 3)

        monkeypatch.setattr(cv2, "HoughLinesP", lines)
        monkeypatch.setattr(cv2, "HoughCircles", circles)
        return OpenCvHudFeatureReader(layout).observe(image)

    assert bind(True) == bind(False)
