"""Development-only recorder observations on a reference map and Source-second bins."""

from __future__ import annotations

import hashlib
import math
from collections.abc import Iterable, Mapping, Sequence
from fractions import Fraction
from typing import Any

import numpy as np
from numpy.typing import NDArray
from shapely.geometry import Point, Polygon

from .evidence import digest, freeze_native_sample, is_sha, native_time, source_scope

VERSION = "development_recorder_map_path_v1"


def project_recorder_witness(
    image: NDArray[np.uint8], sample: dict[str, Any], pool: list[dict[str, Any]],
    selection: dict[str, Any], alignment: dict[str, Any], *,
    reference_sha256s: Mapping[str, str],
) -> dict[str, Any] | None:
    """Invert a current minimap alignment for one measured selector witness."""
    sample = freeze_native_sample(sample)
    index = selection.get("support_candidate_index")
    if (
        selection.get("contract") != "development_map_recorder_selection_v1"
        or selection.get("sample_sha256") != sample["sample_sha256"]
        or selection.get("ordered_candidate_pool_digest") != digest(pool)
        or type(index) is not int or not 0 <= index < len(pool)
        or type(selection.get("support_count")) is not int or selection["support_count"] <= 0
        or selection.get("qualified") is not False
        or selection.get("position_authority") is not False
    ):
        return None
    selected = selection.get("selection_status") == "RESEARCH_SELECTED"
    if selected and selection.get("research_candidate_index") != index:
        return None
    if (
        image.ndim != 3 or image.shape[2] != 3 or image.dtype != np.uint8
        or list(image.shape[:2][::-1]) != sample["frame_size_px"]
        or hashlib.sha256(image.tobytes()).hexdigest() != sample["native_pixel_sha256"]
    ):
        return None
    candidates = alignment.get("map_name_candidates", [])
    if alignment.get("marker_transform_qualified") is not False or len(candidates) != 1:
        return None
    reference = candidates[0]
    map_id = reference.get("map_id")
    sha = reference_sha256s.get(map_id, "")
    if (
        not is_sha(sha) or reference.get("evidence") != "public_reference_feature_alignment"
        or reference.get("position_authority") is not False
        or reference.get("qualified") is not False
    ):
        return None
    width, height = sample["frame_size_px"]
    left, top, right, bottom = alignment["roi_pixel_bounds"]
    x, y = selection["support_center_frame_px"]
    if not (0 <= left <= x < right <= width and 0 <= top <= y < bottom <= height):
        return None
    roi = image[top:bottom, left:right]
    if hashlib.sha256(roi.tobytes()).hexdigest() != alignment.get("roi_pixel_sha256"):
        return None
    matrix = np.asarray(reference["reference_to_roi_homography_candidate"], dtype=float)
    if (
        matrix.shape != (3, 3) or not np.isfinite(matrix).all()
        or not np.array_equal(matrix[2], [0, 0, 1])
        or abs(float(np.linalg.det(matrix))) < 1e-9
    ):
        return None
    coordinate = np.linalg.solve(matrix, np.asarray([x-left, y-top, 1.]))[:2].tolist()
    size = reference.get("reference_image_size_px")
    if size is not None and (
        not isinstance(size, list) or len(size) != 2
        or any(type(dim) is not int or not 0 <= p < dim
               for p, dim in zip(coordinate, size, strict=True))
    ):
        return None
    residual = reference.get("fit_residual_p95_reference_px")
    if residual is not None and (
        type(residual) not in (float, int) or not math.isfinite(residual) or residual < 0
    ):
        return None
    return {
        "sample": sample, "candidate_index": index, "support_count": selection["support_count"],
        "kind": "selected" if selected else "measured_witness", "map_id": map_id,
        "reference_sha256": sha, "map_reference_px": coordinate,
        "recorder_agent_candidate": selection.get("recorder_agent_candidate"),
        "fit_residual_p95_reference_px": residual,
        "qualified": False, "position_authority": False,
        **({"selection_method": selection["selection_method"],
            "track_anchor": selection["track_anchor"],
            "recorder_agent_uuid_candidate": selection["recorder_agent_uuid_candidate"]}
           if selection.get("selection_method") == "knowledge_agent_uuid" else {}),
    }


class ReferenceZones:
    """Explicit Zone polygons in one catalog reference image's pixel coordinates."""

    def __init__(self, map_id: str, reference_sha256: str,
                 polygons: Mapping[str, Sequence[tuple[float, float]]]) -> None:
        if not map_id or not is_sha(reference_sha256):
            raise ValueError("Map ID and exact Zone reference asset required")
        self._map_id = map_id
        self._reference_sha256 = reference_sha256
        self._zones = {zone_id: Polygon(vertices) for zone_id, vertices in polygons.items()}
        if any(not k or not p.is_valid or p.is_empty for k, p in self._zones.items()):
            raise ValueError("Valid named Zone polygons required")

    def classify(self, observation: dict[str, Any], *, margin_reference_px: float) -> str | None:
        if (
            observation["map_id"] != self._map_id
            or observation["reference_sha256"] != self._reference_sha256
        ):
            return None
        if not math.isfinite(margin_reference_px) or margin_reference_px < 0:
            raise ValueError("Finite nonnegative Zone boundary margin required")
        point = Point(observation["map_reference_px"])
        options = [zone_id for zone_id, poly in self._zones.items() if poly.covers(point)]
        if len(options) == 1 and all(
            poly.boundary.distance(point) > margin_reference_px for poly in self._zones.values()
        ):
            return options[0]
        return None


class ReferenceCallouts:
    """Proximity hints for registered anchor points on an exact reference image."""

    def __init__(
        self, map_id: str, reference_sha256: str, image_size: tuple[int, int],
        anchors: Sequence[tuple[str, tuple[float, float]]],
    ) -> None:
        if not map_id or not is_sha(reference_sha256) or min(image_size) <= 0:
            raise ValueError("Callout reference Map, hash, and dimensions required")
        self.map_id = map_id
        self.sha256 = reference_sha256
        width, height = image_size
        self.radius = min(width, height) * .025
        self.anchors = [
            (label, (x * width, y * height)) for label, (x, y) in anchors
            if label and 0 <= x < 1 and 0 <= y < 1
        ]

    def classify(self, observation: dict[str, Any], *, margin_reference_px: float) -> str | None:
        if (observation["map_id"] != self.map_id
                or observation["reference_sha256"] != self.sha256
                or observation.get("fit_residual_p95_reference_px") is None):
            return None
        distances: dict[str, float] = {}
        point = observation["map_reference_px"]
        for label, center in self.anchors:
            distances[label] = min(math.dist(point, center), distances.get(label, math.inf))
        if not distances:
            return None
        rank = sorted((dist, name) for name, dist in distances.items())
        distance, name = rank[0]
        if distance + margin_reference_px > self.radius:
            return None
        if len(rank) > 1 and rank[1][0] - distance <= 2 * margin_reference_px:
            return None
        return name


def build_recorder_paths(
    samples: Iterable[dict[str, Any] | None], *,
    zones: Sequence[ReferenceZones] = (), margin_reference_px: float = 4.0,
    callouts: Sequence[ReferenceCallouts] = (),
) -> dict[str, Any]:
    """Collect only measured witnesses of accepted hypotheses; split at a missing row."""
    paths: list[list[dict[str, Any]]] = []
    run: list[dict[str, Any]] = []
    start: int | None = None
    end = 0

    def flush() -> None:
        if start is not None:
            paths.append(run[start:end])

    last: dict[str, Any] | None = None
    for record in samples:
        if record is None or (last is not None and not _same_run(last, record)):
            flush()
            run, start, end = [], None, 0
        last = record
        if record is None:
            continue
        margin = max(margin_reference_px, record.get("fit_residual_p95_reference_px") or 0)
        zone = {k for index in zones if (k := index.classify(
            record, margin_reference_px=margin,
        )) is not None}
        callout = {k for index in callouts if (k := index.classify(
            record, margin_reference_px=margin,
        )) is not None}
        run.append({**record, "zone_candidate": next(iter(zone)) if len(zone) == 1 else None,
                    "callout_candidate": next(iter(callout)) if len(callout) == 1 else None})
        if record["kind"] == "selected":
            if start is None:
                start = max(0, len(run) - 3)
            end = len(run)
    flush()
    return {
        "schema": VERSION, "segments": paths, "interpolated_samples": 0,
        "qualified": False, "formal_outputs": 0,
    }


def _same_run(a: dict[str, Any], b: dict[str, Any]) -> bool:
    src_a, src_b = a["sample"], b["sample"]
    return (
        source_scope(src_a) == source_scope(src_b)
        and 0 < native_time(src_b) - native_time(src_a) <= Fraction(1, 4)
        and a["support_count"] + 1 == b["support_count"]
        and a.get("selection_method") == b.get("selection_method")
        and a.get("track_anchor") == b.get("track_anchor")
        and a["map_id"] == b["map_id"]
        and a["reference_sha256"] == b["reference_sha256"]
    )


def _linked_sample_ids(
    paths: dict[str, Any], admissible: set[str] | None = None,
) -> set[str]:
    linked: set[str] = set()
    for segment in paths["segments"]:
        for a, b in zip(segment, segment[1:], strict=False):
            if _same_run(a, b):
                ids = {a["sample"]["sample_sha256"], b["sample"]["sample_sha256"]}
                if admissible is None or ids <= admissible:
                    linked.update(ids)
    return linked


def join_recorder_seconds(
    paths: dict[str, Any], timeline: dict[str, Any],
) -> list[dict[str, Any]]:
    """Attach present native path points to existing second rows by exact sample ID."""
    if paths["schema"] != VERSION or paths["formal_outputs"] != 0:
        raise ValueError("Development recorder paths required")
    by_id = {p["sample"]["sample_sha256"]: p for path in paths["segments"] for p in path}
    linked = _linked_sample_ids(paths)
    result = []
    consumed: set[str] = set()
    for second in timeline["seconds"]:
        points = []
        for sample_id in second["sample_refs"]:
            if sample_id in by_id:
                if sample_id in consumed:
                    raise ValueError("Recorder sample belongs to more than one second")
                consumed.add(sample_id)
                points.append(by_id[sample_id])
        points.sort(key=lambda row: native_time(row["sample"]))
        has_edge = any(p["sample"]["sample_sha256"] in linked for p in points)
        result.append({
            "timestamp": second["timestamp"], "recorder_map_observations": points,
            "coverage": "sampled_points_only" if points else "UNKNOWN",
            "trajectory_coverage": "native_edge_observed" if has_edge else (
                "isolated_points" if points else "UNKNOWN"
            ),
            "qualified": False,
        })
    if consumed != by_id.keys():
        raise ValueError("Recorder path has a sample absent from the common timeline")
    return result


def measure_operable_coverage(
    paths: dict[str, Any], timeline_seconds: Sequence[dict[str, Any]],
    second_rows: Sequence[dict[str, Any]], operable_samples: set[str],
) -> dict[str, Any]:
    """Coverage over seconds supported entirely by current SELF/ALIVE evidence.

    One-second sampling can report point coverage. Native edges alone
    contribute trajectory coverage. A second with an edge is not treated as
    a full second of uninterrupted movement.
    """
    linked = _linked_sample_ids(paths, operable_samples)
    eligible = positions = edges = 0
    for domain, row in zip(timeline_seconds, second_rows, strict=True):
        samples = set(domain["sample_refs"])
        if not samples or not samples <= operable_samples:
            continue
        eligible += 1
        points = {
            p["sample"]["sample_sha256"] for p in row["recorder_map_observations"]
        }
        positions += bool(points & samples)
        edges += bool(points & samples & linked)
    return {
        "operable_seconds_with_current_evidence": eligible,
        "seconds_without_full_operability_evidence": len(timeline_seconds) - eligible,
        "operable_seconds_with_position": positions,
        "operable_seconds_with_native_edge": edges,
        "position_rate": positions / eligible if eligible else None,
        "trajectory_rate": edges / eligible if eligible else None,
        "continuous_time_assumed": False,
    }
