"""Image-only development Map observations; no player or timeline state."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from numpy.typing import NDArray
from shapely.geometry import Point, Polygon

from valorant_ai_coach.hud.layout import HudLayout
from valorant_ai_coach.maps.calibration import MinimapCalibrator
from valorant_ai_coach.maps.registry import MapRegistry

from .evidence import digest
from .replay import file_sha, read_json

SCHEMA = "development_generic_map_pixels_v1"
SHAPE_POLICY = {
    "method": "prior_broad_shape_topk_v1_bounded",
    "hough_param1": 80,
    "hough_param2": 10,
    "hough_radius_reference_px": [5, 11],
    "hough_limit": 128,
    "component_saturation_min": 80,
    "component_value_min": 50,
    "component_area_reference_px": [15, 500],
    "component_width_reference_px": [3, 45],
    "component_limit": 64,
    "physical_marker_association": "UNKNOWN",
}


def _shape_proposals(
    image: NDArray[np.uint8], roi: tuple[int, int, int, int], scale: float
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    left, top, right, bottom = roi
    crop = image[top:bottom, left:right]
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    found = cv2.HoughCircles(
        gray,
        cv2.HOUGH_GRADIENT,
        1,
        max(2.0, 3 * scale),
        param1=80,
        param2=10,
        minRadius=max(2, round(5 * scale)),
        maxRadius=max(3, round(11 * scale)),
    )
    circles = [] if found is None else found[0].tolist()
    proposals: list[dict[str, Any]] = []
    for x, y, radius in circles[:128]:
        proposals.append(
            {
                "center_frame_px": [float(left + x), float(top + y)],
                "proposal_kind": "loose_hough_circle",
                "radius_px": float(radius),
            }
        )
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    mask = ((hsv[:, :, 1] >= 80) & (hsv[:, :, 2] >= 50)).astype(np.uint8)
    count, _, stats, centroids = cv2.connectedComponentsWithStats(mask, connectivity=8)
    min_area = max(3, round(15 * scale * scale))
    max_area = max(min_area, round(500 * scale * scale))
    min_side = max(2, round(3 * scale))
    max_side = max(min_side, round(45 * scale))
    eligible = [
        i
        for i in range(1, count)
        if min_area <= int(stats[i, 4]) <= max_area
        and min_side <= min(map(int, stats[i, 2:4]))
        and max(map(int, stats[i, 2:4])) <= max_side
    ]
    for index in eligible[:64]:
        x, y = centroids[index]
        proposals.append(
            {
                "center_frame_px": [float(left + x), float(top + y)],
                "proposal_kind": "chromatic_component",
                "component_area_px": int(stats[index, 4]),
            }
        )
    return proposals, {
        "hough_raw": len(circles),
        "hough_retained": min(len(circles), 128),
        "components_eligible": len(eligible),
        "components_retained": min(len(eligible), 64),
    }


class GenericMapObserver:
    """Read pixels without Source, PTS, agent, roster, or previous-frame input."""

    def __init__(self, config_path: Path) -> None:
        config = read_json(config_path)
        if set(config) != {"layout"}:
            raise ValueError("Generic Map observer requires only an existing HUD layout")
        layout_path = Path(config["layout"]).expanduser().resolve()
        self.layout = HudLayout.load(layout_path)
        if "minimap_normal" not in self.layout.regions:
            raise ValueError("Existing normalized minimap ROI required")
        self.registry = MapRegistry()
        self.calibrator = MinimapCalibrator()
        self.definitions = [
            self.registry.load(map_id)
            for map_id, entry in self.registry.data["maps"].items()
            if entry.get("production") is True
        ]
        self.bindings = {
            "schema": SCHEMA,
            "layout_sha256": file_sha(layout_path),
            "map_registry_sha256": file_sha(self.registry.root / "config" / "map_registry_v1.json"),
            "map_reference_sha256s": {
                definition.map_id: file_sha(definition.reference_asset)
                for definition in self.definitions
                if definition.reference_asset is not None
            },
            "map_definition_digests": {
                definition.map_id: digest(
                    {
                        "data": definition.data,
                        "callouts": definition.callouts,
                        "peek": definition.peek,
                        "mask": definition.mask,
                    }
                )
                for definition in self.definitions
            },
            "code_sha256": file_sha(Path(__file__)),
            "shape_policy": SHAPE_POLICY,
            "opencv": cv2.__version__,
            "numpy": np.__version__,
            "state_authority": False,
        }
        self.fingerprint = digest(self.bindings)

    def inspect(self, image: NDArray[np.uint8]) -> dict[str, Any]:
        if (
            not isinstance(image, np.ndarray)
            or image.dtype != np.uint8
            or image.ndim != 3
            or image.shape[2] != 3
            or not 640 <= image.shape[1] <= 4096
            or not 360 <= image.shape[0] <= 2160
        ):
            raise ValueError("Bounded native BGR frame required")
        height, width = image.shape[:2]
        left, top, right, bottom = self.layout.normalized_roi("minimap_normal").pixel_bounds(
            width, height
        )
        roi = (left, top, right, bottom)
        aspect = width / height
        reference = self.layout.reference_resolution
        reference_aspect = reference[0] / reference[1] if reference else 16 / 9
        geometry_supported = (
            abs(aspect - reference_aspect) <= 0.005 and right - left >= 65 and bottom - top >= 65
        )
        candidates: list[dict[str, Any]] = []
        counts = {
            "hough_raw": 0,
            "hough_retained": 0,
            "components_eligible": 0,
            "components_retained": 0,
        }
        map_names: list[dict[str, Any]] = []
        zones: list[dict[str, Any]] = []
        calibration_diagnostics: dict[str, Any] = {}
        display_score = None
        if geometry_supported:
            crop = image[top:bottom, left:right]
            edges = cv2.Canny(cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY), 80, 160)
            display_score = float(np.count_nonzero(edges) / edges.size)
            scale = width / (reference[0] if reference else 1920)
            proposals, counts = _shape_proposals(image, roi, scale)
            for index, proposal in enumerate(proposals):
                candidates.append(
                    {
                        "proposal_id": ["generic_map_pixels_v1", index],
                        **proposal,
                        "position_subject": "unassigned_visual_candidate",
                        "ownership": "UNKNOWN",
                        "qualification": "development_only",
                        "map_position_norm": None,
                        "zone_resolution": None,
                    }
                )
            scores = {}
            calibrations = {}
            for definition in self.definitions:
                result = self.calibrator.analyze(
                    image,
                    [left / width, top / height, right / width, bottom / height],
                    definition,
                )
                calibration_diagnostics[definition.map_id] = {
                    "status": result.status,
                    "confidence": result.confidence,
                    "diagnostics": list(result.diagnostics),
                }
                if result.status == "ok":
                    scores[definition.map_id] = result.confidence
                    calibrations[definition.map_id] = result
            selected = self.registry.select(template_scores=scores)
            if selected is not None:
                definition = next(d for d in self.definitions if d.map_id == selected)
                calibration = calibrations[selected]
                map_names.append(
                    {
                        "map_id": selected,
                        "confidence": calibration.confidence,
                        "evidence": "bundled_registry_static_map_alignment",
                        "ownership": "UNKNOWN",
                        "qualification": "development_only",
                    }
                )
                polygons = {
                    zone_id: Polygon(zone["polygon_norm"])
                    for zone_id, zone in definition.zone_index.items()
                }
                for index, candidate in enumerate(candidates):
                    x, y = candidate["center_frame_px"]
                    point = calibration.transform(
                        (x - left) / (right - left), (y - top) / (bottom - top)
                    )
                    if point is None:
                        continue
                    candidate["geometry_only_map_position_norm"] = list(point)
                    for zone_id, polygon in polygons.items():
                        if polygon.covers(Point(point)):
                            zones.append(
                                {
                                    "candidate_index": index,
                                    "zone_id_candidate": zone_id,
                                    "map_id_candidate": selected,
                                    "subject": "unassigned_visual_candidate",
                                    "ownership": "UNKNOWN",
                                    "qualification": "development_only",
                                }
                            )
        return {
            "signals": [],
            "context": {"stream_kind": "map_generic", "profile_fingerprint": self.fingerprint},
            "raw": {
                "schema": SCHEMA,
                "map_reader_status": "OBSERVED" if geometry_supported else "GEOMETRY_UNSUPPORTED",
                "frame_pixel_sha256": hashlib.sha256(image.tobytes()).hexdigest(),
                "frame_size_px": [width, height],
                "roi_xywh_native": [left, top, right - left, bottom - top],
                "roi_geometry_qualification": "normalized_layout_candidate_only",
                "display_status": "CANDIDATE"
                if display_score is not None and display_score >= 0.04
                else "UNKNOWN",
                "display_edge_fraction": display_score,
                "candidate_counts": counts,
                "map_name_candidates": map_names,
                "zone_candidates": zones,
                "bundled_registry_calibration": calibration_diagnostics,
                "physical_marker_association": "UNKNOWN",
                "current_view_correspondence": "UNKNOWN",
                "ownership": "UNKNOWN",
                "formal_outputs": 0,
            },
            "map_candidates": candidates,
        }
