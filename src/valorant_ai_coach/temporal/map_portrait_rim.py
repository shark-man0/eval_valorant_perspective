"""Candidate-local measurements of a portrait enclosed by a directional rim.

Development evidence only. The shared timeline remains the owner of player state.
"""
from __future__ import annotations

import hashlib
import math
from collections import defaultdict
from collections.abc import Sequence
from typing import Any, cast

import cv2
import numpy as np
from numpy.typing import NDArray

from .evidence import digest, freeze_native_sample, native_time, source_scope
from .visual_state import selected_agent

VERSION = "development_map_portrait_rim_v1"
Reference = tuple[str, NDArray[np.uint8]]


def measure_portrait_rims(
    image: NDArray[np.uint8], candidates: list[dict[str, Any]],
    references: Sequence[Reference] = (),
) -> dict[str, Any]:
    """Keep the input candidate order and record evidence for each original ID."""
    if image.dtype != np.uint8 or image.ndim != 3 or image.shape[2] != 3:
        raise ValueError("Native BGR frame required")
    height, width = image.shape[:2]
    hsv = cast(NDArray[np.uint8], cv2.cvtColor(image, cv2.COLOR_BGR2HSV))
    scale = width / 1920
    radius = max(2, round(8 * scale))
    extent = radius * 3
    rows = []
    for index, candidate in enumerate(candidates):
        center = candidate.get("center_frame_px")
        if (
            not isinstance(center, list)
            or len(center) != 2
            or any(type(value) not in (int, float) or not math.isfinite(value) for value in center)
        ):
            raise ValueError("Finite native candidate center required")
        x, y = map(round, center)
        features = None
        if extent <= x < width - extent and extent <= y < height - extent:
            bounds = (slice(y - extent, y + extent + 1), slice(x - extent, x + extent + 1))
            features = _measure_patch(
                image[bounds], hsv[bounds], radius, references, (x - extent, y - extent)
            )
            if features:
                cx, cy = features.pop("center_patch_px")
                features["center_frame_px"] = [x - extent + cx, y - extent + cy]
        rows.append({"candidate_index": index, "features": features})
    return {
        "contract": VERSION, "candidates": rows,
        "ordered_candidate_pool_digest": digest(candidates),
        "native_pixel_sha256": hashlib.sha256(image.tobytes()).hexdigest(),
        "frame_size_px": [width, height], "qualified": False, "ownership": "UNKNOWN",
    }


def _measure_patch(
    bgr: NDArray[np.uint8], hsv: NDArray[np.uint8], radius: int,
    references: Sequence[Reference], origin: tuple[int, int],
) -> dict[str, Any] | None:
    """Require one connected color component to support both shape measurements."""
    hue, sat, value = cv2.split(hsv)
    cy = cx = radius * 3
    y, x = np.indices(hue.shape)
    components: list[tuple[float, int, int, dict[str, Any]]] = []
    # These are hue classes for measuring perimeter geometry, not team labels.
    for low, high in ((13, 42), (73, 107), (0, 12), (108, 169), (170, 179)):
        mask = ((hue >= low) & (hue <= high) & (sat >= 45) & (value >= 145)).astype(np.uint8)
        count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
        for tag in range(1, count):
            if not radius <= stats[tag, cv2.CC_STAT_AREA] <= radius * radius * 5:
                continue
            component = labels == tag
            ys, xs = np.nonzero(component)
            first_y = int(ys.min())
            first_x = int(xs.min())
            last_y = int(ys.max())
            last_x = int(xs.max())
            complete = (
                first_y > 0 and first_x > 0
                and last_y < mask.shape[0] - 1 and last_x < mask.shape[1] - 1
            )
            component_id = digest({
                "origin": [origin[0] + first_x, origin[1] + first_y],
                "shape": [last_y - first_y + 1, last_x - first_x + 1],
                "mask": component[first_y:last_y+1, first_x:last_x+1].tobytes().hex(),
            }) if complete else None
            median_hue = float(np.median(hue[component]))
            for oy in (-radius // 3, 0, radius // 3):
                for ox in (-radius // 3, 0, radius // 3):
                    px, py = cx + ox, cy + oy
                    dist = np.hypot(xs-px, ys-py)
                    sector = ((np.arctan2(ys-py, xs-px) + np.pi) * (8/np.pi)).astype(int) % 16
                    distances = np.zeros(16)
                    np.maximum.at(distances, sector, dist)
                    ring = (distances >= .72*radius) & (distances <= 1.8*radius)
                    coverage = float(np.count_nonzero(ring) / 16)
                    if coverage < .5:
                        continue
                    opposite = np.roll(distances, 8)
                    extension = distances - np.maximum(radius, opposite)
                    tip = int(np.argmax(extension))
                    direction = max(0., float(extension[tip] / radius))
                    tip_at = np.flatnonzero((sector == tip) & (dist == distances[tip]))
                    tip_point = (
                        [origin[0] + int(xs[tip_at[0]]), origin[1] + int(ys[tip_at[0]])]
                        if direction > 0 and len(tip_at) else None
                    )
                    interior = ((x-px)**2 + (y-py)**2 <= (.7*radius)**2)
                    texture = min(1., float(np.std(bgr[interior], axis=0).mean() / 48))
                    if texture <= 0:
                        continue
                    # An attached wedge protrudes from an otherwise enclosed
                    # portrait. Include that whole component and its hue.
                    score = coverage * texture * (1 + min(direction, 1.) * coverage)
                    components.append((score, px, py, {
                        "ring_sector_fraction": coverage, "interior_texture": texture,
                        "direction_extension": direction, "direction_sector": tip,
                        "direction_tip_frame_px": tip_point,
                        "component_median_hue": median_hue,
                        "component_area_px": int(stats[tag, cv2.CC_STAT_AREA]),
                        "component_id": component_id,
                    }))
    if not components:
        return None
    score, px, py, rim = max(components, key=lambda item: item[0])
    best = sorted(
        (item[0] for item in components if math.hypot(px-item[1], py-item[2]) >= radius/2),
        reverse=True,
    )
    half = max(1, round(radius * .7))
    portrait = bgr[py-half:py+half+1, px-half:px+half+1]
    gray = cv2.cvtColor(portrait, cv2.COLOR_BGR2GRAY)
    size = gray.shape[0]
    axis = np.arange(size) - half
    circle = np.hypot(axis[:, None], axis[None, :]) <= half
    normalized = gray[circle].astype(np.float32)
    normalized -= normalized.mean()
    norm = float(np.linalg.norm(normalized))
    agents: list[dict[str, Any]] = []
    if norm > 0:
        for name, reference in references:
            target = cv2.resize(reference, (size, size), interpolation=cv2.INTER_AREA)
            vector = target[circle].astype(np.float32)
            vector -= vector.mean()
            denom = norm * float(np.linalg.norm(vector))
            if denom > 0:
                agents.append({"agent": name, "score": float(vector @ normalized / denom)})
    agents.sort(key=lambda item: (-item["score"], item["agent"]))
    return {
        **rim, "structure_score": float(score), "center_patch_px": [px, py],
        "radius_px": radius, "portrait_mean_bgr": portrait[circle].mean(axis=0).tolist(),
        "competing_structure_score": best[0] if best else None,
        "agent_candidates": agents[:3],
    }


def shared_structure_groups(measurement: dict[str, Any]) -> list[list[int]]:
    """Reduce repeated observations of an identical contour and portrait center."""
    matching: dict[tuple[str, tuple[int, int]], list[int]] = defaultdict(list)
    for row in measurement["candidates"]:
        features = row["features"]
        if features is None or features["component_id"] is None:
            continue
        center = tuple(features["center_frame_px"])
        matching[(features["component_id"], center)].append(row["candidate_index"])
    return [indices for indices in matching.values() if len(indices) > 1]


def compare_recorder_anchor(
    measurement: dict[str, Any], pool: list[dict[str, Any]], frame: dict[str, Any],
) -> dict[str, Any]:
    """Compare two agent readings at a bound frame without asserting ownership."""
    sample = freeze_native_sample(frame["sample"])
    if (
        measurement["native_pixel_sha256"] != sample["native_pixel_sha256"]
        or measurement["frame_size_px"] != sample["frame_size_px"]
        or measurement["ordered_candidate_pool_digest"] != digest(pool)
    ):
        raise ValueError("Map portrait evidence and timeline carrier do not match")
    anchor = (frame.get("viewed_identity") or {}).get("recording_player_anchor")
    agent = None
    camera_life_eligible = (
        frame["camera"]["value"] == "SELF" and frame["life"]["value"] == "ALIVE"
    )
    if anchor and camera_life_eligible:
        origin = freeze_native_sample(anchor["sample"])
        if (
            source_scope(origin) == source_scope(sample)
            and native_time(origin) <= native_time(sample)
        ):
            agent = selected_agent(anchor["agent_candidates"])
    agreement = []
    if agent is not None:
        for row in measurement["candidates"]:
            features = row["features"]
            templates = features["agent_candidates"] if features else []
            if templates and templates[0]["agent"] == agent:
                agreement.append(row["candidate_index"])
    return {
        "contract": VERSION, "sample_sha256": sample["sample_sha256"],
        "camera_life_eligible": camera_life_eligible,
        "agent": agent, "agent_agreement_candidate_indices": agreement,
        "ownership": "UNKNOWN", "qualified": False, "recorder_proposed_index": None,
    }
