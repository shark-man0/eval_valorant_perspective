from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from threading import Event
from typing import Any, Protocol

from valorant_ai_coach.models import RoleResolver
from valorant_ai_coach.video import FrameSample, VideoMetadata
from valorant_ai_coach.video.sampling import HudFrameSampler

from .classifier import HudStateClassifier
from .diagnostics import CalibrationTelemetry
from .identity import live_identity
from .layout import CalibrationResult, HudLayout, NormalizedRoi
from .models import HudObservationV2, accept_hud_value, empty_hud_values
from .readers import (
    FrameFeatureObservation,
    HudReader,
    OpenCvHudFeatureReader,
    ReaderResult,
    crop_roi,
    load_frame,
)
from .templates import HudTemplateProfile, TesseractDigitsReader, load_profile_readers
from .temporal import HudDirectEventBuilder


class HudAnalysisError(RuntimeError):
    pass


class HudNotCalibratedError(HudAnalysisError):
    pass


@dataclass(frozen=True, slots=True)
class HudObservations:
    round_packages: tuple[dict[str, Any], ...]
    analyzer_name: str
    diagnostics: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class HudFrameAnalysis:
    """Frame-level HUD output before Round Package construction."""

    observations: tuple[dict[str, Any], ...]
    hud_events: tuple[dict[str, Any], ...]
    change_times_sec: tuple[float, ...]
    calibration: CalibrationResult
    feature_observations: tuple[FrameFeatureObservation, ...] = ()
    diagnostics: tuple[str, ...] = ()
    calibration_diagnostics: dict[str, Any] = field(default_factory=dict)


class HudAnalyzer(Protocol):
    def analyze(
        self,
        frames: Sequence[FrameSample],
        timestamps: Sequence[float] | None = None,
        *,
        video_metadata: VideoMetadata | None = None,
        match_id: str | None = None,
    ) -> HudObservations: ...


class MockHudAnalyzer:
    """Return fixture Round Packages through the same HUD boundary as production."""

    def __init__(self, packages: Sequence[dict[str, Any]] | Path) -> None:
        if isinstance(packages, Path):
            import json

            raw = json.loads(packages.read_text(encoding="utf-8"))
            if isinstance(raw, dict) and "round_packages" in raw:
                raw = raw["round_packages"]
            elif isinstance(raw, dict):
                raw = [raw]
            if not isinstance(raw, list) or not all(isinstance(item, dict) for item in raw):
                raise ValueError("Mock HUD JSONはRound Packageまたはその配列で指定してください")
            self._packages = tuple(raw)
        else:
            self._packages = tuple(deepcopy(list(packages)))
        if not self._packages:
            raise ValueError("Mock HUDには1件以上のRound Packageが必要です")

    def analyze(
        self,
        frames: Sequence[FrameSample],
        timestamps: Sequence[float] | None = None,
        *,
        video_metadata: VideoMetadata | None = None,
        match_id: str | None = None,
    ) -> HudObservations:
        del frames, timestamps
        packages = deepcopy(self._packages)
        diagnostics: list[str] = ["Mock Round Packageを使用しています"]
        for package in packages:
            if match_id:
                package["match_id"] = match_id
            if video_metadata is not None:
                latest_observation = self._latest_observation_sec(package)
                if latest_observation > video_metadata.duration_sec + 0.05:
                    raise HudAnalysisError(
                        "選択動画がMock Round Packageの観測時刻より短いです"
                        f"（{latest_observation:.1f}秒以上が必要）"
                    )
                package["round_window"]["end_sec"] = min(
                    float(package["round_window"]["end_sec"]),
                    video_metadata.duration_sec,
                )
                package["source_video"] = {
                    "path": str(video_metadata.path),
                    "fps": video_metadata.fps,
                    "width": video_metadata.width,
                    "height": video_metadata.height,
                    "duration_sec": video_metadata.duration_sec,
                }
        return HudObservations(tuple(packages), "mock", tuple(diagnostics))

    @staticmethod
    def _latest_observation_sec(package: dict[str, Any]) -> float:
        values = [float(package["round_window"]["start_sec"])]
        for collection in ("events", "state_snapshots", "frames"):
            values.extend(
                float(item["time_sec"])
                for item in package.get(collection, [])
                if item.get("time_sec") is not None
            )
        for fact in package.get("deterministic_facts", []):
            if fact.get("time_sec") is not None:
                values.append(float(fact["time_sec"]))
            if fact.get("time_range") is not None:
                values.append(float(fact["time_range"]["end_sec"]))
        return max(values)


class RealHudAnalyzer:
    """Config-driven boundary reserved for screenshot-based calibration.

    The class deliberately refuses uncalibrated layouts. No guessed VALORANT HUD
    coordinates are embedded in source code.
    """

    def __init__(
        self,
        layout_path: Path,
        ocr_reader: Any | None = None,
        role_resolver: RoleResolver | None = None,
        *,
        readers: Mapping[str, HudReader[Any]] | None = None,
        template_profile_path: Path | None = None,
    ) -> None:
        self.layout_path = Path(layout_path)
        self.layout = HudLayout.load(self.layout_path)
        self.ocr_reader = ocr_reader
        self.role_resolver = role_resolver or RoleResolver()
        auto_profile = self.layout_path.with_name(f"{self.layout_path.stem}.templates.json")
        self.template_profile_path = (
            Path(template_profile_path) if template_profile_path else auto_profile
        )
        self.template_profile: HudTemplateProfile | None = None
        self.profile_diagnostics: list[str] = []
        try:
            self.template_profile, profile_readers = load_profile_readers(
                self.template_profile_path
            )
        except ValueError as exc:
            profile_readers = {}
            self.profile_diagnostics.append(f"template profile: {exc}")
        if self.template_profile is not None:
            self.profile_diagnostics.extend(self.template_profile.reader_diagnostics)
        self.readers = {**profile_readers, **dict(readers or {})}
        self.digit_ocr_reader = self.ocr_reader or TesseractDigitsReader()
        self.feature_reader = OpenCvHudFeatureReader(self.layout)
        self.state_classifier = HudStateClassifier()

    def fingerprint(self) -> str:
        """Hash the layout, selected profile, and all referenced template bytes."""

        if self.template_profile is not None:
            return self.template_profile.fingerprint(self.layout_path)
        digest = hashlib.sha256(self.layout_path.read_bytes())
        if self.template_profile_path.exists():
            digest.update(self.template_profile_path.read_bytes())
        return digest.hexdigest()

    def analyze(
        self,
        frames: Sequence[FrameSample],
        timestamps: Sequence[float] | None = None,
        *,
        video_metadata: VideoMetadata | None = None,
        match_id: str | None = None,
    ) -> HudObservations:
        del timestamps, video_metadata, match_id
        if not self.layout.calibrated:
            raise HudNotCalibratedError(
                "HUD ROIは未校正です。実スクリーンショットからhud_layout.jsonを作成してください"
            )
        if not frames:
            return HudObservations((), "real", ("HUD frameがありません",))
        raise HudAnalysisError(
            "実動画解析にはHudVideoProcessor経由でobserve_framesを使用してください"
        )

    def observe_frames(
        self,
        frames: Sequence[Any],
        video_metadata: VideoMetadata | None = None,
        *,
        anchor_detections: Mapping[str, Sequence[float] | NormalizedRoi]
        | Sequence[Mapping[str, Sequence[float] | NormalizedRoi]]
        | None = None,
        letterboxed: bool | None = None,
        crop_applied: bool | None = None,
        additional_signals: Sequence[Mapping[str, Any]] | None = None,
        cancel_event: Event | None = None,
    ) -> HudFrameAnalysis:
        """Observe sampled frames and return HUD facts before package building.

        The built-in reader always measures configured ROI pixels. V3 observation
        values are released only after geometry and anchor calibration succeeds;
        tests or production template detectors can supply normalized anchor boxes.
        """

        if additional_signals is not None and len(additional_signals) != len(frames):
            raise ValueError("additional_signalsの件数はframesと一致する必要があります")
        telemetry = CalibrationTelemetry(self.template_profile, self.layout)
        self.last_calibration_diagnostics = telemetry.snapshot()
        if not frames:
            calibration = CalibrationResult(
                False, ("no_frames", "calibration_required"), 0, None, None
            )
            return HudFrameAnalysis((), (), (), calibration, (), ("HUD frameがありません",))

        if cancel_event is not None and cancel_event.is_set():
            raise InterruptedError("HUD frame analysis was cancelled")

        first_image = load_frame(frames[0])
        first_height, first_width = first_image.shape[:2]
        detected_anchors = _first_anchor_set(anchor_detections)
        anchor_scores: dict[str, float] = {}
        if detected_anchors is not None:
            anchor_scores = {name: 1.0 for name in detected_anchors}
        anchor_diagnostics: tuple[str, ...] = ()
        if detected_anchors is None and self.template_profile is not None:
            detected_anchors, anchor_scores, anchor_diagnostics = (
                self.template_profile.detect_anchors(
                    first_image,
                    self.layout,
                )
            )
        letterbox_seen = (
            _detect_letterbox(first_image) if letterboxed is None else bool(letterboxed)
        )
        del first_image
        crop_state = crop_applied
        if crop_state is None:
            if video_metadata is not None:
                metadata_aspect = video_metadata.width / video_metadata.height
                frame_aspect = first_width / first_height
                crop_state = abs(metadata_aspect - frame_aspect) > 0.005
            elif self.layout.reference_resolution == (first_width, first_height):
                crop_state = False

        features = self.feature_reader.observe_sequence(
            frames,
            times=[_frame_time(frame, index) for index, frame in enumerate(frames)],
            cancel_event=cancel_event,
        )
        dimensions_match = all(
            feature.signals.get("frame_width") == first_width
            and feature.signals.get("frame_height") == first_height
            for feature in features
        )

        if self.layout.layout_format == "v3":
            calibration = self.layout.validate_calibration(
                first_width,
                first_height,
                detected_anchors=detected_anchors,
                letterboxed=letterbox_seen,
                crop_applied=crop_state,
            )
        elif (
            self.layout.calibrated
            and dimensions_match
            and crop_state is False
            and not letterbox_seen
        ):
            calibration = CalibrationResult(True, (), 0, 0.0, 0.0)
        else:
            reasons = []
            if not self.layout.calibrated:
                reasons.append("layout_uncalibrated")
            if not dimensions_match:
                reasons.append("frame_resolution_changed")
            if letterbox_seen:
                reasons.append("letterbox_present")
            if crop_state is not False:
                reasons.append("crop_unknown_or_present")
            calibration = CalibrationResult(
                False, tuple(reasons or ["calibration_required"]), 0, None, None
            )
        if not dimensions_match:
            calibration = CalibrationResult(False, ("frame_resolution_changed",), 0, None, None)

        observations: list[dict[str, Any]] = []
        evidence_by_frame: dict[int, Mapping[str, Any]] = {}
        diagnostics: list[str] = [*self.profile_diagnostics, *anchor_diagnostics]
        if not calibration.calibrated:
            diagnostics.append("calibration_required: " + ", ".join(calibration.reasons))

        current_anchors = detected_anchors or {}
        current_calibration = calibration
        for index, (frame, feature) in enumerate(zip(frames, features, strict=True)):
            if cancel_event is not None and cancel_event.is_set():
                raise InterruptedError("HUD frame analysis was cancelled")
            image = load_frame(frame)
            time_sec = _frame_time(frame, index)
            if index > 0 and dimensions_match and self.template_profile is not None:
                current_anchors, anchor_scores, messages = self.template_profile.detect_anchors(
                    image, self.layout
                )
                diagnostics.extend(messages)
                current_calibration = self.layout.validate_calibration(
                    image.shape[1],
                    image.shape[0],
                    detected_anchors=current_anchors,
                    letterboxed=_detect_letterbox(image),
                    crop_applied=crop_state,
                )
                # Overlays can hide anchors. Never reuse old anchor scores to
                # classify those frames as live. A later clear frame can calibrate
                # a recording that began with a buy menu or transition.
                # Missing anchors alone may be an overlay. A measured geometry
                # violation must invalidate the previous calibration even when
                # that violation also hides most anchors (e.g. letterboxing).
                geometry_invalid = any(
                    reason != "insufficient_anchors" for reason in current_calibration.reasons
                )
                if current_calibration.calibrated or geometry_invalid:
                    calibration = current_calibration
            signals = dict(feature.signals)
            if calibration.calibrated and self.template_profile is not None:
                signals.update(
                    self.template_profile.detect_signals(image, self.layout, context=signals)
                )
            signals["template_anchor_scores"] = dict(anchor_scores)
            supplemental = {} if additional_signals is None else dict(additional_signals[index])
            signals.update(supplemental)
            values = empty_hud_values()
            reader_confidence: dict[str, float] = {}
            identity_count = 0
            if calibration.calibrated:
                self._read_values(image, values, reader_confidence, calibration, diagnostics)
                for side, key in (("ally", "ally_alive"), ("enemy", "enemy_alive")):
                    debounced = _debounced_roster_count(features, index, side)
                    if debounced is not None and f"{side}_roster" not in self.readers:
                        values[key], confidence = debounced
                        reader_confidence[f"{side}_roster"] = confidence
                _enrich_temporal_evidence(
                    signals, values, observations[-1] if observations else None
                )
            identity = live_identity(signals, geometry_valid=calibration.calibrated)
            identity_count = identity.positive_count
            signals["live_first_person"] = identity.live
            if calibration.calibrated:
                classified = self.state_classifier.classify(signals)
            else:
                classified = self.state_classifier.classify({})

            telemetry.record(
                current_anchors,
                anchor_scores,
                current_calibration,
                calibration,
                classified.primary_state,
                identity_count,
            )
            telemetry.identity_reasons[identity.reason] += 1
            telemetry.spectator_checks[
                signals.get("spectator_detector_reason", "not_evaluated")
            ] += 1
            for key in ("hp_hud_structure", "ability_bar_structure", "weapon_ammo_structure"):
                score = signals.get(key + "_confidence", 0)
                if (
                    signals.get(key) is not True
                    or not isinstance(score, (int, float))
                    or isinstance(score, bool)
                    or not 0.90 <= score <= 1
                ):
                    telemetry.identity_missing[key] += 1

            values["player_specific_hud_valid"] = (
                classified.player_specific_hud_valid if calibration.calibrated else False
            )
            values["combat_report_visible"] = "combat_report_visible" in classified.state_flags
            values["buy_phase_visible"] = "buy_phase_banner" in classified.state_flags
            # Readers describe HUD inputs only. Player values are cleared when
            # their identity is not attributable to the recording player.
            if not values["player_specific_hud_valid"]:
                for key in ("hp", "armor", "ammo_current", "ammo_reserve", "weapon_text"):
                    values[key] = None
                values["ability_slots"] = []
            # This is value-reader provenance, distinct from feature/ROI geometry
            # confidence. It is nonzero only for a current, accepted, owned HP value.
            hp_value_confidence = reader_confidence.get("player_hp_armor", 0.0)
            if (
                not calibration.calibrated
                or values["player_specific_hud_valid"] is not True
                or type(values.get("hp")) is not int
                or not 0 <= values["hp"] <= 100
                or isinstance(hp_value_confidence, bool)
                or not isinstance(hp_value_confidence, (int, float))
                or not math.isfinite(float(hp_value_confidence))
            ):
                hp_value_confidence = 0.0
            else:
                hp_value_confidence = min(1.0, max(0.0, float(hp_value_confidence)))
            quality = {
                "hud_confidence": min([classified.confidence, *reader_confidence.values()])
                if calibration.calibrated
                else 0.0,
                "visual_confidence": 0.0,
                "occluded_rois": [
                    name
                    for name in ("center_crosshair_area",)
                    if "vision_obscured_smoke" in classified.state_flags
                    or "vision_obscured_flash" in classified.state_flags
                ],
                "notes": (
                    ["low_detail_scene_unresolved"]
                    if signals.get("smoke_ambiguous")
                    and not classified.is_player_world_view_trustworthy
                    and classified.primary_state == "live_first_person"
                    and "vision_obscured_smoke" not in classified.state_flags
                    else []
                )
                if calibration.calibrated
                else ["calibration_required"],
                "state_confidence": classified.confidence if calibration.calibrated else 0.0,
                "roi_confidence": {
                    **feature.roi_confidence,
                    **reader_confidence,
                    # Reserved value provenance, independent of generic ROI/geometry
                    # quality. Never authorize shared facts from feature confidence.
                    "round_timer_value": reader_confidence.get("round_timer", 0.0)
                    if values["round_time_remaining_sec"] is not None
                    else 0.0,
                    "hp_value": hp_value_confidence,
                },
            }
            observation = HudObservationV2(
                time_sec=time_sec,
                frame_index=index,
                primary_state=classified.primary_state if calibration.calibrated else "unknown",
                state_flags=classified.state_flags if calibration.calibrated else (),
                values=values,
                quality=quality,
                remote_view_type=(
                    classified.remote_view_type
                    if calibration.calibrated and classified.primary_state == "remote_control_view"
                    else "none"
                ),
                is_player_world_view_trustworthy=(
                    classified.is_player_world_view_trustworthy and calibration.calibrated
                ),
            )
            observations.append(observation.to_dict())
            row_evidence = {
                **signals,
                "reader_confidence": reader_confidence,
                "ally_alive": values["ally_alive"],
                "enemy_alive": values["enemy_alive"],
                "ally_alive_confidence": reader_confidence.get("ally_roster", 0.0),
                "enemy_alive_confidence": reader_confidence.get("enemy_roster", 0.0),
                "player_specific_hud_valid": values["player_specific_hud_valid"],
            }
            if classified.primary_state == "spectator_first_person":
                row_evidence["spectator_transition"] = (
                    index > 0 and observations[index - 1]["primary_state"] == "live_first_person"
                )
            for flag, effect in (
                ("vision_obscured_flash", "flash"),
                ("vision_obscured_smoke", "smoke"),
            ):
                if flag in classified.state_flags:
                    row_evidence.update(
                        confirmed_status_effect=effect,
                        affected_side="player",
                        status_confidence=classified.flag_confidence[flag],
                        status_cross_checked=True,
                    )
            evidence_by_frame[index] = {**row_evidence, **supplemental}

        hud_events = HudDirectEventBuilder().build(
            observations, evidence_by_frame=evidence_by_frame
        )
        change_times = set(_observation_change_times(observations, evidence_by_frame))
        change_times.update(float(event["time_sec"]) for event in hud_events)
        self.last_calibration_diagnostics = telemetry.snapshot()
        return HudFrameAnalysis(
            observations=tuple(observations),
            hud_events=hud_events,
            change_times_sec=tuple(sorted(change_times)),
            calibration=calibration,
            feature_observations=features,
            diagnostics=tuple(dict.fromkeys(diagnostics)),
            calibration_diagnostics=self.last_calibration_diagnostics,
        )

    def _read_values(
        self,
        image: Any,
        values: dict[str, Any],
        reader_confidence: dict[str, float],
        calibration: CalibrationResult,
        diagnostics: list[str],
    ) -> None:
        bindings = {
            "round_timer": ("round_time_remaining_sec", "timer"),
            "ally_score": ("score_ally", "int"),
            "enemy_score": ("score_enemy", "int"),
            "ally_roster": ("ally_alive", "int"),
            "enemy_roster": ("enemy_alive", "int"),
            "location_label": ("location_text", "text"),
            "kill_feed": ("kill_feed_rows", "list"),
            "spike_top_center": ("spike_state", "spike"),
            "spike_carrier_indicator": ("spike_state", "spike"),
            "abilities": ("ability_slots", "list"),
        }
        for region_name, (target, value_kind) in bindings.items():
            reader = self.readers.get(region_name)
            if reader is None and region_name in {"round_timer", "ally_score", "enemy_score"}:
                reader = self.digit_ocr_reader
            if reader is None or region_name not in self.layout.regions:
                continue
            try:
                crop = crop_roi(image, self.layout, region_name, calibration=calibration)
                result = reader.read(image, crop)
                if not isinstance(result, ReaderResult):
                    result = _coerce_reader_result(result)
                accepted = accept_hud_value(
                    result.value,
                    result.confidence,
                    cross_checked=result.cross_checked,
                )
                if accepted is None:
                    continue
                normalized = _normalize_reader_value(target, value_kind, accepted)
                if normalized is not None:
                    if target == "spike_state" and values[target] not in {"unknown", normalized}:
                        values[target] = "unknown"
                        diagnostics.append("spike readers disagree; state left unknown")
                        continue
                    values[target] = normalized
                    reader_confidence[region_name] = min(1.0, max(0.0, result.confidence))
            except (AttributeError, TypeError, ValueError, KeyError) as exc:
                diagnostics.append(f"reader {region_name}: {exc}")

        for region_name, target_keys in {
            "player_hp_armor": ("hp", "armor"),
            "ammo_current_weapon": ("ammo_current", "ammo_reserve", "weapon_text"),
            "weapon_inventory": ("weapon_text",),
        }.items():
            reader = self.readers.get(region_name)
            if reader is None or region_name not in self.layout.regions:
                continue
            try:
                result = reader.read(
                    image,
                    crop_roi(image, self.layout, region_name, calibration=calibration),
                )
                if not isinstance(result, ReaderResult):
                    result = _coerce_reader_result(result)
                accepted = accept_hud_value(
                    result.value,
                    result.confidence,
                    cross_checked=result.cross_checked,
                )
                if isinstance(accepted, dict):
                    for key in target_keys:
                        if key in accepted:
                            normalized = _normalize_reader_value(
                                key, "text" if key == "weapon_text" else "int", accepted[key]
                            )
                            if normalized is not None:
                                values[key] = normalized
                    reader_confidence[region_name] = result.confidence
            except (AttributeError, TypeError, ValueError, KeyError) as exc:
                diagnostics.append(f"reader {region_name}: {exc}")


def _first_anchor_set(
    source: Mapping[str, Sequence[float] | NormalizedRoi]
    | Sequence[Mapping[str, Sequence[float] | NormalizedRoi]]
    | None,
) -> Mapping[str, Sequence[float] | NormalizedRoi] | None:
    if source is None or isinstance(source, Mapping):
        return source
    return source[0] if source else None


def _enrich_temporal_evidence(
    signals: dict[str, Any], values: dict[str, Any], previous: Mapping[str, Any] | None
) -> None:
    prior = previous.get("values", {}) if previous is not None else {}
    for side in ("ally", "enemy"):
        signals[f"{side}_alive_before"] = prior.get(f"{side}_alive")
    score_pairs = [(prior.get(key), values.get(key)) for key in ("score_ally", "score_enemy")]
    scores_known = all(type(before) is int and type(after) is int for before, after in score_pairs)
    if scores_known:
        signals["score_changed"] = any(before != after for before, after in score_pairs)
        signals["score_stable"] = not signals["score_changed"]
        if signals["score_changed"]:
            signals["score_changed_within_sec"] = 0.0
    if signals.get("buy_phase_template") and signals.get("score_stable"):
        signals["banner_confidence"] = signals.get("buy_phase_template_confidence", 0.9)
        signals.update(
            shared_banner=True,
            pre_round_context=True,
            pre_round_timer_context=values.get("round_time_remaining_sec") is not None,
        )
    if signals.get("round_end_template"):
        signals["shared_banner"] = True
        signals["banner_confidence"] = signals.get("round_end_template_confidence", 0.9)
    if signals.get("self_hud_identity_lost"):
        signals["self_hud_identity_trustworthy"] = False

    # A pixel row insertion plus a unique roster decrease is enough to observe
    # an anonymous kill. Names and killer side remain unknown without evidence.
    if not values["kill_feed_rows"] and signals.get("kill_feed_row_added"):
        from .temporal import resolve_kill_sides

        sides = resolve_kill_sides(
            kill_feed_row_added=True,
            ally_alive_before=prior.get("ally_alive"),
            ally_alive_after=values["ally_alive"],
            enemy_alive_before=prior.get("enemy_alive"),
            enemy_alive_after=values["enemy_alive"],
        )
        if sides.victim_side != "unknown":
            values["kill_feed_rows"] = [{"raw_text": None, "confidence": 0.75}]
            signals["kill_feed_added_rows"] = [0]


def _detect_letterbox(image: Any) -> bool:
    """Detect clear black edge bars without confusing an all-dark frame for bars."""

    import cv2
    import numpy as np

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    height, width = gray.shape[:2]
    row_count = max(1, round(height * 0.025))
    col_count = max(1, round(width * 0.025))
    center = gray[height // 4 : (height * 3) // 4, width // 4 : (width * 3) // 4]
    if center.size == 0 or float(center.mean()) < 18:
        return False
    top_bottom = (
        float(np.mean(gray[:row_count] <= 8)) >= 0.98
        and float(np.mean(gray[-row_count:] <= 8)) >= 0.98
    )
    left_right = (
        float(np.mean(gray[:, :col_count] <= 8)) >= 0.98
        and float(np.mean(gray[:, -col_count:] <= 8)) >= 0.98
    )
    return top_bottom or left_right


def _frame_time(frame: Any, fallback_index: int) -> float:
    try:
        value = float(getattr(frame, "time_sec", fallback_index))
    except (TypeError, ValueError):
        value = float(fallback_index)
    return max(0.0, value)


def _coerce_reader_result(value: Any) -> ReaderResult[Any]:
    if isinstance(value, ReaderResult):
        return value
    if isinstance(value, Mapping) and "confidence" in value:
        return ReaderResult(
            value=value.get("value"),
            confidence=float(value.get("confidence", 0.0)),
            sources=tuple(str(item) for item in value.get("sources", ())),
            cross_checked=bool(value.get("cross_checked", False)),
        )
    # Bare reader outputs have no evidence score and are therefore not accepted.
    return ReaderResult(value=value, confidence=0.0)


def _normalize_reader_value(target: str, kind: str, value: Any) -> Any:
    if kind == "timer":
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value) if math.isfinite(value) and value >= 0 else None
        if isinstance(value, str):
            match = re.fullmatch(r"\s*([0-9]{1,2}):([0-5][0-9])\s*", value)
            if match:
                minutes, seconds = (int(part) for part in match.groups())
                if seconds < 60:
                    return float(minutes * 60 + seconds)
        return None
    if kind == "int":
        if isinstance(value, bool):
            return None
        if isinstance(value, str) and value.strip().isdecimal():
            value = int(value.strip())
        maxima = {"hp": 100, "armor": 50, "ally_alive": 5, "enemy_alive": 5}
        if isinstance(value, int) and 0 <= value <= maxima.get(target, value):
            return value
        return None
    if kind == "text":
        return value.strip() if isinstance(value, str) and value.strip() else None
    if kind == "spike":
        supported = {
            "not_carried",
            "carried_by_player",
            "carried_by_ally",
            "dropped",
            "planted",
            "defusing",
            "resolved",
            "unknown",
        }
        return value if isinstance(value, str) and value in supported else None
    if kind == "list" and isinstance(value, list):
        if target == "ability_slots":
            return [item for item in value if isinstance(item, dict)][:4]
        if target == "kill_feed_rows":
            rows: list[dict[str, Any]] = []
            for item in value:
                if not isinstance(item, Mapping):
                    continue
                row = {
                    key: item[key]
                    for key in (
                        "raw_text",
                        "killer_text",
                        "victim_text",
                        "confidence",
                        "killer_side",
                        "victim_side",
                        "weapon_text",
                        "row_added",
                        "color_agrees",
                        "normal_kill_confirmed",
                    )
                    if key in item
                }
                # Internal row timing/side evidence is consumed before schema shaping.
                row.pop("row_added", None)
                row.pop("color_agrees", None)
                row.pop("normal_kill_confirmed", None)
                row.setdefault("raw_text", None)
                row.setdefault("confidence", 0.0)
                if set(row) <= {
                    "raw_text",
                    "killer_text",
                    "victim_text",
                    "confidence",
                    "killer_side",
                    "victim_side",
                    "weapon_text",
                }:
                    rows.append(row)
            return rows
    del target
    return None


def _observation_change_times(
    observations: Sequence[Mapping[str, Any]], evidence: Mapping[int, Mapping[str, Any]]
) -> tuple[float, ...]:
    changed = set(HudFrameSampler.change_times([dict(item) for item in observations]))
    for index, item in enumerate(observations):
        if evidence.get(index, {}).get("kill_feed_row_added"):
            changed.add(float(item["time_sec"]))
    return tuple(sorted(changed))


def _debounced_roster_count(
    features: Sequence[FrameFeatureObservation], index: int, side: str
) -> tuple[int, float] | None:
    """Require two adjacent agreeing roster reads; ambiguity stays unknown."""

    def candidate(position: int) -> tuple[int, float] | None:
        slots = features[position].signals.get(f"{side}_liveness_candidates", [])
        if len(slots) != 5 or any(type(slot.get("alive_candidate")) is not bool for slot in slots):
            return None
        confidence = min(float(slot.get("confidence", 0.0)) for slot in slots)
        if confidence < 0.65:
            return None
        return sum(slot["alive_candidate"] for slot in slots), confidence

    current = candidate(index)
    if current is None:
        return None
    for neighbor in (index - 1, index + 1):
        if not 0 <= neighbor < len(features):
            continue
        time, other_time = features[index].time_sec, features[neighbor].time_sec
        if time is None or other_time is None or abs(time - other_time) > 1.0:
            continue
        other = candidate(neighbor)
        if other is not None and other[0] == current[0]:
            return current[0], min(current[1], other[1])
    return None
