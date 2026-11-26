"""Knowledge-reader facts on Rounds confirmed by the shared timeline."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from tests.unit.test_timeline_formal_promotion import SOURCE_VIDEO, Timeline, add_round, promote
from valorant_ai_coach.application.timeline_evaluation import (
    API_NOT_RUN_MESSAGE,
    MissingFactAbstentionCoach,
    evaluate_timeline,
)
from valorant_ai_coach.facts import FactBuilder
from valorant_ai_coach.facts.second_feature_promotion import (
    SecondFeaturePromoter,
    feed_arrivals,
)
from valorant_ai_coach.facts.timeline_promotion import PromotionError, TimelinePromoter
from valorant_ai_coach.rules.development_readiness import FeedKill, Observation
from valorant_ai_coach.rules.second_series import SecondRecord

SHA = "a" * 64
Bar = Callable[[int], tuple[int, int] | None]


def observation(second: int, *, bar: tuple[int, int] | None = (5, 5), agent: str = "Sova",
                charges: tuple[float, float, float, float] = (1.0, 1.0, 0.0, 0.0),
                spike: bool = False, feed: tuple[FeedKill, ...] = (),
                score: tuple[int, int] | None = None) -> SecondRecord:
    return SecondRecord(
        observation=Observation(
            sec=second + 0.4, hud_present=True, viewed_agent=agent, viewed_score=0.9,
            charges=charges, ally_alive=None if bar is None else bar[0],
            enemy_alive=None if bar is None else bar[1], feed=feed,
            spike_carried=spike, spike_score=0.95 if spike else None, score=score,
        ),
        magazine=None, residual_p90=None, tracked=0,
    )


def records(length: int, bar: Bar, **kwargs: Any) -> list[SecondRecord]:
    return [observation(s, bar=bar(s), **kwargs) for s in range(length)]


def recorder_dies_first(second: int) -> tuple[int, int]:
    # R1 (0-66): the recorder (death at 45/46) is the first elimination.
    if second < 46:
        return (5, 5)
    if second < 52:
        return (4, 5)
    if second < 66:
        return (4, 4)
    return (5, 5)


def augment(bundle: dict[str, Any], feature_records: list[SecondRecord], sha: str = SHA,
            frame_refs: dict[float, str] | None = None):
    result = promote(bundle)
    report = SecondFeaturePromoter().augment(bundle, result, feature_records,
                                             records_sha256=sha, frame_refs=frame_refs)
    return result, report


def facts_of(result, round_no: int) -> dict[str, list[Any]]:
    item = next(r for r in result.rounds if r.round_no == round_no)
    package = {
        "events": item.events, "state_snapshots": item.snapshots,
        "round_meta": {"side": item.round_meta.get("side", "unknown"),
                       "player_role": item.round_meta.get("player_role", "unknown"),
                       "map": "unknown", "player_agent": "unknown", "round_result": "unknown",
                       "score_before": None, "economy_context": None},
        "deterministic_facts": [],
    }
    out: dict[str, list[Any]] = {}
    for fact in FactBuilder().build(package):
        out.setdefault(fact.key, []).append(fact.value)
    return out


def two_rounds_bundle() -> dict[str, Any]:
    t = Timeline(140)
    add_round(t, 1, 0, ally=0, enemy=0, won=False, death_at=45)
    add_round(t, 2, 66, ally=0, enemy=1, won=True)
    return t.bundle()


def test_features_from_another_recording_are_refused():
    with pytest.raises(PromotionError):
        augment(two_rounds_bundle(), records(140, recorder_dies_first), sha="b" * 64)


def test_alive_counts_utility_role_and_elimination_order_are_promoted():
    result, report = augment(two_rounds_bundle(), records(140, recorder_dies_first))
    assert report.recorder_agent == "Sova" and report.recorder_role == "initiator"
    first = result.rounds[0]
    snapshot = next(s for s in first.snapshots if s["ally_alive"] is not None)
    assert snapshot["source_confidence"]["ally_alive"] == 0.9
    assert any(s.get("utility_available_count") == 2 for s in first.snapshots)
    death = next(e for e in first.events if e["type"] == "player_death")
    proof = death["attributes"]["evidence_provenance"]
    assert proof["elimination_coverage"] == "top_bar_alive_counts"
    assert proof["evidence_refs"]  # timeline refs plus the frame of the drop
    kills = [e for e in first.events if e["type"] == "kill"]
    assert [k["attributes"]["victim_team"] for k in kills] == ["enemy"]
    facts = facts_of(result, 1)
    assert facts["first_death_by_player"] == [True]
    assert facts["numbers_state"] and facts["utility_available_count"]
    assert first.round_meta["player_role"] == "initiator"


def test_an_earlier_enemy_elimination_makes_the_death_not_first():
    def bar(second: int) -> tuple[int, int]:
        if second < 30:
            return (5, 5)
        if second < 46:
            return (5, 4)
        return (4, 4) if second < 66 else (5, 5)

    result, _ = augment(two_rounds_bundle(), records(140, bar))
    facts = facts_of(result, 1)
    # Both the first (enemy) elimination and the death itself say "not first".
    assert set(facts["first_death_by_player"]) == {False}
    # The first elimination was an enemy, killer unknown: no first-kill claim.
    assert "first_kill_by_player" not in facts


def test_simultaneous_drops_leave_the_order_unknown():
    def bar(second: int) -> tuple[int, int]:
        if second < 46:
            return (5, 5)
        return (4, 4) if second < 66 else (5, 5)

    result, report = augment(two_rounds_bundle(), records(140, bar))
    death = next(e for e in result.rounds[0].events if e["type"] == "player_death")
    assert death["attributes"]["evidence_provenance"]["elimination_coverage"] == (
        "self_death_only"
    )
    assert report.rejected["death_top_bar_order_ambiguous"] == 1
    assert "first_death_by_player" not in facts_of(result, 1)


def test_unreadable_top_bar_promotes_no_elimination_order():
    result, report = augment(two_rounds_bundle(), records(140, lambda s: None))
    assert not [e for e in result.rounds[0].events if e["type"] == "kill"]
    assert report.rejected["top_bar_coverage_too_low"] >= 1


def test_recorder_kill_needs_the_own_player_highlight_in_the_kill_feed():
    def bar(second: int) -> tuple[int, int]:
        if second < 30:
            return (5, 5)
        if second < 46:
            return (5, 4)
        return (4, 4) if second < 66 else (5, 5)

    feed = (FeedKill("ally", "enemy", "Jett", True, False),)
    feature_records = records(140, bar)
    feature_records[30] = observation(30, bar=(5, 4), feed=feed)
    result, report = augment(two_rounds_bundle(), feature_records)
    kill = next(e for e in result.rounds[0].events if e["type"] == "kill")
    assert kill["actor"] == "player" and report.counts["kills_by_recorder"] == 1
    assert facts_of(result, 1)["first_kill_by_player"] == [True]


def test_last_ally_alive_death_without_spectator_view_is_recovered():
    t = Timeline(80)
    add_round(t, 1, 0, ally=0, enemy=0, won=False)
    t.player(50, 60, "UNKNOWN", "UNKNOWN")  # own view ends at 49, Round ends at 60

    def bar(second: int) -> tuple[int, int]:
        if second < 30:
            return (5, 5)
        return (1, 3) if second < 50 else (0, 3)

    result, report = augment(t.bundle(), records(80, bar))
    death = [e for e in result.rounds[0].events if e["type"] == "player_death"]
    assert len(death) == 1 and death[0]["time_sec"] == 50.0
    assert death[0]["attributes"]["promotion_rule"].endswith("_team_eliminated")
    assert report.counts["recovered_deaths"] == 1


def test_two_ally_drops_after_the_own_view_ends_are_not_a_recovered_death():
    t = Timeline(80)
    add_round(t, 1, 0, ally=0, enemy=0, won=False)
    t.player(50, 60, "UNKNOWN", "UNKNOWN")

    def bar(second: int) -> tuple[int, int]:
        if second < 49:
            return (2, 3)
        return (1, 3) if second < 51 else (0, 3)

    result, report = augment(t.bundle(), records(80, bar))
    assert not [e for e in result.rounds[0].events if e["type"] == "player_death"]
    assert report.rejected["recovered_death_ambiguous_ally_drops"] == 1


def test_revive_is_recorded_on_the_death_not_as_a_new_life_state():
    t = Timeline(80)
    add_round(t, 1, 0, ally=0, enemy=0, won=False, death_at=35)
    t.player(46, 60, "ALIVE", "SELF")  # back in the own live view after a revive
    result, report = augment(t.bundle(), records(80, lambda s: (5, 5)))
    death = next(e for e in result.rounds[0].events if e["type"] == "player_death")
    assert death["attributes"]["revived_at_sec"] == 46
    assert report.counts["revives"] == 1


def test_side_comes_from_own_spike_sightings_and_the_half_structure():
    t = Timeline(140)
    add_round(t, 1, 0, ally=0, enemy=0, won=False)
    add_round(t, 2, 66, ally=0, enemy=1, won=True)
    feature_records = records(140, lambda s: (5, 5))
    for second in (25, 26):
        feature_records[second] = observation(second, spike=True)
    result, report = augment(t.bundle(), feature_records)
    assert report.side_status == "half_structure" and report.first_half_side == "attack"
    assert [r.round_meta.get("side") for r in result.rounds] == ["attack", "attack"]


def test_utility_on_another_agents_hud_is_not_the_recorders():
    feature_records = records(140, lambda s: (5, 5))
    for second in range(20, 40):
        feature_records[second] = observation(second, agent="Jett")
    result, report = augment(two_rounds_bundle(), feature_records)
    assert report.rejected["utility_hud_not_recorder"] >= 1
    assert all(
        s.get("utility_available_count") is None
        for s in result.rounds[0].snapshots if 20 <= s["time_sec"] < 40
    )


def test_bridge_routes_features_and_keeps_formal_rounds_consistent(tmp_path: Path):
    bundle = two_rounds_bundle()
    evaluation = evaluate_timeline(
        bundle, match_id="DEV-feat", source_video=SOURCE_VIDEO, promoter=TimelinePromoter(),
        second_features=(records(140, recorder_dies_first), SHA),
    )
    assert evaluation.second_features["recorder_agent"] == "Sova"
    package = evaluation.packages[0]
    assert package["round_meta"]["player_role"] == "initiator"
    times = [e["time_sec"] for e in package["events"]]
    assert all(0 <= t < 66 for t in times)


class _ScoringMock:
    def evaluate(self, round_package, candidate_rule_ids, **_: Any) -> dict[str, Any]:
        return {"schema_version": "3.0", "analysis_id": "x", "match_id": "m",
                "round_no": 1, "evaluations": [{
                    "evaluation_id": "e1", "clip_id": "c", "primary_rule_id": "UTL-01",
                    "related_rule_ids": [], "label": "good", "decision_source": "llm",
                    "fact_refs": ["f"], "concept_tags": [], "title": "t", "situation": "s",
                    "reason": "r", "improvement": None, "confidence": 0.9,
                    "evidence": [], "evidence_range": None, "display_clip": {},
                    "missing_information": [], "unscored_reason_code": None,
                }]}


def test_offline_scores_are_not_formal_unless_the_rule_engine_decided_them():
    from valorant_ai_coach.application.timeline_evaluation import default_round_analyzer

    selector = default_round_analyzer().selector
    coach = MissingFactAbstentionCoach(_ScoringMock(), selector)
    package = {"match_id": "m", "round_no": 1, "events": [], "deterministic_facts": []}
    output = coach.evaluate(package, ["UTL-01"])
    item = output["evaluations"][0]
    assert item["label"] == "unscored" and item["missing_information"] == [API_NOT_RUN_MESSAGE]
    decided = coach.evaluate(package, ["UTL-01"],
                             deterministic_decisions={"UTL-01": {"label": "good"}})
    assert decided["evaluations"][0]["label"] == "good"


def test_measurement_counts_each_recording_once(tmp_path: Path):
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "measure", Path("scripts/measure_formal_promotion.py")
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    path = tmp_path / "t.json"
    path.write_text(json.dumps(two_rounds_bundle()), encoding="utf-8")
    copy = tmp_path / "copy.json"
    copy.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    kept, skipped = module.deduplicate([("A", "timeline", path), ("B", "timeline", copy)])
    assert [k[0] for k in kept] == ["A"] and skipped[0]["name"] == "B"


# ----------------------------------------------------------------- kill feed


def _obs(sec: float, *feed: FeedKill) -> Observation:
    return Observation(sec=sec, hud_present=True, viewed_agent="Sova", viewed_score=0.9,
                       charges=(0.0, 0.0, 0.0, 0.0), ally_alive=5, enemy_alive=5, feed=feed)


def test_feed_arrivals_ignore_victim_colour_and_name_flicker_and_dropouts():
    kill = FeedKill("ally", "enemy", "Jett", False, False)
    flicker = FeedKill("ally", "ally", "Jet", False, False)  # victim colour and name misread
    second = FeedKill("ally", "enemy", "Sage", False, False)
    series = [_obs(10, kill), _obs(11, flicker), _obs(12), _obs(13, kill),
              _obs(14, kill, second)]
    arrivals = [a for a in feed_arrivals(series, 2.0) if a.kind == "elimination"]
    # One entry at 10 (flicker, a single dropout and the re-read are the same entry)
    # and a second one at 14, when two ally-killer rows are shown at once.
    assert [(a.sec, a.killer_team, a.victim_team) for a in arrivals] == [
        (10, "ally", "enemy"), (14, "ally", "enemy")
    ]


def _one_enemy_then_recorder_bar(second: int) -> tuple[int, int]:
    if second < 30:
        return (5, 5)
    if second < 46:
        return (5, 4)
    return (4, 4) if second < 66 else (5, 5)


def test_one_feed_entry_serves_only_one_elimination():
    def bar(second: int) -> tuple[int, int]:
        if second < 30:
            return (5, 5)
        if second < 33:
            return (5, 4)
        if second < 46:
            return (5, 3)
        return (4, 3) if second < 66 else (5, 5)

    highlighted = (FeedKill("ally", "enemy", "Jett", True, False),)
    feature_records = records(140, bar)
    feature_records[31] = observation(31, bar=(5, 4), feed=highlighted)
    result, report = augment(two_rounds_bundle(), feature_records)
    kills = [e for e in result.rounds[0].events if e["type"] == "kill"]
    # Drops at 30 and 33 are both within the feed delay of the entry at 31, but the
    # entry (and its highlight) is assigned to the earlier drop only.
    assert [k["actor"] for k in kills] == ["player", "unknown"]
    assert report.counts["feed_assigned"] == 1
    assert report.counts["eliminations_without_feed"] == 2  # second enemy, recorder


def test_feed_entries_without_a_top_bar_drop_are_phantom_and_name_nobody():
    phantom = (FeedKill("ally", "enemy", "Jett", True, False),)
    feature_records = records(140, recorder_dies_first)
    feature_records[20] = observation(20, feed=phantom)  # nothing drops near 20
    result, report = augment(two_rounds_bundle(), feature_records)
    assert report.counts["feed_phantom"] == 2  # the row and its highlight
    assert report.counts["kills_by_recorder"] == 0
    assert not [e for e in result.rounds[0].events if e["actor"] == "player"
                and e["type"] == "kill"]


def test_feed_naming_the_recorder_at_another_drop_withholds_the_order():
    # Ally drops at 40 and 46; the timeline death is at 45, but the feed puts the
    # recorder's highlight on the drop at 40, outside the death's window.
    def bar(second: int) -> tuple[int, int]:
        if second < 40:
            return (5, 5)
        if second < 46:
            return (4, 5)
        return (3, 5) if second < 66 else (5, 5)

    feature_records = records(140, bar)
    feature_records[40] = observation(
        40, bar=(4, 5), feed=(FeedKill("enemy", "ally", "Sova", False, True),)
    )
    result, report = augment(two_rounds_bundle(), feature_records)
    death = next(e for e in result.rounds[0].events if e["type"] == "player_death")
    assert death["attributes"]["kill_feed_attribution"] == "conflict"
    assert death["attributes"]["evidence_provenance"]["elimination_coverage"] == (
        "self_death_only"
    )
    kills = [e for e in result.rounds[0].events if e["type"] == "kill"]
    assert {k["attributes"]["evidence_provenance"]["elimination_coverage"] for k in kills} == {
        "top_bar_partial"
    }
    assert "first_death_by_player" not in facts_of(result, 1)
    assert report.checks["recorder_death_vs_kill_feed"] == {"disagree": 1}


def test_feed_order_resolves_eliminations_read_in_the_same_second():
    def bar(second: int) -> tuple[int, int]:
        if second < 46:
            return (5, 5)
        return (4, 4) if second < 66 else (5, 5)

    feature_records = records(140, bar)
    feature_records[44] = observation(
        44, feed=(FeedKill("ally", "enemy", "Jett", False, False),)
    )
    feature_records[46] = observation(46, bar=(4, 4), feed=(
        FeedKill("ally", "enemy", "Jett", False, False),
        FeedKill("enemy", "ally", "Sova", False, True),
    ))
    result, report = augment(two_rounds_bundle(), feature_records)
    death = next(e for e in result.rounds[0].events if e["type"] == "player_death")
    assert death["attributes"]["evidence_provenance"]["elimination_coverage"] == (
        "top_bar_alive_counts"
    )
    assert facts_of(result, 1)["first_death_by_player"] == [False]
    assert report.checks["first_death_vs_kill_feed"] == {"agree": 1}


def test_ambiguous_kill_order_derives_no_first_elimination_fact():
    package = {
        "events": [{
            "event_id": "k1", "type": "kill", "time_sec": 10.0, "actor": "unknown",
            "confidence": 0.85, "attributes": {
                "order_ambiguous": True,
                "evidence_provenance": {"elimination_coverage": "top_bar_alive_counts"},
            },
        }],
        "state_snapshots": [], "round_meta": {}, "deterministic_facts": [],
    }
    keys = {fact.key for fact in FactBuilder().build(package)}
    assert "first_death_by_player" not in keys and "first_kill_by_player" not in keys


def test_a_repeated_frame_image_is_one_piece_of_evidence():
    feature_records = records(140, recorder_dies_first)
    refs = {r.observation.sec: f"frame:{int(r.observation.sec)}" for r in feature_records}
    refs[21.4] = refs[20.4]  # the same acquired frame at a later time
    _, report = augment(two_rounds_bundle(), feature_records, frame_refs=refs)
    assert report.counts["reused_frame_readings_dropped"] == 1


# ----------------------------------------------------------------- economy


def _eco_bundle(won_first: bool) -> dict[str, Any]:
    t = Timeline(140)
    add_round(t, 1, 0, ally=0, enemy=0, won=won_first)
    add_round(t, 2, 66, ally=1 if won_first else 0, enemy=0 if won_first else 1, won=True)
    return t.bundle()


def _eco_records(score: tuple[int, int]) -> list[SecondRecord]:
    out = records(140, lambda s: (5, 5))
    for second in range(66, 96):
        out[second] = observation(second, score=score)
    for second in range(0, 30):
        out[second] = observation(second, score=(0, 0))
    return out


def test_enemy_eco_after_a_won_pistol_round_from_the_credit_upper_bound():
    result, report = augment(_eco_bundle(True), _eco_records((1, 0)))
    buy = next(e for e in result.rounds[1].events if e["type"] == "buy_phase")
    economy = buy["attributes"]["enemy_economy"]
    assert economy["enemy_eco_likely"] is True
    assert economy["enemy_average_credits_upper_bound"] < economy["full_buy_min_cost"] == 3900
    assert economy["evidence_refs"] == [] and economy["rule_source"]
    assert facts_of(result, 2)["enemy_eco_likely"] == [True]
    assert report.counts["enemy_eco_rounds"] == 1
    # The pistol round itself is never called an eco.
    assert "enemy_eco_likely" not in facts_of(result, 1)


def test_no_enemy_eco_after_a_lost_pistol_round_and_never_false():
    result, report = augment(_eco_bundle(False), _eco_records((0, 1)))
    assert report.counts["enemy_eco_rounds"] == 0
    assert report.counts["economy_rounds_not_after_won_pistol"] == 1
    assert "enemy_eco_likely" not in facts_of(result, 2)


def test_full_buy_bound_matches_the_knowledge_base():
    from valorant_ai_coach.knowledge import load_game_knowledge
    from valorant_ai_coach.resources import resource_path

    knowledge = load_game_knowledge()
    rifles = max(w.cost for w in knowledge.weapons if w.category == "Rifle")
    rules = json.loads(
        resource_path("config/game_knowledge/game_rules_v1.json").read_text(encoding="utf-8")
    )
    assert rifles + knowledge.rule("heavy_shield_cost") == (
        rules["derived_bounds"]["full_buy_min_cost"]["value"]
    )
    assert knowledge.rules["round_loss_credits"].source_id == "community_economy_references"


# ----------------------------------------------------------------- shots (#169)


def _ammo_bundle(readings: dict[int, tuple[int, int]], weapon: str | None = None,
                 spectating: tuple[int, int] | None = None) -> dict[str, Any]:
    t = Timeline(140)
    add_round(t, 1, 0, ally=0, enemy=0, won=False, death_at=45)
    add_round(t, 2, 66, ally=0, enemy=1, won=True)
    for second, (magazine, reserve) in readings.items():
        t.hud(second, second + 1, ammo_current=magazine, ammo_reserve=reserve)
        if weapon is not None:
            t.hud(second, second + 1, weapon=weapon)
    if spectating is not None:
        t.player(spectating[0], spectating[1], "ALIVE", "SPECTATOR")
    return t.bundle()


# R2 combat 86-126: a burst, a reload, a switch to the sidearm and two shots.
_AMMO = {90: (25, 50), 91: (25, 50), 92: (22, 50), 93: (22, 50), 95: (25, 47),
         96: (25, 47), 99: (12, 36), 100: (11, 36), 101: (10, 36)}


def _shots(result, round_no: int = 2) -> list[dict[str, Any]]:
    item = next(r for r in result.rounds if r.round_no == round_no)
    return [e for e in item.events if e["type"] == "shot"]


def test_shots_come_from_magazine_drops_and_exclude_reloads_and_switches():
    bundle = _ammo_bundle(_AMMO, weapon="ヴァンダル")
    result, report = augment(bundle, records(140, lambda s: (5, 5)))
    shots = _shots(result)
    assert [(s["time_sec"], s["attributes"]["first_shot"], s["attributes"]["rounds_fired"])
            for s in shots] == [(92.0, True, 3), (100.0, True, 1), (101.0, False, 1)]
    assert report.counts["ammo_reload"] == 1 and report.counts["ammo_weapon_switch"] == 1
    assert all(s["actor"] == "player" and s["event_id"].startswith("tl-shot-R2-") for s in shots)
    assert shots[0]["attributes"]["weapon"] == "Vandal"
    assert shots[0]["attributes"]["evidence_provenance"]["evidence_refs"] == ["ammo_current-ref"]
    facts = facts_of(result, 2)
    assert facts["first_shot_detected"] == [True, True, False]
    assert "first_shot_stationary" not in facts and "shot_while_moving" not in facts


def test_no_shot_outside_own_live_view_or_across_a_gap():
    readings = {90: (25, 50), 91: (20, 50), 100: (20, 50), 104: (18, 50)}
    result, _ = augment(_ammo_bundle(readings, spectating=(90, 92)), records(140, lambda s: (5, 5)))
    # 90->91 is in spectator view; 91->100 and 100->104 are too far apart.
    assert _shots(result) == []


def test_unread_or_low_confidence_ammo_gives_no_shot():
    bundle = _ammo_bundle({90: (25, 50), 91: (22, 50)})
    for second in (90, 91):
        for name in ("ammo_current", "ammo_reserve"):
            bundle["seconds"][second]["hud_observations"][name]["candidates"][0]["confidence"] = 0.5
    result, _ = augment(bundle, records(140, lambda s: (5, 5)))
    assert _shots(result) == []


def test_shots_are_checked_against_the_feature_magazine_readings():
    # Feature keyframes sit at second + 0.4; only the timeline reads ammo in this test.
    readings = {90: (25, 50), 92: (22, 50), 100: (20, 50), 101: (19, 50), 110: (9, 50),
                111: (8, 50)}

    def with_magazines(values: dict[int, int]) -> list[SecondRecord]:
        from dataclasses import replace

        out = records(140, lambda s: (5, 5))
        for second, magazine in values.items():
            # Agent unread on these keyframes: they cross-check but never fill.
            obs = replace(out[second].observation, viewed_score=0.1)
            out[second] = SecondRecord(obs, magazine, None, 0)
        return out

    feature_records = with_magazines({
        91: 25, 92: 22,          # a drop inside the shot's interval: agree
        98: 20, 99: 20, 102: 20,  # same count before and after 100-101: disagree
        109: 9, 110: 9,          # both before the shot read at 111, none after
    })
    result, report = augment(_ammo_bundle(readings), feature_records)
    checks = [s["attributes"]["feature_ammo_check"] for s in _shots(result)]
    assert checks == ["agree", "disagree", "undetermined"]
    assert report.checks["shot_vs_feature_ammo"] == {
        "agree": 1, "disagree": 1, "undetermined": 1
    }


def test_first_shot_frame_from_engagement_motion():
    from valorant_ai_coach.rules.engagement_motion import MotionFrame

    frames = [MotionFrame(91.0 + k / 60, 100, 80, 0.1, 0.1, 0.0, 0.0,
                          25 if k < 30 else 24) for k in range(60)]
    result = promote(_ammo_bundle(_AMMO))
    SecondFeaturePromoter().augment(_ammo_bundle(_AMMO), result, records(140, lambda s: (5, 5)),
                                    records_sha256=SHA, motion_frames=frames)
    first = _shots(result)[0]
    assert first["attributes"]["first_shot_frame_sec"] == round(91.0 + 30 / 60, 4)


def test_keyframe_ammo_fills_unread_timeline_seconds_in_the_recorders_hud_only():
    feature_records = records(140, lambda s: (5, 5))
    feature_records[91] = SecondRecord(feature_records[91].observation, 21, 50, 0)
    result, _ = augment(_ammo_bundle({90: (25, 50)}), feature_records)
    shot = _shots(result)[0]
    assert shot["attributes"]["ammo_sources"] == ["timeline", "features"]
    assert shot["attributes"]["feature_ammo_check"] == "feature_sourced"
    # Another agent's HUD (a teammate viewed while alive) never fills a reading.
    feature_records[91] = observation(91, agent="Jett")
    feature_records[91] = SecondRecord(feature_records[91].observation, 21, 50, 0)
    result, _ = augment(_ammo_bundle({90: (25, 50)}), feature_records)
    assert _shots(result) == []


def test_a_revive_needs_the_top_bar_to_explain_live_own_view_after_a_death():
    from valorant_ai_coach.facts.timeline_promotion import verify_promotion

    def revived_bundle() -> dict[str, Any]:
        t = Timeline(140)
        add_round(t, 1, 0, ally=0, enemy=0, won=False, death_at=45)
        add_round(t, 2, 66, ally=0, enemy=1, won=True)
        t.player(46, 52, "DEAD", "SPECTATOR")
        t.player(52, 60, "ALIVE", "SELF")  # own live view again, with HP
        t.hud(52, 60, hp="100")
        return t.bundle()

    def bar(rise: bool) -> Bar:
        def inner(second: int) -> tuple[int, int]:
            if 46 <= second < 51 or (not rise and 46 <= second < 66):
                return (4, 5)
            return (5, 5)
        return inner

    for rise, expected in ((True, "revived"), (False, "false")):
        bundle = revived_bundle()
        result, report = augment(bundle, records(140, bar(rise)))
        death = next(e for e in result.rounds[0].events if e["type"] == "player_death")
        assert death["attributes"]["revive_corroborated_by_top_bar"] is rise
        assert verify_promotion(bundle, result)["counts"]["player_death"].get(expected) == 1


def test_a_switch_read_with_the_reserve_missing_at_one_end_is_not_a_shot():
    # Marshal 5/11, a switch to the Classic 12/36, back to the Marshal with only the
    # magazine read: 12 -> 5 looks like seven shots without the weapon names or the
    # next reserve reading.
    readings = {90: (5, 11), 91: (12, 36), 93: (5, 11)}
    bundle = _ammo_bundle(readings)
    bundle["seconds"][92]["hud_observations"]["ammo_current"] = {
        "status": "CANDIDATES", "candidates": [
            {"value": 5, "confidence": 0.95, "evidence_ref": "ammo_current-ref"}]}
    result, report = augment(bundle, records(140, lambda s: (5, 5)))
    assert _shots(result) == []
    assert report.rejected["shot_reserve_changed"] == 1

    named = _ammo_bundle({91: (12, 36)})
    named["seconds"][92]["hud_observations"]["ammo_current"] = {
        "status": "CANDIDATES", "candidates": [
            {"value": 5, "confidence": 0.95, "evidence_ref": "ammo_current-ref"}]}
    for second, weapon in ((91, "クラシック"), (92, "マーシャル")):
        named["seconds"][second]["hud_observations"]["weapon"] = {
            "status": "CANDIDATES", "candidates": [
                {"value": weapon, "confidence": 0.93, "evidence_ref": "weapon-ref"}]}
    result, report = augment(named, records(140, lambda s: (5, 5)))
    assert _shots(result) == []
    assert report.rejected["shot_weapon_changed"] == 1


# ----------------------------------------------------------------- utility and engagement


def _utility_records(c_values: dict[int, float], x: float = 1.0) -> list[SecondRecord]:
    out = records(140, lambda s: (5, 5), charges=(1.0, 1.0, 0.0, x))
    for second, value in c_values.items():
        out[second] = observation(second, charges=(value, 1.0, 0.0, x))
    return out


def _uses(result, round_no: int = 2) -> list[dict[str, Any]]:
    item = next(r for r in result.rounds if r.round_no == round_no)
    return [e for e in item.events if e["type"] == "utility_used"]


def test_a_held_spent_slot_in_own_combat_is_a_utility_use_with_ultimate_state():
    # R2 combat 86-126: Sova's C slot is spent from 100 on and stays spent.
    spent = _utility_records({s: 0.0 for s in range(100, 140)})
    result, report = augment(_ammo_bundle({}), spent)
    uses = _uses(result)
    assert [(u["time_sec"], u["attributes"]["keybind_role"]) for u in uses] == [(100.0, "C")]
    assert uses[0]["attributes"]["ability"] == "Owl Drone"
    assert uses[0]["actor"] == "player" and uses[0]["event_id"].endswith("-C")
    facts = facts_of(result, 2)
    assert facts["ultimate_available"] == [True]
    assert report.counts["utility_used_ability"] == 1


def test_a_slot_that_comes_back_within_the_hold_is_not_a_use():
    flicker = {s: 0.0 for s in range(100, 104)}  # back at 104, inside the 8 s hold
    result, report = augment(_ammo_bundle({}), _utility_records(flicker))
    assert _uses(result) == []
    assert report.rejected["utility_use_not_held"] >= 1


def test_no_utility_use_in_the_buy_phase_or_in_another_agents_hud():
    # Spent from 70 (buy phase of R2, before the Round starts at 86): no use.
    early = _utility_records({s: 0.0 for s in range(70, 140)})
    result, _ = augment(_ammo_bundle({}), early)
    assert _uses(result) == []
    out = _utility_records({s: 0.0 for s in range(100, 140)})
    for second in range(98, 112):
        out[second] = observation(second, agent="Jett", charges=(0.0, 1.0, 0.0, 1.0))
    result, _ = augment(_ammo_bundle({}), out)
    assert _uses(result) == []


def test_each_first_shot_starts_an_engagement():
    result, report = augment(_ammo_bundle(_AMMO), records(140, lambda s: (5, 5)))
    item = next(r for r in result.rounds if r.round_no == 2)
    starts = [e for e in item.events if e["type"] == "engagement_start"]
    firsts = [s for s in _shots(result) if s["attributes"]["first_shot"]]
    assert [e["attributes"]["first_shot_event_id"] for e in starts] == [
        s["event_id"] for s in firsts
    ]
    assert all(e["actor"] == "player" for e in starts)
    assert report.counts["engagement_start_events"] == len(firsts) == 2
    # Nothing about the enemy or a peek is carried or derived from it.
    for start in starts:
        attributes = start["attributes"]
        assert attributes["observed"] == "recorder_started_firing"
        assert not {"visible_enemy_count", "allies_in_trade_range", "exposed_directions",
                    "enemy_spotted"} & set(attributes)
    keys = set(facts_of(result, 2))
    assert not {"preaim_lead_sec", "tradeable_ally_nearby", "exposed_directions_count",
                "enemy_spotted_count"} & keys



def test_a_utility_hold_is_traced_and_gaps_or_view_changes_reject_it():
    spent = _utility_records({s: 0.0 for s in range(100, 140)})
    result, _ = augment(_ammo_bundle({}), spent)
    use = _uses(result)[0]
    trace = use["attributes"]["hold_trace"]
    assert [e["sec"] for e in trace] == list(range(98, 109))
    assert {e["state"] for e in trace} == {"available", "spent"}
    assert use["attributes"]["missing_seconds"] == []
    assert len(use["attributes"]["evidence_provenance"]["evidence_refs"]) == 0  # no frame refs

    # Two missing readings in a row inside the hold: unproven.
    gappy = _utility_records({s: 0.0 for s in range(100, 140)})
    for second in (103, 104):
        gappy[second] = observation(second, bar=None, charges=(0.0, 1.0, 0.0, 1.0))
        gappy[second] = SecondRecord(
            replace(gappy[second].observation, hud_present=False), None, None, 0
        )
    result, report = augment(_ammo_bundle({}), gappy)
    assert _uses(result) == [] and report.rejected["utility_hold_missing_readings"] == 1

    # One missing reading is recorded, not filled.
    single = _utility_records({s: 0.0 for s in range(100, 140)})
    single[104] = SecondRecord(replace(single[104].observation, hud_present=False), None, None, 0)
    result, _ = augment(_ammo_bundle({}), single)
    assert _uses(result)[0]["attributes"]["missing_seconds"] == [104]

    # The recorder's view interrupted (drone, spectator) inside the hold: unproven.
    bundle = _ammo_bundle({})
    Timeline_seconds = bundle["seconds"]
    Timeline_seconds[105]["camera_state"] = {"value": "REMOTE", "status": "OBSERVED"}
    result, report = augment(bundle, _utility_records({s: 0.0 for s in range(100, 140)}))
    assert _uses(result) == [] and report.rejected["utility_hold_view_interrupted"] == 1
