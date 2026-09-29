from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from .source_contract import EventSourceContract


class DerivedEventBuilder:
    """Build non-evaluative events that require more than one direct reader.

    It deliberately does not invent save decisions, position, or utility usage.
    Those events need evidence that is not available from an HUD snapshot alone.
    """

    def __init__(self, contract: EventSourceContract) -> None:
        self.contract = contract

    def build(self, observations: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        previous_state: tuple[Any, ...] | None = None
        previous_spike: str | None = None
        for index, observation in enumerate(sorted(observations, key=self._time)):
            values = observation.get("values", {})
            if not isinstance(values, dict):
                continue
            state = (
                values.get("ally_alive"),
                values.get("enemy_alive"),
                values.get("hp"),
                values.get("armor"),
                values.get("spike_state"),
                values.get("round_time_remaining_sec"),
            )
            timestamp = self._time(observation)
            confidence = self._hud_confidence(observation)
            if confidence < 0.65:
                previous_state = None
                previous_spike = None
                continue
            if previous_state is None or state != previous_state:
                event = {
                    "event_id": f"DERIVED-STATE-{index:06d}",
                    "time_sec": timestamp,
                    "type": "state_snapshot",
                    "actor": "system",
                    "attributes": {
                        "primary_state": observation.get("primary_state", "unknown"),
                        "ally_alive": values.get("ally_alive"),
                        "enemy_alive": values.get("enemy_alive"),
                        "spike_state": values.get("spike_state", "unknown"),
                    },
                    "confidence": confidence,
                }
                self.contract.validate_event(event, "derived_event_builder")
                events.append(event)
                previous_state = state
            spike_state = str(values.get("spike_state", "unknown"))
            if spike_state != previous_spike and spike_state not in {"unknown", ""}:
                event = {
                    "event_id": f"DERIVED-OBJECTIVE-{index:06d}",
                    "time_sec": timestamp,
                    "type": "objective_state",
                    "actor": "system",
                    "attributes": {"spike_state": spike_state},
                    "confidence": confidence,
                }
                self.contract.validate_event(event, "derived_event_builder")
                events.append(event)
            previous_spike = spike_state
        return events

    @staticmethod
    def _time(observation: dict[str, Any]) -> float:
        return max(0.0, float(observation.get("time_sec", 0.0)))

    @staticmethod
    def _hud_confidence(observation: dict[str, Any]) -> float:
        quality = observation.get("quality", {})
        value = quality.get("hud_confidence", 0.0) if isinstance(quality, dict) else 0.0
        return min(1.0, max(0.0, float(value)))
