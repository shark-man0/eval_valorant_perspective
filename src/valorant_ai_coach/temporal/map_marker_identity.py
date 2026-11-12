"""Independent candidate-specific marker evidence; no player ownership authority."""
from __future__ import annotations

import math
from copy import deepcopy
from typing import Any

import cv2
import numpy as np
from numpy.typing import NDArray

from .evidence import digest

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
    ranked: list[dict[str, Any]] = []
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
            if not 3 <= area <= max(150, 320 * scale * scale):
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



def _verified_legacy_rankings(
    frame: dict[str, Any],
    source: dict[str, Any],
    pool: dict[str, Any],
) -> list[dict[str, Any]]:
    """Accept baseline order only from the exact current native Map supplier."""
    bridge = frame["map"].get("marker_ranking_hypotheses")
    if not isinstance(bridge, dict):
        return []
    ranked = bridge.get("rankings")
    if (
        not isinstance(ranked, list)
        or not ranked
        or bridge.get("map_supplier_fingerprint") != pool["producer_fingerprint"]
        or source.get("marker_candidate_supplier") != pool["producer_fingerprint"]
        or source.get("marker_context_rankings") != ranked
    ):
        return []
    pool_size = len(pool["map_candidates"])
    indices: set[int] = set()
    for item in ranked:
        if not isinstance(item, dict):
            return []
        index, score = item.get("candidate_index"), item.get("score")
        if (
            type(index) is not int
            or not 0 <= index < pool_size
            or index in indices
            or type(score) not in (int, float)
            or not math.isfinite(score)
        ):
            return []
        indices.add(index)
    return ranked


def _proximity_groups(
    candidates: list[dict[str, Any]],
    baseline: list[dict[str, Any]],
    width: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Group spatially adjacent proposals; proximity is NOT physical identity.

    A group's anchor is the earliest baseline candidate. Never join by a
    chain of progressively offset coordinates, and never relabel an actor.
    The alternative ranking distributes distinct locations first, while the
    original baseline order is retained unchanged as the primary metric.
    """
    radius = max(4.0, 8.0 * width / 1920)
    groups: list[dict[str, Any]] = []
    membership: dict[int, int] = {}
    baseline_lookup: dict[int, int] = {}
    for original_rank, item in enumerate(baseline, 1):
        index = item["candidate_index"]
        baseline_lookup[index] = original_rank
        x, y = candidates[index]["center_frame_px"]
        assigned = False
        for group_id, group in enumerate(groups):
            anchor = group["representative_candidate_index"]
            ax, ay = candidates[anchor]["center_frame_px"]
            if math.hypot(x - ax, y - ay) <= radius:
                group["member_indices"].append(index)
                membership[index] = group_id
                assigned = True
                break
        if not assigned:
            membership[index] = len(groups)
            groups.append({
                "representative_candidate_index": index,
                "member_indices": [index],
                "best_baseline_rank": original_rank,
                "grouping_reason": "nearby_native_proposals_not_marker_identity",
            })
    representatives = [group["representative_candidate_index"] for group in groups]
    used = set(representatives)
    diversified = representatives + [
        item["candidate_index"] for item in baseline
        if item["candidate_index"] not in used
    ]
    ordering = [{
        "candidate_index": index,
        "diversified_rank": rank,
        "original_baseline_rank": baseline_lookup[index],
        "proximity_group_id": membership[index],
    } for rank, index in enumerate(diversified, 1)]
    return groups, ordering


def _safe_candidate_diagnostics(
    frame: dict[str, Any],
    source: dict[str, Any],
    pool: dict[str, Any],
    result: dict[str, Any],
) -> dict[str, Any] | None:
    """Gate image scores, preserve legacy rank and fail closed on pool mismatch."""
    supplied_digest = source.get("marker_identity_pool_digest")
    expected_digest = digest(pool["map_candidates"])
    if supplied_digest != expected_digest:
        return None
    baseline = _verified_legacy_rankings(frame, source, pool)
    if not baseline:
        return None
    sample = frame["sample"]
    width = sample["frame_size_px"][0]
    groups, diversified = _proximity_groups(pool["map_candidates"], baseline, width)
    camera = frame["camera"]["value"]
    life = frame.get("life", {}).get("value")
    camera_eligible = camera == "SELF" and life == "ALIVE"
    existing_roles = frame["map"].get("research_map_correspondence_hypotheses", [])
    role_eligible = any(
        "RECORDER_SELF" in h.get("role_hypotheses", []) for h in existing_roles
    )
    baseline_indices = [item["candidate_index"] for item in baseline]
    raw_indices = [item["candidate_index"] for item in result["rankings"]]
    baseline_top = baseline_indices[0]
    pixel_top = raw_indices[0] if raw_indices else None
    return {
        "contract": "development_map_marker_proof_gate_v2",
        "sample": deepcopy(sample),
        "map_observation_id": pool["observation_id"],
        "visual_observation_id": result["visual_observation_id"],
        "map_supplier_fingerprint": pool["producer_fingerprint"],
        "ordered_candidate_pool_digest": expected_digest,
        "baseline_context_order": baseline_indices,
        "baseline_top_index": baseline_top,
        "pixel_only_top_index": pixel_top,
        "pixel_override_accepted": False,
        "pixel_and_baseline_disagree": pixel_top != baseline_top,
        "proximity_groups": groups,
        "spatial_diversified_order": diversified,
        "spatial_grouping_is_marker_identity": False,
        "camera_life_gate": camera_eligible,
        "self_role_gate": role_eligible,
        "recorder_proposed_index": None,
        "selection_status": "ABSTAIN",
        "abstain_reason": (
            "not_current_recorder_view"
            if not camera_eligible
            else "unverified_current_recorder_view"
            if not role_eligible
            else "no_independent_candidate_recorder_correspondence"
        ),
        "score_scope": "diagnostic_not_probability",
        "ownership": "UNKNOWN",
        "qualified": False,
        "position_authority": False,
        "temporal_path_eligible": False,
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
    source = matches[0]["raw"]
    raw = source["marker_identity_pixels"]
    supplied_digest = source.get("marker_identity_pool_digest")
    if supplied_digest is not None and supplied_digest != digest(pool["map_candidates"]):
        return
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
    # The old pixel-only selector produced a false owner in a SPECTATOR frame.
    # Preserve its output only as a diagnostic; never emit an active selection.
    result["untrusted_pixel_proposal_index"] = result.get("proposed_index")
    result["proposed_index"] = None
    result["selection_status"] = "ABSTAIN"
    result["pixel_proposal_not_owner_proof"] = True
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
    v2 = _safe_candidate_diagnostics(frame, source, pool, result)
    if v2 is not None:
        frame["map"]["research_recorder_marker_v2"] = v2
