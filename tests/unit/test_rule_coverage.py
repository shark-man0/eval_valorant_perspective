from __future__ import annotations

from valorant_ai_coach.rules.coverage import (
    LEVELS,
    blocker_ranking,
    coverage,
    load_producer_status,
    load_rules,
    summarize,
)
from valorant_ai_coach.rules.development_readiness import (
    Observation,
    derive,
    rule_occurrences,
)


def test_status_registry_covers_every_rule_input() -> None:
    status = load_producer_status()
    rules = load_rules()
    assert len(rules) == 44
    for rule in rules:
        for event in rule["trigger"]["trigger_event_types"]:
            assert event in status["events"], event
        for predicate in rule["trigger"]["required_state_predicates"]:
            assert predicate["fact_key"] in status["facts"], predicate["fact_key"]
    for group in ("events", "facts"):
        for item in status[group].values():
            assert LEVELS.index(item["after"]) >= LEVELS.index(item["before"])


def test_readiness_before_and_after() -> None:
    before = summarize(coverage("before"))
    after = summarize(coverage("after"))
    assert sum(before.values()) == sum(after.values()) == 44
    assert before["qualified"] == after["qualified"] == 0
    assert after["development"] > before["development"]
    ready = {r.rule_id for r in coverage("after") if r.readiness == "development"}
    assert {"UTL-01", "ADV-08", "ROLE-02", "INFO-03"} <= ready
    assert all(not blocker.startswith("fact:player_role")
               for blocker, _ in blocker_ranking(coverage("after")))


def _obs(sec: float, agent: str | None, charges: tuple[float, float, float, float],
         ally: int, enemy: int) -> Observation:
    return Observation(sec, agent is not None, agent, 0.9 if agent else 0.0, charges, ally, enemy)


def test_derived_candidates_and_rule_occurrences() -> None:
    series = [
        _obs(0, "Omen", (1, 1, 1, 0), 5, 5),
        _obs(5, "Omen", (1, 0, 1, 1), 5, 4),  # Q used, an enemy died
        _obs(10, "Omen", (1, 0, 1, 1), 1, 3),  # recorder is the last ally alive
        _obs(15, "Sova", (1, 1, 1, 0), 1, 3),  # teammate's HUD: recorder died
    ]
    samples = derive(series, "Omen", "controller")
    assert "utility_used" in samples[1].events and "kill" in samples[1].events
    assert samples[1].facts["ultimate_available"] is True
    assert samples[2].facts["clutch_state"] is True
    assert samples[3].facts["player_died"] is True and "player_death" in samples[3].events
    assert samples[3].facts["utility_available_count"] == 2
    counts = rule_occurrences(load_rules(), samples)
    assert counts["UTL-01"] == 1
    assert counts["ROLE-02"] == 1
    assert counts["ADV-08"] == 1
    assert counts["ROLE-03"] == 0  # initiator rule never fires for a controller
