from __future__ import annotations

import math
from collections.abc import Mapping
from itertools import combinations
from typing import Any

from jsonschema import Draft202012Validator
from shapely.geometry import Point, Polygon

from .registry import MapDefinition, MapRegistry


class ZoneResolver:
    """Resolve map positions into a strict ZoneResolution timeline record."""

    _CALIBRATION_STATES = {"ok", "degraded", "failed", "calibration_required"}

    def __init__(
        self,
        definition: MapDefinition | None,
        runtime: dict[str, Any] | None = None,
    ) -> None:
        registry = MapRegistry()
        self.definition = definition
        self.runtime = runtime if runtime is not None else registry.runtime
        if not isinstance(self.runtime, dict):
            raise ValueError("runtime must be the canonical runtime contract object")
        runtime_validator = Draft202012Validator(registry.schemas["runtime"])
        if list(runtime_validator.iter_errors(self.runtime)):
            raise ValueError("runtime violates map_zone_runtime_contract_schema_v1")
        self._resolution_validator = Draft202012Validator(registry.schemas["resolution"])
        self._zone_index = definition.zone_index if definition is not None else {}
        self._polygons = {
            zone_id: Polygon(zone["polygon_norm"]) for zone_id, zone in self._zone_index.items()
        }
        self._shared_boundaries = self._make_shared_boundaries()
        self._callouts = self._make_callout_index()
        self.reset()

    def reset(self) -> None:
        """Clear label, transition, and boundary history between timelines."""
        self._label_key: str | None = None
        self._label_since: float | None = None
        self._label_last_time: float | None = None
        self._label_confidence_min = 1.0
        self._last_time: float | None = None
        self._stable_zone: str | None = None
        self._stable_confidence = 0.0
        self._candidate_zone: str | None = None
        self._candidate_since: float | None = None
        self._boundary_since: float | None = None

    def resolve(
        self,
        *,
        time_sec: float,
        frame_index: int,
        point: tuple[float, float] | None = None,
        marker_confidence: float = 0,
        calibration: dict[str, Any] | None = None,
        label: str | None = None,
        label_confidence: float = 0,
        controlled_player: bool = True,
    ) -> dict[str, Any]:
        time_value = self._finite_number(time_sec, "time_sec")
        if time_value < 0:
            raise ValueError("time_sec must be non-negative")
        if isinstance(frame_index, bool) or not isinstance(frame_index, int) or frame_index < 0:
            raise ValueError("frame_index must be a non-negative integer")
        marker_conf = self._confidence(marker_confidence, "marker_confidence")
        label_conf = self._confidence(label_confidence, "label_confidence")
        if not isinstance(controlled_player, bool):
            raise ValueError("controlled_player must be a boolean")

        diagnostics: list[str] = []
        if self._last_time is not None and time_value < self._last_time:
            self.reset()
            diagnostics.append("timeline_reset_out_of_order")
        self._last_time = time_value

        calibration_status, calibration_confidence, calibration_diagnostics = (
            self._read_calibration(calibration)
        )
        diagnostics.extend(calibration_diagnostics)
        map_id = self.definition.map_id if self.definition is not None else ""
        geometry_version = self.definition.geometry_version if self.definition is not None else ""

        if self.definition is None:
            self.reset()
            return self._resolution(
                time_value,
                frame_index,
                map_id,
                geometry_version,
                calibration_status="calibration_required",
                diagnostics=diagnostics + ["map_definition_unresolved"],
            )
        if calibration_status in {"failed", "calibration_required"}:
            self.reset()
            return self._resolution(
                time_value,
                frame_index,
                map_id,
                geometry_version,
                calibration_status=calibration_status,
                diagnostics=diagnostics,
            )

        label_zone, stable_label_conf = self._stable_callout(
            label,
            label_conf,
            time_value,
            controlled_player=controlled_player,
        )
        if (
            label_zone is None
            and self._label_key is not None
            and self._label_since is not None
            and time_value - self._label_since
            < float(self.definition.callouts["location_label_policy"]["stable_duration_sec"])
        ):
            diagnostics.append("location_label_pending")
        polygon_zone, polygon_conf, spatial_candidates, boundary_ambiguous, point_valid = (
            self._polygon_observation(point, marker_conf, calibration_confidence)
        )
        if point is not None and not point_valid:
            diagnostics.append("self_marker_position_invalid")

        (
            proposed_zone,
            proposed_confidence,
            source,
            fusion_diagnostics,
            fusion_conflict,
            degraded_fusion,
        ) = self._fuse(
            label_zone,
            stable_label_conf,
            polygon_zone,
            polygon_conf,
            boundary_ambiguous=boundary_ambiguous,
        )
        diagnostics.extend(fusion_diagnostics)
        ambiguous = boundary_ambiguous or fusion_conflict

        candidate_ids = list(spatial_candidates)
        if label_zone is not None:
            candidate_ids.append(label_zone)
        if polygon_zone is not None:
            candidate_ids.append(polygon_zone)
        if proposed_zone is not None:
            candidate_ids.append(proposed_zone)
        candidate_ids = self._ordered_unique(candidate_ids)

        if ambiguous:
            if self._boundary_since is None:
                self._boundary_since = time_value
        else:
            self._boundary_since = None

        if boundary_ambiguous and self._stable_zone in candidate_ids:
            # A held previous zone interrupts observation of any new candidate.
            self._candidate_zone = None
            self._candidate_since = None
            assert self._boundary_since is not None
            held_for = max(0.0, time_value - self._boundary_since)
            hold_limit = float(self.runtime["boundary_policy"]["previous_zone_hold_sec"])
            if held_for <= hold_limit + 1e-9:
                decay = float(self.runtime["boundary_policy"]["confidence_decay_per_sec"])
                held_confidence = max(0.0, self._stable_confidence - decay * held_for)
                return self._resolution(
                    time_value,
                    frame_index,
                    map_id,
                    geometry_version,
                    zone_id=self._stable_zone,
                    confidence=held_confidence,
                    source="held_previous_boundary",
                    calibration_status=calibration_status,
                    boundary_state="ambiguous",
                    candidate_zone_ids=candidate_ids,
                    held_from_previous=True,
                    diagnostics=diagnostics,
                )
            self._candidate_zone = None
            self._candidate_since = None
            return self._resolution(
                time_value,
                frame_index,
                map_id,
                geometry_version,
                calibration_status=calibration_status,
                boundary_state="ambiguous",
                candidate_zone_ids=candidate_ids,
                diagnostics=diagnostics + ["previous_zone_boundary_hold_expired"],
            )

        if proposed_zone is None:
            self._candidate_zone = None
            self._candidate_since = None
            if not ambiguous:
                self._stable_zone = None
                self._stable_confidence = 0.0
            if not fusion_conflict and polygon_zone is not None and polygon_conf > 0:
                return self._coarse_resolution(
                    time_value,
                    frame_index,
                    map_id,
                    geometry_version,
                    polygon_zone,
                    min(
                        polygon_conf,
                        float(
                            self.runtime["canonical_provider_ids"]["coarse_fallback"][
                                "confidence_cap"
                            ]
                        ),
                    ),
                    calibration_status,
                    "ambiguous" if ambiguous else "unknown",
                    candidate_ids,
                    diagnostics,
                )
            return self._resolution(
                time_value,
                frame_index,
                map_id,
                geometry_version,
                calibration_status=calibration_status,
                boundary_state="ambiguous" if ambiguous else "unknown",
                candidate_zone_ids=candidate_ids,
                diagnostics=diagnostics,
            )

        if degraded_fusion:
            self._candidate_zone = None
            self._candidate_since = None
            context_zone = self._zone_index[proposed_zone]
            return self._coarse_resolution(
                time_value,
                frame_index,
                map_id,
                geometry_version,
                proposed_zone,
                proposed_confidence,
                "degraded",
                "ambiguous" if ambiguous else "clear",
                candidate_ids,
                diagnostics + ["fused_zone_below_accept_threshold"],
                source=source,
                zone_context=context_zone,
            )

        named_min = float(self.runtime["fusion_thresholds"]["named_zone_min"])
        if proposed_confidence < named_min:
            self._candidate_zone = None
            self._candidate_since = None
            context_zone = self._zone_index[proposed_zone]
            return self._coarse_resolution(
                time_value,
                frame_index,
                map_id,
                geometry_version,
                proposed_zone,
                min(
                    proposed_confidence,
                    float(
                        self.runtime["canonical_provider_ids"]["coarse_fallback"]["confidence_cap"]
                    ),
                ),
                "degraded" if calibration_status == "ok" else calibration_status,
                "ambiguous" if ambiguous else "unknown",
                candidate_ids,
                diagnostics,
                source=source,
                zone_context=context_zone,
            )

        if ambiguous and self._boundary_since is not None and self._stable_zone is None:
            # With no stable zone, an ambiguous candidate must persist for the
            # normal transition interval before it becomes a named zone.
            pass
        elif not ambiguous:
            self._boundary_since = None

        if self._stable_zone == proposed_zone:
            self._stable_confidence = proposed_confidence
            self._candidate_zone = None
            self._candidate_since = None
            return self._resolution(
                time_value,
                frame_index,
                map_id,
                geometry_version,
                zone_id=proposed_zone,
                confidence=proposed_confidence,
                source=source,
                calibration_status=calibration_status,
                boundary_state="ambiguous" if ambiguous else "clear",
                candidate_zone_ids=candidate_ids or [proposed_zone],
                diagnostics=diagnostics,
            )

        if self._candidate_zone != proposed_zone:
            self._candidate_zone = proposed_zone
            self._candidate_since = time_value
        assert self._candidate_since is not None
        persistence = float(self.runtime["temporal_debounce"]["zone_transition_persistence_sec"])
        if time_value - self._candidate_since + 1e-9 < persistence:
            return self._resolution(
                time_value,
                frame_index,
                map_id,
                geometry_version,
                calibration_status=calibration_status,
                boundary_state="ambiguous" if ambiguous else "unknown",
                candidate_zone_ids=candidate_ids or [proposed_zone],
                diagnostics=diagnostics + ["zone_transition_pending"],
            )

        self._stable_zone = proposed_zone
        self._stable_confidence = proposed_confidence
        self._candidate_zone = None
        self._candidate_since = None
        return self._resolution(
            time_value,
            frame_index,
            map_id,
            geometry_version,
            zone_id=proposed_zone,
            confidence=proposed_confidence,
            source=source,
            calibration_status=calibration_status,
            boundary_state="ambiguous" if ambiguous else "clear",
            candidate_zone_ids=candidate_ids or [proposed_zone],
            diagnostics=diagnostics,
        )

    def match_peek(
        self,
        point: tuple[float, float] | None,
        resolution: Mapping[str, Any],
        position_confidence: float,
    ) -> int | None:
        """Match only a static, human-authored anchor at confidence >= 0.9."""
        if self.definition is None or point is None or not isinstance(resolution, Mapping):
            return None
        try:
            confidence = self._confidence(position_confidence, "position_confidence")
        except ValueError:
            return None
        if confidence < 0.9 or resolution.get("map_id") != self.definition.map_id:
            return None
        if (
            resolution.get("geometry_version") != self.definition.geometry_version
            or resolution.get("calibration_status") not in {"ok", "degraded"}
            or resolution.get("boundary_state") != "clear"
            or resolution.get("resolution_scope") != "exact_zone"
            or resolution.get("held_from_previous")
            or resolution.get("zone_confidence", 0) < 0.9
        ):
            return None
        try:
            x, y = self._point_value(point)
        except ValueError:
            return None

        matches: list[dict[str, Any]] = []
        for anchor in self.definition.peek.get("anchors", []):
            provenance = str(anchor.get("provenance", "")).casefold()
            if "human" not in provenance or anchor.get("confidence_cap", 0) < 0.9:
                continue
            if anchor.get("zone_id") != resolution.get("zone_id"):
                continue
            if anchor.get("site_id") not in {None, resolution.get("site_id")}:
                continue
            ax, ay = anchor["position_norm"]
            if math.hypot(x - ax, y - ay) <= anchor["radius_norm"]:
                matches.append(anchor)
        if len(matches) != 1:
            return None
        return int(matches[0]["exposed_directions_count"])

    def _read_calibration(self, calibration: dict[str, Any] | None) -> tuple[str, float, list[str]]:
        if calibration is None:
            return "calibration_required", 0.0, ["calibration_required"]
        if not isinstance(calibration, dict):
            return "calibration_required", 0.0, ["calibration_contract_invalid"]
        if not {"status", "confidence"}.issubset(calibration):
            return "calibration_required", 0.0, ["calibration_contract_incomplete"]
        status = calibration["status"]
        if status not in self._CALIBRATION_STATES:
            return "calibration_required", 0.0, ["calibration_status_invalid"]
        try:
            confidence = self._confidence(calibration["confidence"], "calibration.confidence")
        except ValueError:
            return "calibration_required", 0.0, ["calibration_confidence_invalid"]
        diagnostics = calibration.get("diagnostics", [])
        if not isinstance(diagnostics, list) or any(
            not isinstance(item, str) for item in diagnostics
        ):
            return "calibration_required", 0.0, ["calibration_diagnostics_invalid"]
        return status, confidence, list(diagnostics)

    def _stable_callout(
        self,
        label: str | None,
        confidence: float,
        time_value: float,
        *,
        controlled_player: bool,
    ) -> tuple[str | None, float]:
        if (
            self.definition is None
            or label is None
            or not controlled_player
            or confidence < float(self.runtime["fusion_thresholds"]["support"])
        ):
            self._clear_label()
            return None, 0.0
        record = self._callouts.get(self._normalize_label(label))
        if record is None:
            self._clear_label()
            return None, 0.0
        key, zone_id = record
        if self._label_key != key:
            self._label_key = key
            self._label_since = time_value
            self._label_last_time = time_value
            self._label_confidence_min = confidence
        else:
            if self._label_last_time is not None and time_value - self._label_last_time > 0.5:
                self._label_since = time_value
                self._label_confidence_min = confidence
            else:
                self._label_confidence_min = min(self._label_confidence_min, confidence)
            self._label_last_time = time_value
        assert self._label_since is not None
        duration = float(self.definition.callouts["location_label_policy"]["stable_duration_sec"])
        if time_value - self._label_since + 1e-9 < duration:
            return None, 0.0
        cap = float(self.definition.callouts["records"][key]["confidence_cap"])
        return zone_id, min(self._label_confidence_min, cap)

    def _clear_label(self) -> None:
        self._label_key = None
        self._label_since = None
        self._label_last_time = None
        self._label_confidence_min = 1.0

    def _make_callout_index(self) -> dict[str, tuple[str, str]]:
        if self.definition is None:
            return {}
        indexed: dict[str, tuple[str, str]] = {}
        for name, record in self.definition.callouts.get("records", {}).items():
            zone_id = str(record["zone_id"])
            indexed[self._normalize_label(name)] = (name, zone_id)
            for aliases in record["aliases"].values():
                for alias in aliases:
                    indexed[self._normalize_label(alias)] = (name, zone_id)
        return indexed

    def _polygon_observation(
        self,
        point: tuple[float, float] | None,
        marker_confidence: float,
        calibration_confidence: float,
    ) -> tuple[str | None, float, list[str], bool, bool]:
        if self.definition is None or point is None:
            return None, 0.0, [], False, point is None
        try:
            x, y = self._point_value(point)
        except ValueError:
            return None, 0.0, [], False, False
        if x < 0 or x > 1 or y < 0 or y > 1:
            return None, 0.0, [], False, False
        point_geometry = Point(x, y)
        containing = [
            zone_id for zone_id, polygon in self._polygons.items() if polygon.covers(point_geometry)
        ]
        candidates = list(containing)
        boundary_candidates: set[str] = set(containing)
        margin = float(self.runtime["boundary_policy"]["margin_norm"])
        for (left, right), shared in self._shared_boundaries.items():
            if not shared.is_empty and point_geometry.distance(shared) <= margin + 1e-12:
                boundary_candidates.update((left, right))
        ambiguous = len(containing) > 1 or len(boundary_candidates) > 1
        if ambiguous:
            candidates = [zone_id for zone_id in self._zone_index if zone_id in boundary_candidates]
            if len(containing) != 1:
                return None, 0.0, candidates, True, True
        if len(containing) != 1:
            return None, 0.0, candidates, ambiguous, True
        zone_id = containing[0]
        zone = self._zone_index[zone_id]
        confidence = min(
            calibration_confidence,
            marker_confidence,
            float(self.definition.data["geometry_confidence_cap"]),
            float(zone["geometry_confidence_cap"]),
        )
        return zone_id, confidence, candidates or [zone_id], ambiguous, True

    def _make_shared_boundaries(self) -> dict[tuple[str, str], Any]:
        if self.definition is None:
            return {}
        boundaries: dict[tuple[str, str], Any] = {}
        for left, right in combinations(self._polygons, 2):
            shared = self._polygons[left].boundary.intersection(self._polygons[right].boundary)
            if not shared.is_empty:
                boundaries[(left, right)] = shared
                boundaries[(right, left)] = shared
        return boundaries

    def _fuse(
        self,
        label_zone: str | None,
        label_confidence: float,
        polygon_zone: str | None,
        polygon_confidence: float,
        *,
        boundary_ambiguous: bool,
    ) -> tuple[str | None, float, str, list[str], bool, bool]:
        thresholds = self.runtime["fusion_thresholds"]
        accept = float(thresholds["accept"])
        support = float(thresholds["support"])
        diagnostics: list[str] = []

        if (
            label_zone is not None
            and polygon_zone is not None
            and label_zone == polygon_zone
            and label_confidence >= support
            and polygon_confidence >= support
        ):
            if label_confidence < accept and polygon_confidence < accept:
                # The reference helper's earlier same-zone branch shadows this
                # degraded case; the contract requires min confidence here.
                return (
                    label_zone,
                    min(label_confidence, polygon_confidence),
                    "fused_label_polygon",
                    diagnostics,
                    False,
                    True,
                )
            return (
                label_zone,
                max(label_confidence, polygon_confidence),
                "fused_label_polygon",
                diagnostics,
                False,
                False,
            )

        if (
            label_zone is not None
            and label_confidence >= accept
            and (polygon_zone is None or polygon_confidence < support)
        ):
            return label_zone, label_confidence, "location_label", diagnostics, False, False
        if (
            polygon_zone is not None
            and polygon_confidence >= accept
            and (label_zone is None or label_confidence < support)
        ):
            return polygon_zone, polygon_confidence, "polygon", diagnostics, False, False

        if label_zone is not None and polygon_zone is not None and label_zone != polygon_zone:
            if label_confidence >= accept and polygon_confidence >= accept:
                diagnostics.append("zone_conflict_high_confidence")
                return None, 0.0, "unknown", diagnostics, True, False
            if label_confidence >= accept and polygon_confidence >= support:
                diagnostics.append("source_disagreement_secondary")
                return label_zone, label_confidence, "location_label", diagnostics, False, False
            if polygon_confidence >= accept and label_confidence >= support:
                diagnostics.append("source_disagreement_secondary")
                return polygon_zone, polygon_confidence, "polygon", diagnostics, False, False

        return None, 0.0, "unknown", diagnostics, False, False

    def _coarse_resolution(
        self,
        time_value: float,
        frame_index: int,
        map_id: str,
        geometry_version: str,
        context_zone_id: str,
        confidence: float,
        calibration_status: str,
        boundary_state: str,
        candidates: list[str],
        diagnostics: list[str],
        *,
        source: str = "coarse_fallback",
        zone_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        context = zone_context or self._zone_index[context_zone_id]
        result = self._resolution(
            time_value,
            frame_index,
            map_id,
            geometry_version,
            site_id=context["site_id"] if context["kind"] == "site" else None,
            site_affinity=list(context["site_affinity"]),
            confidence=confidence,
            scope="coarse_role",
            source=source,
            calibration_status=calibration_status,
            boundary_state=boundary_state,
            candidate_zone_ids=candidates,
            diagnostics=diagnostics,
        )
        return result

    def _resolution(
        self,
        time_value: float,
        frame_index: int,
        map_id: str,
        geometry_version: str,
        *,
        zone_id: str | None = None,
        site_id: str | None = None,
        site_affinity: list[str] | None = None,
        confidence: float = 0.0,
        scope: str | None = None,
        source: str | None = None,
        calibration_status: str,
        boundary_state: str | None = None,
        candidate_zone_ids: list[str] | None = None,
        held_from_previous: bool = False,
        diagnostics: list[str] | None = None,
    ) -> dict[str, Any]:
        zone = self._zone_index.get(zone_id) if zone_id is not None else None
        if zone is not None:
            kind: str | None = str(zone["kind"])
            site_id = zone["site_id"]
            site_affinity = list(zone["site_affinity"])
            scope = "exact_zone"
        else:
            kind = None
            site_affinity = list(site_affinity or [])
            scope = scope or "unknown"
        if scope == "unknown":
            zone_id = None
            site_id = None
            site_affinity = []
            confidence = 0.0
        result = {
            "time_sec": time_value,
            "frame_index": frame_index,
            "map_id": map_id,
            "geometry_version": geometry_version,
            "zone_id": zone_id,
            "zone_kind": kind,
            "site_id": site_id,
            "site_affinity": site_affinity,
            "zone_confidence": max(0.0, min(1.0, float(confidence))),
            "resolution_scope": scope,
            "resolution_source": source or ("unknown" if zone_id is None else "polygon"),
            "calibration_status": calibration_status,
            "boundary_state": boundary_state or ("clear" if zone_id is not None else "unknown"),
            "candidate_zone_ids": self._ordered_unique(candidate_zone_ids or []),
            "held_from_previous": held_from_previous,
            "diagnostics": list(dict.fromkeys(diagnostics or [])),
        }
        errors = list(self._resolution_validator.iter_errors(result))
        if errors:
            detail = "; ".join(error.message for error in errors[:5])
            raise RuntimeError(f"Generated invalid ZoneResolution: {detail}")
        return result

    def _ordered_unique(self, zone_ids: list[str]) -> list[str]:
        unique = set(zone_ids)
        return [zone_id for zone_id in self._zone_index if zone_id in unique]

    @staticmethod
    def _normalize_label(value: str) -> str:
        return " ".join(value.strip().casefold().split())

    @staticmethod
    def _point_value(point: tuple[float, float]) -> tuple[float, float]:
        if not isinstance(point, (tuple, list)) or len(point) != 2:
            raise ValueError("point must contain normalized x and y")
        x = ZoneResolver._finite_number(point[0], "point.x")
        y = ZoneResolver._finite_number(point[1], "point.y")
        return x, y

    @staticmethod
    def _finite_number(value: Any, label: str) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{label} must be a finite number")
        number = float(value)
        if not math.isfinite(number):
            raise ValueError(f"{label} must be a finite number")
        return number

    @classmethod
    def _confidence(cls, value: Any, label: str) -> float:
        number = cls._finite_number(value, label)
        if not 0 <= number <= 1:
            raise ValueError(f"{label} must be in [0, 1]")
        return number
