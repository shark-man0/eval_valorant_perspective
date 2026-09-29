"""Image calibration and strict resolver timelines; no gameplay event generation."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from numpy.typing import NDArray

from valorant_ai_coach.maps.calibration import CalibrationResult, MinimapCalibrator
from valorant_ai_coach.maps.registry import MapRegistry
from valorant_ai_coach.maps.resolver import ZoneResolver


class MapTimeline:
    def __init__(self, profile: dict[str, Any]) -> None:
        self.profile = profile
        self.options = profile.get("map_zone", {})
        root = self.options.get("registry_root")
        self.registry = MapRegistry(Path(root) if root else None)
        selected = self.registry.select(
            manual_map_id=self.options.get("manual_map_id") or None,
            map_label=self.options.get("trusted_map_label"),
            label_confidence=self.options.get("map_label_confidence", 0),
        )
        self.definition = self.registry.load(selected) if selected else None
        self.resolver = ZoneResolver(self.definition, self.registry.runtime)
        self.calibrator = MinimapCalibrator()
        self.tracks: dict[str, dict[str, Any]] = {}
        self.next_track = 0
        self.previous: tuple[float, tuple[float, float]] | None = None
        self.last_time: float | None = None

    def calibrate(self, frame: NDArray[Any]) -> CalibrationResult | None:
        roi = self.profile.get("rois", {}).get("minimap")
        if roi is None:
            return None
        if self.definition is None:
            scores = {}
            results = {}
            # Selection is confidence-gated even when exactly one map is installed.
            for map_id, entry in self.registry.data["maps"].items():
                if not entry.get("production", False):
                    continue
                definition = self.registry.load(map_id)
                result = self.calibrator.analyze(frame, roi, definition, profile=self.options)
                if result.status == "ok":
                    scores[map_id], results[map_id] = result.confidence, result
            selected = self.registry.select(template_scores=scores)
            if selected:
                self.definition = self.registry.load(selected)
                self.resolver = ZoneResolver(self.definition, self.registry.runtime)
                return results[selected]
            return None
        return self.calibrator.analyze(frame, roi, self.definition, profile=self.options)

    def resolve(
        self,
        observation: dict[str, Any],
        proof: dict[str, Any],
        hud: dict[str, Any],
        calibration: CalibrationResult | None,
    ) -> None:
        t, index = observation["time_sec"], observation["frame_index"]
        minimap = observation["minimap"]
        safe = observation["analysis_eligibility"]["player_mechanics"]
        if not safe or (self.last_time is not None and not 0 < t - self.last_time <= 0.5):
            self.resolver.reset()
            self.tracks.clear()
            self.previous = None
        self.last_time = float(t)
        context = (
            {
                "status": calibration.status,
                "confidence": calibration.confidence,
                "diagnostics": list(calibration.diagnostics),
            }
            if calibration
            else {
                "status": "calibration_required",
                "confidence": 0,
                "diagnostics": ["map_selection_or_calibration_required"],
            }
        )
        point = None
        if calibration and safe and minimap.get("self_x_norm") is not None:
            point = calibration.transform(minimap["self_x_norm"], minimap["self_y_norm"])
        if point is not None:
            minimap["self_x_norm"], minimap["self_y_norm"] = point
        else:
            minimap["self_x_norm"] = minimap["self_y_norm"] = None
        observation["motion"]["map_displacement_norm_per_sec"] = (
            math.dist(point, self.previous[1]) / (t - self.previous[0])
            if point is not None and self.previous and 0 < t - self.previous[0] <= 0.5
            else None
        )
        self.previous = (t, point) if point is not None else None
        values = hud.get("values", {})
        quality = hud.get("quality", {})
        resolution = self.resolver.resolve(
            time_sec=t,
            frame_index=index,
            point=point,
            marker_confidence=minimap["track_confidence"],
            calibration=context,
            label=values.get("location_text"),
            label_confidence=quality.get("roi_confidence", {}).get("location_label", 0),
            controlled_player=bool(safe),
        )
        proof["zone_resolution"] = resolution
        proof["static_peek_exposure"] = (
            self.resolver.match_peek(point, resolution, minimap["track_confidence"])
            if point is not None
            else None
        )
        allies = []
        available = {key: value for key, value in self.tracks.items() if t - value["time"] <= 0.5}
        updated = {}
        transformed = []
        for marker in minimap["ally_markers"] if safe and calibration else ():
            assert calibration is not None
            p = calibration.transform(marker["x_norm"], marker["y_norm"])
            if (
                p is None
                or marker["confidence"] < self.registry.runtime["fusion_thresholds"]["accept"]
            ):
                continue
            marker["x_norm"], marker["y_norm"] = p
            transformed.append((marker, p))
        for marker, p in transformed:
            matches = [
                key for key, value in available.items() if math.dist(p, value["point"]) < 0.15
            ]
            unique_reverse = (
                len(matches) == 1
                and sum(
                    math.dist(other, available[matches[0]]["point"]) < 0.15
                    for _, other in transformed
                )
                == 1
            )
            if unique_reverse:
                key = matches[0]
                track = available.pop(key)
            else:
                key = f"ally-{self.next_track}"
                self.next_track += 1
                track = {"resolver": ZoneResolver(self.definition, self.registry.runtime)}
            track.update(point=p, time=t)
            updated[key] = track
            allies.append(
                (
                    key,
                    track["resolver"].resolve(
                        time_sec=t,
                        frame_index=index,
                        point=p,
                        marker_confidence=marker["confidence"],
                        calibration=context,
                        controlled_player=False,
                    ),
                )
            )
        minimap["ally_markers"] = [marker for marker, _ in transformed]
        enemies = []
        for marker in minimap["enemy_markers"] if safe and calibration else ():
            assert calibration is not None
            p = calibration.transform(marker["x_norm"], marker["y_norm"])
            if p is not None:
                marker["x_norm"], marker["y_norm"] = p
                enemies.append(marker)
        minimap["enemy_markers"] = enemies
        self.tracks = updated
        proof["ally_zone_resolutions"] = allies
