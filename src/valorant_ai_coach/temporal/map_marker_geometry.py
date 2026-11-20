"""Native minimap portrait and attached rim measurements for development replay."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, cast

import cv2
import numpy as np
from numpy.typing import NDArray

from .map_portrait_rim import Reference, portrait_agent_candidates


@dataclass(frozen=True)
class MarkerGeometry:
    center: tuple[int, int]
    radius: float
    palette: str
    rim_pixels: frozenset[tuple[int, int]]
    support: float
    tip: tuple[int, int] | None
    agent_candidates: tuple[dict[str, Any], ...]


def _fit_rim(
    mask: NDArray[np.uint8], gray: NDArray[np.uint8], center: tuple[int, int], scale: float,
    limit: int,
) -> tuple[float, tuple[int, int], float, NDArray[np.intp], NDArray[np.intp]] | None:
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    ys, xs = np.indices(mask.shape)
    offsets = np.arange(-limit, limit + 1)
    dx, dy = np.meshgrid(offsets, offsets)
    cx = dx.ravel() + center[0]
    cy = dy.ravel() + center[1]
    best = None
    for label in range(1, count):
        left, top, width, height, area = stats[label]
        if not (
            22 * scale**2 <= area <= 300 * scale**2
            and 11 * scale <= width <= 30 * scale and 11 * scale <= height <= 30 * scale
            and left > 0 and top > 0 and left + width < mask.shape[1]
            and top + height < mask.shape[0]
        ):
            continue
        iy, ix = np.nonzero(labels == label)
        distances = np.hypot(ix - cx[:, None], iy - cy[:, None]) / scale
        sectors = np.floor((np.arctan2(iy - cy[:, None], ix - cx[:, None]) + math.pi)
                           * (12 / math.pi)).astype(int) % 24
        for radius in (6.5, 7.5, 8.5, 9.5):
            annulus = np.abs(distances - radius) <= 1.6
            coverage = np.zeros((len(cx), 24), dtype=bool)
            rows, points = np.nonzero(annulus)
            coverage[rows, sectors[rows, points]] = True
            enclosure = (coverage.mean(axis=1)
                         + (coverage & np.roll(coverage, 12, axis=1)).mean(axis=1)) / 2
            fill = (distances < radius - 2.4).sum(axis=1) / (math.pi * (radius - 2.4)**2 * scale**2)
            score = enclosure * np.clip(1 - fill, 0, 1)
            score -= .025 * np.hypot(dx.ravel(), dy.ravel()) / scale
            for i in np.argsort(-score, kind="stable")[:3]:
                if score[i] < .45 or (best is not None and score[i] <= best[0]):
                    break
                interior = (xs-cx[i])**2 + (ys-cy[i])**2 <= (scale * (radius-2.4))**2
                inner = gray[interior]
                if inner.size and inner.std() > 9 and np.median(inner) < 170:
                    best = float(score[i]), (int(cx[i]), int(cy[i])), radius * scale, iy, ix
    return best


def _attached_tip(
    x: NDArray[np.intp], y: NDArray[np.intp], center: tuple[int, int], radius: float, scale: float,
) -> tuple[int, int] | None:
    delta_x, delta_y = x - center[0], y - center[1]
    radial = np.hypot(delta_x, delta_y)
    # A lobe must have area beyond the enclosing ring. Follow a connected
    # extension of the same silhouette and reject a second competing lobe.
    angles = np.arctan2(delta_y, delta_x)
    sectors = np.floor((angles + math.pi) * (12 / math.pi)).astype(int) % 24
    envelope = np.zeros(24)
    np.maximum.at(envelope, sectors, radial)
    enclosing_edge = float(np.median(envelope))
    outer = radial >= max(radius + 2.5 * scale, enclosing_edge + .9 * scale)
    if not np.any(outer) or float(radial.max()) > radius + 10 * scale:
        return None
    shape = (int(y.max()) + 1, int(x.max()) + 1)
    silhouette = np.zeros(shape, dtype=np.uint8)
    silhouette[y[outer], x[outer]] = 1
    n, labels, stats, _ = cv2.connectedComponentsWithStats(silhouette, connectivity=8)
    lobes = [i for i in range(1, n) if stats[i, cv2.CC_STAT_AREA] >= max(3, 4 * scale**2)]
    if len(lobes) != 1:
        return None
    points = labels[y, x] == lobes[0]
    far = radial[points] >= radial[points].max() - 1.25 * scale
    # Estimate the tip from the outer cap, rather than an extreme pixel.
    vx, vy = x[points][far], y[points][far]
    tip_x, tip_y = float(vx.mean()), float(vy.mean())
    direction = math.atan2(tip_y - center[1], tip_x - center[0])
    deviation = np.angle(np.exp(1j * (angles[points] - direction)))
    if np.max(np.abs(deviation)) > math.pi / 3:
        return None
    nearest = int(np.argmin((vx-tip_x)**2 + (vy-tip_y)**2))
    return int(vx[nearest]), int(vy[nearest])


def measure_marker_geometry(
    image: NDArray[np.uint8], candidates: list[dict[str, Any]],
    references: Sequence[Reference] = (),
) -> list[MarkerGeometry | None]:
    """Fit local portrait geometry, preserving the original candidate indices."""
    if (image.dtype != np.uint8 or image.ndim != 3 or image.shape[2] != 3
            or not image.shape[0] or not image.shape[1]):
        raise ValueError("Native BGR frame required")
    height, width = image.shape[:2]
    scale = width / 1920
    if scale < .5:
        return [None] * len(candidates)
    extent, shift = math.ceil(23 * scale), round(5 * scale)
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    gray = cast(NDArray[np.uint8], cv2.cvtColor(image, cv2.COLOR_BGR2GRAY))
    results: list[MarkerGeometry | None] = []
    for candidate in candidates:
        x, y = map(round, candidate["center_frame_px"])
        if not (extent <= x < width - extent and extent <= y < height - extent):
            results.append(None)
            continue
        left, top = x - extent, y - extent
        bounds = np.s_[top:y+extent+1, left:x+extent+1]
        hue, saturation, value = cv2.split(hsv[bounds])
        masks = {
            "WARM": ((hue >= 17) & (hue <= 42) & (saturation >= 20)
                     & (saturation <= 155) & (value >= 166)),
            "CYAN": ((hue >= 73) & (hue <= 105) & (saturation >= 55) & (value >= 135)),
        }
        fits = []
        for palette, mask in masks.items():
            fitted = _fit_rim(mask.astype(np.uint8), gray[bounds], (extent, extent), scale, shift)
            if fitted is None and palette == "WARM":
                dim = ((hue >= 17) & (hue <= 42) & (saturation >= 20)
                       & (saturation <= 155) & (value >= 125))
                fitted = _fit_rim(
                    dim.astype(np.uint8), gray[bounds], (extent, extent), scale, shift,
                )
                if fitted and fitted[0] < .65:
                    fitted = None
            if fitted is not None:
                fits.append((palette, fitted))
        if not fits:
            results.append(None)
            continue
        palette, (support, center, radius, iy, ix) = max(fits, key=lambda row: row[1][0])
        # Competing overlapping colors are common in crowded starts.
        if any(other != palette and math.dist(center, fit[1]) < radius
               and abs(support - fit[0]) < .10 for other, fit in fits):
            results.append(None)
            continue
        offset_tip = _attached_tip(ix, iy, center, radius, scale)
        global_center = (left + center[0], top + center[1])
        tip = (left + offset_tip[0], top + offset_tip[1]) if offset_tip else None
        cx, cy = global_center
        half = max(1, round(radius * .7))
        patch = gray[cy-half:cy+half+1, cx-half:cx+half+1]
        agents = portrait_agent_candidates(patch, references)
        results.append(MarkerGeometry(
            global_center, radius, palette,
            frozenset(zip((ix + left).tolist(), (iy + top).tolist(), strict=True)),
            support, tip, tuple(agents),
        ))
    return results


def same_marker(a: MarkerGeometry, b: MarkerGeometry) -> bool:
    """Require shared native pixels and center agreement, not proximity alone."""
    return (
        a.palette == b.palette
        and math.dist(a.center, b.center) <= .55 * min(a.radius, b.radius)
        and len(a.rim_pixels & b.rim_pixels) >= .75 * max(len(a.rim_pixels), len(b.rim_pixels))
        and (a.tip is None or b.tip is None
             or math.dist(a.tip, b.tip) <= min(a.radius, b.radius) / 2)
    )
