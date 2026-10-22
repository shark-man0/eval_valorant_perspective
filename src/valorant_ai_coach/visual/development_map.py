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
import numpy as np
from numpy.typing import NDArray

from valorant_ai_coach.maps.outline_calibration import OutlineMinimapCalibrator
from valorant_ai_coach.maps.registry import MapRegistry, MapRegistryError
from valorant_ai_coach.maps.resolver import ZoneResolver
from valorant_ai_coach.resources import resource_path
from valorant_ai_coach.video.geometry import normalized_roi_bounds

from .map_pipeline import MapTimeline
from .self_marker import MarkerPosition, MarkerReferenceInspector, SelfMarkerTracker


def bind_development_registry() -> MapRegistry:
    canonical = resource_path("config/map_zone_v3/config/map_registry_v1.json").parents[1]
    root = resource_path("config/map_zone_development/bind/config/map_registry_v1.json").parents[1]
    return MapRegistry(root, schema_root=canonical / "schemas")


class DevelopmentMapTimeline:
    def __init__(self, profile: dict[str, Any], *, registry: MapRegistry | None = None,
                 inspect_reference_appearances: bool = False) -> None:
        self.registry = registry if registry is not None else bind_development_registry()
        self.profile = profile
        self.timeline = MapTimeline(profile, registry=self.registry)
        if self.timeline.definition is None:
            raise ValueError("Development map requires an explicitly identified registered map")
        if self.registry.registry["maps"][self.timeline.definition.map_id]["production"]:
            raise ValueError("Development timeline requires an isolated non-production map entry")
        definition = self.timeline.definition
        self.resolver = ZoneResolver(definition, self.registry.runtime)
        self._candidate_zone: str | None = None
        self._context: tuple[Any, ...] | None = None
        self.marker = SelfMarkerTracker()
        self.inspector = MarkerReferenceInspector() if inspect_reference_appearances else None
        self.previous: tuple[float, tuple[float, float], int | None] | None = None
        self.next_segment = 0
        self.segment: int | None = None
        path = self.registry.root / "provenance.json"
        provenance = json.loads(path.read_text(encoding="utf-8"))
        self.timeline.calibrator = OutlineMinimapCalibrator(
            expected_reference_sha256=provenance["reference_sha256"],
        )
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
        self._candidate_zone = None

    def reset(self) -> None:
        """Drop all tracking/acquisition state, including a failed input call."""
        self._break()
        self.marker.reset()
        self._context = None
        assert isinstance(self.timeline.calibrator, OutlineMinimapCalibrator)
        self.timeline.calibrator.clear_reference_cache()

    def observe(
        self, frame: NDArray[Any], time_sec: float, frame_index: int, *,
        view: dict[str, Any], evidence_kind: str, source_id: str, acquisition_id: str,
    ) -> dict[str, Any]:
        if evidence_kind not in {"source_review", "unqualified_hud_observation"}:
            self.reset()
            raise ValueError("Explicit source of view evidence is required")
        try:
            valid_time = math.isfinite(time_sec) and time_sec >= 0
        except (TypeError, ValueError):
            valid_time = False
        if not valid_time:
            self.reset()
            raise ValueError("Finite non-negative source time required")
        if (not isinstance(source_id, str) or not source_id
                or not isinstance(acquisition_id, str) or not acquisition_id):
            self.reset()
            raise ValueError("Explicit source and acquisition identity required")
        if (not isinstance(frame, np.ndarray) or frame.ndim != 3
                or frame.shape[2] != 3 or frame.dtype != np.uint8):
            self.reset()
            raise ValueError("A uint8 BGR source frame is required")
        roi = self.profile.get("rois", {}).get("minimap")
        bounds = normalized_roi_bounds(roi, frame.shape[1], frame.shape[0])
        if bounds is None:
            self.reset()
            raise ValueError("Explicit valid minimap ROI required")
        left, top, right, bottom = bounds
        definition = self.timeline.definition
        assert definition is not None
        options = self.profile.get("map_zone", {})
        try:
            selected = self.registry.select(
                manual_map_id=options.get("manual_map_id") or None,
                map_label=options.get("trusted_map_label"),
                label_confidence=options.get("map_label_confidence", 0),
            )
        except (KeyError, ValueError, TypeError, AttributeError):
            selected = None
        if selected != definition.map_id:
            self.reset()
            raise ValueError("Map selection changed or became unknown; create a new timeline")
        self.timeline.options = options
        context_key = (
            source_id, acquisition_id, frame.shape, bounds,
            json.dumps(self.profile, sort_keys=True), json.dumps(definition.data, sort_keys=True),
        )
        if context_key != self._context:
            self._break()
            self.marker.reset()
            assert isinstance(self.timeline.calibrator, OutlineMinimapCalibrator)
            self.timeline.calibrator.clear_reference_cache()
            self._context = context_key
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
        reference_evidence = self.inspector.inspect(
            frame[top:bottom, left:right], self.profile["minimap_self_marker"],
        ) if self.inspector is not None else None
        if (reference_evidence is not None and appearance.x_roi_norm is not None
                and reference_evidence.get("reference_fingerprint")
                != self.marker.reference_fingerprint):
            # Two readers must not silently associate different reference bytes
            # if a private reference file is replaced during this observation.
            self.marker.reset()
            self._break()
            appearance = MarkerPosition("unknown", "reference_changed_during_observation")
        calibration = self.timeline.calibrate(frame)
        point = None
        if calibration is not None and appearance.x_roi_norm is not None:
            assert appearance.y_roi_norm is not None
            point = calibration.transform(appearance.x_roi_norm, appearance.y_roi_norm)
        diagnostics = []
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
        zone = resolution["zone_id"]
        if (point is not None and zone is not None
                and resolution["boundary_state"] == "clear"
                and not resolution["held_from_previous"]):
            if self._candidate_zone is not None and self._candidate_zone != zone:
                # Deliberately incompatible with the Production Event contract:
                # no type, actor, confidence or start_sec, and no player claim.
                events.append({
                    "candidate_kind": "zone_transition", "ownership": "UNKNOWN",
                    "qualification": "development_only",
                    "from_zone_id": self._candidate_zone, "to_zone_id": zone,
                    "observed_at_sec": time_sec, "map_segment": self.segment,
                })
            self._candidate_zone = zone
        else:
            self._candidate_zone = None
        # Nested data must also retain its boundary when copied independently
        # of this envelope. Extra keys intentionally fail the formal schema.
        resolution = {**resolution, "qualification": "development_only", "ownership": "UNKNOWN"}
        region = None
        candidates = resolution["candidate_zone_ids"]
        if (point is not None and len(candidates) == 1
                and resolution["boundary_state"] != "ambiguous"
                and not resolution["held_from_previous"]):
            # Preserve the Resolver's low-confidence / pending candidate without
            # raising its cap or converting it into an accepted named Zone.
            zone_definition = next(z for z in definition.data["zones"]
                                   if z["zone_id"] == candidates[0])
            region = {
                "region_id": candidates[0], "region_name": zone_definition["zone_name"],
                "resolver_scope": resolution["resolution_scope"],
                "geometry_confidence_cap": zone_definition["geometry_confidence_cap"],
                "qualification": "development_only", "ownership": "UNKNOWN",
            }
        return {
            "qualification": "development_only", "formal_self_position_fact": None,
            "source_id": source_id, "acquisition_id": acquisition_id,
            "context_sha256": hashlib.sha256(
                repr(context_key).encode("utf-8")
            ).hexdigest(),
            "time_sec": time_sec, "frame_index": frame_index,
            "appearance": appearance.to_dict(),
            "marker_reference_evidence": reference_evidence,
            "ownership": {"identity": "UNKNOWN", "view_eligible": eligible,
                          "observed_view": view.get("primary_state", "unknown"),
                          "view_evidence_kind": evidence_kind,
                          "reference_identity_confirmed": bool(
                              self.profile.get("reference_identity_confirmed", False))},
            "map_id": definition.map_id, "geometry_version": definition.geometry_version,
            "calibration": context, "map_position_norm": list(point) if point else None,
            "map_segment": self.segment, "map_speed_norm_per_sec": velocity,
            "zone_resolution": resolution,
            "development_region_candidate": region,
            "development_events": events,
            "diagnostics": diagnostics,
        }
