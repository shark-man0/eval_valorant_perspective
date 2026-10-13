"""Training-only geometry experiment: retain closed frame boundaries, not contents.

This is not a presence detector or a production qualification decision. Missing
enclosures produce no support; a tiny open line cannot substitute for a frame.
"""
from __future__ import annotations

import cv2
import numpy as np


def enclosure_boundary_support(template: np.ndarray) -> np.ndarray:
    if template.dtype != np.uint8 or template.ndim != 2 or min(template.shape) < 16:
        raise ValueError("grayscale uint8 geometry template required")
    edges = cv2.Canny(template, 60, 150)
    contours, hierarchy = cv2.findContours(edges, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    support = np.zeros_like(template)
    if hierarchy is None:
        return support
    for index, contour in enumerate(contours):
        # Only top-level enclosed 2D shapes. Child glyphs/counters must not
        # become independent geometry even if their content remained constant.
        if hierarchy[0, index, 3] != -1 or hierarchy[0, index, 2] == -1:
            continue
        _, _, width, height = cv2.boundingRect(contour)
        area = abs(cv2.contourArea(contour))
        if min(width, height) < 12 or area < 64 or area > template.size * .35:
            continue
        filled = np.zeros_like(template)
        cv2.drawContours(filled, [contour], -1, 255, cv2.FILLED)
        # Keep both sides of the outline for raw-pixel NCC; exclude the content
        # behind it. This changes only a candidate mask, never runtime scoring.
        outer = cv2.dilate(filled, np.ones((3, 3), np.uint8))
        inner = cv2.erode(filled, np.ones((5, 5), np.uint8))
        support |= cv2.subtract(outer, inner)
    return support
