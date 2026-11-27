"""Measure current outline and directional context independently of Agent portraits."""

from __future__ import annotations

import math

import cv2
import numpy as np

from valorant_ai_coach.temporal.map_marker_geometry import measure_marker_geometry


def enclosing_outline(image, center):
    shape = measure_marker_geometry(image, [{"center_frame_px": list(center)}])[0]
    scale = image.shape[1] / 1920
    if shape is None or shape.palette != "WARM":
        return None
    if math.dist(shape.center, center) > 3 * scale:
        return None
    return {
        "center_frame_px": list(shape.center),
        "support": shape.support,
        "palette": shape.palette,
    }


def directional_context(image, center):
    """Return sector evidence without asserting that a visible fan belongs to SELF."""
    scale = image.shape[1] / 1920
    x, y = center
    angles = np.arange(32) * math.tau / 32
    radii = np.arange(17, 43, 3) * scale
    xs = np.rint(x + radii[:, None] * np.cos(angles)).astype(int)
    ys = np.rint(y + radii[:, None] * np.sin(angles)).astype(int)
    if xs.min() < 0 or ys.min() < 0 or xs.max() >= image.shape[1] or ys.max() >= image.shape[0]:
        return None
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    pixels = hsv[ys, xs]
    neutral = (pixels[:, :, 1] <= 45) & (pixels[:, :, 2] >= 160)
    sectors = neutral.mean(axis=0)
    wedge = sum(np.roll(sectors, shift) for shift in (-2, -1, 0, 1, 2)) / 5
    best = int(wedge.argmax())
    return {
        "angle_radians": float(angles[best]),
        "wedge_support": float(wedge[best]),
        "opposite_support": float(wedge[(best + 16) % 32]),
        "directional_contrast": float(wedge[best] - np.median(wedge)),
    }
