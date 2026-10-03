"""Structural presence in a configured, dedicated Spectator icon slot.

No sliding search, identity recognition, or learned picture reference. The slot
must be calibrated; ordinary geometry elsewhere provides no positive evidence.
"""

from typing import Any

import cv2
import numpy as np


def detect_icon(
    crop: np.ndarray, configured: bool = True, *, obscured: bool = False
) -> dict[str, Any]:
    result: dict[str, Any] = dict(
        checked=False, panel_present=None, reason="reference_unavailable", metrics={}
    )
    if not configured:
        return result
    result["reason"] = "geometry_mismatch"
    if crop.dtype != np.uint8 or crop.ndim not in (2, 3) or (crop.ndim == 3 and crop.shape[2] != 3):
        return result
    h, w = crop.shape[:2]
    if min(h, w) < 24 or abs(w / h / (75 / 83) - 1) > 0.12:
        return result
    if obscured:
        result["reason"] = "icon_roi_obscured"
        return result
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if crop.ndim == 3 else crop
    gray = cv2.resize(gray, (75, 83), interpolation=cv2.INTER_AREA)
    mean, contrast = float(gray.mean()), float(gray.std())
    sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    result["metrics"] = dict(mean=mean, contrast=contrast, sharpness=sharpness)
    if not 45 < mean < 245 or contrast < 8 or sharpness < 10:
        result["reason"] = "icon_roi_unobservable"
        return result
    if np.mean(gray <= 1) >= 0.02 or np.mean(gray >= 254) >= 0.25:
        result["reason"] = "icon_roi_unobservable"
        return result
    edges = cv2.Canny(gray, 60, 150)
    occupied = edges > 0
    density = float(occupied.mean())
    cells = [
        float(part.mean())
        for row in np.array_split(occupied, 4, axis=0)
        for part in np.array_split(row, 4, axis=1)
    ]
    gx, gy = cv2.Sobel(gray, cv2.CV_32F, 1, 0), cv2.Sobel(gray, cv2.CV_32F, 0, 1)
    magnitude = np.hypot(gx, gy)
    acutance = (
        float(
            np.median(
                np.abs(cv2.Laplacian(gray, cv2.CV_32F))[occupied]
                / np.maximum(magnitude[occupied], 1)
            )
        )
        if occupied.any()
        else 0.0
    )
    result["metrics"]["edge_acutance"] = acutance
    if acutance < 0.12:
        result["reason"] = "icon_roi_unobservable"
        return result
    angle = np.mod(np.degrees(np.arctan2(gy, gx)), 360)
    hist = np.histogram(angle[occupied], bins=np.linspace(0, 360, 9))[0]
    distribution = hist / max(1, int(hist.sum()))
    _, _, groups, _ = cv2.connectedComponentsWithStats(edges)
    localized = sum(
        area >= 6 and 2 <= gw < 0.90 * 75 and 2 <= gh < 0.90 * 83
        for x, y, gw, gh, area in groups[1:]
    )
    populated = sum(cell >= 0.08 for cell in cells)
    bins = int(sum(distribution >= 0.05))
    result["metrics"].update(
        edge_density=density,
        occupied_cells=populated,
        localized_groups=int(localized),
        orientation_bins=bins,
    )
    # Strong, distributed small-scale structure. A partial contour or sparse
    # ordinary world lines cannot prove presence. Dense noise stays ambiguous.
    if (
        0.18 <= density <= 0.32
        and populated >= 13
        and localized >= 10
        and bins == 8
        and sharpness >= 6500
        and contrast >= 35
    ):
        result.update(checked=True, panel_present=True, reason="icon_present")
    elif density <= 0.08 and mean >= 45:
        result.update(checked=True, panel_present=False, reason="icon_absent")
    else:
        result["reason"] = "icon_structure_ambiguous"
    return result


def menu_overlay_candidate(crop: np.ndarray) -> bool:
    """Conservative short-X veto in the configured menu-close context ROI.

    This establishes possible obscuration only, never icon presence or absence.
    The ordinary menu reader requires longer lines and can miss a small close X.
    """
    if crop.size == 0 or crop.dtype != np.uint8 or crop.ndim != 3 or crop.shape[2] != 3:
        return False
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, (93, 95), interpolation=cv2.INTER_AREA)
    lines = cv2.HoughLinesP(
        cv2.Canny(gray, 50, 130),
        1,
        np.pi / 180,
        threshold=8,
        minLineLength=5,
        maxLineGap=3,
    )
    if lines is None:
        return False
    signs = set()
    for x1, y1, x2, y2 in lines[:, 0, :]:
        dx, dy = int(x2 - x1), int(y2 - y1)
        if abs(dx) >= 3 and abs(dy) >= 3 and abs(abs(dy / dx) - 1) <= 0.45:
            signs.add(1 if dx * dy > 0 else -1)
    return len(signs) == 2
