from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from valorant_ai_coach.models import RuleCandidate

PRIORITY_ORDER = {"mvp_required": 0, "important": 1, "additional": 2}


class RuleSelector:
    def __init__(self, registry: Path | dict[str, Any]):
        self.registry = (
            json.loads(registry.read_text(encoding="utf-8"))
            if isinstance(registry, Path)
            else registry
        )
        self.max_candidates = int(self.registry.get("fallback", {}).get("max_candidate_rules", 12))

    def select(self, round_package: dict[str, Any]) -> list[RuleCandidate]:
        event_types = {str(event["type"]) for event in round_package.get("events", [])}
        facts: dict[str, list[Any]] = defaultdict(list)
        for fact in round_package.get("deterministic_facts", []):
            facts[str(fact["key"])].append(fact.get("value"))
        ranked: list[tuple[tuple[int, int, int, str], RuleCandidate]] = []
        for rule_id, config in self.registry["rules"].items():
            triggers = set(config.get("trigger_event_types", []))
            matched = tuple(sorted(event_types & triggers))
            if triggers and not matched:
                continue
            missing: list[str] = []
            excluded = False
            satisfied = 0
            for predicate in config.get("required_state_predicates", []):
                values = facts.get(predicate["fact_key"], [])
                result = self._compare(values, predicate["op"], predicate.get("value"))
                if result is None:
                    if predicate.get("missing_policy", "exclude") == "exclude":
                        excluded = True
                        break
                    missing.append(predicate["fact_key"])
                elif result is False:
                    excluded = True
                    break
                else:
                    satisfied += 1
            if excluded:
                continue
            supporting = tuple(
                key for key in config.get("supporting_fact_keys", []) if key in facts
            )
            candidate = RuleCandidate(
                rule_id=rule_id,
                priority=config["priority"],
                temporal_level=config["temporal_level"],
                label_mode=config["label_mode"],
                missing_fact_keys=tuple(missing),
                matched_event_types=matched,
                supporting_fact_keys=supporting,
            )
            # Explicitly satisfied gates outrank broad event-only matches. Missing allow_unscored
            # candidates remain eligible as required by registry v2 semantics.
            score = (
                PRIORITY_ORDER.get(candidate.priority, 9),
                -satisfied,
                len(candidate.missing_fact_keys),
                rule_id,
            )
            ranked.append((score, candidate))
        ranked.sort(key=lambda item: item[0])
        return [candidate for _, candidate in ranked[: self.max_candidates]]

    def select_ids(self, round_package: dict[str, Any]) -> list[str]:
        return [candidate.rule_id for candidate in self.select(round_package)]

    @staticmethod
    def _compare(values: list[Any], operator: str, expected: Any) -> bool | None:
        if not values:
            return None
        if operator == "exists":
            return True
        if operator == "eq":
            return any(value == expected for value in values)
        if operator == "neq":
            return any(value != expected for value in values)
        if operator == "in":
            return any(value in expected for value in values)
        numeric = [
            value
            for value in values
            if isinstance(value, (int, float)) and not isinstance(value, bool)
        ]
        if operator == "gte":
            return any(value >= expected for value in numeric)
        if operator == "lte":
            return any(value <= expected for value in numeric)
        if operator == "gt":
            return any(value > expected for value in numeric)
        if operator == "lt":
            return any(value < expected for value in numeric)
        raise ValueError(f"Unsupported predicate operator: {operator}")
