"""Development-only Map observations measured on the canonical timeline's own samples.

The Map library (#186) measured the minimap on its own acquisition of each source video.
Those samples have other pixel and sample hashes than the repaired common timeline, so
``load_map_timeline`` cannot bind them (#191 connected them by source time instead).

This pass binds exactly. Every observation it writes is measured on a frame that was
decoded again from the source with the timeline's own native decode and whose
``native_pixel_sha256`` equals the timeline sample's. The report carries the timeline
file's SHA-256 and each point carries the timeline's own frozen sample, so the unchanged
``load_map_timeline`` accepts it.

Two methods fill a point; each point names its method:

``self_ring``
    The game's own-player highlight (``map_self_ring``) read on the canonical minimap,
    without portrait classification. Ownership comes from the timeline: only frames
    whose native sample and both bracketing seconds observe camera ``SELF`` and life
    ``ALIVE`` are read.
``map_library_rim``
    A Map library observation at the identical native PTS whose position, mapped back
    onto the canonical minimap, still shows the existing tracker's rim evidence
    (at least five warm sectors and one opposite pair) on the canonical pixels.

Both need a registration of the canonical minimap to the Map reference image. A frame is
registered by the existing public-reference matcher (``PublicMapPixels``) on its own
pixels, or by one of the recording's registration modes (built from those per-frame fits)
when the frame's floor agrees with that mode clearly better than with the others.

Nothing is promoted. Points stay ``qualified: false`` and ``position_authority: false``.
"""

from __future__ import annotations

import hashlib
import math
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import cv2
import numpy as np
from numpy.typing import NDArray

from .evidence import digest, freeze_native_sample, is_sha
from .map_recorder_path import (
    VERSION as PATH_VERSION,
)
from .map_recorder_path import (
    ReferenceZones,
    build_recorder_paths,
    join_recorder_seconds,
)
from .map_self_ring import VERSION as RING_VERSION
from .map_self_ring import RingParameters, read_self_ring, warm_mask

PASS_VERSION = "development_canonical_map_pass_v1"
RIM_METHOD = "map_library_rim"
RING_METHOD = "self_ring"
ROI_1080P = (20, 48, 475, 475)

ColorImage = NDArray[np.uint8]


def _observed(state: Mapping[str, Any] | None, value: str) -> bool:
    return (state is not None and state.get("value") == value
            and state.get("status") == "OBSERVED")


def own_live_samples(timeline: Mapping[str, Any]) -> dict[str, int]:
    """Canonical samples whose frame and both bracketing seconds observe SELF/ALIVE.

    Returns sample SHA-256 -> second. The bracket rule is the one #191 uses: a death,
    a switch to spectating or a return between two samples leaves one of them changed.
    """
    seconds = timeline["seconds"]
    frames = timeline["native_frames"]
    result: dict[str, int] = {}
    for index, row in enumerate(seconds):
        following = seconds[index + 1] if index + 1 < len(seconds) else None
        if not (
            _observed(row.get("camera_state"), "SELF") and _observed(row.get("life_state"), "ALIVE")
            and following is not None
            and _observed(following.get("camera_state"), "SELF")
            and _observed(following.get("life_state"), "ALIVE")
        ):
            continue
        for key in row.get("sample_refs", ()):
            frame = frames.get(key, {})
            if (frame.get("camera", {}).get("value") == "SELF"
                    and frame.get("life", {}).get("value") == "ALIVE"):
                result[key] = int(row["timestamp"])
    return result


def rim_evidence(roi: ColorImage, x: float, y: float, scale: float = 1.0) -> tuple[int, int]:
    """Warm sectors and opposite pairs around a point, as the existing direct tracker reads them.

    Same rays and HSV bounds as ``map_direct_recorder._rim_evidence``.
    """
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    height, width = roi.shape[:2]
    angles = np.arange(16) * (math.tau / 16)
    radii = np.arange(5, 12)[:, None] * scale
    xs = np.clip(np.rint(x + radii * np.cos(angles)).astype(int), 0, width - 1)
    ys = np.clip(np.rint(y + radii * np.sin(angles)).astype(int), 0, height - 1)
    hue, sat, light = np.moveaxis(hsv[ys, xs], -1, 0)
    warm = ((hue >= 13) & (hue <= 42) & (sat >= 32) & (light >= 152)).any(axis=0)
    return int(warm.sum()), int((warm[:8] & warm[8:]).sum())


# ---------------------------------------------------------------------------
# Registration


def _floor_mask(roi: ColorImage) -> NDArray[np.uint8]:
    """Walkable floor of the minimap: grey, unsaturated, mid-bright pixels."""
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    floor = (hsv[:, :, 1] <= 40) & (hsv[:, :, 2] >= 110) & (hsv[:, :, 2] <= 215)
    return np.asarray(floor, dtype=np.uint8)


def _atlas_mask(atlas: NDArray[np.uint8]) -> NDArray[np.uint8]:
    if atlas.ndim == 3 and atlas.shape[2] == 4:
        return np.asarray(atlas[:, :, 3] > 127, dtype=np.uint8)
    gray = cv2.cvtColor(atlas[:, :, :3], cv2.COLOR_BGR2GRAY) if atlas.ndim == 3 else atlas
    return np.asarray(gray > 0, dtype=np.uint8)


@dataclass
class RegistrationModes:
    """The recording's few minimap placements (one per side), from per-frame fits."""

    map_id: str
    reference_sha256: str
    atlas_mask: NDArray[np.uint8]
    modes: list[NDArray[np.float64]] = field(default_factory=list)
    support: list[int] = field(default_factory=list)

    @staticmethod
    def _signature(matrix: NDArray[np.float64]) -> tuple[int, int, int]:
        angle = math.degrees(math.atan2(matrix[1, 0], matrix[0, 0]))
        return round(angle / 5), round(matrix[0, 2] / 8), round(matrix[1, 2] / 8)

    @classmethod
    def from_fits(
        cls, map_id: str, reference_sha256: str, atlas: NDArray[np.uint8],
        fits: Iterable[NDArray[np.float64]], *, min_support: int = 5,
    ) -> RegistrationModes:
        groups: dict[tuple[int, int, int], list[NDArray[np.float64]]] = {}
        for matrix in fits:
            groups.setdefault(cls._signature(matrix), []).append(matrix)
        result = cls(map_id, reference_sha256, _atlas_mask(atlas))
        for _, members in sorted(groups.items(), key=lambda item: -len(item[1])):
            if len(members) < min_support:
                continue
            result.modes.append(np.median(np.stack(members), axis=0))
            result.support.append(len(members))
        return result

    def agreement(self, roi: ColorImage, matrix: NDArray[np.float64]) -> float:
        """IoU of the canonical floor with the reference floor placed by ``matrix``."""
        height, width = roi.shape[:2]
        placed = np.asarray(cv2.warpPerspective(self.atlas_mask, matrix, (width, height),
                                                flags=cv2.INTER_NEAREST), dtype=np.uint8)
        floor = _floor_mask(roi)
        union = int((placed | floor).sum())
        return float((placed & floor).sum()) / union if union else 0.0

    def verify(self, roi: ColorImage, *, minimum: float = 0.35, margin: float = 0.10,
               ) -> tuple[int, float, float] | None:
        """Mode index whose floor agreement is high and clearly above every other mode."""
        if not self.modes:
            return None
        scores = [self.agreement(roi, mode) for mode in self.modes]
        order = sorted(range(len(scores)), key=lambda i: -scores[i])
        best = order[0]
        runner = scores[order[1]] if len(order) > 1 else 0.0
        if scores[best] >= minimum and scores[best] - runner >= margin:
            return best, scores[best], runner
        return None


def to_reference(matrix: NDArray[np.float64], point: Sequence[float]) -> list[float]:
    coordinate = np.linalg.solve(matrix, np.asarray([point[0], point[1], 1.0]))
    return [float(coordinate[0] / coordinate[2]), float(coordinate[1] / coordinate[2])]


def to_roi(matrix: NDArray[np.float64], point: Sequence[float]) -> list[float]:
    coordinate = matrix @ np.asarray([point[0], point[1], 1.0])
    return [float(coordinate[0] / coordinate[2]), float(coordinate[1] / coordinate[2])]


# ---------------------------------------------------------------------------
# Measurement of one canonical frame


@dataclass(frozen=True)
class FrameInput:
    sample: dict[str, Any]
    roi: ColorImage
    roi_pixel_sha256: str
    frame_fit: NDArray[np.float64] | None = None
    library_points: tuple[dict[str, Any], ...] = ()


def measure_frame(
    item: FrameInput, modes: RegistrationModes, *, ring: RingParameters | None = None,
    reference_size: tuple[int, int] = (1024, 1024),
) -> dict[str, Any]:
    """Every development reading of one own-live canonical frame, chosen or not."""
    sample = freeze_native_sample(item.sample)
    if hashlib.sha256(item.roi.tobytes()).hexdigest() != item.roi_pixel_sha256:
        raise ValueError("Canonical minimap pixels changed after decoding")
    record: dict[str, Any] = {"sample_sha256": sample["sample_sha256"], "registration": None,
                              "ring": None, "library": [], "chosen": None}
    matrix: NDArray[np.float64] | None = None
    if item.frame_fit is not None:
        matrix = item.frame_fit
        record["registration"] = {"kind": "frame_fit"}
    else:
        verified = modes.verify(item.roi)
        if verified is not None:
            index, score, runner = verified
            matrix = modes.modes[index]
            record["registration"] = {"kind": "recording_mode", "mode": index,
                                      "floor_iou": round(score, 4),
                                      "runner_up_iou": round(runner, 4)}
    ring_result = read_self_ring(item.roi, parameters=ring)
    record["ring"] = {k: ring_result[k] for k in ("status", "center_roi_px", "accepted_count")}
    if matrix is None:
        return record
    width, height = reference_size

    def inside(point: list[float]) -> bool:
        return 0 <= point[0] < width and 0 <= point[1] < height

    candidates: list[dict[str, Any]] = []
    if ring_result["status"] == "UNIQUE":
        reference = to_reference(matrix, ring_result["center_roi_px"])
        if inside(reference):
            candidates.append({"method": RING_METHOD, "map_reference_px": reference,
                               "roi_px": ring_result["center_roi_px"]})
    for point in item.library_points:
        if (point.get("map_id") != modes.map_id
                or point.get("reference_sha256") != modes.reference_sha256):
            continue
        roi_px = to_roi(matrix, point["map_reference_px"])
        warm, pairs = rim_evidence(item.roi, *roi_px)
        entry = {"library_kind": point.get("kind"), "roi_px": [round(v, 2) for v in roi_px],
                 "warm_sectors": warm, "opposite_pairs": pairs}
        record["library"].append(entry)
        if point.get("kind") == "selected" and warm >= 5 and pairs >= 1:
            candidates.append({"method": RIM_METHOD, "map_reference_px":
                               [float(v) for v in point["map_reference_px"]],
                               "roi_px": entry["roi_px"]})
    if not candidates:
        return record
    # Conflict rule: two methods that disagree by more than 6 minimap pixels abstain.
    anchor = candidates[0]["roi_px"]
    if any(math.dist(anchor, c["roi_px"]) > 6 for c in candidates[1:]):
        record["conflict"] = True
        return record
    preferred = next((c for c in candidates if c["method"] == RIM_METHOD), candidates[0])
    record["chosen"] = {**preferred, "methods_agreeing": sorted({c["method"] for c in candidates})}
    return record


def observation(
    record: dict[str, Any], sample: dict[str, Any], modes: RegistrationModes,
    receipt_sha256: str,
) -> dict[str, Any]:
    chosen = record["chosen"]
    return {
        "sample": freeze_native_sample(sample),
        "candidate_index": 0,
        "support_count": 1,
        "kind": "selected",
        "map_id": modes.map_id,
        "reference_sha256": modes.reference_sha256,
        "map_reference_px": chosen["map_reference_px"],
        "fit_residual_p95_reference_px": None,
        "selection_method": chosen["method"],
        "methods_agreeing": chosen["methods_agreeing"],
        "registration": record["registration"]["kind"],
        "track_anchor": digest([PASS_VERSION, chosen["method"], sample["sample_sha256"]]),
        "recorder_agent_uuid_candidate": None,
        "canonical_decode_receipt_sha256": receipt_sha256,
        "qualified": False,
        "position_authority": False,
    }


def build_report(
    timeline: Mapping[str, Any], timeline_sha256: str, records: Mapping[str, dict[str, Any]],
    modes: RegistrationModes, *, zones: Sequence[ReferenceZones] = (),
    receipt_sha256: str, provenance: Mapping[str, Any],
) -> dict[str, Any]:
    """Assemble a ``development_recorder_map_path_v1`` report bound to the canonical file."""
    if not is_sha(timeline_sha256) or not is_sha(receipt_sha256):
        raise ValueError("Canonical timeline and decode receipt hashes required")
    frames = timeline["native_frames"]
    rows: list[dict[str, Any] | None] = []
    for second in timeline["seconds"]:
        for key in second["sample_refs"]:
            record = records.get(key)
            if record is None or record.get("chosen") is None:
                rows.append(None)
                continue
            rows.append(observation(record, frames[key]["sample"], modes, receipt_sha256))
    paths = build_recorder_paths(rows, zones=zones)
    second_rows = join_recorder_seconds(paths, dict(timeline))
    counts: Counter[str] = Counter()
    for record in records.values():
        counts["own_live_frames_measured"] += 1
        registration = record.get("registration")
        counts[f"registration_{registration['kind'] if registration else 'none'}"] += 1
        counts[f"ring_{record['ring']['status'].lower()}"] += 1
        if record.get("conflict"):
            counts["method_conflict_abstained"] += 1
        if record.get("chosen"):
            counts["positions"] += 1
            counts["positions_" + "+".join(record["chosen"]["methods_agreeing"])] += 1
    return {
        **paths,
        "second_rows": second_rows,
        "timeline_sha256": timeline_sha256,
        "canonical_pass": {
            "version": PASS_VERSION,
            "ring_method": RING_VERSION,
            "ring_parameters_sha256": RingParameters().fingerprint(),
            "decode_receipt_sha256": receipt_sha256,
            "registration_modes": [
                {"matrix": mode.tolist(), "support": support}
                for mode, support in zip(modes.modes, modes.support, strict=True)
            ],
            "counts": dict(sorted(counts.items())),
            "continuous_time_assumed": False,
            **dict(provenance),
        },
    }


__all__ = [
    "FrameInput",
    "PATH_VERSION",
    "RegistrationModes",
    "build_report",
    "measure_frame",
    "own_live_samples",
    "rim_evidence",
    "warm_mask",
]
