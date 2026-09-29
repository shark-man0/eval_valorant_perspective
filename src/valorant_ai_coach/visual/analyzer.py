from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from valorant_ai_coach.events import EventSourceContract
from valorant_ai_coach.video import FrameSample, VideoMetadata


@dataclass(frozen=True, slots=True)
class VisualAnalysis:
    events: tuple[dict[str, Any], ...]
    frame_confidences: tuple[tuple[float, float], ...] = ()
    diagnostics: tuple[str, ...] = ()
    observations: tuple[dict[str, Any], ...] = ()
    candidates: tuple[dict[str, Any], ...] = ()
    zone_resolutions: tuple[dict[str, Any], ...] = ()


class VisualAnalyzer(Protocol):
    def analyze(
        self,
        frames: Sequence[FrameSample],
        hud_observations: Sequence[dict[str, Any]],
        *,
        video_metadata: VideoMetadata,
    ) -> VisualAnalysis: ...


class WorldViewGate:
    """Prevent first-person visual inference from non-player or obscured views."""

    _blocking_flags = {
        "vision_obscured_smoke",
        "vision_obscured_flash",
        "visual_transition",
    }

    @classmethod
    def is_trustworthy(cls, observation: dict[str, Any]) -> bool:
        if observation.get("primary_state") != "live_first_person":
            return False
        flags = set(observation.get("state_flags", []))
        if flags & cls._blocking_flags:
            return False
        context = observation.get("view_context", {})
        return bool(
            isinstance(context, dict) and context.get("is_player_world_view_trustworthy", False)
        )

    @classmethod
    def allows_event(
        cls,
        event: dict[str, Any],
        observations: Sequence[dict[str, Any]],
        *,
        max_observation_age_sec: float = 0.5,
    ) -> bool:
        """Gate canonical point events against the observed screen-state timeline.

        Non-world HUD/visual producers (e.g. weapon or location label readers)
        can still operate while the main scene is unavailable.
        """
        if event.get("type") in {
            "spike_pickup",
            "spike_dropped",
            "spike_defuse_started",
            "spike_defused",
            "purchase",
            "weapon_pickup",
        }:
            return True
        start = end = float(event.get("time_sec", 0.0))
        if (
            not math.isfinite(start)
            or not math.isfinite(max_observation_age_sec)
            or max_observation_age_sec < 0
        ):
            return False
        ordered = sorted(observations, key=lambda item: float(item["time_sec"]))
        before = [item for item in ordered if float(item["time_sec"]) <= start]
        covered = [item for item in ordered if start < float(item["time_sec"]) <= end]
        if not before:
            return False
        if start - float(before[-1]["time_sec"]) > max_observation_age_sec:
            return False
        covered.insert(0, before[-1])
        if event.get("type") == "shot":
            # Smoke/flash obscures targets, not ammo evidence of burst onset.
            if not all(
                item.get("primary_state") == "live_first_person"
                and item.get("values", {}).get("player_specific_hud_valid", True)
                and not set(item.get("state_flags", ()))
                & {"visual_transition", "buy_phase_banner", "round_end_banner"}
                for item in covered
            ):
                return False
        elif any(not cls.is_trustworthy(item) for item in covered):
            return False
        return not any(
            "visual_transition" in item.get("state_flags", [])
            and start <= float(item["time_sec"]) + 0.25
            and end >= float(item["time_sec"]) - 0.25
            for item in ordered
        )


class NullVisualAnalyzer:
    """Explicit replaceable boundary while high-precision visual models are absent."""

    def __init__(self, contract: EventSourceContract) -> None:
        self.contract = contract

    def analyze(
        self,
        frames: Sequence[FrameSample],
        hud_observations: Sequence[dict[str, Any]],
        *,
        video_metadata: VideoMetadata,
    ) -> VisualAnalysis:
        del frames, video_metadata
        eligible = sum(WorldViewGate.is_trustworthy(item) for item in hud_observations)
        total = len(hud_observations)
        return VisualAnalysis(
            (),
            (),
            (
                "高精度Visual Analyzerは未接続です。HUD契約外イベントは生成していません",
                f"world-view eligible observations: {eligible}/{total}",
            ),
        )
