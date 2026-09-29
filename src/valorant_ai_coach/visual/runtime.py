"""Original-clock CV -> strict observations -> factual candidate pipeline."""

from __future__ import annotations

import hashlib
import json
from bisect import bisect_right
from collections.abc import Sequence
from pathlib import Path
from threading import Event
from typing import Any

import cv2

from valorant_ai_coach.events import EventSourceContract
from valorant_ai_coach.resources import resource_path
from valorant_ai_coach.schema_validation import SchemaValidator
from valorant_ai_coach.video import FrameSample, VideoMetadata

from .analyzer import VisualAnalysis
from .core import VisualEventEngine, project_candidate_to_v3_event
from .map_pipeline import MapTimeline
from .models import VisualObservation
from .pixels import PixelMeasurementExtractor
from .semantic import SemanticVisualAdapter


class RealVisualAnalyzer:
    def __init__(
        self,
        contract: EventSourceContract,
        *,
        profile: dict[str, Any] | None = None,
        semantic: SemanticVisualAdapter | None = None,
    ) -> None:
        self.contract = contract
        self.profile = profile or {}
        if {"map_registry", "peek_registry"} & self.profile.keys():
            raise ValueError(
                "旧Map/Zone形式は廃止されました。map_zone.registry_rootを指定してください"
            )
        sampling = json.loads(
            resource_path("config/visual_v2/config/visual_sampling_policy_v2.json").read_text()
        )
        self.trigger_fps = float(
            next(
                item["fps"]
                for item in sampling["passes"]
                if item["id"] == "B_always_on_trigger_scan"
            )
        )
        self.semantic = semantic
        self.validator = SchemaValidator()
        self.match_id = ""
        self.map_name = "unknown"
        self.round_starts: list[float] = []
        self.cancel_event: Event | None = None
        self.map_timeline: MapTimeline | None = None

    def set_cancel_event(self, value: Event | None) -> None:
        self.cancel_event = value

    def _check_cancel(self) -> None:
        if self.cancel_event is not None and self.cancel_event.is_set():
            raise InterruptedError("Visual解析がキャンセルされました")

    def begin_match(self, match_id: str, hud_events: Sequence[dict[str, Any]]) -> None:
        self.match_id = match_id
        self.round_starts = sorted(
            float(event["time_sec"]) for event in hud_events if event["type"] == "round_start"
        )
        if self.semantic:
            self.semantic.diagnostics.clear()

    def fingerprint(self) -> dict[str, Any]:
        root = resource_path("config/visual_v2/MANIFEST.json").parent
        digest = hashlib.sha256()
        for path in sorted(root.rglob("*.json")):
            digest.update(path.relative_to(root).as_posix().encode())
            digest.update(path.read_bytes())
        map_root = MapTimeline(self.profile).registry.root
        for path in sorted(map_root.rglob("*")):
            if path.is_file() and path.suffix in {".json", ".png"}:
                digest.update(path.relative_to(map_root).as_posix().encode())
                digest.update(path.read_bytes())
        paths = [
            value
            for key, value in self.profile.items()
            if key.endswith("_template") and isinstance(value, str) and value
        ]
        paths += list(self.profile.get("remote_templates", {}).values())
        for filename in sorted(paths):
            path = Path(filename)
            digest.update(filename.encode())
            digest.update(path.read_bytes() if path.is_file() else b"missing")
        return {
            "implementation": 5,
            "profile": self.profile,
            "contracts": digest.hexdigest(),
            "semantic_enabled": self.semantic is not None,
            "semantic_model": getattr(getattr(self.semantic, "transport", None), "model", None),
        }

    def _measure(
        self, frames: Sequence[FrameSample], hud: Sequence[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], dict[int, dict[str, Any]], list[str]]:
        extractor = PixelMeasurementExtractor()
        timeline = MapTimeline(self.profile)
        self.map_timeline = timeline
        ordered_hud = sorted(hud, key=lambda item: item["time_sec"])
        times = [float(item["time_sec"]) for item in ordered_hud]
        observations: list[dict[str, Any]] = []
        evidence: dict[int, dict[str, Any]] = {}
        diagnostics: list[str] = []
        previous_image = None
        previous_hud: dict[str, Any] | None = None
        for index, frame in enumerate(sorted(frames, key=lambda item: item.time_sec)):
            self._check_cancel()
            image = cv2.imread(str(frame.path))
            if image is None:
                diagnostics.append(f"visual_frame_unreadable:{frame.time_sec:.6f}")
                previous_image, previous_hud = None, None
                continue
            hi = bisect_right(times, frame.time_sec + 1e-6) - 1
            state: dict[str, Any] = (
                ordered_hud[hi]
                if hi >= 0 and frame.time_sec - times[hi] <= 0.21
                else {
                    "time_sec": frame.time_sec,
                    "primary_state": "unknown",
                    "values": {},
                    "quality": {},
                    "state_flags": [],
                }
            )
            if previous_hud is not None and frame.time_sec - previous_hud["time_sec"] > 0.3:
                previous_image, previous_hud = None, None
            # Do not spend SIFT/map-matching work on views whose positions may
            # not be attributed to the controlled player in the first place.
            map_eligible = (
                state.get("primary_state") == "live_first_person"
                and state.get("values", {}).get("player_specific_hud_valid") is True
                and not set(state.get("state_flags", ()))
                & {"visual_transition", "buy_phase_banner", "round_end_banner"}
            )
            calibration = timeline.calibrate(image) if map_eligible else None
            pixel_profile = dict(self.profile)
            pixel_profile["minimap_north_up_calibrated"] = bool(
                calibration and calibration.status == "ok"
            )
            measured = extractor.measure(
                image, previous_image, state, previous_hud, profile=pixel_profile
            )
            proof = dict(measured.pop("measurement_meta", {}))
            proof["frame_ref"] = str(frame.path)
            proof["hud_confidence"] = state.get("quality", {}).get("hud_confidence", 0.0)
            primary = proof.get("primary_state", state.get("primary_state", "unknown"))
            primary = (
                primary
                if primary
                in {
                    "live_first_person",
                    "spectator_first_person",
                    "remote_control_view",
                    "buy_menu_open",
                    "expanded_tactical_map",
                }
                else "unknown"
            )
            flags = set(state.get("state_flags", ()))
            safe = (
                primary == "live_first_person"
                and state.get("values", {}).get("player_specific_hud_valid", False)
                and not flags & {"visual_transition", "buy_phase_banner", "round_end_banner"}
            )
            obscured = bool(flags & {"vision_obscured_smoke", "vision_obscured_flash"})
            proof["vision_obscured_smoke"] = "vision_obscured_smoke" in flags
            proof["vision_obscured_flash"] = "vision_obscured_flash" in flags
            measured.update(
                time_sec=frame.time_sec,
                frame_index=index,
                hud_primary_state=primary,
                analysis_eligibility={
                    "player_mechanics": bool(safe),
                    "world_semantics": bool(
                        safe
                        and not obscured
                        and state.get("view_context", {}).get(
                            "is_player_world_view_trustworthy", False
                        )
                        and (measured.get("quality", {}).get("blur_score") or 0) < 0.9
                    ),
                    "reason_codes": [
                        "vision_obscured"
                        if obscured
                        else "live_first_person"
                        if safe
                        else "unknown_state"
                    ],
                },
            )
            measured.setdefault("quality", {}).update(occluded=obscured)
            observation = VisualObservation.from_mapping(measured).to_dict()
            timeline.resolve(observation, proof, state, calibration)
            self.validator.validate_visual_observation(observation)
            observations.append(observation)
            evidence[index] = proof
            previous_image, previous_hud = image, state
        return observations, evidence, diagnostics

    def trigger_windows(
        self,
        frames: Sequence[FrameSample],
        hud_observations: Sequence[dict[str, Any]],
        *,
        video_metadata: VideoMetadata,
    ) -> tuple[tuple[float, str], ...]:
        del video_metadata
        observations, evidence, _ = self._measure(frames, hud_observations)
        triggers = []
        previous_enemy = False
        for obs in observations:
            if not obs["analysis_eligibility"]["player_mechanics"]:
                previous_enemy = False
                continue
            action = obs["weapon_action"]
            proof = evidence[obs["frame_index"]]
            delta = action["ammo_delta"]
            cue = max(action["recoil_score"] or 0, action["muzzle_flash_score"] or 0)
            if (
                not proof.get("weapon_changed")
                and not proof.get("reload_detected")
                and ((delta is not None and delta < 0) or cue >= 0.5)
            ):
                triggers.append((obs["time_sec"], "shot"))
            visible = bool(obs["entities"]["visible_enemies"])
            if visible and not previous_enemy:
                triggers.append((obs["time_sec"], "engagement"))
            previous_enemy = visible
            if obs["utility"]["cast_candidate"]:
                triggers.append((obs["time_sec"], "utility"))
            if proof.get("cover_transition"):
                triggers.append((obs["time_sec"], "peek"))
        return tuple(triggers)

    def analyze(
        self,
        frames: Sequence[FrameSample],
        hud_observations: Sequence[dict[str, Any]],
        *,
        video_metadata: VideoMetadata,
    ) -> VisualAnalysis:
        del video_metadata
        observations, evidence, diagnostics = self._measure(frames, hud_observations)
        resolutions = [
            proof["zone_resolution"] for proof in evidence.values() if "zone_resolution" in proof
        ]
        unavailable = sum(
            r["calibration_status"] in {"failed", "calibration_required"} for r in resolutions
        )
        if unavailable:
            diagnostics.append(
                f"map_calibration_required:{unavailable}/{len(resolutions)} frames; "
                "verify Map selection and minimap profile"
            )
        if any("client_build_unverified" in r["diagnostics"] for r in resolutions):
            diagnostics.append("map_client_build_unverified")
        definition = self.map_timeline.definition if self.map_timeline else None
        engine = VisualEventEngine(map_definition=definition)
        candidates = engine.process(observations, evidence_by_frame=evidence)
        observations = [dict(item) for item in engine.enriched_observations]
        if self.semantic is not None:
            attempted: set[int] = set()
            for candidate in candidates:
                self._check_cancel()
                raw = candidate.to_dict()
                if raw["status"] != "candidate" or raw["confidence"] < 0.65:
                    continue
                if raw["semantic_confirmation"] not in {"required", "unavailable"}:
                    continue
                timestamp = raw["end_sec"]
                round_no = bisect_right(self.round_starts, timestamp)
                # A missing boundary must not create multiple invented budget buckets.
                round_id = str(round_no) if round_no else "partial"
                window = [
                    frame for frame in frames if timestamp - 1 <= frame.time_sec <= timestamp + 1
                ]
                facts = self.semantic.observe(window, match_id=self.match_id, round_id=round_id)
                if facts is None:
                    continue
                nearest = min(observations, key=lambda obs: abs(obs["time_sec"] - timestamp))
                index = nearest["frame_index"]
                if index in attempted:
                    continue
                attempted.add(index)
                proof = evidence[index]
                if facts.get("crosshair_aligned_at_visible_corner") is True:
                    proof["semantic_alignment_confidence"] = min(0.69, facts["confidence"])
                for key, value in facts.items():
                    if key != "confidence" and value is not None:
                        proof[key] = value
                        proof[f"{key}_confidence"] = facts["confidence"]
                proof["semantic_confirmed"] = [
                    key
                    for key, value in facts.items()
                    if key != "confidence" and value is not None and value != "unknown"
                ]
            engine = VisualEventEngine(map_definition=definition)
            candidates = engine.process(observations, evidence_by_frame=evidence)
            observations = [dict(item) for item in engine.enriched_observations]
            diagnostics.extend(self.semantic.diagnostics)
        self.map_name = definition.map_id if definition else "unknown"
        if definition is None:
            diagnostics.append(
                "feature_unavailable(map_geometry_missing):rotation,ally_entry,PEEK-04"
            )
        elif not definition.peek.get("anchors"):
            diagnostics.append("feature_unavailable(peek_registry_missing):PEEK-04")
        events = []
        for observation in observations:
            self.validator.validate_visual_observation(observation)
        for number, candidate in enumerate(candidates):
            self.validator.validate_visual_candidate(candidate.to_dict())
            event = project_candidate_to_v3_event(candidate, event_id=f"VIS-{number:06d}")
            if event is not None:
                self.contract.validate_event(event, "visual_analyzer")
                events.append(event)
        return VisualAnalysis(
            tuple(events),
            tuple((obs["time_sec"], obs["quality"]["visual_confidence"]) for obs in observations),
            tuple(dict.fromkeys(diagnostics)),
            tuple(observations),
            tuple(candidate.to_dict() for candidate in candidates),
            tuple(resolutions),
        )


def load_visual_profile(path: str) -> dict[str, Any]:
    if not path.strip():
        return {}
    profile_path = Path(path).expanduser().resolve()
    value = json.loads(profile_path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Visual profile must be a JSON object")
    for key, entry in list(value.items()):
        if key.endswith("_template") and isinstance(entry, str) and entry:
            value[key] = str((profile_path.parent / entry).resolve())
    for key, entry in value.get("remote_templates", {}).items():
        value["remote_templates"][key] = str((profile_path.parent / entry).resolve())
    if {"map_registry", "peek_registry"} & value.keys():
        raise ValueError("旧Map/Zone形式は廃止されました。map_zone.registry_rootを指定してください")
    if value.get("map_zone", {}).get("registry_root"):
        value["map_zone"]["registry_root"] = str(
            (profile_path.parent / value["map_zone"]["registry_root"]).resolve()
        )
    return value
