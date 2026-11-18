"""Development-only dense portrait search and separate recorder identity evidence."""

from __future__ import annotations

import hashlib
import math
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from typing import Any, cast

import cv2
import numpy as np
from numpy.typing import NDArray

from .evidence import digest, freeze_native_sample, native_time, source_scope
from .map_recorder_camera import measure_recorder_view
from .visual_state import selected_agent

ColorImage = NDArray[np.uint8]
VERSION = "map_direct_portrait_v1"


@dataclass(frozen=True)
class RecorderUUID:
    source_sha256: str
    uuid: str
    evidence_samples: tuple[str, ...]

    @classmethod
    def bind(
        cls, evidence: Sequence[tuple[dict[str, Any], str]],
    ) -> RecorderUUID | None:
        """Use at least three spaced, measured own-HUD readings from one Source."""
        if not evidence:
            return None
        rows = [(freeze_native_sample(sample), value) for sample, value in evidence]
        sources = {sample["source_sha256"] for sample, _ in rows}
        if len(sources) != 1:
            raise ValueError("Recorder identity must bind one source")
        seen_pixels: set[str] = set()
        votes: Counter[str] = Counter()
        distinct: list[tuple[dict[str, Any], str]] = []
        last_time: Fraction | None = None
        for sample, value in sorted(rows, key=lambda row: native_time(row[0])):
            when = native_time(sample)
            if (sample["native_pixel_sha256"] in seen_pixels
                    or (last_time is not None and when - last_time < 2)):
                continue
            seen_pixels.add(sample["native_pixel_sha256"])
            votes[value] += 1
            distinct.append((sample, value))
            last_time = when
        if not votes:
            return None
        uuid, count = votes.most_common(1)[0]
        second = votes.most_common(2)[1][1] if len(votes) > 1 else 0
        if count < 3 or count / len(distinct) < .80 or count - second < 3:
            return None
        return cls(sources.pop(), uuid, tuple(s["sample_sha256"] for s, u in distinct if u == uuid))


@dataclass(frozen=True)
class DirectPeak:
    center: tuple[int, int]
    response: float
    warm_sectors: int
    opposite_pairs: int
    chromatic_rivals: int


def measured_direct_view(
    frame: dict[str, Any], observations: Sequence[dict[str, Any]],
) -> str | None:
    """The static recorder UUID cannot supply current Camera or Life evidence."""
    if (frame.get("camera", {}).get("value") != "SELF"
            or frame.get("life", {}).get("value") != "ALIVE"):
        return None
    current, veto = measure_recorder_view(frame, observations)
    return None if veto else current


class DensePortraitSearch:
    """Search every supported minimap pixel, without candidate circles or Hough."""

    def __init__(
        self, templates: Sequence[tuple[str, ColorImage]], *, augment: bool,
        fast_search: bool = False,
        rim_guided: bool = False,
        learned_templates: Mapping[str, ColorImage] | None = None,
    ) -> None:
        self.rim_guided = rim_guided
        self._fast = fast_search
        self._templates: dict[str, list[ColorImage]] = {}
        for uuid, portrait in templates:
            bgr = portrait[:, :, :3]
            if not bgr.size:
                continue
            if portrait.shape[2] == 4:
                ys, xs = np.nonzero(portrait[:, :, 3] > 100)
                if len(xs):
                    bgr = bgr[ys.min():ys.max()+1, xs.min():xs.max()+1]
            keep = self._templates.setdefault(uuid, [])
            sizes = (11, 13, 15, 17, 19) if augment else (13, 15, 17)
            for size in sizes:
                scaled = cv2.resize(bgr, (size, size), interpolation=cv2.INTER_AREA)
                half = (size - 9) // 2
                shifts: tuple[tuple[int, int], ...] = ((0, 0),)
                if augment and (not fast_search or size == 15):
                    shifts = (*shifts, (-1, 0), (1, 0), (0, -1), (0, 1))
                for dx, dy in shifts:
                    x, y = half + dx, half + dy
                    patch = np.ascontiguousarray(scaled[y:y+9, x:x+9], dtype=np.uint8)
                    if patch.shape == (9, 9, 3) and np.std(patch, axis=(0, 1)).mean() >= 12:
                        keep.append(patch)
        for uuid, patch in (learned_templates or {}).items():
            if (patch.shape != (9, 9, 3) or patch.dtype != np.uint8
                    or np.std(patch, axis=(0, 1)).mean() < 12 or uuid not in self._templates):
                raise ValueError("Learned kernel must be a textured 9×9 color template")
            self._templates[uuid].append(patch.copy())
        self._search_templates = self._templates if not fast_search else {
            uuid: [cv2.cvtColor(patch, cv2.COLOR_BGR2GRAY) for patch in patches]
            for uuid, patches in self._templates.items()
        }

    def anchor_templates(self) -> list[tuple[str, ColorImage]]:
        """Expose external augmentation patches for an isolated training experiment."""
        return [(uuid, patch.copy()) for uuid, rows in self._templates.items() for patch in rows]

    def peaks(
        self, roi: ColorImage, uuid: str, *, scale: float, count: int = 12,
    ) -> list[DirectPeak]:
        height, width = roi.shape[:2]
        half = max(2, round(4 * scale))
        size = 2 * half + 1
        extent = math.ceil(12 * scale)
        minimum_side = max(size, 2 * extent + 2)
        if min(height, width) < minimum_side or not self._search_templates.get(uuid):
            return []
        scored = np.full((height-size+1, width-size+1), -1.0, np.float32)
        image = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY) if self._fast else roi
        for reference in self._search_templates[uuid]:
            patch = reference if size == 9 else cv2.resize(reference, (size, size))
            response = cv2.matchTemplate(image, patch, cv2.TM_CCOEFF_NORMED)
            np.maximum(scored, response, out=scored)
        hsv = cast(ColorImage, cv2.cvtColor(roi, cv2.COLOR_BGR2HSV))
        if self.rim_guided:
            # Sparse yellow pixels on opposite arcs can survive partial occlusion.
            # Apply the spatial prior before NMS so unrelated UI cannot spend the peak budget.
            warm_mask = cv2.inRange(hsv, (13, 32, 152), (42, 255, 255))
            radius = max(2, round(8 * scale))
            kernel = np.zeros((2*radius+1, 2*radius+1), np.uint8)
            cv2.circle(kernel, (radius, radius), radius, 1, max(1, round(3*scale)))
            votes = cv2.filter2D(warm_mask // 255, cv2.CV_32F, kernel)
            scored[votes[half:height-half, half:width-half] < 4] = -1
        fence = extent - half
        if fence > 0:
            scored[:fence] = scored[-fence:] = -1
            scored[:, :fence] = scored[:, -fence:] = -1
        results = []
        reach = max(3, round(7 * scale))
        for _ in range(count):
            _, score, _, point = cv2.minMaxLoc(scored)
            if score < .60:
                break
            tx, ty = point
            x, y = tx + half, ty + half
            warm, pairs, rivals = _rim_evidence(hsv, x, y, scale)
            results.append(DirectPeak((x, y), score, warm, pairs, rivals))
            scored[max(0, ty-reach):ty+reach+1, max(0, tx-reach):tx+reach+1] = -1
        return results


def _rim_evidence(
    hsv: ColorImage, x: int, y: int, scale: float,
) -> tuple[int, int, int]:
    angles = np.arange(16) * (math.tau / 16)
    radii = np.arange(5, 12)[:, None] * scale
    xs = x + np.rint(radii * np.cos(angles)).astype(int)
    ys = y + np.rint(radii * np.sin(angles)).astype(int)
    hue, sat, light = np.moveaxis(hsv[ys, xs], -1, 0)
    warm = ((hue >= 13) & (hue <= 42) & (sat >= 32) & (light >= 152)).any(axis=0)
    rival = (((hue <= 10) | ((hue >= 73) & (hue <= 104)))
             & (sat >= 105) & (light >= 180)).any(axis=0)
    return int(warm.sum()), int((warm[:8] & warm[8:]).sum()), int(rival.sum())


@dataclass(frozen=True)
class _Witness:
    sample: dict[str, Any]
    round_token: str | None
    camera: str
    center: tuple[int, int]
    count: int


class DirectRecorderTracker:
    """Validate observed direct peaks against the binding and exact view gate."""

    def __init__(
        self, search: DensePortraitSearch, identity: RecorderUUID, portrait_reader: Any, *,
        fallback_search: DensePortraitSearch | None = None,
        compare_centers: bool = False,
    ):
        self.compare_centers = compare_centers
        self.search = search
        self.fallback_search = fallback_search
        self.identity = identity
        self.portrait_reader = portrait_reader
        self.previous: _Witness | None = None

    def observe(
        self, image: ColorImage, roi_xyxy: tuple[int, int, int, int],
        frame: dict[str, Any], observations: Sequence[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        sample = freeze_native_sample(frame["sample"])
        camera = measured_direct_view(frame, observations)
        if camera is not None and (
            image.shape[:2][::-1] != tuple(sample["frame_size_px"])
            or digest_pixels(image) != sample["native_pixel_sha256"]
        ):
            camera = None
        return self._observe_measured(image, roi_xyxy, sample, frame, camera)

    def _observe_measured(
        self, image: ColorImage, roi_xyxy: tuple[int, int, int, int], sample: dict[str, Any],
        frame: dict[str, Any], camera: str | None,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        previous, self.previous = self.previous, None
        result: dict[str, Any] = {
            "contract": "development_map_recorder_selection_v1",
            "sample_sha256": sample["sample_sha256"],
            "recording_agent_uuid": self.identity.uuid if (
                sample["source_sha256"] == self.identity.source_sha256
            ) else None,
            "selection_status": "ABSTAIN", "selection_reason": "no_current_recorder_view",
            "research_candidate_index": None, "support_candidate_index": None,
            "support_count": 0, "qualified": False, "position_authority": False,
            "ownership": "UNKNOWN", "ordered_candidate_pool_digest": digest([]),
        }
        if camera is None or result["recording_agent_uuid"] is None:
            return [], result
        view = frame.get("viewed_identity") or {}
        if view.get("agent_signature_relation") == "DIFFERENT":
            result["selection_reason"] = "viewed_identity_conflicts_with_recording"
            return [], result
        name = selected_agent(view.get("viewed_agent_candidates", []))
        seen = self.portrait_reader._catalog.agent(name) if name else None
        if seen is not None and seen.uuid != self.identity.uuid:
            result["selection_reason"] = "viewed_identity_conflicts_with_recording"
            return [], result
        left, top, right, bottom = roi_xyxy
        if not (0 <= left < right <= image.shape[1] and 0 <= top < bottom <= image.shape[0]):
            raise ValueError("Valid minimap bounds required")
        scale = image.shape[1] / 1920
        roi = image[top:bottom, left:right]
        peaks = self.search.peaks(roi, self.identity.uuid, scale=scale)
        accepted = self._confirmed_peaks(image, peaks, left, top)
        if self.fallback_search is not None and (not accepted or self.compare_centers):
            additional = self.fallback_search.peaks(roi, self.identity.uuid, scale=scale)
            confirmed = self._confirmed_peaks(image, additional, left, top)
            accepted.extend((i + len(peaks), score, margin) for i, score, margin in confirmed)
            peaks.extend(additional)
        pool = [
            {"center_frame_px": [p.center[0]+left, p.center[1]+top], "proposal_kind": VERSION}
            for p in peaks
        ]
        result["ordered_candidate_pool_digest"] = digest(pool)
        result["selection_reason"] = "direct_portrait_or_rim_unresolved"
        # Shifted renderings may fire a second time inside the same portrait.
        # Keep truly separated peaks as ambiguous irrespective of their rank.
        unique: list[tuple[int, float, float]] = []
        for candidate in sorted(accepted, key=lambda row: (-row[1], row[0])):
            if all(math.dist(peaks[candidate[0]].center, peaks[r[0]].center) > 6*scale
                   for r in unique):
                unique.append(candidate)
        if len(unique) != 1:
            if unique:
                result["selection_reason"] = "ambiguous_direct_portraits"
            return pool, result
        index, score, margin = unique[0]
        chosen = peaks[index]
        center = (chosen.center[0] + left, chosen.center[1] + top)
        count = 1
        round_token = frame.get("round_token")
        if previous is not None:
            gap = native_time(sample) - native_time(previous.sample)
            if (0 < gap <= Fraction(1, 4) and source_scope(sample) == source_scope(previous.sample)
                    and sample["native_pixel_sha256"] != previous.sample["native_pixel_sha256"]
                    and round_token == previous.round_token and camera == previous.camera
                    and frame.get("continuity", {}).get("carry_allowed") is True
                    and math.dist(center, previous.center) <= scale * (3 + 35 * float(gap))):
                count = previous.count + 1
        self.previous = _Witness(sample, round_token, camera, center, count)
        result.update(
            selection_method="knowledge_agent_uuid",
            track_anchor=digest([VERSION, camera, round_token, self.identity.uuid]),
            recorder_agent_uuid_candidate=self.identity.uuid,
            support_candidate_index=index, support_count=count,
            support_center_frame_px=list(center),
        )
        if count < 2 and not (
            score >= .87 and margin >= .20 and chosen.warm_sectors >= 9
            and chosen.opposite_pairs >= 3
        ):
            result["selection_reason"] = "direct_portrait_needs_adjacent_observation"
            return pool, result
        result.update(
            selection_status="RESEARCH_SELECTED",
            selection_reason="dense_portrait_and_measured_view",
            research_candidate_index=index, research_marker_center_frame_px=list(center),
        )
        return pool, result

    def _confirmed_peaks(
        self, image: ColorImage, peaks: Sequence[DirectPeak], left: int, top: int,
    ) -> list[tuple[int, float, float]]:
        accepted = []
        target = self.portrait_reader._uuids.index(self.identity.uuid)
        for index, peak in enumerate(peaks):
            if peak.response < .68 or peak.warm_sectors < 5 or peak.opposite_pairs < 1:
                continue
            center = (peak.center[0]+left, peak.center[1]+top)
            scores = self.portrait_reader._portrait_scores(image, center)
            if scores is None:
                continue
            score = float(scores[target])
            margin = score - float(np.delete(scores, target).max())
            if score >= .77 and margin >= .14 and peak.chromatic_rivals <= 5:
                accepted.append((index, score, margin))
        return accepted


def digest_pixels(image: ColorImage) -> str:
    return hashlib.sha256(image.tobytes()).hexdigest()

def corroborate_direct_selection(
    direct: dict[str, Any], legacy: dict[str, Any], scale: float,
) -> dict[str, Any]:
    """Reconcile independent proposal centers on one current image."""
    if (not direct.get("support_count") or not direct.get("sample_sha256")
            or direct["sample_sha256"] != legacy.get("sample_sha256")):
        return direct
    if legacy.get("selection_reason") == "recorder_selection_conflict":
        conflict = True
    elif legacy.get("selection_status") == "RESEARCH_SELECTED":
        center = legacy.get("support_center_frame_px")
        conflict = center is None or math.dist(center, direct["support_center_frame_px"]) > 5*scale
        uid = legacy.get("recorder_agent_uuid_candidate")
        if uid and uid != direct.get("recording_agent_uuid"):
            conflict = True
        if (not conflict and uid and direct.get("selection_reason")
                == "direct_portrait_needs_adjacent_observation"
                and legacy.get("selection_method") == "knowledge_agent_uuid"
                and legacy.get("knowledge_reason") == "matched_agent_uuid"):
            return {**direct, "selection_status": "RESEARCH_SELECTED",
                    "selection_reason": "current_fitted_marker_agrees",
                    "research_candidate_index": direct["support_candidate_index"],
                    "research_marker_center_frame_px": direct["support_center_frame_px"]}
    else:
        return direct
    if conflict:
        return {**direct, "selection_status": "ABSTAIN",
                "selection_reason": "direct_and_fitted_marker_conflict", "support_count": 0,
                "support_candidate_index": None, "research_candidate_index": None,
                "support_center_frame_px": None, "research_marker_center_frame_px": None}
    return direct
