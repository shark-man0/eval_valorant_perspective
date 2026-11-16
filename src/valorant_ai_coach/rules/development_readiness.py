"""Development-only check of which rules can fire on real recordings.

Input is a per-match series of knowledge-reader observations (ability HUD and
top match bar, sampled every few seconds). The module derives candidate facts
and events, then checks every rule's trigger and required predicates. Results
are counts of *candidate occurrences* for planning and regression tracking:
nothing here is a formal Fact, Event or evaluation (formal_outputs = 0).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

SELF_VIEW_MIN_SCORE = 0.6
CHARGE_DROP = 0.25


@dataclass(frozen=True)
class Observation:
    sec: float
    hud_present: bool
    viewed_agent: str | None
    viewed_score: float
    charges: tuple[float, float, float, float]  # C, Q, E, X
    ally_alive: int | None
    enemy_alive: int | None


@dataclass
class DerivedSample:
    sec: float
    facts: dict[str, Any]
    events: set[str] = field(default_factory=set)


def derive(series: Sequence[Observation], recorder_agent: str | None,
           recorder_role: str) -> list[DerivedSample]:
    """Candidate facts/events per sample. Facts are omitted (missing) when unobserved."""
    samples: list[DerivedSample] = []
    previous: Observation | None = None
    previous_self: Observation | None = None
    for obs in series:
        facts: dict[str, Any] = {}
        events: set[str] = set()
        self_view = (
            recorder_agent is not None
            and obs.hud_present
            and obs.viewed_agent == recorder_agent
            and obs.viewed_score >= SELF_VIEW_MIN_SCORE
        )
        if recorder_agent is not None:
            facts["player_role"] = recorder_role
        bar_ok = obs.ally_alive is not None and obs.enemy_alive is not None
        if bar_ok and obs.ally_alive and obs.enemy_alive:
            ally, enemy = int(obs.ally_alive), int(obs.enemy_alive)
            facts["numbers_state"] = (
                "advantage" if ally > enemy else "disadvantage" if ally < enemy else "even"
            )
            events.add("state_snapshot")
            if self_view:
                facts["clutch_state"] = ally == 1 and enemy >= 1
        if self_view:
            events.add("ability_state")
            facts["utility_available_count"] = sum(c >= 0.25 for c in obs.charges[:3])
            facts["ultimate_available"] = obs.charges[3] >= 0.6
            facts["player_died"] = False
            if previous_self is not None and obs.sec - previous_self.sec <= 10:
                drops = [a - b for a, b in zip(previous_self.charges[:3], obs.charges[:3],
                                               strict=True)]
                if max(drops) >= CHARGE_DROP:
                    events.add("utility_used")
            previous_self = obs
        elif (
            previous is not None
            and previous_self is previous
            and obs.hud_present
            and obs.viewed_agent not in (None, recorder_agent)
        ):
            # Own HUD replaced by a teammate's: the recorder died (or spectates).
            events.add("player_death")
            facts["player_died"] = True
            if obs.sec - previous.sec <= 10:
                # Utilities still charged on the last own-HUD sample before the death.
                facts["utility_available_count"] = sum(c >= 0.25 for c in previous.charges[:3])
        if (previous is not None and bar_ok and previous.enemy_alive is not None
                and previous.ally_alive is not None and obs.sec - previous.sec <= 10):
            # Team-level kill: an alive count dropped without the round resetting (a
            # reset raises counts). Killer identity is unknown.
            ally_drop = 0 < int(obs.ally_alive or 0) < int(previous.ally_alive)
            enemy_drop = 0 < int(obs.enemy_alive or 0) < int(previous.enemy_alive)
            raised = (int(obs.ally_alive or 0) > int(previous.ally_alive)
                      or int(obs.enemy_alive or 0) > int(previous.enemy_alive))
            if (ally_drop or enemy_drop) and not raised:
                events.add("kill")
        samples.append(DerivedSample(obs.sec, facts, events))
        previous = obs
    return samples


def _predicate(value: Any, op: str, expected: Any) -> bool:
    if op == "eq":
        return bool(value == expected)
    if op == "in":
        return value in expected
    if op == "gt":
        return bool(value > expected)
    if op == "gte":
        return bool(value >= expected)
    raise ValueError(f"Unsupported predicate op {op}")


def rule_occurrences(rules: Sequence[dict[str, Any]], samples: Sequence[DerivedSample]
                     ) -> dict[str, int]:
    """Samples where a trigger event and all required predicates hold, per rule."""
    counts = {rule["id"]: 0 for rule in rules}
    for sample in samples:
        for rule in rules:
            trigger = rule["trigger"]
            if not sample.events.intersection(trigger["trigger_event_types"]):
                continue
            ok = True
            for predicate in trigger["required_state_predicates"]:
                key = predicate["fact_key"]
                if key not in sample.facts or not _predicate(
                        sample.facts[key], predicate["op"], predicate["value"]):
                    ok = False
                    break
            if ok:
                counts[rule["id"]] += 1
    return counts
