"""Development-only appearance -> map position -> ZoneResolution envelope.

Nothing in this module writes a VisualObservation, Round Package or formal
Self Position Fact. Reference identity, per-frame view evidence, and measured
coordinates are deliberately separate. Callers must preserve that separation.
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any

import cv2
from numpy.typing import NDArray

from valorant_ai_coach.maps.outline_calibration import OutlineMinimapCalibrator
from valorant_ai_coach.maps.registry import MapRegistry, MapRegistryError
from valorant_ai_coach.maps.resolver import ZoneResolver
from valorant_ai_coach.resources import resource_path
from valorant_ai_coach.video.geometry import normalized_roi_bounds

from .map_consumer import MapEventConsumer
from .map_pipeline import MapTimeline
from .self_marker import SelfMarkerTracker


def bind_development_registry() -> MapRegistry:
    canonical = resource_path("config/map_zone_v3/config/map_registry_v1.json").parents[1]
    root = resource_path("config/map_zone_development/bind/config/map_registry_v1.json").parents[1]
    return MapRegistry(root, schema_root=canonical / "schemas")


class DevelopmentMapTimeline:
    def __init__(self, profile: dict[str, Any], *, registry: MapRegistry | None = None) -> None:
        self.registry = registry if registry is not None else bind_development_registry()
        self.profile = profile
        self.timeline = MapTimeline(profile, registry=self.registry)
        if self.timeline.definition is None:
            raise ValueError("Development map requires an explicitly identified registered map")
        if self.registry.registry["maps"][self.timeline.definition.map_id]["production"]:
            raise ValueError("Development timeline requires an isolated non-production map entry")
        self.timeline.calibrator = OutlineMinimapCalibrator()
        definition = self.timeline.definition
        self.resolver = ZoneResolver(definition, self.registry.runtime)
        self.consumer = MapEventConsumer(definition, self.registry.runtime)
        self.marker = SelfMarkerTracker()
        self.previous: tuple[float, tuple[float, float], int | None] | None = None
        self.next_segment = 0
        self.segment: int | None = None
        path = self.registry.root / "provenance.json"
        provenance = json.loads(path.read_text(encoding="utf-8"))
        mask_path = self.registry.root / "assets/bind_visible_floor.png"
        if hashlib.sha256(mask_path.read_bytes()).hexdigest() != provenance["visible_floor_sha256"]:
            raise MapRegistryError("Development visible-floor raster hash mismatch")
        self.floor = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
        if self.floor is None:
            raise MapRegistryError("Development visible-floor raster unavailable")

    def _break(self) -> None:
        self.previous = None
        self.segment = None
        self.resolver.reset()
        self.consumer.reset()

    def observe(
        self, frame: NDArray[Any], time_sec: float, frame_index: int, *,
        view: dict[str, Any], evidence_kind: str,
    ) -> dict[str, Any]:
        if evidence_kind not in {"source_review", "unqualified_hud_observation"}:
            raise ValueError("Explicit source of view evidence is required")
        if not math.isfinite(time_sec) or time_sec < 0:
            raise ValueError("Finite non-negative source time required")
        roi = self.profile.get("rois", {}).get("minimap")
        bounds = normalized_roi_bounds(roi, frame.shape[1], frame.shape[0])
        if bounds is None:
            raise ValueError("Explicit valid minimap ROI required")
        left, top, right, bottom = bounds
        eligible = (
            view.get("primary_state") == "live_first_person"
            and view.get("values", {}).get("player_specific_hud_valid") is True
            and not set(view.get("state_flags", [])) & {
                "visual_transition", "buy_phase_banner", "round_end_banner",
            }
        )
        appearance = self.marker.observe(
            frame[top:bottom, left:right], time_sec, self.profile["minimap_self_marker"],
            ownership_eligible=eligible,
        )
        calibration = self.timeline.calibrate(frame)
        point = None
        if calibration is not None and appearance.x_roi_norm is not None:
            assert appearance.y_roi_norm is not None
            point = calibration.transform(appearance.x_roi_norm, appearance.y_roi_norm)
        diagnostics = []
        definition = self.timeline.definition
        assert definition is not None
        if point is not None:
            assert self.floor is not None
            x0, y0, x1, y1 = definition.data["coordinate_system"][
                "reference_map_mask_bbox_within_roi_px"
            ]
            x, y = round(x0 + point[0]*(x1-x0)), round(y0 + point[1]*(y1-y0))
            if not (0 <= y < self.floor.shape[0] and 0 <= x < self.floor.shape[1]
                    and self.floor[y, x] > 0):
                diagnostics.append("candidate_outside_visible_floor")
                point = None
        velocity = None
        previous = self.previous
        if point is None:
            self._break()
        elif previous is not None:
            dt = time_sec-previous[0]
            if (not 0 < dt <= .3 or previous[2] != appearance.track_id):
                self._break()
                diagnostics.append("map_track_discontinuity")
            else:
                velocity = math.dist(point, previous[1])/dt
                if velocity > .4:
                    self._break()
                    diagnostics.append("map_position_jump")
                    point = None
                    velocity = None
        if point is not None:
            if self.segment is None:
                self.segment = self.next_segment
                self.next_segment += 1
            self.previous = time_sec, point, appearance.track_id
        context = {
            "status": calibration.status if calibration else "calibration_required",
            "confidence": calibration.confidence if calibration else 0,
            "diagnostics": list(calibration.diagnostics) if calibration else [],
        }
        resolution = self.resolver.resolve(
            time_sec=time_sec, frame_index=frame_index, point=point,
            marker_confidence=appearance.appearance_score if point is not None else 0,
            calibration=context, controlled_player=False,
        )
        events = []
        if point is not None and resolution["zone_id"] is not None:
            events = self.consumer.consume(resolution)
        else:
            self.consumer.reset()
        return {
            "qualification": "development_only", "formal_self_position_fact": None,
            "time_sec": time_sec, "frame_index": frame_index,
            "appearance": appearance.to_dict(),
            "ownership": {"identity": "UNKNOWN", "view_eligible": eligible,
                          "view_evidence_kind": evidence_kind,
                          "reference_identity_confirmed": bool(
                              self.profile.get("reference_identity_confirmed", False))},
            "map_id": definition.map_id, "geometry_version": definition.geometry_version,
            "calibration": context, "map_position_norm": list(point) if point else None,
            "map_segment": self.segment, "map_speed_norm_per_sec": velocity,
            "zone_resolution": resolution,
            "development_events": events,
            "diagnostics": diagnostics,
        }
