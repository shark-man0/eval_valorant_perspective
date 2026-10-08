from __future__ import annotations

import math
from collections.abc import Iterable
from copy import deepcopy
from typing import Any, Literal

from valorant_ai_coach.models import DeterministicFact

type FactSource = Literal["hud", "visual", "event_normalization", "derived_code", "config", "audio"]


class FactBuilder:
    """Build only normalized, provenance-backed observations; never evaluation conclusions."""

    def build(self, round_package: dict[str, Any]) -> list[DeterministicFact]:
        used_ids = {
            str(fact["fact_id"])
            for fact in round_package.get("deterministic_facts", [])
            if fact.get("fact_id") is not None
        }
        existing = {
            (fact["key"], self._freeze(fact.get("value")), fact.get("time_sec"))
            for fact in round_package.get("deterministic_facts", [])
        }
        generated: list[DeterministicFact] = []
        counter = 1

        def add(
            key: str,
            value: Any,
            confidence: float,
            source: FactSource,
            time_sec: float | None = None,
            provenance: Iterable[str] = (),
        ) -> None:
            nonlocal counter
            if value is None:
                return
            identity = (key, self._freeze(value), time_sec)
            if identity in existing:
                return
            existing.add(identity)
            while f"FB{counter:04d}" in used_ids:
                counter += 1
            fact_id = f"FB{counter:04d}"
            used_ids.add(fact_id)
            generated.append(
                DeterministicFact(
                    fact_id=fact_id,
                    key=key,
                    value=value,
                    confidence=max(0.0, min(1.0, float(confidence))),
                    source=source,
                    provenance_event_ids=tuple(provenance),
                    time_sec=time_sec,
                )
            )
            counter += 1

        meta = round_package.get("round_meta", {})
        add("side", meta.get("side"), 1.0, "config")
        add("player_role", meta.get("player_role"), 1.0, "config")
        economy = meta.get("economy_context") or {}
        add("team_buy_class", economy.get("team_buy_class"), 1.0, "config")
        add("player_buy_class", economy.get("player_buy_class"), 1.0, "config")
        # Snapshot-derived facts take the confidence of the observation each field was read
        # from (snapshot.source_confidence), never the package-level aggregate, and never
        # more than that source. A field without a source confidence counts as 0.0, so it
        # cannot pass any deterministic gate.
        for snapshot in round_package.get("state_snapshots", []):
            timestamp = float(snapshot["time_sec"])
            ally, enemy = snapshot.get("ally_alive"), snapshot.get("enemy_alive")
            if ally is not None and enemy is not None:
                numbers = min(
                    self._source_confidence(snapshot, "ally_alive"),
                    self._source_confidence(snapshot, "enemy_alive"),
                )
                state = "advantage" if ally > enemy else "disadvantage" if ally < enemy else "even"
                add("numbers_state", state, numbers, "derived_code", timestamp)
                add("clutch_state", ally == 1 and enemy > 1, numbers, "derived_code", timestamp)
            add(
                "weapon",
                snapshot.get("weapon"),
                self._source_confidence(snapshot, "weapon"),
                "hud",
                timestamp,
            )
            spike = snapshot.get("spike_state")
            if spike and spike != "unknown":
                spike_confidence = self._source_confidence(snapshot, "spike_state")
                add(
                    "spike_carried_by_player",
                    spike == "carried_by_player",
                    spike_confidence,
                    "derived_code",
                    timestamp,
                )
                add(
                    "spike_planted",
                    spike in {"planted", "defusing"},
                    spike_confidence,
                    "derived_code",
                    timestamp,
                )
            add(
                "round_time_remaining_sec",
                snapshot.get("round_time_remaining_sec"),
                self._source_confidence(snapshot, "round_time_remaining_sec"),
                "hud",
                timestamp,
            )
            add(
                "utility_available_count",
                snapshot.get("utility_available_count"),
                self._source_confidence(snapshot, "utility_available_count"),
                "hud",
                timestamp,
            )
            location = snapshot.get("player_location") or {}
            add(
                "zone_id",
                location.get("zone_id"),
                self._source_confidence(snapshot, "player_location"),
                "visual",
                timestamp,
            )
            spatial = snapshot.get("spatial_context") or {}
            spatial_confidence = self._source_confidence(snapshot, "spatial_context")
            spatial_values = [
                spatial.get("cover_available"),
                spatial.get("escape_route_available"),
                spatial.get("exposed_directions_count"),
                spatial.get("view_target_zone_id"),
            ]
            los = spatial.get("line_of_sight_state")
            available = any(value is not None for value in spatial_values) or los not in {
                None,
                "unknown",
            }
            if available:
                add(
                    "spatial_context_available",
                    True,
                    spatial_confidence,
                    "derived_code",
                    timestamp,
                )
            add(
                "cover_available",
                spatial.get("cover_available"),
                spatial_confidence,
                "visual",
                timestamp,
            )
            add(
                "escape_route_available",
                spatial.get("escape_route_available"),
                spatial_confidence,
                "visual",
                timestamp,
            )
            if los not in {None, "unknown"}:
                add("line_of_sight_state", los, spatial_confidence, "visual", timestamp)
            add(
                "exposed_directions_count",
                spatial.get("exposed_directions_count"),
                spatial_confidence,
                "visual",
                timestamp,
            )

        events = sorted(round_package.get("events", []), key=lambda event: event["time_sec"])
        for index, event in enumerate(events):
            event_id = str(event["event_id"])
            event_type = event["type"]
            attributes = event.get("attributes", {})
            timestamp = float(event["time_sec"])
            confidence = float(event.get("confidence", 0.0))
            provenance = (event_id,)
            if event_type == "shot":
                add(
                    "shot_while_moving",
                    attributes.get("moving"),
                    confidence,
                    "event_normalization",
                    timestamp,
                    provenance,
                )
                add(
                    "first_shot_detected",
                    attributes.get("first_shot"),
                    confidence,
                    "event_normalization",
                    timestamp,
                    provenance,
                )
                if attributes.get("first_shot") is True and attributes.get("moving") is not None:
                    add(
                        "first_shot_stationary",
                        not attributes["moving"],
                        confidence,
                        "derived_code",
                        timestamp,
                        provenance,
                    )
                add(
                    "weapon",
                    attributes.get("weapon"),
                    confidence,
                    "event_normalization",
                    timestamp,
                    provenance,
                )
            elif event_type == "preaim_started":
                next_action = next(
                    (
                        candidate
                        for candidate in events[index + 1 :]
                        if candidate["type"] in {"peek", "engagement_start"}
                    ),
                    None,
                )
                if next_action:
                    add(
                        "preaim_lead_sec",
                        round(float(next_action["time_sec"]) - timestamp, 4),
                        min(confidence, float(next_action.get("confidence", 0.0))),
                        "derived_code",
                        timestamp,
                        (event_id, str(next_action["event_id"])),
                    )
            elif event_type == "peek":
                add(
                    "exposed_directions_count",
                    attributes.get("exposed_directions"),
                    confidence,
                    "event_normalization",
                    timestamp,
                    provenance,
                )
                tradeable = attributes.get("tradeable_ally_nearby")
                if tradeable is None and attributes.get("allies_in_trade_range") is not None:
                    tradeable = attributes["allies_in_trade_range"] > 0
                add(
                    "tradeable_ally_nearby",
                    tradeable,
                    confidence,
                    "event_normalization",
                    timestamp,
                    provenance,
                )
            elif event_type == "engagement_start":
                if attributes.get("allies_in_trade_range") is not None:
                    add(
                        "tradeable_ally_nearby",
                        attributes["allies_in_trade_range"] > 0,
                        confidence,
                        "event_normalization",
                        timestamp,
                        provenance,
                    )
            elif event_type == "player_death":
                add("player_died", True, confidence, "event_normalization", timestamp, provenance)
                earlier_eliminations = [
                    candidate
                    for candidate in events[:index]
                    if candidate["type"] in {"kill", "player_death"}
                ]
                add(
                    "first_death_by_player",
                    not earlier_eliminations,
                    min(confidence, 0.9),
                    "derived_code",
                    timestamp,
                    provenance,
                )
            elif event_type == "kill" and str(event.get("actor", "")) == "player":
                earlier_eliminations = [
                    candidate
                    for candidate in events[:index]
                    if candidate["type"] in {"kill", "player_death"}
                ]
                add(
                    "first_kill_by_player",
                    not earlier_eliminations,
                    min(confidence, 0.9),
                    "derived_code",
                    timestamp,
                    provenance,
                )
            elif event_type == "ability_state":
                add(
                    "utility_available_count",
                    attributes.get("charges_remaining"),
                    confidence,
                    "event_normalization",
                    timestamp,
                    provenance,
                )
                is_ultimate = (
                    attributes.get("semantic_role") == "ultimate"
                    or attributes.get("keybind_role") == "X"
                    or attributes.get("slot") == 3
                )
                if is_ultimate and isinstance(attributes.get("available"), bool):
                    add(
                        "ultimate_available",
                        attributes["available"],
                        confidence,
                        "event_normalization",
                        timestamp,
                        provenance,
                    )
            elif event_type == "spike_planted":
                add("spike_planted", True, confidence, "event_normalization", timestamp, provenance)
            elif event_type == "enemy_spotted":
                add(
                    "enemy_spotted_count",
                    attributes.get("count", 1),
                    confidence,
                    "event_normalization",
                    timestamp,
                    provenance,
                )
            elif event_type == "rotation_started":
                add(
                    "rotation_delay_sec",
                    attributes.get("delay_since_enemy_info_sec"),
                    confidence,
                    "event_normalization",
                    timestamp,
                    provenance,
                )
            elif event_type == "site_state":
                add(
                    "site_incoming_damage_risk_observed",
                    attributes.get("incoming_damage_risk_observed"),
                    confidence,
                    "event_normalization",
                    timestamp,
                    provenance,
                )
            elif event_type == "objective_state":
                add(
                    "objective_state_observed",
                    True,
                    confidence,
                    "event_normalization",
                    timestamp,
                    provenance,
                )
                add(
                    "round_time_remaining_sec",
                    attributes.get("round_time_remaining_sec"),
                    confidence,
                    "event_normalization",
                    timestamp,
                    provenance,
                )
                if attributes.get("spike_available") is not None:
                    add(
                        "spike_carried_by_player",
                        attributes["spike_available"],
                        confidence,
                        "event_normalization",
                        timestamp,
                        provenance,
                    )
            elif event_type == "buy_phase":
                add(
                    "buy_phase_observed",
                    True,
                    confidence,
                    "event_normalization",
                    timestamp,
                    provenance,
                )
                add(
                    "team_buy_class",
                    attributes.get("team_plan"),
                    confidence,
                    "event_normalization",
                    timestamp,
                    provenance,
                )
            elif event_type == "purchase":
                add(
                    "player_buy_class",
                    attributes.get("buy_class"),
                    confidence,
                    "event_normalization",
                    timestamp,
                    provenance,
                )
            elif event_type == "save_decision":
                add(
                    "save_context_observed",
                    True,
                    confidence,
                    "event_normalization",
                    timestamp,
                    provenance,
                )
            elif event_type == "ally_entry_start":
                add(
                    "ally_entry_active",
                    True,
                    confidence,
                    "event_normalization",
                    timestamp,
                    provenance,
                )
            elif event_type == "audio_cue":
                add("audio_cue_observed", True, confidence, "audio", timestamp, provenance)
            elif event_type == "status_effect":
                if attributes.get("affected_side") in {"player", "ally"}:
                    add(
                        "disadvantageous_effect_active",
                        True,
                        confidence,
                        "event_normalization",
                        timestamp,
                        provenance,
                    )
            elif event_type == "utility_used":
                effect = str(attributes.get("ability_effect", "")).lower()
                if attributes.get("affects_player_area") is True and any(
                    token in effect for token in ("flash", "slow", "delay", "suppress")
                ):
                    add(
                        "disadvantageous_effect_active",
                        True,
                        confidence,
                        "event_normalization",
                        timestamp,
                        provenance,
                    )
            elif event_type == "hold_angle":
                add(
                    "weapon",
                    attributes.get("weapon"),
                    confidence,
                    "event_normalization",
                    timestamp,
                    provenance,
                )

        return generated

    def enrich(self, round_package: dict[str, Any]) -> dict[str, Any]:
        result = deepcopy(round_package)
        result.setdefault("deterministic_facts", []).extend(
            fact.to_dict() for fact in self.build(round_package)
        )
        return result

    @staticmethod
    def _source_confidence(snapshot: dict[str, Any], field: str) -> float:
        """Confidence of the observation a snapshot field came from; absent means 0.0."""
        source = snapshot.get("source_confidence")
        value = source.get(field) if isinstance(source, dict) else None
        if isinstance(value, bool) or not isinstance(value, int | float):
            return 0.0
        if not math.isfinite(value) or not 0.0 <= value <= 1.0:
            return 0.0
        return float(value)

    @staticmethod
    def _freeze(value: Any) -> Any:
        if isinstance(value, dict):
            return tuple(sorted((key, FactBuilder._freeze(item)) for key, item in value.items()))
        if isinstance(value, list):
            return tuple(FactBuilder._freeze(item) for item in value)
        return value
