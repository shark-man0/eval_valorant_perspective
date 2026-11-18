"""Knowledge-reader facts on Rounds confirmed by the shared timeline."""

from __future__ import annotations

import json
from collections.abc import Callable
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
from valorant_ai_coach.facts.second_feature_promotion import SecondFeaturePromoter
from valorant_ai_coach.facts.timeline_promotion import PromotionError, TimelinePromoter
from valorant_ai_coach.rules.development_readiness import FeedKill, Observation
from valorant_ai_coach.rules.second_series import SecondRecord

SHA = "a" * 64
Bar = Callable[[int], tuple[int, int] | None]


def observation(second: int, *, bar: tuple[int, int] | None = (5, 5), agent: str = "Sova",
                charges: tuple[float, float, float, float] = (1.0, 1.0, 0.0, 0.0),
                spike: bool = False, feed: tuple[FeedKill, ...] = ()) -> SecondRecord:
    return SecondRecord(
        observation=Observation(
            sec=second + 0.4, hud_present=True, viewed_agent=agent, viewed_score=0.9,
            charges=charges, ally_alive=None if bar is None else bar[0],
            enemy_alive=None if bar is None else bar[1], feed=feed,
            spike_carried=spike, spike_score=0.95 if spike else None,
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


def augment(bundle: dict[str, Any], feature_records: list[SecondRecord], sha: str = SHA):
    result = promote(bundle)
    report = SecondFeaturePromoter().augment(bundle, result, feature_records,
                                             records_sha256=sha)
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
