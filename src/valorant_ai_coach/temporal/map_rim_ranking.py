"""Development-only ranking based on portrait-local warm rim evidence."""
from __future__ import annotations

import math
from typing import Any

import cv2
import numpy as np
from numpy.typing import NDArray

VERSION = "development_map_rim_ranking_v1"


def measure_warm_rims(
    image: NDArray[np.uint8], candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Measure a warm annulus around textured interior, with radial direction cues.

    The contour is a recorder-like display cue. Map backgrounds, overlays and
    different display settings can produce competing measurements.
    """
    if (image.dtype != np.uint8 or image.ndim != 3 or image.shape[2] != 3
            or not image.shape[0] or not image.shape[1]):
        raise ValueError("Native BGR frame required")
    height, width = image.shape[:2]
    scale = width / 1920
    hue, sat, value = cv2.split(cv2.cvtColor(image, cv2.COLOR_BGR2HSV))
    strength = (
        ((hue >= 13) & (hue <= 42))
        * np.clip((sat.astype(np.float32) - 20) / 65, 0, 1)
        * np.clip((value.astype(np.float32) - 138) / 85, 0, 1)
    )
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY).astype(np.float32)
    angles = np.arange(24) * math.tau / 24
    base_radii = np.arange(3, 17)
    rad = base_radii[:, None] * scale
    dx = np.rint(rad * np.cos(angles)).astype(int)
    dy = np.rint(rad * np.sin(angles)).astype(int)
    offset = np.arange(-4, 5, 2) * scale
    ox, oy = np.meshgrid(np.rint(offset).astype(int), np.rint(offset).astype(int))
    offsets = np.stack((ox.ravel(), oy.ravel()), axis=1)
    extent = max(1, math.ceil(20 * scale))
    output = []
    for index, candidate in enumerate(candidates):
        x, y = map(round, candidate["center_frame_px"])
        item: dict[str, Any] = {"candidate_index": index, "features": None}
        output.append(item)
        if not (extent <= x < width - extent and extent <= y < height - extent):
            continue
        centers = offsets + [x, y]
        sx = centers[:, 0, None, None] + dx[None, :, :]
        sy = centers[:, 1, None, None] + dy[None, :, :]
        ring = strength[sy, sx]
        inner = ring[:, :3, :].mean(axis=(1, 2))
        outside = ring[:, -2:, :].mean(axis=(1, 2))
        interior = np.clip(gray[sy[:, :3, :], sx[:, :3, :]].std(axis=(1, 2)) / 36, 0, 1)
        # Sector support rewards an enclosing rim, and penalizes a warm filled
        # icon or map surface even if it also contains an outward projection.
        shell = ring[:, 3:10, :].max(axis=1)
        support = shell.mean(axis=1)
        opposing = np.minimum(shell, np.roll(shell, 12, axis=1)).mean(axis=1)
        local = (support + opposing) / 2
        local *= np.clip(1 - inner, 0, 1) * np.clip(1 - outside, 0, 1)
        local *= (.45 + .55 * interior)
        displacement = np.linalg.norm(offsets, axis=1) / max(scale, .1)
        local *= np.clip(1 - displacement / 18, 0, 1)
        best = int(np.argmax(local))
        if local[best] <= 0:
            continue
        radial = ring[best]
        # An extension must continue along the same ray from the rim.
        continuous = np.minimum(radial[7], radial[8])
        extension = np.zeros_like(continuous)
        for step in range(9, len(base_radii)):
            continuous = np.minimum(continuous, radial[step])
            extension += continuous
        tip = int(np.argmax(extension))
        tip_steps = np.flatnonzero(radial[9:, tip] > .12)
        direction_tip = None
        if len(tip_steps) and extension[tip] > 0:
            outer = 9 + int(tip_steps[0])
            while outer + 1 < len(base_radii) and radial[outer+1, tip] > .12:
                outer += 1
            direction_tip = [int(sx[best, outer, tip]), int(sy[best, outer, tip])]
        item["features"] = {
            "portrait_center_frame_px": centers[best].tolist(),
            "warm_shell_support": float(local[best]), "interior_texture": float(interior[best]),
            "opposing_shell_support": float(opposing[best]),
            "direction_support": float(extension[tip] / (len(base_radii) - 9)),
            "direction_tip_frame_px": direction_tip,
        }
    return output


def rank_rim_candidates(
    legacy: list[dict[str, Any]], rims: list[dict[str, Any]], *,
    rim_weight: float, direction_weight: float,
) -> list[dict[str, Any]]:
    """Preserve every input candidate ID in a separate development ranking."""
    if (len(legacy) != len(rims)
            or len({row["candidate_index"] for row in legacy}) != len(rims)):
        raise ValueError("Legacy and rim candidate sets do not agree")
    if any(not math.isfinite(w) or w < 0 for w in (rim_weight, direction_weight)):
        raise ValueError("Weights must be finite and nonnegative")
    output = []
    for row in legacy:
        index = row["candidate_index"]
        if not 0 <= index < len(rims) or rims[index]["candidate_index"] != index:
            raise ValueError("Legacy and rim candidate indexes do not agree")
        feature = rims[index]["features"]
        support = feature["warm_shell_support"] if feature else 0.0
        direction = feature["direction_support"] if feature else 0.0
        output.append({
            "candidate_index": index, "score": row["score"] + rim_weight * support
            + direction_weight * support * direction,
            "rim_support": support, "direction_support": direction,
            "method": VERSION, "qualified": False, "ownership": "UNKNOWN",
            "position_authority": False,
        })
    return sorted(output, key=lambda row: (-row["score"], row["candidate_index"]))
