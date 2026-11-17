from __future__ import annotations

import cv2
import numpy as np

from valorant_ai_coach.knowledge.timeline_view import TimelineView
from valorant_ai_coach.knowledge.top_bar import BAR_ORIGIN, CENTRE_BOX, spike_planted_indicator
from valorant_ai_coach.rules.coverage import (
    LEVELS,
    blocker_ranking,
    coverage,
    load_producer_status,
    load_rules,
    summarize,
)
from valorant_ai_coach.rules.development_readiness import (
    FeedKill,
    Observation,
    derive,
    rule_occurrences,
)
from valorant_ai_coach.rules.recorder_life import Round, reconcile, rounds_from_alive_counts


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
    assert {"UTL-01", "ADV-08", "ROLE-02", "INFO-03", "ADV-01", "ADV-02", "OBJ-03",
            "POS-04", "DEC-05"} <= ready
    assert all(not blocker.startswith("fact:player_role")
               for blocker, _ in blocker_ranking(coverage("after")))


def _obs(sec: float, agent: str | None, charges: tuple[float, float, float, float],
         ally: int, enemy: int, *, spike: bool | None = None,
         feed: tuple[FeedKill, ...] | None = None) -> Observation:
    return Observation(sec, agent is not None, agent, 0.9 if agent else 0.0, charges, ally, enemy,
                       spike, feed)


def test_derived_candidates_and_rule_occurrences() -> None:
    own_death = FeedKill("enemy", "ally", "Omen", False, True)
    series = [
        _obs(0, "Omen", (1, 1, 1, 0), 5, 5, spike=False, feed=()),
        _obs(5, "Omen", (1, 0, 1, 1), 5, 4, spike=False,
             feed=(FeedKill("ally", "enemy", "Jett", True, False),)),  # recorder's kill
        _obs(10, "Omen", (1, 0, 1, 1), 1, 3, spike=True, feed=()),  # plant; last ally alive
        _obs(15, "Sova", (1, 1, 1, 0), 1, 3, spike=True, feed=(own_death,)),
        _obs(20, "Sova", (1, 1, 1, 0), 1, 3, spike=True, feed=(own_death,)),  # same entry
        _obs(25, "Omen", (1, 1, 1, 1), 5, 5, spike=False, feed=()),  # next round
    ]
    derivation = derive(series, "Omen", "controller")
    samples = derivation.samples
    assert derivation.sources["rounds"] == "top_bar_reset"
    assert "utility_used" in samples[1].events and "kill" in samples[1].events
    assert samples[1].facts["first_kill_by_player"] is True
    assert samples[1].facts["first_death_by_player"] is False
    assert samples[1].facts["ultimate_available"] is True
    assert samples[2].facts["clutch_state"] is True
    assert {"spike_planted", "objective_state"} <= samples[2].events
    assert samples[3].facts["player_died"] is True and "player_death" in samples[3].events
    assert samples[3].facts["utility_available_count"] == 2
    assert "kill" not in samples[4].events  # a persisting entry is not a new kill
    assert len(derivation.reconciliation.deaths) == 1
    counts = rule_occurrences(load_rules(), samples)
    assert counts["UTL-01"] == 1
    assert counts["ROLE-02"] == 1
    assert counts["ADV-02"] == 1 and counts["ADV-01"] == 0
    assert counts["OBJ-03"] == 1
    assert counts["ROLE-03"] == 0  # initiator rule never fires for a controller


def test_round_reconciliation_dedupes_revives_and_bounds() -> None:
    rounds = rounds_from_alive_counts([(0, 5, 5), (10, 3, 4), (40, 5, 5), (60, 2, 2)])
    assert [(r.start, r.end) for r in rounds] == [(0, 40), (40, None)]
    result = reconcile(rounds, {"timeline": [12.0, 50.0], "kill_feed": [14.0, 30.0, -5.0]},
                       live_samples=[21.0, 25.0, 45.0])
    deaths = [(d.round_index, d.sec, sorted(d.sources), d.after_revive) for d in result.deaths]
    # 12 + 14 merge; 30 is a second death after the recorder was live again at 21/25 (revive).
    assert deaths == [(0, 12.0, ["kill_feed", "timeline"], False), (0, 30.0, ["kill_feed"], True),
                      (1, 50.0, ["timeline"], False)]
    assert result.dropped["outside_round"] == 1
    no_revive = reconcile([Round(0, 40)], {"hud": [12.0, 30.0]})
    assert len(no_revive.deaths) == 1 and no_revive.dropped["duplicate"] == 1
    spectating = reconcile([Round(0, 40)], {"hud": [30.0]}, spectating_at=lambda t: t > 20)
    assert not spectating.deaths and spectating.dropped["while_spectating"] == 1


def test_timeline_drives_self_view_and_rounds() -> None:
    timeline = TimelineView.from_compact({
        "states": [[0.0, "BUY", "ALIVE", "SELF", 1, "OBSERVED"],
                   [10.0, "ACTIVE", "DEAD", "SPECTATOR", 1, "OBSERVED"],
                   [30.0, "BUY", "ALIVE", "SELF", 2, "OBSERVED"]],
        "events": [["round_start", 0.0, 0.2], ["death_hypothesis", 9.8, 10.0],
                   ["round_end", 25.0, 25.2], ["round_start", 30.0, 30.2]]})
    series = [_obs(0, "Omen", (1, 1, 1, 0), 5, 5), _obs(5, "Omen", (1, 1, 1, 0), 5, 5),
              _obs(10, "Omen", (1, 1, 1, 0), 4, 5),  # HUD still looks like Omen
              _obs(15, "Sova", (1, 1, 1, 0), 4, 5), _obs(30, "Omen", (1, 1, 1, 0), 5, 5)]
    derivation = derive(series, "Omen", "controller", timeline)
    assert derivation.sources == {"rounds": "timeline", "self_view": "timeline",
                                  "deaths": "kill_feed+timeline"}
    assert "ability_state" not in derivation.samples[2].events  # timeline says spectating
    assert [s.sec for s in derivation.samples if "player_death" in s.events] == [10.0]


def test_spike_indicator_reads_red_icon() -> None:
    crop = np.full((100, 1155, 3), 90, np.uint8)
    assert spike_planted_indicator(crop)[0] is False
    x0, y0, x1, y1 = CENTRE_BOX
    cv2.circle(crop, ((x0 + x1) // 2 - BAR_ORIGIN[0], (y0 + y1) // 2), 20, (0, 0, 230), -1)
    planted, fraction = spike_planted_indicator(crop)
    assert planted and fraction > 0.06
