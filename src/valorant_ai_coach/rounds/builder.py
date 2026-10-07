from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Any

from valorant_ai_coach.events import DerivedEventBuilder, EventSourceContract
from valorant_ai_coach.hud.temporal import aggregate_observation_quality as aggregate_confidences
from valorant_ai_coach.maps.registry import MapRegistry
from valorant_ai_coach.models import DeterministicFact, RoleResolver
from valorant_ai_coach.schema_validation import SchemaValidator
from valorant_ai_coach.video import VideoMetadata


class RoundPackageBuildError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class _RoundWindow:
    start_sec: float
    end_sec: float
    complete: bool = True
    include_end: bool = True

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



# Spike states that are relative to whose first-person view is on screen. Seen through a
# spectator/non-player view they describe someone else, so they must not become player facts.
_VIEWPOINT_RELATIVE_SPIKE_STATES = frozenset(
    {"carried_by_player", "carried_by_ally", "not_carried"}
)


def _player_scoped_spike_state(spike_state: Any, player_valid: bool) -> Any:
    if not player_valid and spike_state in _VIEWPOINT_RELATIVE_SPIKE_STATES:
        return "unknown"
    return spike_state


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
                    window.contains(float(event["time_sec"]))
                    and not (
                        event["type"] == "round_end"
                        and number > 1
                        and float(event["time_sec"]) == windows[number - 2].end_sec
                    )
                )
                or (event["type"] == "round_end" and float(event["time_sec"]) == window.end_sec)
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
            by_time[timestamp] = snapshot
        return [by_time[key] for key in sorted(by_time)]

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
        active_start: float | None = None
        cursor = -math.inf

        def first_observed_until(end: float) -> float | None:
            return next((time for time in usable if cursor < time < end), None)

        for timestamp, kind in boundaries:
            if kind == "round_start":
                start = (
                    active_start if active_start is not None else first_observed_until(timestamp)
                )
                if start is not None and timestamp > start:
                    windows.append(_RoundWindow(start, timestamp, False, False))
                active_start = timestamp
            else:
                start = (
                    active_start if active_start is not None else first_observed_until(timestamp)
                )
                if start is not None and timestamp > start:
                    windows.append(_RoundWindow(start, timestamp, active_start is not None))
                active_start = None
            cursor = timestamp
        if active_start is not None and video_duration > active_start:
            windows.append(_RoundWindow(active_start, video_duration, False))
        elif active_start is None:
            remaining = [time for time in usable if time > cursor]
            if remaining:
                end = min(video_duration, max(remaining[-1], remaining[0] + 0.1))
                if end > remaining[0]:
                    windows.append(_RoundWindow(remaining[0], end, False))
        for index in range(len(windows) - 1):
            if windows[index].end_sec == windows[index + 1].start_sec:
                windows[index] = replace(windows[index], include_end=False)
        return windows

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
                "spike_state": _player_scoped_spike_state(
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
            key = (
                snapshot["ally_alive"],
                snapshot["enemy_alive"],
                snapshot["hp"],
                snapshot["armor"],
                snapshot["weapon"],
                snapshot["spike_state"],
                snapshot["utility_available_count"],
                zone_id,
            )
            timestamp = float(snapshot["time_sec"])
            if key != last_key or timestamp - last_time >= 2.0:
                snapshots.append(snapshot)
                last_key = key
                last_time = timestamp
        return snapshots

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
