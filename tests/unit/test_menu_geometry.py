"""Current-pixel menu structure has no life, owner or phase authority."""

from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from valorant_ai_coach.temporal.menu_geometry import (
    VERSION,
    MenuGeometrySupplementObserver,
    measure_menu_grid,
)


class Roi:
    def pixel_bounds(self, width, height):
        return (
            round(0.1875 * width),
            round(0.083333 * height),
            round(0.786458 * width),
            round(0.888889 * height),
        )


class Layout:
    regions = {"buy_menu_grid": object()}

    def normalized_roi(self, name):
        assert name == "buy_menu_grid"
        return Roi()


def image(*, vertical=True, horizontal=True):
    frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
    if vertical:
        for x in (600, 825, 1087, 1322, 1497):
            cv2.line(frame, (x, 150), (x, 730), (255, 255, 255), 2)
    if horizontal:
        for y in (150, 245, 385, 505, 625, 740):
            cv2.line(frame, (420, y), (1490, y), (255, 255, 255), 2)
    return frame


def ui(present=True):
    return {
        "buy_menu_close_anchor_present": present,
        "buy_menu_close_anchor_present_confidence": 0.99 if present else 0.0,
    }


def test_menu_grid_is_a_pixel_only_advisory_candidate():
    result = measure_menu_grid(image(), layout=Layout(), ui=ui())
    assert result["schema"] == VERSION
    assert result["supported"] is True and result["status"] == "CANDIDATE"
    assert result["unique_vertical_lines"] >= 4
    assert result["unique_horizontal_lines"] >= 5
    assert len(result["roi_pixel_sha256"]) == 64
    assert all(
        result[key] is False
        for key in ("owner_authority", "camera_authority", "phase_authority", "qualified")
    )


@pytest.mark.parametrize(
    "frame,present",
    [
        (image(vertical=False), True),
        (image(horizontal=False), True),
        (image(), False),
    ],
)
def test_missing_grid_or_close_anchor_stays_unknown(frame, present):
    result = measure_menu_grid(frame, layout=Layout(), ui=ui(present))
    assert result["status"] == "UNKNOWN" and result["supported"] is False


def test_supplier_appends_observation_without_changing_parent_claims():
    parent_result = {
        "signals": ["report"],
        "context": {"stream_kind": "hud_generic"},
        "raw": {"ui": ui()},
        "map_candidates": [],
    }
    observer = MenuGeometrySupplementObserver.__new__(MenuGeometrySupplementObserver)
    observer.parent = SimpleNamespace(inspect=lambda _: parent_result, fingerprint="a" * 64)
    observer.layout = Layout()
    observer.bindings = {"layout_sha256": "b" * 64}
    observer.menu_fingerprint = "c" * 64
    output = observer.inspect(image())
    assert output["signals"] == ["report"]
    assert len(output["supplier_observations"]) == 2
    extra = output["supplier_observations"][-1]
    assert extra["signals"] == [] and extra["map_candidates"] == []
    assert extra["context"]["stream_kind"] == "hud_menu_geometry"
    assert extra["raw"]["menu_grid_measurement"]["supported"] is True
    assert extra["raw"]["formal_outputs"] == 0
