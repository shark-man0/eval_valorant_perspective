from __future__ import annotations

import json
import math
from collections import Counter
from collections.abc import Sequence
from typing import Any

from .source_contract import EventSourceContract

MIN_HUD_CONFIDENCE = 0.65

# Spike states that are relative to whose first-person view is on screen. Seen through a
# spectator/non-player view they describe someone else, so they must never become facts or
# events about the player. Viewpoint-independent states (planted, dropped, ...) stay.
VIEWPOINT_RELATIVE_SPIKE_STATES = frozenset({"carried_by_player", "carried_by_ally", "not_carried"})


class DerivedEventInputError(ValueError):
    """An observation cannot be turned into events without guessing."""


def player_scoped_spike_state(spike_state: Any, player_valid: bool) -> Any:
    if not player_valid and spike_state in VIEWPOINT_RELATIVE_SPIKE_STATES:
        return "unknown"
    return spike_state


class DerivedEventBuilder:
    """Build non-evaluative events that require more than one direct reader.

    It deliberately does not invent save decisions, position, or utility usage.
    Those events need evidence that is not available from an HUD snapshot alone.

    Event ids come from the observation's own timestamp, never from its position in the
    input, so resampling, trimming or reordering the video does not rename events. The
    result is a pure function of the observation set.
    """

    def __init__(self, contract: EventSourceContract) -> None:
        self.contract = contract

    def build(self, observations: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
        ordered = sorted(
            ((self._time(item), item) for item in observations),
            key=lambda pair: (pair[0], self._canonical(pair[1])),
        )
        events: list[dict[str, Any]] = []
        seen_ids: Counter[str] = Counter()
        previous_state: tuple[Any, ...] | None = None
        previous_spike: str | None = None
        for timestamp, observation in ordered:
            values = observation.get("values")
            if not isinstance(values, dict):
                raise DerivedEventInputError(
                    f"time_sec={timestamp} のobservationにvaluesオブジェクトがありません"
                )
            player_valid = bool(values.get("player_specific_hud_valid", True))
            spike = player_scoped_spike_state(values.get("spike_state", "unknown"), player_valid)
            state = (
                values.get("ally_alive"),
                values.get("enemy_alive"),
                values.get("hp") if player_valid else None,
                values.get("armor") if player_valid else None,
                spike,
                values.get("round_time_remaining_sec"),
            )
            confidence = self._hud_confidence(observation)
            if confidence < MIN_HUD_CONFIDENCE:
                previous_state = None
                previous_spike = None
                continue
            if previous_state is None or state != previous_state:
                event = {
                    "event_id": self._event_id("DERIVED-STATE", timestamp, seen_ids),
                    "time_sec": timestamp,
                    "type": "state_snapshot",
                    "actor": "system",
                    "attributes": {
                        "primary_state": observation.get("primary_state", "unknown"),
                        "ally_alive": values.get("ally_alive"),
                        "enemy_alive": values.get("enemy_alive"),
                        "spike_state": spike if spike is not None else "unknown",
                    },
                    "confidence": confidence,
                }
                self.contract.validate_event(event, "derived_event_builder")
                events.append(event)
                previous_state = state
            spike_text = str(spike if spike is not None else "unknown")
            if spike_text != previous_spike and spike_text not in {"unknown", ""}:
                event = {
                    "event_id": self._event_id("DERIVED-OBJECTIVE", timestamp, seen_ids),
                    "time_sec": timestamp,
                    "type": "objective_state",
                    "actor": "system",
                    "attributes": {"spike_state": spike_text},
                    "confidence": confidence,
                }
                self.contract.validate_event(event, "derived_event_builder")
                events.append(event)
            previous_spike = spike_text
        return events

    @staticmethod
    def _event_id(prefix: str, timestamp: float, seen: Counter[str]) -> str:
        base = f"{prefix}-{round(timestamp * 1000):09d}"
        seen[base] += 1
        # Same-millisecond collisions are numbered in the (deterministic) sorted order.
        return base if seen[base] == 1 else f"{base}-{seen[base]:02d}"

    @staticmethod
    def _canonical(observation: dict[str, Any]) -> str:
        return json.dumps(observation, sort_keys=True, default=str, ensure_ascii=False)

    @staticmethod
    def _time(observation: dict[str, Any]) -> float:
        value = observation.get("time_sec")
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise DerivedEventInputError(f"time_sec が数値ではありません: {value!r}")
        if not math.isfinite(value) or value < 0:
            raise DerivedEventInputError(f"time_sec が有限の非負値ではありません: {value!r}")
        return float(value)

    @staticmethod
    def _hud_confidence(observation: dict[str, Any]) -> float:
        """Unusable confidence counts as no confidence, so the observation is skipped."""
        quality = observation.get("quality")
        value = quality.get("hud_confidence") if isinstance(quality, dict) else None
        if isinstance(value, bool) or not isinstance(value, int | float):
            return 0.0
        if not math.isfinite(value):
            return 0.0
        return min(1.0, max(0.0, float(value)))
