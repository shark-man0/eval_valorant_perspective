from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

Producer = Literal[
    "hud_analyzer",
    "visual_analyzer",
    "derived_event_builder",
    "audio_analyzer",
]
_ACTORS = frozenset({"player", "ally", "enemy", "team", "system", "unknown"})
_ROUND_LIFECYCLE_TYPES = frozenset({"round_start", "round_end"})


class EventSourceContractError(ValueError):
    """Raised when an event crosses the producer boundary from the patch contract."""


@dataclass(frozen=True, slots=True)
class EventSourceRule:
    event_type: str
    primary_producer: str
    mvp_status: str
    notes: str
    allowed_actors: tuple[str, ...] | None = None

    def accepts(self, producer: Producer) -> bool:
        if self.primary_producer == producer:
            return True
        return self.primary_producer == "hud_or_visual_analyzer" and producer in {
            "hud_analyzer",
            "visual_analyzer",
        }


class EventSourceContract:
    """Load and enforce the authoritative event producer registry.

    This check is intentionally independent from JSON Schema validation: the
    existing Round Package schema describes event shape, while this contract
    controls which analyzer is allowed to originate each event type.
    """

    def __init__(self, rules: dict[str, EventSourceRule]) -> None:
        if not rules:
            raise EventSourceContractError("Event Source Contractが空です")
        self.rules = dict(rules)

    @classmethod
    def load(cls, path: Path) -> EventSourceContract:
        source = Path(path).expanduser().resolve()
        try:
            raw = json.loads(source.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise EventSourceContractError(
                f"Event Source Contractを読み込めません: {source}: {exc}"
            ) from exc
        events = raw.get("events") if isinstance(raw, dict) else None
        if not isinstance(events, dict):
            raise EventSourceContractError("Event Source Contractのeventsが不正です")
        rules: dict[str, EventSourceRule] = {}
        for event_type, value in events.items():
            if not isinstance(value, dict):
                raise EventSourceContractError(f"event contract {event_type} が不正です")
            producer = value.get("primary_producer")
            if not isinstance(producer, str) or not producer:
                raise EventSourceContractError(f"{event_type} のprimary_producerが不正です")
            allowed_actors: tuple[str, ...] | None = None
            if "allowed_actors" in value:
                actor_values = value["allowed_actors"]
                if (
                    not isinstance(actor_values, list)
                    or not actor_values
                    or any(
                        not isinstance(actor, str) or actor not in _ACTORS for actor in actor_values
                    )
                    or len(set(actor_values)) != len(actor_values)
                ):
                    raise EventSourceContractError(f"{event_type} のallowed_actorsが不正です")
                allowed_actors = tuple(actor_values)
            rules[str(event_type)] = EventSourceRule(
                event_type=str(event_type),
                primary_producer=producer,
                mvp_status=str(value.get("mvp_status", "")),
                notes=str(value.get("notes", "")),
                allowed_actors=allowed_actors,
            )
        return cls(rules)

    def validate_registry(self, registry: dict[str, Any]) -> None:
        registered = registry.get("event_types") if isinstance(registry, dict) else None
        if not isinstance(registered, dict):
            raise EventSourceContractError("Event Type Registryのevent_typesが不正です")
        missing = set(registered) - set(self.rules)
        unknown = set(self.rules) - set(registered)
        if missing or unknown:
            details: list[str] = []
            if missing:
                details.append(f"contract欠落={','.join(sorted(missing))}")
            if unknown:
                details.append(f"registry未定義={','.join(sorted(unknown))}")
            raise EventSourceContractError(
                "Event registryとproducer契約が不一致です: " + "; ".join(details)
            )

    def validate_event(self, event: dict[str, Any], producer: Producer) -> None:
        event_type = str(event.get("type", ""))
        rule = self.rules.get(event_type)
        if rule is None:
            raise EventSourceContractError(f"未登録のevent typeです: {event_type or '(empty)'}")
        if not rule.accepts(producer):
            raise EventSourceContractError(
                f"{event_type} は {producer} から生成できません（producer={rule.primary_producer}）"
            )
        # Actor checks are deliberately limited to round lifecycle events for
        # backward compatibility with existing producer contracts and events.
        if event_type in _ROUND_LIFECYCLE_TYPES and rule.allowed_actors is not None:
            actor = event.get("actor")
            if actor not in rule.allowed_actors:
                allowed = ", ".join(rule.allowed_actors)
                raise EventSourceContractError(
                    f"{event_type} のactorが契約に適合しません: {actor!r} (allowed: {allowed})"
                )

    def validate_events(self, events: list[dict[str, Any]], producer: Producer) -> None:
        for event in events:
            self.validate_event(event, producer)

    def producer_for(self, event_type: str) -> str:
        try:
            return self.rules[event_type].primary_producer
        except KeyError as exc:
            raise EventSourceContractError(f"未登録のevent typeです: {event_type}") from exc
