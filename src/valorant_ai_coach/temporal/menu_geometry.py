"""Opt-in current-pixel purchase-menu grid evidence without ownership authority.

This observes long rectangular menu-cell borders inside the configured grid
ROI. The existing close-anchor witness is a required independent prerequisite.
No Source, time, previous state or human label enters the pixel reader.
"""

from __future__ import annotations

import hashlib
import importlib
import math
from copy import deepcopy
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from numpy.typing import NDArray

from valorant_ai_coach.hud.layout import HudLayout

from .evidence import digest
from .replay import file_sha, read_json

VERSION = "development_buy_menu_grid_geometry_v1"
# A central portion of the existing grid ROI excludes the left roster, right
# ability description and bottom HUD. These are fractions of a layout ROI, not
# recording-specific pixels or timing rules.
INNER_GRID = (0.055, 0.041, 0.989, 0.672)
CANNY = (80, 160)
HOUGH_VOTES = 70
MIN_LINE_FRAME_WIDTH = 0.09
MAX_LINE_GAP = 8
MIN_VERTICAL = 4
MIN_HORIZONTAL = 5


def _unique_positions(values: list[int], minimum_gap: int) -> list[int]:
    distinct: list[int] = []
    for value in sorted(values):
        if not distinct or value - distinct[-1] > minimum_gap:
            distinct.append(value)
    return distinct


def _pixel_bounds(layout: HudLayout, width: int, height: int) -> tuple[int, int, int, int]:
    if "buy_menu_grid" not in layout.regions:
        raise ValueError("Configured buy-menu grid ROI required")
    left, top, right, bottom = layout.normalized_roi("buy_menu_grid").pixel_bounds(width, height)
    grid_width, grid_height = right - left, bottom - top
    x1 = left + round(INNER_GRID[0] * grid_width)
    y1 = top + round(INNER_GRID[1] * grid_height)
    x2 = left + round(INNER_GRID[2] * grid_width)
    y2 = top + round(INNER_GRID[3] * grid_height)
    if not 0 <= x1 < x2 <= width or not 0 <= y1 < y2 <= height:
        raise ValueError("Buy-menu grid ROI outside current pixels")
    return x1, y1, x2, y2


def measure_menu_grid(
    image: NDArray[np.uint8], *, layout: HudLayout, ui: dict[str, Any]
) -> dict[str, Any]:
    """Return a current-pixel overlay candidate, never a state or owner claim."""
    if (
        not isinstance(image, np.ndarray)
        or image.dtype != np.uint8
        or image.ndim != 3
        or image.shape[2] != 3
        or min(image.shape[:2]) < 64
    ):
        raise ValueError("Native BGR pixels required")
    height, width = image.shape[:2]
    x1, y1, x2, y2 = _pixel_bounds(layout, width, height)
    crop = image[y1:y2, x1:x2]
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, *CANNY)
    minimum = round(MIN_LINE_FRAME_WIDTH * width)
    lines = cv2.HoughLinesP(
        edges,
        1,
        np.pi / 180,
        threshold=HOUGH_VOTES,
        minLineLength=minimum,
        maxLineGap=MAX_LINE_GAP,
    )
    vertical: list[int] = []
    horizontal: list[int] = []
    if lines is not None:
        for x_start, y_start, x_end, y_end in lines[:, 0]:
            dx, dy = abs(int(x_end - x_start)), abs(int(y_end - y_start))
            if dx <= 3 and dy >= round(MIN_LINE_FRAME_WIDTH * height):
                vertical.append(round((int(x_start) + int(x_end)) / 2))
            if dy <= 3 and dx >= minimum:
                horizontal.append(round((int(y_start) + int(y_end)) / 2))
    unique_vertical = _unique_positions(vertical, max(2, round(width / 192)))
    unique_horizontal = _unique_positions(horizontal, max(2, round(height / 108)))
    close = ui.get("buy_menu_close_anchor_present") is True
    confidence = ui.get("buy_menu_close_anchor_present_confidence")
    close_supported = (
        close
        and type(confidence) in (int, float)
        and isinstance(confidence, (int, float))
        and math.isfinite(confidence)
        and 0.90 <= confidence <= 1
    )
    grid_supported = (
        len(unique_vertical) >= MIN_VERTICAL and len(unique_horizontal) >= MIN_HORIZONTAL
    )
    supported = bool(close_supported and grid_supported)
    reason = (
        "close_anchor_and_rectangular_grid_current_pixels"
        if supported
        else "close_anchor_unresolved"
        if not close_supported
        else "grid_geometry_unresolved"
    )
    return {
        "schema": VERSION,
        "status": "CANDIDATE" if supported else "UNKNOWN",
        "supported": supported,
        "reason": reason,
        "score": round(
            min(1.0, len(unique_vertical) / MIN_VERTICAL, len(unique_horizontal) / MIN_HORIZONTAL),
            4,
        ),
        "score_scope": "uncalibrated_geometric_support_not_probability",
        "unique_vertical_lines": len(unique_vertical),
        "unique_horizontal_lines": len(unique_horizontal),
        "close_anchor_present": close,
        "close_anchor_confidence": confidence,
        "roi_pixel_bounds": [x1, y1, x2, y2],
        "roi_pixel_sha256": hashlib.sha256(crop.tobytes()).hexdigest(),
        "geometry_scope": "current_pixel_menu_overlay_only",
        "owner_authority": False,
        "camera_authority": False,
        "phase_authority": False,
        "qualified": False,
    }


class MenuGeometrySupplementObserver:
    """Append one separately fingerprinted menu observation to an old observer."""

    def __init__(self, config_path: Path) -> None:
        cfg = read_json(config_path)
        if set(cfg) != {"parent_observer", "parent_config", "layout"}:
            raise ValueError("Explicit old parent and existing HUD layout required")
        module, name = cfg["parent_observer"].split(":", 1)
        self.parent = getattr(importlib.import_module(module), name)(Path(cfg["parent_config"]))
        layout_path = Path(cfg["layout"])
        self.layout = HudLayout.load(layout_path)
        if "buy_menu_grid" not in self.layout.regions:
            raise ValueError("Buy-menu grid absent from existing layout")
        self.bindings = {
            "schema": VERSION,
            "parent": self.parent.bindings,
            "parent_fingerprint": self.parent.fingerprint,
            "layout_sha256": file_sha(layout_path),
            "config_sha256": file_sha(config_path),
            "code_sha256": file_sha(Path(__file__)),
            "opencv": cv2.__version__,
            "numpy": np.__version__,
            "inner_grid": INNER_GRID,
            "canny": CANNY,
            "hough_votes": HOUGH_VOTES,
            "minimum_line_frame_width": MIN_LINE_FRAME_WIDTH,
            "max_line_gap": MAX_LINE_GAP,
            "minimum_vertical": MIN_VERTICAL,
            "minimum_horizontal": MIN_HORIZONTAL,
            "state_or_owner_authority": False,
        }
        self.menu_fingerprint = digest(
            {k: v for k, v in self.bindings.items() if k not in {"parent", "parent_fingerprint"}}
        )
        parent_suppliers = self.parent.bindings.get(
            "supplier_producer_fingerprints", [self.parent.fingerprint]
        )
        self.bindings.update(
            baseline_producer_fingerprints=list(parent_suppliers),
            supplier_producer_fingerprints=[*parent_suppliers, self.menu_fingerprint],
        )
        self.fingerprint = digest(self.bindings)

    def inspect_menu_geometry(self, image: NDArray[np.uint8], ui: dict[str, Any]) -> dict[str, Any]:
        measurement = measure_menu_grid(image, layout=self.layout, ui=ui)
        return {
            "signals": [],
            "map_candidates": [],
            "context": {
                "stream_kind": "hud_menu_geometry",
                "profile_fingerprint": self.bindings["layout_sha256"],
            },
            "raw": {
                "schema": VERSION,
                "menu_grid_measurement": measurement,
                "ownership": "UNKNOWN",
                "formal_outputs": 0,
            },
        }

    def inspect(self, image: NDArray[np.uint8]) -> dict[str, Any]:
        original: dict[str, Any] = self.parent.inspect(image)
        result = deepcopy(original)
        suppliers = result.get("supplier_observations")
        if suppliers is None:
            suppliers = [
                {
                    k: deepcopy(v)
                    for k, v in original.items()
                    if k in {"signals", "raw", "context", "map_candidates"}
                }
            ]
            suppliers[0]["producer_fingerprint"] = self.parent.fingerprint
        generic = next(
            (
                row
                for row in suppliers
                if row.get("context", {}).get("stream_kind") == "hud_generic"
            ),
            None,
        )
        if generic is None or not isinstance(generic.get("raw", {}).get("ui"), dict):
            raise ValueError("Existing current-pixel HUD UI observation required")
        extra = self.inspect_menu_geometry(image, generic["raw"]["ui"])
        result["supplier_observations"] = suppliers + [
            {**extra, "producer_fingerprint": self.menu_fingerprint}
        ]
        return result
