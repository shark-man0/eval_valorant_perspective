"""Research selection from Map pixels and read-only shared timeline context."""

from __future__ import annotations

import hashlib
import math
from collections.abc import Sequence
from dataclasses import dataclass
from fractions import Fraction
from typing import Any

import cv2
import numpy as np
from numpy.typing import NDArray

from .evidence import digest, freeze_native_sample, native_time, source_scope
from .map_marker_geometry import MarkerGeometry, measure_marker_geometry, same_marker
from .map_portrait_rim import Reference
from .map_recorder_camera import measure_recorder_view
from .map_rim_ranking import measure_warm_rims, rank_rim_candidates
from .map_shape_ranking import rank_marker_context
from .visual_state import selected_agent

VERSION = "development_map_recorder_selection_v1"


@dataclass(frozen=True)
class _Witness:
    sample: dict[str, Any]
    anchor: str
    round_token: str | None
    marker: MarkerGeometry
    count: int
    appearance: NDArray[np.float32] | None
    measured_tips: tuple[bool, ...]


class MapRecorderSelector:
    """Read current native pixels and the shared context for the exact same sample."""

    def __init__(
        self, references: Sequence[Reference], *, recover_supported_portraits: bool = False,
    ) -> None:
        self._recover_supported_portraits = recover_supported_portraits
        self._references = tuple((name, patch.copy()) for name, patch in references)
        self._previous: _Witness | None = None

    def reset(self) -> None:
        self._previous = None

    def observe(
        self, image: NDArray[np.uint8], pool: list[dict[str, Any]],
        sample: dict[str, Any], timeline: dict[str, Any], *,
        observations: Sequence[dict[str, Any]] = (),
    ) -> dict[str, Any]:
        previous, self._previous = self._previous, None
        sample = freeze_native_sample(sample)
        context = freeze_native_sample(timeline["sample"])
        candidate_digest = digest(pool)
        result: dict[str, Any] = {
            "contract": VERSION,
            "sample_sha256": sample["sample_sha256"],
            "ordered_candidate_pool_digest": candidate_digest,
            "selection_status": "ABSTAIN",
            "selection_reason": "unmatched_native_context",
            "research_candidate_index": None,
            "research_marker_center_frame_px": None,
            "support_count": 0,
            "support_candidate_index": None,
            "support_center_frame_px": None,
            "ownership": "UNKNOWN", "qualified": False, "position_authority": False,
        }
        if (
            sample != context
            or not isinstance(image, np.ndarray) or image.ndim != 3 or image.shape[2] != 3
            or image.dtype != np.uint8 or list(image.shape[:2][::-1]) != sample["frame_size_px"]
            or hashlib.sha256(image.tobytes()).hexdigest() != sample["native_pixel_sha256"]
        ):
            return result
        if (timeline.get("camera", {}).get("value") != "SELF"
                or timeline.get("life", {}).get("value") != "ALIVE"):
            result["selection_reason"] = "self_alive_context_required"
            return result
        view = timeline.get("viewed_identity") or {}
        anchor = view.get("recording_player_anchor")
        measured_view, veto = measure_recorder_view(timeline, observations)
        if veto:
            result["selection_reason"] = "current_view_evidence_conflicts"
            return result
        agent = None
        anchor_identity = None
        if anchor:
            origin = freeze_native_sample(anchor["sample"])
            if (source_scope(origin) == source_scope(sample)
                    and native_time(origin) < native_time(sample) and anchor.get("evidence_ids")):
                agent = selected_agent(anchor.get("agent_candidates", []))
                anchor_identity = digest(anchor)
        viewed_agent = selected_agent(view.get("viewed_agent_candidates", []))
        if measured_view is None:
            if anchor_identity is None or agent is None:
                result["selection_reason"] = (
                    "recorder_anchor_unusable" if anchor else "recorder_anchor_missing"
                )
                return result
            if view.get("agent_signature_relation") != "COMPATIBLE" or viewed_agent != agent:
                result["selection_reason"] = "current_view_not_bound_to_recorder"
                return result
        elif view.get("agent_signature_relation") == "DIFFERENT" or (
            agent is not None and viewed_agent is not None and viewed_agent != agent
        ):
            result["selection_reason"] = "current_view_not_bound_to_recorder"
            return result
        else:
            anchor_identity = measured_view
        if not pool:
            result["selection_reason"] = "no_marker_candidates"
            return result
        mapped = timeline.get("map") or {}
        v2 = mapped.get("research_recorder_marker_v2") or {}
        supplied = v2.get("ordered_candidate_pool_digest")
        if ((supplied is not None and supplied != candidate_digest)
                or (supplied is None and mapped.get("candidates") != pool)):
            result["selection_reason"] = "different_candidate_pool"
            return result
        if measured_view is None and not mapped.get("current_recorder_view_evidence_ids"):
            result["selection_reason"] = "current_recorder_view_unobserved"
            return result

        rims = measure_warm_rims(image, pool)
        ranked = rank_rim_candidates(
            rank_marker_context(image, pool), rims,
            rim_weight=6, direction_weight=2,
        )
        top = ranked[0]
        index = top["candidate_index"]
        # Include candidates near the top portrait even if their rank is low;
        # an overlapping candidate is relevant regardless of its score.
        scale = image.shape[1] / 1920
        contenders = [
            row for row in ranked
            if top["score"] - row["score"] <= .35
            or math.dist(pool[index]["center_frame_px"],
                         pool[row["candidate_index"]]["center_frame_px"]) <= 16 * scale
        ]
        fitted = measure_marker_geometry(
            image, [pool[row["candidate_index"]] for row in contenders], self._references,
        )
        marker = fitted[0]
        expected_agent = agent or viewed_agent
        if (
            self._recover_supported_portraits and measured_view and previous
            and any(previous.measured_tips)
            and _adjacent(previous, sample, measured_view, timeline)
            and not _clear_current_marker(marker, top)
        ):
            recovered = self._recover_marker(
                image, pool, ranked, rims, previous, sample, expected_agent, scale,
            )
            if recovered is not None:
                contenders, fitted = recovered
                top, marker = contenders[0], fitted[0]
                index = top["candidate_index"]
                result["portrait_recovered_from_continuity"] = True
        recovered_portrait = result.get("portrait_recovered_from_continuity") is True
        if marker is None or (not recovered_portrait and (
            marker.support < .70 or (
                marker.tip is None and (measured_view is None or marker.support < .78)
            )
        )):
            result["selection_reason"] = "top_portrait_unresolved"
            return result
        marker_agent = selected_agent(list(marker.agent_candidates))
        if measured_view is None and marker_agent != agent:
            result["selection_reason"] = "top_portrait_or_agent_unresolved"
            return result
        if measured_view is not None and (
            marker.palette != "WARM" or top["rim_support"] < .35
            or (marker_agent and expected_agent and marker_agent != expected_agent)
        ):
            result["selection_reason"] = "recorder_portrait_evidence_unresolved"
            return result
        for row, rival in zip(contenders[1:], fitted[1:], strict=True):
            if rival is not None and same_marker(marker, rival):
                continue
            rival_center = (rival.center if rival
                            else pool[row["candidate_index"]]["center_frame_px"])
            distance = math.dist(marker.center, rival_center)
            if (rival is not None and distance <= marker.radius * 2
                    or rival is None and row["rim_support"] >= .35 and distance <= marker.radius * 2
                    or (not recovered_portrait and top["score"] - row["score"] <= .25)):
                result["selection_reason"] = "competing_marker_or_overlap"
                return result

        assert anchor_identity is not None
        appearance = _portrait_appearance(image, marker) if measured_view else None
        round_token = timeline.get("round_token")
        count = 1
        measured_tips: tuple[bool, ...] = (marker.tip is not None,)
        if previous is not None:
            gap = native_time(sample) - native_time(previous.sample)
            if (
                _adjacent(previous, sample, anchor_identity, timeline)
                and previous.marker.palette == marker.palette
                and (measured_view is None or _appearance_agrees(previous.appearance, appearance))
                and math.dist(previous.marker.center, marker.center) <= scale * (3 + 35*float(gap))
            ):
                count = previous.count + 1
                measured_tips = (*previous.measured_tips[-2:], marker.tip is not None)
        self._previous = _Witness(
            sample, anchor_identity, round_token, marker, count, appearance, measured_tips,
        )
        result["support_count"] = count
        result["support_candidate_index"] = index
        result["support_center_frame_px"] = list(marker.center)
        if count < 3:
            result["selection_reason"] = "insufficient_consecutive_native_support"
            return result
        if not any(measured_tips):
            result["selection_reason"] = "attached_tip_not_seen_in_last_three_observations"
            return result
        result["recorder_agent_candidate"] = (
            expected_agent if marker_agent and marker_agent == expected_agent else None
        )
        return {
            **result,
            "selection_status": "RESEARCH_SELECTED",
            "selection_reason": (
                "measured_recorder_hud_and_consecutive_map_portrait" if measured_view
                else "recorder_anchor_and_consecutive_portrait_geometry"
            ),
            "research_candidate_index": index,
            "research_marker_center_frame_px": list(marker.center),
        }


    def _recover_marker(
        self, image: NDArray[np.uint8], pool: list[dict[str, Any]],
        ranked: list[dict[str, Any]], rims: list[dict[str, Any]],
        previous: _Witness, sample: dict[str, Any],
        expected_agent: str | None, scale: float,
    ) -> tuple[list[dict[str, Any]], list[MarkerGeometry | None]] | None:
        # Check all candidate IDs in the local neighborhood, including dim or
        # lower-ranked competitors. The published single-frame order is independent.
        gap = float(native_time(sample) - native_time(previous.sample))
        reach = scale * (3 + 35 * gap)
        local = [
            row for row in ranked
            if math.dist(pool[row["candidate_index"]]["center_frame_px"], previous.marker.center)
            <= reach + 17 * scale
        ]
        fitted = measure_marker_geometry(
            image, [pool[row["candidate_index"]] for row in local], self._references,
        )
        match: list[int] = []
        for i, (row, marker) in enumerate(zip(local, fitted, strict=True)):
            if marker is not None and marker.palette != "WARM":
                continue
            if marker is not None and expected_agent:
                fitted_agent = selected_agent(list(marker.agent_candidates))
                if fitted_agent is not None and fitted_agent != expected_agent:
                    continue
            if marker is None or not _clear_current_marker(marker, row):
                measured = rims[row["candidate_index"]]["features"]
                if measured is None:
                    continue
                marker = _partial_portrait(image, measured, previous.marker.radius)
                if marker is None:
                    continue
                fitted[i] = marker
            if math.dist(marker.center, previous.marker.center) > reach:
                continue
            observed_agent = selected_agent(list(marker.agent_candidates))
            if expected_agent and observed_agent and expected_agent != observed_agent:
                continue
            if not _appearance_agrees(
                previous.appearance, _portrait_appearance(image, marker), minimum=.90,
            ):
                continue
            if all(not same_marker(marker, rival) for j in match if (rival := fitted[j])):
                match.append(i)
        if len(match) != 1:
            return None
        chosen = match[0]
        return [local[chosen], *local[:chosen], *local[chosen+1:]], [
            fitted[chosen], *fitted[:chosen], *fitted[chosen+1:],
        ]


def _partial_portrait(
    image: NDArray[np.uint8], rim: dict[str, Any], previous_radius: float,
) -> MarkerGeometry | None:
    # This is a current image observation. It cannot serve as evidence of an
    # attached tip or start a track without a recent fully fitted observation.
    if rim["warm_shell_support"] < .35 or rim["opposing_shell_support"] < .30:
        return None
    x, y = rim["portrait_center_frame_px"]
    extent = math.ceil(previous_radius + 2)
    patch = image[y-extent:y+extent+1, x-extent:x+extent+1]
    if patch.shape[:2] != (2 * extent + 1, 2 * extent + 1):
        return None
    hue, sat, value = cv2.split(cv2.cvtColor(patch, cv2.COLOR_BGR2HSV))
    py, px = np.indices(hue.shape) - extent
    annulus = np.abs(np.hypot(px, py) - previous_radius) <= 1.75
    support = annulus & (hue >= 13) & (hue <= 42) & (sat >= 25) & (value >= 145)
    ys, xs = np.nonzero(support)
    if len(xs) < .30 * int(annulus.sum()):
        return None
    return MarkerGeometry(
        (x, y), previous_radius, "WARM",
        frozenset(zip((xs+x-extent).tolist(), (ys+y-extent).tolist(), strict=True)),
        rim["warm_shell_support"], None, (),
    )


def _clear_current_marker(marker: MarkerGeometry | None, row: dict[str, Any]) -> bool:
    return bool(
        marker and marker.palette == "WARM"
        and marker.support >= (.70 if marker.tip is not None else .78)
        and row["rim_support"] >= .35
    )


def _adjacent(
    previous: _Witness, sample: dict[str, Any], anchor: str, timeline: dict[str, Any],
) -> bool:
    return (
        0 < native_time(sample) - native_time(previous.sample) <= Fraction(1, 4)
        and source_scope(previous.sample) == source_scope(sample)
        and previous.sample["native_pixel_sha256"] != sample["native_pixel_sha256"]
        and timeline.get("continuity", {}).get("carry_allowed") is True
        and previous.anchor == anchor
        and previous.round_token == timeline.get("round_token")
    )


def _portrait_appearance(
    image: NDArray[np.uint8], marker: MarkerGeometry,
) -> NDArray[np.float32]:
    x, y = marker.center
    half = max(1, round(marker.radius * .55))
    patch = image[y-half:y+half+1, x-half:x+half+1]
    gray = cv2.cvtColor(patch, cv2.COLOR_BGR2GRAY)
    normalized = cv2.resize(gray, (9, 9), interpolation=cv2.INTER_LINEAR).astype(np.float32)
    return normalized - normalized.mean()


def _appearance_agrees(
    a: NDArray[np.float32] | None, b: NDArray[np.float32] | None, *, minimum: float = .80,
) -> bool:
    if a is None or b is None:
        return False
    norm = float(np.linalg.norm(a) * np.linalg.norm(b))
    return norm > 0 and float(np.sum(a * b)) >= minimum * norm
