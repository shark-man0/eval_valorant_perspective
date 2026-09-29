"""Gameplay events belong to Visual; this consumer never resolves polygons."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from valorant_ai_coach.maps.registry import MapDefinition


class MapEventConsumer:
    def __init__(self, definition: MapDefinition | None, runtime: Mapping[str, Any]) -> None:
        self.definition = definition
        self.runtime = runtime
        self.reset()

    def reset(self) -> None:
        self.path: list[str] = []
        self.path_confidence = 1.0
        self.zone_since: float | None = None
        self.hold_since: float | None = None
        self.hold_emitted = False
        self.hold_confidence = 1.0
        self.rotation: dict[str, Any] | None = None
        self.allies: dict[str, dict[str, Any]] = {}

    def _usable(self, resolution: Mapping[str, Any]) -> bool:
        return bool(
            self.definition
            and resolution.get("map_id") == self.definition.map_id
            and resolution.get("geometry_version") == self.definition.geometry_version
            and resolution.get("calibration_status") == "ok"
            and resolution.get("boundary_state") == "clear"
            and resolution.get("resolution_scope") == "exact_zone"
            and not resolution.get("held_from_previous")
            and resolution.get("zone_confidence", 0)
            >= self.runtime["fusion_thresholds"]["named_zone_min"]
            and resolution.get("zone_id") in self.definition.zone_index
        )

    def consume(
        self,
        resolution: Mapping[str, Any],
        allies: Sequence[tuple[str, Mapping[str, Any]]] = (),
        *,
        stationary: bool = False,
    ) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        if self.definition is None:
            return out
        t = float(resolution["time_sec"])
        if resolution.get("calibration_status") in {"failed", "calibration_required"}:
            self.reset()
            return out
        zi = self.definition.zone_index
        edges = {
            frozenset((e["from_zone_id"], e["to_zone_id"]))
            for e in self.definition.data["topology_edges"]
            if e["active_by_default"]
        }

        def emit(
            kind: str,
            attributes: dict[str, Any],
            confidence: float,
            actor: str = "player",
            start: float | None = None,
        ) -> None:
            out.append(
                {
                    "type": kind,
                    "attributes": attributes,
                    "confidence": confidence,
                    "actor": actor,
                    "start_sec": t if start is None else start,
                }
            )

        if self._usable(resolution):
            zone = str(resolution["zone_id"])
            conf = float(resolution["zone_confidence"])
            self.path_confidence = min(self.path_confidence, conf)
            old = self.path[-1] if self.path else None
            if old != zone:
                self.zone_since = t
                self.hold_since = None
                self.hold_emitted = False
                self.hold_confidence = 1.0
                if old is not None:
                    emit(
                        "position_change",
                        {"from": old, "to": zone},
                        min(conf, self.path_confidence),
                    )
                if old is None or frozenset((old, zone)) not in edges:
                    self.path = [zone]
                    self.path_confidence = conf
                    self.rotation = None
                else:
                    self.path.append(zone)
                    self.path_confidence = min(self.path_confidence, conf)
                    origin = self.path[0]
                    origin_sites = set(zi[origin]["site_affinity"])
                    destination_sites = set(zi[zone]["site_affinity"])
                    if not origin_sites:
                        self.path = [zone]
                        self.path_confidence = conf
                    elif destination_sites and origin_sites.isdisjoint(destination_sites):
                        if self.rotation is None:
                            emit(
                                "rotation_started",
                                {
                                    "from": origin,
                                    "to": zone,
                                    "known_enemy_info_count": None,
                                    "delay_since_enemy_info_sec": None,
                                },
                                self.path_confidence,
                            )
                            self.rotation = {"from": origin, "to": zone, "start": t}
                        else:
                            self.rotation["to"] = zone
                    elif self.rotation is not None:
                        self.rotation = None
            if (
                self.rotation
                and self.zone_since is not None
                and t - self.zone_since + 1e-9
                >= self.runtime["temporal_debounce"]["rotation_destination_persistence_sec"]
            ):
                emit(
                    "rotation_completed",
                    {
                        "from": self.rotation["from"],
                        "to": zone,
                        "duration_sec": t - self.rotation["start"],
                    },
                    self.path_confidence,
                )
                self.rotation = None
                self.path, self.path_confidence = [zone], conf
            if stationary:
                if self.hold_since is None:
                    self.hold_confidence = conf
                else:
                    self.hold_confidence = min(self.hold_confidence, conf)
                self.hold_since = t if self.hold_since is None else self.hold_since
                if t - self.hold_since >= 3 and not self.hold_emitted:
                    emit(
                        "position_hold",
                        {"zone_id": zone, "duration_sec": t - self.hold_since},
                        self.hold_confidence,
                        start=self.hold_since,
                    )
                    self.hold_emitted = True
            else:
                self.hold_since, self.hold_emitted = None, False
        else:
            # Ambiguous gaps cannot count as observed destination dwell.
            self.zone_since = t
            self.hold_since, self.hold_emitted = None, False
            if not {"zone_transition_pending", "location_label_pending"}.intersection(
                resolution.get("diagnostics", ())
            ) and not resolution.get("held_from_previous"):
                self.path, self.rotation = [], None
                self.path_confidence = 1.0

        active = set()
        for track, ally in allies:
            active.add(track)
            if not self._usable(ally):
                if ally.get("calibration_status") in {"failed", "calibration_required"}:
                    self.allies.pop(track, None)
                elif track in self.allies:
                    if {"zone_transition_pending", "location_label_pending"}.intersection(
                        ally.get("diagnostics", ())
                    ) or ally.get("held_from_previous"):
                        self.allies[track]["entry"] = None
                    else:
                        self.allies.pop(track, None)
                continue
            zone, site = ally["zone_id"], ally["site_id"]
            conf = float(ally["zone_confidence"])
            previous = self.allies.get(track)
            if previous is None:
                self.allies[track] = {
                    "zone": zone,
                    "site": site,
                    "entry": None,
                    "entered": False,
                    "confidence": conf,
                }
                continue
            if zone != previous["zone"]:
                if site is not None and site != previous["site"]:
                    previous["entry"], previous["entered"] = t, False
                    previous["confidence"] = min(previous["confidence"], conf)
                    emit(
                        "ally_entry_start",
                        {"site": site, "ally_count": 1},
                        previous["confidence"],
                        actor="ally",
                    )
                elif site != previous["site"]:
                    previous["entry"] = None
                previous["zone"], previous["site"] = zone, site
            previous["confidence"] = min(previous["confidence"], conf)
            if (
                site is not None
                and previous["entry"] is not None
                and not previous["entered"]
                and t - previous["entry"] + 1e-9
                >= self.runtime["temporal_debounce"]["site_entry_persistence_sec"]
            ):
                emit(
                    "ally_enter_site",
                    {"site": site, "ally_count": 1},
                    previous["confidence"],
                    actor="ally",
                )
                previous["entered"] = True
        self.allies = {key: value for key, value in self.allies.items() if key in active}
        return out
