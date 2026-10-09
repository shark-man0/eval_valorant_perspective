from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from valorant_ai_coach.events import DerivedEventBuilder, EventSourceContract
from valorant_ai_coach.events.derived import player_scoped_spike_state
from valorant_ai_coach.hud.models import timer_display_evidence
from valorant_ai_coach.hud.temporal import aggregate_observation_quality as aggregate_confidences
from valorant_ai_coach.maps.registry import MapRegistry
from valorant_ai_coach.models import DeterministicFact, RoleResolver
from valorant_ai_coach.schema_validation import SchemaValidator
from valorant_ai_coach.video import VideoMetadata


class RoundPackageBuildError(ValueError):
    pass


@dataclass(slots=True)
class _RoundWindow:
    start_sec: float
    end_sec: float
    complete: bool = True
    include_end: bool = True
    start_event_sec: float | None = None
    end_event_sec: float | None = None

    def contains(self, timestamp: float) -> bool:
        return self.start_sec <= timestamp and (
            timestamp < self.end_sec or (self.include_end and timestamp == self.end_sec)
        )


def _bounded_confidence(value: Any) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return 0.0
    return min(1.0, max(0.0, parsed)) if math.isfinite(parsed) else 0.0


def _source_confidence(value: Any) -> float:
    """Provenance confidence: a finite number within [0, 1], otherwise 0.0.

    Unlike _bounded_confidence, a bool, a numeric string or an out-of-range value never
    counts as confidence (it is not clamped up to a usable value).
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0.0
    return float(value) if math.isfinite(value) and 0.0 <= value <= 1.0 else 0.0



def _shared_timer_facts(observations: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Preserve accepted current-frame shared values without attributing a player."""
    facts: list[dict[str, Any]] = []
    seen: set[tuple[float, float]] = set()
    for observation in observations:
        values = observation.get("values")
        quality = observation.get("quality")
        if not isinstance(values, dict) or not isinstance(quality, dict):
            continue
        confidence_by_roi = quality.get("roi_confidence")
        if not isinstance(confidence_by_roi, dict):
            continue
        # round_timer alone can be feature/geometry confidence. Only the analyzer's
        # reserved accepted-reader score authorizes this value-only fact.
        confidence = confidence_by_roi.get("round_timer_value")
        value = values.get("round_time_remaining_sec")
        timestamp = observation.get("time_sec")
        if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        if isinstance(timestamp, bool) or not isinstance(timestamp, (int, float)):
            continue
        if not all(math.isfinite(item) for item in (confidence, value, timestamp)):
            continue
        if not 0.90 <= confidence <= 1.0 or value < 0 or timestamp < 0:
            continue
        if "calibration_required" in (quality.get("notes") or ()):
            continue
        identity = (float(timestamp), float(value))
        if identity in seen:
            continue
        seen.add(identity)
        facts.append(
            DeterministicFact(
                fact_id=f"HT{len(facts) + 1:04d}",
                key="round_time_remaining_sec",
                value=value,
                confidence=float(confidence),
                source="hud",
                time_sec=float(timestamp),
            ).to_dict()
        )
    return facts


def _owned_hp_facts(observations: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Preserve accepted current-frame HP readings for the identified player."""
    facts: list[dict[str, Any]] = []
    seen: set[tuple[float, int]] = set()
    for observation in observations:
        values = observation.get("values")
        quality = observation.get("quality")
        if not isinstance(values, dict) or not isinstance(quality, dict):
            continue
        if (
            observation.get("primary_state") != "live_first_person"
            or values.get("player_specific_hud_valid") is not True
        ):
            continue
        notes = quality.get("notes")
        if not isinstance(notes, (list, tuple)) or "calibration_required" in notes:
            continue
        value = values.get("hp")
        timestamp = observation.get("time_sec")
        confidence_by_roi = quality.get("roi_confidence")
        confidence = (
            confidence_by_roi.get("hp_value")
            if isinstance(confidence_by_roi, dict)
            else None
        )
        if (
            type(value) is not int
            or not 0 <= value <= 100
            or isinstance(timestamp, bool)
            or not isinstance(timestamp, (int, float))
            or not math.isfinite(float(timestamp))
            or timestamp < 0
            or isinstance(confidence, bool)
            or not isinstance(confidence, (int, float))
            or not math.isfinite(float(confidence))
            or not 0.90 <= confidence <= 1.0
        ):
            continue
        identity = (float(timestamp), value)
        if identity in seen:
            continue
        seen.add(identity)
        facts.append(
            DeterministicFact(
                fact_id=f"HH{len(facts) + 1:04d}",
                key="hp",
                value=value,
                confidence=float(confidence),
                source="hud",
                time_sec=float(timestamp),
            ).to_dict()
        )
    return facts


def _coverage_summary(
    valid_times: Sequence[float], start_sec: float, end_sec: float, *, coverage_radius: float
) -> tuple[float, list[dict[str, float]]]:
    if end_sec <= start_sec:
        return 0.0, []
    intervals: list[tuple[float, float]] = []
    for time_sec in sorted(set(valid_times)):
        if start_sec <= time_sec <= end_sec:
            intervals.append(
                (
                    max(start_sec, time_sec - coverage_radius),
                    min(end_sec, time_sec + coverage_radius),
                )
            )
    merged: list[list[float]] = []
    for left, right in intervals:
        if not merged or left > merged[-1][1]:
            merged.append([left, right])
        else:
            merged[-1][1] = max(merged[-1][1], right)
    missing: list[dict[str, float]] = []
    covered_duration = sum(right - left for left, right in merged)
    cursor = start_sec
    for left, right in merged:
        if left - cursor >= 1.0:
            missing.append({"start_sec": cursor, "end_sec": left})
        cursor = max(cursor, right)
    if end_sec - cursor >= 1.0:
        missing.append({"start_sec": cursor, "end_sec": end_sec})
    return min(end_sec - start_sec, covered_duration), missing


def aggregate_observation_quality(
    observations: Sequence[dict[str, Any]],
    start_sec: float,
    end_sec: float,
    *,
    coverage_radius_sec: float = 0.5,
) -> dict[str, Any]:
    """Aggregate accepted frame quality without remapping it to Coach confidence."""

    duration = max(0.0, end_sec - start_sec)
    in_round = [
        item for item in observations if start_sec <= float(item.get("time_sec", -1.0)) <= end_sec
    ]
    accepted = [
        item
        for item in in_round
        if _bounded_confidence((item.get("quality") or {}).get("hud_confidence")) >= 0.65
    ]
    valid_times = [float(item["time_sec"]) for item in accepted]
    covered_duration, missing = _coverage_summary(
        valid_times,
        start_sec,
        end_sec,
        coverage_radius=max(0.01, float(coverage_radius_sec)),
    )
    completeness = 0.0 if duration <= 0 else covered_duration / duration
    hud_values = [
        _bounded_confidence((item.get("quality") or {}).get("hud_confidence")) for item in accepted
    ]
    visual_eligible = [
        item
        for item in in_round
        if item.get("primary_state") == "live_first_person"
        and bool((item.get("view_context") or {}).get("is_player_world_view_trustworthy"))
        and not set(item.get("state_flags", ()))
        & {"vision_obscured_smoke", "vision_obscured_flash", "visual_transition"}
    ]
    visual_samples = [
        item
        for item in visual_eligible
        if _bounded_confidence((item.get("quality") or {}).get("visual_confidence")) > 0
    ]
    visual_values = [
        _bounded_confidence((item.get("quality") or {}).get("visual_confidence"))
        for item in visual_samples
    ]
    visual_covered_duration, _visual_missing = _coverage_summary(
        [float(item["time_sec"]) for item in visual_samples],
        start_sec,
        end_sec,
        coverage_radius=max(0.01, float(coverage_radius_sec)),
    )
    visual_eligible_duration, _eligible_gaps = _coverage_summary(
        [float(item["time_sec"]) for item in visual_eligible],
        start_sec,
        end_sec,
        coverage_radius=max(0.01, float(coverage_radius_sec)),
    )
    visual_completeness = (
        0.0
        if visual_eligible_duration <= 0
        else min(1.0, visual_covered_duration / visual_eligible_duration)
    )
    return aggregate_confidences(
        hud_values,
        completeness,
        frame_visual_confidences=visual_values,
        visual_timeline_fraction=visual_completeness,
        missing_intervals=missing,
    )


class RoundPackageBuilder:
    """Convert observation/event timelines into canonical Round Package v2 objects."""

    def __init__(
        self,
        *,
        contract: EventSourceContract,
        validator: SchemaValidator,
        role_resolver: RoleResolver | None = None,
    ) -> None:
        self.contract = contract
        self.validator = validator
        self.role_resolver = role_resolver or RoleResolver()
        self.derived = DerivedEventBuilder(contract)
        self.map_runtime = MapRegistry().runtime

    def build(
        self,
        *,
        match_id: str,
        video_metadata: VideoMetadata,
        hud_observations: Sequence[dict[str, Any]],
        hud_events: Sequence[dict[str, Any]],
        visual_events: Sequence[dict[str, Any]] = (),
        visual_observations: Sequence[dict[str, Any]] = (),
        zone_resolutions: Sequence[dict[str, Any]] = (),
        map_name: str = "unknown",
        player_agent: str = "unknown",
        side: str = "unknown",
        require_detected_rounds: bool = True,
    ) -> tuple[dict[str, Any], ...]:
        observations = sorted((dict(item) for item in hud_observations), key=self._time)
        for resolution in zone_resolutions:
            self.validator.validate_zone_resolution(resolution)
        for observation in observations:
            self.validator.validate_hud_observation(observation)
        direct_hud = [dict(item) for item in hud_events]
        direct_visual = [dict(item) for item in visual_events]
        self.contract.validate_events(direct_hud, "hud_analyzer")
        self.contract.validate_events(direct_visual, "visual_analyzer")
        direct_hud = self._unique_boundaries(direct_hud)
        derived = self.derived.build(observations)
        all_events = sorted(direct_hud + direct_visual + derived, key=self._event_sort_key)
        windows = self._round_windows(observations, direct_hud, video_metadata.duration_sec)
        # Diagnostics may retain observations without inventing round boundaries.
        # Interactive coaching keeps the strict default. All other validation stays active.
        if not windows and require_detected_rounds:
            raise RoundPackageBuildError(
                "信頼できるラウンド区間を検出できませんでした。HUD校正と録画範囲を確認してください"
            )
        if video_metadata.fps <= 0:
            raise RoundPackageBuildError("動画FPSを取得できないためRound Packageを生成できません")
        role = self._resolve_role(player_agent)
        packages: list[dict[str, Any]] = []
        for number, window in enumerate(windows, start=1):
            round_observations = [
                item for item in observations if window.contains(self._time(item))
            ]
            round_events = [
                event
                for event in all_events
                if (
                    event["type"] == "round_start"
                    and window.start_event_sec == float(event["time_sec"])
                )
                or (
                    event["type"] == "round_end"
                    and window.end_event_sec == float(event["time_sec"])
                )
                or (
                    event["type"] not in {"round_start", "round_end"}
                    and window.contains(float(event["time_sec"]))
                )
            ]
            score_before = self._score_before(round_observations)
            result = self._round_result(round_events)
            quality = aggregate_observation_quality(
                round_observations, window.start_sec, window.end_sec
            )
            if not window.complete:
                # With a missing round boundary the full-round denominator is
                # unknown. Do not represent a fragment as complete round context.
                quality.update(hud_confidence=0.0, visual_confidence=0.0, timeline_completeness=0.0)
                quality["missing_intervals"] = (
                    [{"start_sec": window.start_sec, "end_sec": window.end_sec}]
                    if window.end_sec - window.start_sec >= 1.0
                    else []
                )
            package: dict[str, Any] = {
                "schema_version": "2.0",
                "match_id": match_id,
                "round_no": number,
                "source_video": {
                    "path": str(video_metadata.path),
                    "fps": float(video_metadata.fps),
                    "width": int(video_metadata.width),
                    "height": int(video_metadata.height),
                    "duration_sec": float(video_metadata.duration_sec),
                },
                "round_window": {
                    "start_sec": window.start_sec,
                    "end_sec": window.end_sec,
                },
                "round_meta": {
                    "side": side if side in {"attack", "defense"} else "unknown",
                    "map": map_name or "unknown",
                    "player_agent": player_agent or "unknown",
                    "player_role": role,
                    "round_result": result,
                    "score_before": score_before,
                    "economy_context": None,
                },
                "observation_quality": quality,
                "events": round_events,
                "state_snapshots": self._merge_visual_snapshots(
                    self._state_snapshots(round_observations),
                    [item for item in visual_observations if window.contains(self._time(item))],
                    round_observations,
                    [item for item in zone_resolutions if window.contains(self._time(item))],
                ),
                "deterministic_facts": (
                    _shared_timer_facts(round_observations)
                    + _owned_hp_facts(round_observations)
                ),
                "frames": [],
                "previous_round_context": None,
            }
            # v3 snapshots have no per-location confidence field. Preserve the
            # resolver's bound in the existing fact schema before enrichment;
            # FactBuilder deduplicates these exact key/value/time identities.
            resolution_by_time = {self._time(item): item for item in zone_resolutions}
            for snapshot in package["state_snapshots"]:
                timestamp = snapshot["time_sec"]
                zone = snapshot["player_location"]["zone_id"]
                zone_resolution = resolution_by_time.get(timestamp)
                if zone is None or zone_resolution is None or zone_resolution["zone_id"] != zone:
                    continue
                package["deterministic_facts"].append(
                    DeterministicFact(
                        fact_id=f"MZ{len(package['deterministic_facts']) + 1:04d}",
                        key="zone_id",
                        value=zone,
                        confidence=min(
                            zone_resolution["zone_confidence"], quality["visual_confidence"]
                        ),
                        source="visual",
                        time_sec=timestamp,
                    ).to_dict()
                )
            self.validator.validate_round_package(package)
            packages.append(package)
        return tuple(packages)

    def _merge_visual_snapshots(
        self,
        snapshots: list[dict[str, Any]],
        visuals: Sequence[dict[str, Any]],
        hud: Sequence[dict[str, Any]],
        resolutions: Sequence[dict[str, Any]] = (),
    ) -> list[dict[str, Any]]:
        from bisect import bisect_right
        from copy import deepcopy

        by_time = {item["time_sec"]: item for item in snapshots}
        hud_times = [self._time(item) for item in hud]
        for visual in visuals:
            self.validator.validate_visual_observation(visual)
            if not visual["analysis_eligibility"]["player_mechanics"]:
                continue
            spatial = visual["spatial"]
            spatial_ok = spatial["confidence"] >= 0.85 and not visual["quality"]["occluded"]
            if not spatial_ok:
                continue
            timestamp = self._time(visual)
            index = bisect_right(hud_times, timestamp) - 1
            if index < 0 or timestamp - hud_times[index] > 0.5:
                continue
            base = self._state_snapshots([hud[index]])
            if not base:
                continue
            snapshot = deepcopy(by_time.get(timestamp, base[0]))
            snapshot["time_sec"] = timestamp
            if spatial_ok:
                # Copy only v3 fields. Intermediate sources/scores never leak.
                for key in snapshot["spatial_context"]:
                    snapshot["spatial_context"][key] = spatial[key]
                snapshot.setdefault("source_confidence", {})["spatial_context"] = min(
                    _source_confidence(spatial["confidence"]),
                    _source_confidence(visual["quality"]["visual_confidence"]),
                )
            by_time[timestamp] = snapshot
        for resolution in resolutions:
            timestamp = self._time(resolution)
            index = bisect_right(hud_times, timestamp) - 1
            if index < 0 or timestamp - hud_times[index] > 0.5:
                continue
            base = self._state_snapshots([hud[index]])
            if not base:
                continue
            snapshot = deepcopy(by_time.get(timestamp, base[0]))
            snapshot["time_sec"] = timestamp
            usable = (
                resolution["calibration_status"] == "ok"
                and resolution["resolution_scope"] == "exact_zone"
                and resolution["zone_confidence"]
                >= self.map_runtime["fusion_thresholds"]["named_zone_min"]
            )
            zone = resolution["zone_id"] if usable else None
            snapshot["player_location"] = {"zone_id": zone, "zone_name": zone}
            source = snapshot.setdefault("source_confidence", {})
            if zone is None:
                source.pop("player_location", None)
            else:
                source["player_location"] = _source_confidence(resolution["zone_confidence"])
            by_time[timestamp] = snapshot
        return [by_time[key] for key in sorted(by_time)]

    def _unique_boundaries(self, events: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
        """Use the same boundary population for windows and package events.

        Replayed copies of a decision must not multiply trace event counts. A
        conflicting continuity segment is not a duplicate and cannot safely
        determine round membership. Non-lifecycle events are left untouched.
        """
        result: list[dict[str, Any]] = []
        indices: dict[tuple[str, float], int] = {}
        for event in events:
            if event["type"] not in {"round_start", "round_end"}:
                result.append(event)
                continue
            key = (event["type"], float(event["time_sec"]))
            if key not in indices:
                indices[key] = len(result)
                result.append(event)
                continue
            index = indices[key]
            existing = result[index]
            before, after = self._continuity_segment(existing), self._continuity_segment(event)
            if before != after:
                raise RoundPackageBuildError(
                    "同一ラウンド境界のcontinuity segmentが一致しません"
                )
            # Keep one existing decision, including its original provenance;
            # never merge signals or manufacture higher confidence.
            if _bounded_confidence(event.get("confidence")) > _bounded_confidence(
                existing.get("confidence")
            ):
                result[index] = event
        return result

    def _round_windows(
        self,
        observations: Sequence[dict[str, Any]],
        hud_events: Sequence[dict[str, Any]],
        video_duration: float,
    ) -> list[_RoundWindow]:
        windows: list[_RoundWindow] = []
        usable = sorted(
            {
                self._time(item)
                for item in observations
                if item.get("primary_state")
                in {
                    "live_first_person",
                    "spectator_first_person",
                    "remote_control_view",
                    "expanded_tactical_map",
                }
                and _bounded_confidence((item.get("quality") or {}).get("hud_confidence")) >= 0.65
                and not set(item.get("state_flags", ())) & {"buy_phase_banner", "round_end_banner"}
                and not item.get("values", {}).get("buy_phase_visible", False)
                and 0 <= self._time(item) <= video_duration
            }
        )
        boundaries = sorted(
            {
                (float(item["time_sec"]), item["type"])
                for item in hud_events
                if item.get("type") in {"round_start", "round_end"}
                and 0 <= float(item["time_sec"]) <= video_duration
            }
        )  # round_end sorts before round_start at an identical timestamp.
        boundary_segments = {
            (float(item["time_sec"]), item["type"]): self._continuity_segment(item)
            for item in hud_events
            if item.get("type") in {"round_start", "round_end"}
            and 0 <= float(item["time_sec"]) <= video_duration
        }
        observed_times = sorted({self._time(item) for item in observations})
        timeline: list[tuple[float, int, str, int | None]] = [
            (
                timestamp,
                0 if kind == "round_end" else 2,
                kind,
                boundary_segments.get((timestamp, kind)),
            )
            for timestamp, kind in boundaries
        ]
        timeline.extend(
            (following, 1, "_observation_gap", None)
            for previous, following in zip(
                observed_times, observed_times[1:], strict=False
            )
            if following - previous > 1.0
        )
        timeline.sort()
        active_start: float | None = None
        active_start_segment: int | None = None
        cursor = -math.inf

        def first_observed_until(end: float) -> float | None:
            return next((time for time in usable if cursor < time < end), None)

        for timestamp, _priority, kind, segment in timeline:
            if kind == "_observation_gap":
                previous_observation = max(
                    (time_sec for time_sec in observed_times if time_sec < timestamp),
                    default=cursor,
                )
                if active_start is not None:
                    observed_end = (
                        previous_observation
                        if previous_observation > active_start
                        else min(timestamp, active_start + 0.1)
                    )
                    windows.append(
                        _RoundWindow(
                            active_start,
                            observed_end,
                            False,
                            previous_observation > active_start,
                            active_start,
                            None,
                        )
                    )
                    active_start = None
                    active_start_segment = None
                else:
                    uncovered = [
                        time_sec
                        for time_sec in usable
                        if cursor < time_sec <= previous_observation
                        and not any(window.contains(time_sec) for window in windows)
                    ]
                    has_prior_end = any(
                        window.end_event_sec is not None
                        and window.end_event_sec <= previous_observation
                        for window in windows
                    )
                    if uncovered and not has_prior_end:
                        fragment_start = min(uncovered)
                        # Keep later observed-but-unusable samples inside the
                        # partial window. They must not establish gameplay
                        # continuity, but accepted shared-value facts at those
                        # timestamps still belong to the observed fragment.
                        fragment_end = min(
                            timestamp,
                            max(previous_observation, fragment_start + 0.1),
                        )
                        windows.append(
                            _RoundWindow(fragment_start, fragment_end, False)
                        )
                cursor = max(cursor, previous_observation)
                continue
            if kind == "round_start":
                if (
                    active_start is not None
                    and active_start_segment is not None
                    and segment is not None
                    and active_start_segment != segment
                ):
                    windows.append(
                        _RoundWindow(
                            active_start,
                            timestamp,
                            False,
                            False,
                            active_start,
                            None,
                        )
                    )
                    active_start = None
                    active_start_segment = None
                    cursor = max(cursor, timestamp)
                previous_boundary = max(
                    (boundary_time for boundary_time, _ in boundaries if boundary_time < timestamp),
                    default=None,
                )
                preparation_start = self._preparation_context_start(
                    observations, timestamp, floor_sec=previous_boundary
                )
                has_prior_end = any(
                    boundary_kind == "round_end" and boundary_time < timestamp
                    for boundary_time, boundary_kind in boundaries
                )
                start = (
                    active_start
                    if active_start is not None
                    else first_observed_until(timestamp)
                )
                if active_start is None and (has_prior_end or preparation_start is not None):
                    start = None
                if start is not None and timestamp > start:
                    windows.append(
                        _RoundWindow(start, timestamp, False, False, active_start, None)
                    )
                active_start = timestamp
                active_start_segment = segment
            else:
                if (
                    active_start is not None
                    and active_start_segment is not None
                    and segment is not None
                    and active_start_segment != segment
                ):
                    windows.append(
                        _RoundWindow(
                            active_start,
                            timestamp,
                            False,
                            False,
                            active_start,
                            None,
                        )
                    )
                    active_start = None
                    active_start_segment = None
                    cursor = max(cursor, timestamp)
                    windows.append(
                        _RoundWindow(
                            max(0.0, timestamp - 0.1),
                            timestamp,
                            False,
                            True,
                            None,
                            timestamp,
                        )
                    )
                    cursor = timestamp
                    continue
                start = (
                    active_start if active_start is not None else first_observed_until(timestamp)
                )
                if start is not None and timestamp > start:
                    windows.append(
                        _RoundWindow(
                            start,
                            timestamp,
                            active_start is not None,
                            True,
                            active_start,
                            timestamp,
                        )
                    )
                active_start = None
                active_start_segment = None
            cursor = timestamp
        if active_start is not None and video_duration > active_start:
            windows.append(
                _RoundWindow(active_start, video_duration, False, True, active_start, None)
            )
        elif active_start is None:
            remaining = [time for time in usable if time > cursor]
            if remaining:
                end = min(video_duration, max(remaining[-1], remaining[0] + 0.1))
                if end > remaining[0]:
                    windows.append(_RoundWindow(remaining[0], end, False))

        # Extend observed context around actual round starts. Preparation samples
        # are assigned to the upcoming round, while contiguous post-end samples
        # before preparation remain with the round that just ended.
        starts = [window for window in windows if window.start_event_sec is not None]
        for window in starts:
            event_start = window.start_event_sec
            assert event_start is not None
            previous_boundary = max(
                (boundary_time for boundary_time, _ in boundaries if boundary_time < event_start),
                default=None,
            )
            preparation_start = self._preparation_context_start(
                observations, event_start, floor_sec=previous_boundary
            )
            if preparation_start is None:
                continue
            window.start_sec = min(window.start_sec, preparation_start)
            prior_ended = next(
                (
                    prior
                    for prior in reversed(windows)
                    if prior is not window
                    and prior.end_event_sec is not None
                    and prior.end_event_sec <= preparation_start
                    and prior.end_event_sec < event_start
                ),
                None,
            )
            if prior_ended is not None:
                prior_end_event = prior_ended.end_event_sec
                assert prior_end_event is not None
                prior_ended.end_sec, prior_ended.include_end = self._observed_context_end(
                    observations,
                    prior_end_event,
                    preparation_start,
                )

        # With no next preparatory context, keep a contiguous observed tail on
        # the ended round. A gap over one second stops this extension.
        for window in windows:
            if window.end_event_sec is None:
                continue
            next_preparation = min(
                (
                    candidate.start_sec
                    for candidate in starts
                    if candidate.start_event_sec is not None
                    and candidate.start_event_sec > window.end_event_sec
                    and candidate.start_sec > window.end_event_sec
                    and candidate.start_sec < candidate.start_event_sec
                ),
                default=math.inf,
            )
            if next_preparation == math.inf:
                next_round_start = min(
                    (
                        candidate.start_event_sec
                        for candidate in starts
                        if candidate.start_event_sec is not None
                        and candidate.start_event_sec > window.end_event_sec
                    ),
                    default=min(
                        (
                            candidate.start_sec
                            for candidate in windows
                            if candidate.start_event_sec is None
                            and candidate.start_sec > window.end_event_sec
                        ),
                        default=video_duration,
                    ),
                )
                window.end_sec, window.include_end = self._observed_context_end(
                    observations, window.end_event_sec, next_round_start
                )
        windows.sort(key=lambda item: (item.start_sec, item.end_sec))
        for index in range(len(windows) - 1):
            current, following = windows[index], windows[index + 1]
            if current.end_sec >= following.start_sec:
                current.end_sec = following.start_sec
                current.include_end = False
        return windows

    @staticmethod
    def _is_preparation_observation(observation: dict[str, Any]) -> bool:
        values = observation.get("values")
        flags = set(observation.get("state_flags", ()))
        quality = observation.get("quality")
        if not isinstance(quality, dict):
            return False
        roi_confidence = quality.get("roi_confidence")
        # Source-qualified global phase can establish preparation context while
        # player identity remains unknown. Never use it as an active boundary.
        if (
            "buy_phase_banner" in flags
            and isinstance(values, dict)
            and values.get("buy_phase_visible") is True
            and isinstance(roi_confidence, dict)
            and _bounded_confidence(roi_confidence.get("center_phase_banner_semantic_text"))
            >= 0.90
        ):
            return True
        if _bounded_confidence(quality.get("hud_confidence")) < 0.65:
            return False
        return (
            observation.get("primary_state") == "buy_menu_open"
            or "buy_phase_banner" in flags
            or isinstance(values, dict) and values.get("buy_phase_visible") is True
        )

    @staticmethod
    def _continuity_segment(event: dict[str, Any]) -> int | None:
        attributes = event.get("attributes")
        provenance = attributes.get("evidence_provenance") if isinstance(attributes, dict) else None
        segment = provenance.get("continuity_segment") if isinstance(provenance, dict) else None
        return segment if type(segment) is int and segment >= 0 else None

    def _preparation_context_start(
        self,
        observations: Sequence[dict[str, Any]],
        event_start: float,
        *,
        floor_sec: float | None = None,
    ) -> float | None:
        before = [
            item
            for item in observations
            if self._time(item) < event_start
            and (floor_sec is None or self._time(item) > floor_sec)
        ]
        if not before or event_start - self._time(before[-1]) > 1.0:
            return None
        chain: list[dict[str, Any]] = [before[-1]]
        for item in reversed(before[:-1]):
            if self._time(chain[0]) - self._time(item) > 1.0:
                break
            chain.insert(0, item)
        prep_indices = [
            index
            for index, item in enumerate(chain)
            if self._is_preparation_observation(item)
        ]
        if not prep_indices:
            return None
        # Choose the beginning of the latest contiguous preparation episode,
        # rather than an earlier round's prep or the final repeated sample.
        prep_index = prep_indices[-1]
        while prep_index > 0 and self._is_preparation_observation(chain[prep_index - 1]):
            prep_index -= 1
        if any(
            self._time(right) - self._time(left) > 1.0
            for left, right in zip(chain[prep_index:], chain[prep_index + 1 :], strict=False)
        ):
            return None
        return self._time(chain[prep_index])

    def _observed_context_end(
        self, observations: Sequence[dict[str, Any]], event_end: float, limit: float
    ) -> tuple[float, bool]:
        end = event_end
        include_end = True
        previous = event_end
        for observation in observations:
            timestamp = self._time(observation)
            if timestamp <= event_end:
                continue
            if timestamp >= limit or timestamp - previous > 1.0:
                break
            if self._is_preparation_observation(observation):
                break
            end = timestamp
            previous = timestamp
        return end, include_end

    def _state_snapshots(self, observations: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
        snapshots: list[dict[str, Any]] = []
        last_key: tuple[Any, ...] | None = None
        last_time = -math.inf
        for observation in observations:
            values = observation.get("values", {})
            if not isinstance(values, dict):
                continue
            if _bounded_confidence((observation.get("quality") or {}).get("hud_confidence")) < 0.65:
                continue
            player_valid = bool(values.get("player_specific_hud_valid", True))
            abilities = values.get("ability_slots", [])
            utility_count = None
            if player_valid and isinstance(abilities, list):
                # Count only a fully observed standard C/Q/E set. Unknown slots
                # must not turn into zero remaining utility; X is not utility.
                slots = {item.get("slot"): item for item in abilities if isinstance(item, dict)}
                if all(
                    slot in slots and isinstance(slots[slot].get("available"), bool)
                    for slot in (0, 1, 2)
                ):
                    utility_count = sum(int(slots[slot]["available"]) for slot in (0, 1, 2))
            zone_id = None  # Only the validated resolver timeline supplies location identity.
            snapshot = {
                "time_sec": self._time(observation),
                "ally_alive": values.get("ally_alive"),
                "enemy_alive": values.get("enemy_alive"),
                "hp": values.get("hp") if player_valid else None,
                "armor": values.get("armor") if player_valid else None,
                "weapon": values.get("weapon_text") if player_valid else None,
                "spike_state": player_scoped_spike_state(
                    values.get("spike_state", "unknown"), player_valid
                ),
                "round_time_remaining_sec": values.get("round_time_remaining_sec"),
                "utility_available_count": utility_count,
                "player_location": {
                    "zone_id": zone_id if isinstance(zone_id, str) and zone_id else None,
                    "zone_name": None,
                },
                "known_enemy_locations": [],
                "spatial_context": {
                    "cover_available": None,
                    "escape_route_available": None,
                    "line_of_sight_state": "unknown",
                    "exposed_directions_count": None,
                    "view_target_zone_id": None,
                },
            }
            snapshot["source_confidence"] = self._hud_source_confidence(
                observation, snapshot
            )
            timer_display = timer_display_evidence(values)
            if (
                timer_display is not None
                and timer_display["provenance"]["confidence"] >= 0.90
                and _bounded_confidence(
                    (observation.get("quality", {}).get("roi_confidence") or {}).get(
                        "round_timer_value"
                    )
                ) >= 0.90
            ):
                snapshot["round_time_remaining_display"] = timer_display["display"]
                snapshot["round_time_remaining_display_provenance"] = timer_display["provenance"]
            key = (
                snapshot["ally_alive"],
                snapshot["enemy_alive"],
                snapshot["hp"],
                snapshot["armor"],
                snapshot["weapon"],
                snapshot["spike_state"],
                snapshot["utility_available_count"],
                zone_id,
                snapshot.get("round_time_remaining_display"),
            )
            timestamp = float(snapshot["time_sec"])
            if key != last_key or timestamp - last_time >= 2.0:
                snapshots.append(snapshot)
                last_key = key
                last_time = timestamp
        return snapshots

    @staticmethod
    def _hud_source_confidence(
        observation: dict[str, Any], snapshot: dict[str, Any]
    ) -> dict[str, float]:
        """Per-field confidence of the HUD observation this snapshot was read from.

        hud_confidence is the minimum over the observation's accepted readers, so it never
        exceeds any reader's confidence. The round timer additionally has a reserved
        value-level score; generic ROI/feature confidence is never used as value provenance.
        The package-level aggregate is not consulted.
        """
        quality = observation.get("quality") or {}
        hud = _source_confidence(quality.get("hud_confidence"))
        roi = quality.get("roi_confidence")
        timer = _source_confidence(roi.get("round_timer_value")) if isinstance(roi, dict) else 0.0
        source: dict[str, float] = {}
        for field in (
            "ally_alive",
            "enemy_alive",
            "weapon",
            "spike_state",
            "utility_available_count",
        ):
            if snapshot[field] is not None:
                source[field] = hud
        if snapshot["round_time_remaining_sec"] is not None:
            source["round_time_remaining_sec"] = timer
        return source

    @staticmethod
    def _score_before(observations: Sequence[dict[str, Any]]) -> dict[str, int] | None:
        for observation in observations:
            values = observation.get("values", {})
            if isinstance(values, dict):
                ally = values.get("score_ally")
                enemy = values.get("score_enemy")
                if isinstance(ally, int) and isinstance(enemy, int):
                    return {"ally": ally, "enemy": enemy}
        return None

    @staticmethod
    def _round_result(events: Sequence[dict[str, Any]]) -> str:
        for event in reversed(events):
            if event.get("type") != "round_end":
                continue
            attributes = event.get("attributes", {})
            result = attributes.get("result") if isinstance(attributes, dict) else None
            if result in {"win", "loss"}:
                return str(result)
        return "unknown"

    def _resolve_role(self, agent: str) -> str:
        if not agent or agent == "unknown":
            return "unknown"
        resolved = self.role_resolver.resolve(agent)
        return (
            resolved
            if resolved in {"controller", "duelist", "initiator", "sentinel"}
            else "unknown"
        )

    @staticmethod
    def _time(observation: dict[str, Any]) -> float:
        return max(0.0, float(observation.get("time_sec", 0.0)))

    @staticmethod
    def _event_sort_key(event: dict[str, Any]) -> tuple[float, str]:
        return float(event.get("time_sec", 0.0)), str(event.get("event_id", ""))
