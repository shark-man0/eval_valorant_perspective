"""Independent candidate-specific marker evidence; no player ownership authority."""
from __future__ import annotations

import math
from copy import deepcopy
from typing import Any

import cv2
import numpy as np
from numpy.typing import NDArray

VERSION = "development_marker_specific_pixel_rank_v1"
MAX_RANKS = 64


def pixel_rank(
    image: NDArray[np.uint8],
    candidates: list[dict[str, Any]],
    roi: list[int] | None,
) -> dict[str, Any]:
    """Compare central white triangular pixels with nearby colored competitors.

    Scores are uncalibrated measurements, never ownership probabilities.
    The optional ROI must be the current Map supplier's explicit native ROI.
    """
    if image.dtype != np.uint8 or image.ndim != 3 or image.shape[2] != 3:
        raise ValueError("Native BGR frame required")
    height, width = image.shape[:2]
    roi_valid = bool(
        isinstance(roi, list) and len(roi) == 4
        and all(type(v) is int for v in roi)
        and roi[0] >= 0 and roi[1] >= 0
        and roi[2] > 0 and roi[3] > 0
        and roi[0] + roi[2] <= width and roi[1] + roi[3] <= height
    )
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    scale = width / 1920
    radius = max(6, round(12 * scale))
    inner = max(2, round(4 * scale))
    ranked = []
    for index, candidate in enumerate(candidates):
        center = candidate.get("center_frame_px")
        if (
            not isinstance(center, list) or len(center) != 2
            or any(type(v) not in (int, float)
                   or not math.isfinite(float(v)) for v in center)
        ):
            raise ValueError("Finite Map candidate center required")
        x, y = float(center[0]), float(center[1])
        if not 0 <= x < width or not 0 <= y < height:
            raise ValueError("Map candidate outside native frame")
        within = bool(
            roi_valid and roi is not None
            and roi[0] <= x < roi[0] + roi[2]
            and roi[1] <= y < roi[1] + roi[3]
        )
        left, right = max(0, round(x)-radius), min(width, round(x)+radius+1)
        top, bottom = max(0, round(y)-radius), min(height, round(y)+radius+1)
        crop = hsv[top:bottom, left:right]
        hue, saturation, value = crop[:, :, 0], crop[:, :, 1], crop[:, :, 2]
        white = ((saturation <= 70) & (value >= 170)).astype(np.uint8)
        yy, xx = np.ogrid[:crop.shape[0], :crop.shape[1]]
        near = (xx - (x-left))**2 + (yy - (y-top))**2 <= inner**2
        near_total = max(1, int(np.count_nonzero(near)))
        bright = float(np.count_nonzero(white[near]) / near_total)
        saturated = (saturation >= 85) & (value >= 100) & near
        color = {
            "cyan": int(np.count_nonzero(saturated & (hue >= 77) & (hue <= 106))),
            "amber": int(np.count_nonzero(saturated & (hue >= 12) & (hue <= 40))),
            "red": int(np.count_nonzero(saturated & ((hue <= 10) | (hue >= 170)))),
            "other": int(np.count_nonzero(saturated)),
        }
        chroma = max(color.values()) / near_total
        contours, _ = cv2.findContours(
            white, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        triangle = 0.0
        for contour in contours:
            area = float(cv2.contourArea(contour))
            if not 3 <= area <= max(6, 150 * scale * scale):
                continue
            moments = cv2.moments(contour)
            if moments["m00"] <= 0:
                continue
            distance = math.hypot(
                left + moments["m10"] / moments["m00"] - x,
                top + moments["m01"] / moments["m00"] - y,
            )
            if distance >= .75 * radius:
                continue
            hull = float(cv2.contourArea(cv2.convexHull(contour)))
            if hull <= 0:
                continue
            corners = len(cv2.approxPolyDP(
                contour, .055 * cv2.arcLength(contour, True), True
            ))
            triangle = max(
                triangle,
                (1 / (1 + abs(corners-3))) * min(1.0, area / max(3, 12 * scale**2))
                * min(1.0, area / hull) * (1 - distance/radius),
            )
        ranked.append({
            "candidate_index": index,
            "score": round(2*triangle + .5*bright - 1.5*chroma, 5),
            "white_triangle_support": round(triangle, 5),
            "center_white_fraction": round(bright, 5),
            "color_competitor_fraction": round(chroma, 5),
            "central_color_pixels": color,
            "inside_supplier_map_roi": within,
            "method": VERSION, "score_scope": "heuristic_not_probability",
            "ownership": "UNKNOWN", "qualified": False,
        })
    ranked.sort(key=lambda h: (-h["score"], h["candidate_index"]))
    in_map = [h for h in ranked if h["inside_supplier_map_roi"]]
    chosen = None
    if in_map:
        first = in_map[0]
        second = in_map[1] if len(in_map) > 1 else None
        margin = first["score"] - second["score"] if second else math.inf
        xy = candidates[first["candidate_index"]]["center_frame_px"]
        nearby = any(
            h["candidate_index"] != first["candidate_index"]
            and math.hypot(
                candidates[h["candidate_index"]]["center_frame_px"][0]-xy[0],
                candidates[h["candidate_index"]]["center_frame_px"][1]-xy[1],
            ) <= max(5, 7*scale)
            for h in in_map
        )
        if (first["score"] >= 1.05 and first["white_triangle_support"] >= .4
                and first["color_competitor_fraction"] <= .12
                and margin >= .45 and not nearby):
            chosen = first["candidate_index"]
    return {
        "contract": VERSION, "rankings": ranked[:MAX_RANKS],
        "candidate_count": len(candidates),
        "explicit_map_roi_present": roi_valid,
        "proposed_index": chosen,
        "selection_status": "PROVISIONAL_UNQUALIFIED" if chosen is not None else "ABSTAIN",
        "ownership": "UNKNOWN", "qualified": False,
        "position_authority": False,
    }


def attach_rank(
    frame: dict[str, Any],
    rows: list[dict[str, Any]],
    pool: dict[str, Any],
) -> None:
    """Join same native visual supplier once; never change common camera state."""
    supplier = pool["producer_fingerprint"]
    matches = [
        r for r in rows
        if r.get("sample") == frame["sample"]
        and r["raw"].get("schema") == "development_composite_view_pixels_v1"
        and r["raw"].get("marker_identity_supplier") == supplier
        and isinstance(r["raw"].get("marker_identity_pixels"), dict)
    ]
    if len(matches) != 1:
        return
    raw = matches[0]["raw"]["marker_identity_pixels"]
    proposals = raw.get("rankings")
    if not isinstance(proposals, list):
        return
    indices = [h.get("candidate_index") for h in proposals if isinstance(h, dict)]
    if (len(indices) != len(proposals) or len(set(indices)) != len(indices)
            or raw.get("candidate_count") != len(pool["map_candidates"])
            or any(type(i) is not int or not 0 <= i < len(pool["map_candidates"])
                   for i in indices)):
        return
    result = deepcopy(raw)
    result["rankings"] = [
        {
            **deepcopy(h),
            "candidate": deepcopy(pool["map_candidates"][h["candidate_index"]]),
        }
        for h in proposals
    ]
    result["sample"] = deepcopy(frame["sample"])
    result["map_observation_id"] = pool["observation_id"]
    result["visual_observation_id"] = matches[0]["observation_id"]
    result["camera_candidate"] = frame["camera"]["value"]
    result["role_hypotheses"] = (
        ["RECORDER_SELF", "OTHER", "UNKNOWN"]
        if any(
            "RECORDER_SELF" in h.get("role_hypotheses", [])
            for h in frame["map"].get("research_map_correspondence_hypotheses", [])
        )
        else ["SPECTATED_ACTOR", "OTHER", "UNKNOWN"]
        if frame["camera"]["value"] == "SPECTATOR"
        else ["VIEWED_ACTOR", "OTHER", "UNKNOWN"]
    )
    result["evidence_ids"] = sorted(set(
        [pool["observation_id"], matches[0]["observation_id"]]
        + frame["camera"].get("evidence_ids", [])
    ))
    result["temporal_path_eligible"] = False
    frame["map"]["research_marker_identity_ranking"] = result
