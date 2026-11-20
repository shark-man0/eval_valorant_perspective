"""Readiness of the 44 evaluation rules, computed from producer status.

A rule can produce a scored evaluation only when at least one trigger event and
every required fact are observable. Readiness is the weakest of those inputs on
the scale none < contract < development < qualified. ``allow_unscored``
predicates still count as required here: without the fact the rule can only be
emitted as ``unscored``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from valorant_ai_coach.resources import resource_path

LEVELS = ("none", "contract", "development", "qualified")
_RANK = {name: index for index, name in enumerate(LEVELS)}


@dataclass(frozen=True)
class RuleReadiness:
    rule_id: str
    item: str
    label_mode: str
    trigger_level: str
    trigger_best: str | None
    required: dict[str, str]
    blocking: tuple[str, ...]
    readiness: str


def load_rules(path: Path | None = None) -> list[dict[str, Any]]:
    source = path or resource_path("config/valorant_evaluation_rules_v4.json")
    return list(json.loads(source.read_text(encoding="utf-8"))["rules"])


def load_producer_status(path: Path | None = None) -> dict[str, Any]:
    source = path or resource_path("config/rule_producer_status_v1.json")
    data = json.loads(source.read_text(encoding="utf-8"))
    for group in ("events", "facts"):
        for key, item in data[group].items():
            for state in ("before", "after"):
                if item[state] not in _RANK:
                    raise ValueError(f"{group}.{key}.{state}: unknown level {item[state]}")
    return dict(data)


def rule_readiness(rule: dict[str, Any], status: dict[str, Any], state: str) -> RuleReadiness:
    trigger = rule["trigger"]
    events = status["events"]
    facts = status["facts"]
    best_event, best_level = None, "none"
    for event in trigger["trigger_event_types"]:
        level = events.get(event, {}).get(state, "none")
        if _RANK[level] > _RANK[best_level]:
            best_event, best_level = event, level
    required = {
        p["fact_key"]: facts.get(p["fact_key"], {}).get(state, "none")
        for p in trigger["required_state_predicates"]
    }
    readiness = best_level
    for level in required.values():
        if _RANK[level] < _RANK[readiness]:
            readiness = level
    target = max(_RANK["development"], _RANK[readiness])
    blocking = []
    if _RANK[best_level] < target:
        blocking.append("trigger:" + "/".join(trigger["trigger_event_types"]))
    blocking.extend(f"fact:{k}" for k, v in required.items() if _RANK[v] < target)
    return RuleReadiness(rule["id"], rule["item"], trigger["label_mode"], best_level, best_event,
                         required, tuple(blocking), readiness)


def coverage(state: str, rules: list[dict[str, Any]] | None = None,
             status: dict[str, Any] | None = None) -> list[RuleReadiness]:
    rules = rules if rules is not None else load_rules()
    status = status if status is not None else load_producer_status()
    return [rule_readiness(rule, status, state) for rule in rules]


def summarize(rows: list[RuleReadiness]) -> dict[str, int]:
    counts = {level: 0 for level in LEVELS}
    for row in rows:
        counts[row.readiness] += 1
    return counts


def blocker_ranking(rows: list[RuleReadiness]) -> list[tuple[str, int]]:
    """Inputs ordered by how many rules they keep below development readiness."""
    counts: dict[str, int] = {}
    for row in rows:
        if _RANK[row.readiness] >= _RANK["development"]:
            continue
        for blocker in row.blocking:
            counts[blocker] = counts.get(blocker, 0) + 1
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))
