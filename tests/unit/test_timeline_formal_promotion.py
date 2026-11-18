"""Formal promotion of shared-timeline candidates (#16/#20/#21/#32/#138)."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from valorant_ai_coach.application.match_aggregation_service import aggregate_saved_match
from valorant_ai_coach.application.timeline_evaluation import (
    check_consistency,
    evaluate_timeline,
    main,
    persist_evaluation,
    segment_rounds,
)
from valorant_ai_coach.facts.timeline_promotion import (
    FORMAL_QUALIFICATION,
    PromotionError,
    PromotionPolicy,
    TimelinePromoter,
    timeline_view_from_replay,
    verify_promotion,
)
from valorant_ai_coach.rules.policy_runtime import enforce_confidence_floor
from valorant_ai_coach.schema_validation import SchemaValidator
from valorant_ai_coach.storage import SQLiteRepository

SOURCE_VIDEO = {"path": "private:synthetic", "fps": 1.0, "width": 1, "height": 1,
                "duration_sec": 400.0}


# ------------------------------------------------------------------ fixtures


def _state(value: str, status: str = "OBSERVED") -> dict[str, Any]:
    return {"value": value, "status": status, "evidence_refs": []}


def _hud(**values: Any) -> dict[str, Any]:
    return {
        key: {"status": "CANDIDATE",
              "candidates": [{"value": value, "confidence": 0.97, "evidence_ref": f"{key}-ref"}]}
        for key, value in values.items()
    }


class Timeline:
    """Builder for a synthetic application bundle with per-second states."""

    def __init__(self, length: int) -> None:
        self.rows = [
            {
                "timestamp": i,
                "observation_present": True,
                "round_state": _state("UNKNOWN", "UNKNOWN"),
                "round_number": {"value": None, "status": "UNKNOWN", "candidates": []},
                "life_state": _state("UNKNOWN", "UNKNOWN"),
                "camera_state": _state("UNKNOWN", "UNKNOWN"),
                "hud_observations": {},
                "event_candidates": [],
                "evidence_refs": [f"obs-{i}"],
            }
            for i in range(length)
        ]
        self.events: dict[str, dict[str, Any]] = {}

    def phase(self, low: int, high: int, value: str, round_no: int | None,
              status: str = "OBSERVED") -> Timeline:
        for row in self.rows[low:high]:
            row["round_state"] = _state(value, status)
            if round_no is not None:
                row["round_number"] = {"value": round_no, "status": "CANDIDATE",
                                       "candidates": [round_no]}
        return self

    def player(self, low: int, high: int, life: str, camera: str,
               status: str = "OBSERVED") -> Timeline:
        for row in self.rows[low:high]:
            row["life_state"] = _state(life, status if life != "UNKNOWN" else "UNKNOWN")
            row["camera_state"] = _state(camera, status if camera != "UNKNOWN" else "UNKNOWN")
        return self

    def hud(self, low: int, high: int, **values: Any) -> Timeline:
        for row in self.rows[low:high]:
            row["hud_observations"].update(_hud(**values))
        return self

    def transition(self, kind: str, lower: float, upper: float, before: str | None,
                   after: str | None, members: list[int]) -> Timeline:
        event_id = f"{kind}-{lower}-{upper}"
        self.events[event_id] = {
            "kind": kind, "status": "CANDIDATE", "lower_timestamp": lower,
            "upper_timestamp": upper,
            "native_transition": {"before": before, "after": after},
            "round_membership": {"candidates": members, "status": "CANDIDATE"},
            "evidence_refs": [f"ev-{event_id}"], "qualified": False,
        }
        for second in range(int(lower), int(upper) + 1):
            self.rows[second]["event_candidates"].append(event_id)
        return self

    def bundle(self) -> dict[str, Any]:
        return {
            "version": "development_application_timeline_v1",
            "qualification": "development_only",
            "formal_outputs": 0,
            "source": {"source_id": "synthetic", "source_sha256": "a" * 64,
                       "physical_match_id": "physical"},
            "recording": {"end_timestamp": float(len(self.rows))},
            "seconds": self.rows,
            "events": self.events,
        }


def add_round(t: Timeline, round_no: int, base: int, *, ally: int, enemy: int,
              won: bool, death_at: int | None = None) -> None:
    """Buy 20 s, combat 40 s, ENDED 6 s, all observed, starting at ``base``."""
    start, end = base + 20, base + 60
    t.phase(base, start, "BUY", round_no).phase(start, end, "ACTIVE", round_no)
    t.phase(end, end + 6, "ENDED", None)
    t.player(base, end if death_at is None else death_at, "ALIVE", "SELF")
    t.hud(base, end + 6, ally_score=str(ally), enemy_score=str(enemy))
    t.hud(base, start, hp="100", armor="50", weapon="ヴァンダル")
    t.hud(start, start + 5, timer="1:39", hp="100", armor="50", weapon="ヴァンダル")
    after = (ally + 1, enemy) if won else (ally, enemy + 1)
    t.hud(end + 1, end + 6, ally_score=str(after[0]), enemy_score=str(after[1]))
    t.transition("round_start", start - 1, start, "BUY", "ACTIVE", [round_no])
    t.transition("round_end", end - 1, end, "ACTIVE", "ENDED", [round_no])
    if death_at is not None:
        t.player(death_at, death_at + 1, "UNKNOWN", "UNKNOWN")
        t.player(death_at + 1, end, "UNKNOWN", "SPECTATOR")
        t.transition("spectator", death_at, death_at + 1, "SELF", "SPECTATOR", [round_no])


def two_rounds() -> dict[str, Any]:
    t = Timeline(140)
    add_round(t, 1, 0, ally=0, enemy=0, won=False, death_at=45)
    add_round(t, 2, 66, ally=0, enemy=1, won=True)
    return t.bundle()


def promote(bundle: dict[str, Any]):
    rounds, _ = segment_rounds(bundle)
    return TimelinePromoter().promote(
        bundle, [(r.round_no, r.start_sec, r.end_sec) for r in rounds]
    )


# ----------------------------------------------------------------- promotion


def test_clean_rounds_are_promoted_with_evidence_and_valid_events():
    result = promote(two_rounds())
    first, second = result.rounds
    assert first.confirmed and second.confirmed
    assert (first.start.time_sec, first.end.time_sec) == (20, 60)
    assert first.window == (0, 66) and second.window[0] == 66
    kinds = sorted({e["type"] for e in first.events})
    assert kinds == ["buy_phase", "player_death", "round_end", "round_start", "state_snapshot"]
    death = next(e for e in first.events if e["type"] == "player_death")
    assert death["time_sec"] == 46.0 and death["actor"] == "player"
    for event in first.events:
        attributes = event["attributes"]
        assert attributes["qualification"] == FORMAL_QUALIFICATION
        assert attributes["evidence_provenance"]["source"] == "shared_timeline"
        assert event["event_id"].startswith("tl-")
    assert first.round_meta == {"round_result": "loss", "score_before": {"ally": 0, "enemy": 0}}
    assert second.round_meta["round_result"] == "win"
    snapshot = first.snapshots[0]
    assert snapshot["weapon"] == "Vandal"  # resolved by the shared game knowledge (#96)
    assert snapshot["hp"] == 100 and set(snapshot["source_confidence"]) <= {
        "weapon", "round_time_remaining_sec", "score_ally", "score_enemy"
    }
    report = result.report()
    assert report["rounds_confirmed"] == 2 and report["formal_events"] > 0


def test_inferred_flicker_inside_buy_phase_is_not_a_round_start():
    t = Timeline(80)
    add_round(t, 1, 0, ally=0, enemy=0, won=True)
    t.phase(10, 11, "ACTIVE", None, status="INFERRED").phase(11, 12, "BUY", 1)
    t.transition("round_start", 9, 10, "BUY", "ACTIVE", [1])
    result = promote(t.bundle())
    # Two candidates more than 3 s apart -> competing evidence; or the flicker is
    # rejected outright. Either way nothing is promoted at 10 s.
    item = result.rounds[0]
    assert item.start is None or item.start.time_sec == 20
    assert item.rejected.get("round_start_phase_not_corroborated", 0) + item.abstentions.get(
        "round_start_competing_candidates", 0
    ) >= 1


def test_round_start_without_observed_buy_phase_abstains_and_stays_provisional():
    t = Timeline(80)
    add_round(t, 1, 0, ally=0, enemy=0, won=True)
    t.phase(0, 20, "UNKNOWN", None, status="UNKNOWN")
    del t.events["round_start-19-20"]
    for row in t.rows:
        row["event_candidates"] = [e for e in row["event_candidates"] if e in t.events]
    bundle = t.bundle()
    result = promote(bundle)
    assert result.rounds[0].start is None and not result.rounds[0].confirmed
    evaluation = evaluate_timeline(bundle, match_id="DEV-a", source_video=SOURCE_VIDEO,
                                   promoter=TimelinePromoter())
    assert evaluation.analyses[0].admission == "provisional_withheld"
    lifecycle = evaluation.packages[0]["round_lifecycle"]
    assert lifecycle["start"]["status"] == "provisional"


def test_observed_state_pair_is_used_only_when_no_transition_exists():
    t = Timeline(80)
    add_round(t, 1, 0, ally=0, enemy=0, won=True)
    del t.events["round_start-19-20"]
    for row in t.rows:
        row["event_candidates"] = [e for e in row["event_candidates"] if e in t.events]
    t.phase(19, 21, "UNKNOWN", None, status="UNKNOWN")
    result = promote(t.bundle())
    start = result.rounds[0].start
    assert start is not None and start.time_sec == 21
    assert start.basis == "shared_timeline_observed_state_pair_buy_to_active"
    # Too wide a gap between the observed phases -> abstain.
    t.phase(12, 21, "UNKNOWN", None, status="UNKNOWN")
    assert promote(t.bundle()).rounds[0].start is None


def test_brief_spectator_view_returning_to_self_is_not_a_death():
    t = Timeline(80)
    add_round(t, 1, 0, ally=0, enemy=0, won=True)
    t.player(40, 41, "UNKNOWN", "SPECTATOR").player(41, 60, "ALIVE", "SELF")
    t.transition("spectator", 39, 40, "SELF", "SPECTATOR", [1])
    item = promote(t.bundle()).rounds[0]
    assert not [e for e in item.events if e["type"] == "player_death"]
    assert item.rejected["player_death_life_not_corroborated"] == 1


def test_snapshot_score_must_match_the_round_number_and_unknown_weapons_are_rejected():
    t = Timeline(80)
    add_round(t, 1, 0, ally=0, enemy=0, won=True)
    t.hud(30, 35, ally_score="3", enemy_score="1", weapon="存在しない武器")
    item = promote(t.bundle()).rounds[0]
    assert item.rejected["snapshot_score_inconsistent_with_round"] >= 1
    assert item.rejected["snapshot_weapon_unmapped"] >= 1
    assert all(s["score_ally"] in {None, 0} for s in item.snapshots)


def test_round_search_never_reaches_into_an_earlier_unconfirmed_round():
    t = Timeline(140)
    add_round(t, 1, 0, ally=0, enemy=0, won=False)
    add_round(t, 2, 66, ally=0, enemy=1, won=True)
    # R1 loses its end; R2's start search must still begin after R1's segment.
    del t.events["round_end-59-60"]
    t.phase(60, 66, "UNKNOWN", None, status="UNKNOWN")
    for row in t.rows:
        row["event_candidates"] = [e for e in row["event_candidates"] if e in t.events]
    t.transition("round_start", 19, 20, "BUY", "ACTIVE", [1, 2])
    result = promote(t.bundle())
    assert result.rounds[1].start is not None and result.rounds[1].start.time_sec == 86


def test_policy_rejects_invalid_confidence(tmp_path: Path):
    raw = json.loads(Path("config/timeline_promotion_v1.json").read_text(encoding="utf-8"))
    raw["player_death"]["confidence"] = 1.5
    path = tmp_path / "policy.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(PromotionError):
        PromotionPolicy.load(path)


# -------------------------------------------------------------- evaluation path


def test_confirmed_rounds_reach_scoring_storage_and_agree_with_the_stored_view(
    tmp_path: Path,
):
    bundle = two_rounds()
    before = deepcopy(bundle)
    evaluation = evaluate_timeline(bundle, match_id="DEV-promoted", source_video=SOURCE_VIDEO,
                                   promoter=TimelinePromoter())
    assert bundle == before
    assert {a.admission for a in evaluation.analyses} == {"confirmed"}
    for package in evaluation.packages:
        SchemaValidator().validate_round_package(package)
        assert package["round_lifecycle"]["start"]["status"] == "confirmed"
        assert package["round_lifecycle"]["start"]["formal_event_id"].startswith("tl-round_start")
        assert package["observation_quality"]["timeline_completeness"] == 1.0
    facts = evaluation.analyses[0].round_package["deterministic_facts"]
    assert {"buy_phase_observed", "player_died"} <= {f["key"] for f in facts}
    evaluations = [e for a in evaluation.analyses for e in a.output["evaluations"]]
    # Rules triggered by the formal events with facts that are not observable yet are
    # explicit UNSCORED with their missing facts, not "no evaluation".
    assert evaluations and {e["label"] for e in evaluations} == {"unscored"}
    assert all(e["missing_information"] for e in evaluations)
    repository = SQLiteRepository(tmp_path / "app.db")
    stored = persist_evaluation(repository, evaluation, source_video_path=tmp_path / "v.mp4",
                                source=bundle["source"])
    assert check_consistency(evaluation, stored) == []
    assert aggregate_saved_match(repository, "DEV-promoted")["rules"] == (
        evaluation.aggregation["rules"]
    )


def test_confidence_floor_is_shared_and_idempotent():
    item = {"label": "good", "confidence": 0.5, "clip_id": "c", "display_clip": {},
            "improvement": None, "missing_information": [], "unscored_reason_code": None}
    once = enforce_confidence_floor(item)
    assert once["label"] == "unscored" and once["unscored_reason_code"] == "low_confidence"
    assert enforce_confidence_floor(once) == once
    assert item["label"] == "good"


def test_cli_writes_the_promotion_report_and_independent_checks(tmp_path: Path):
    path = tmp_path / "timeline.json"
    path.write_text(json.dumps(two_rounds()), encoding="utf-8")
    out = tmp_path / "out"
    assert main(["evaluate", "--timeline", str(path), "--output", str(out),
                 "--match-id", "DEV-cli", "--database", str(tmp_path / "a.db")]) == 0
    report = json.loads((out / "match_evaluation_PRIVATE.json").read_text(encoding="utf-8"))
    assert report["formal_input_counts"]["rounds_confirmed"] == 2
    assert report["formal_input_counts"]["formal_events"] > 0
    tiers = report["result_tiers"]
    promoted = tiers["promoted_from_shared_timeline"]
    assert promoted["events"] == promoted["events_labelled"] == (
        report["formal_input_counts"]["formal_events"]
    )
    assert tiers["independently_qualified"] == {"events": 0, "facts": 0}
    checks = report["independent_signal_checks"]["counts"]
    assert checks["round_start"] == {"correct": 2}
    assert checks["round_result"] == {"correct": 1, "undetermined": 1}
    assert checks["player_death"] == {"correct": 1}
    out2 = tmp_path / "out2"
    assert main(["evaluate", "--timeline", str(path), "--output", str(out2),
                 "--match-id", "DEV-cli2", "--no-promotion"]) == 0
    report = json.loads((out2 / "match_evaluation_PRIVATE.json").read_text(encoding="utf-8"))
    assert report["formal_promotion"] is None
    assert report["formal_input_counts"]["formal_events"] == 0


def test_independent_check_flags_a_promoted_start_inside_the_buy_phase():
    bundle = two_rounds()
    result = promote(bundle)
    for row in bundle["seconds"][20:25]:
        row["hud_observations"]["timer"]["candidates"][0]["value"] = "0:12"
    counts = verify_promotion(bundle, result)["counts"]
    assert counts["round_start"]["false"] == 1


# ---------------------------------------------------------------- replay input


def _sample(tick: int) -> dict[str, Any]:
    return {"source_id": "s", "source_sha256": "b" * 64, "acquisition_id": "a",
            "native_epoch": "a", "native_pts_tick": tick, "native_time_base": "1/10",
            "sample_sha256": f"{tick:064d}"}


def test_replay_projection_bins_engine_states_without_hud_values():
    states = []
    for second in range(30):
        phase = "BUY" if second < 10 else "ACTIVE" if second < 25 else "ENDED"
        estimate = {"value": phase, "hypotheses": [phase],
                    "reason": "current_observation", "evidence_ids": [f"e{second}"],
                    "origin": "observation_projection", "uncertainty": "x"}
        states.append({
            "sample": _sample(second * 10),
            "round": estimate,
            "round_number": {"value": 1, "candidates": [1], "status": "CANDIDATE",
                             "phase": phase, "evidence_ids": [], "unknown_possible": False},
            "life": {**estimate, "value": "ALIVE", "hypotheses": ["ALIVE"]},
            "camera": {**estimate, "value": "SELF", "hypotheses": ["SELF"]},
            "observation_ids": [f"o{second}"],
        })
    replay = {"formal_outputs": 0, "native_states": states, "events": [
        {"kind": "round_start", "lower_sample": _sample(90), "lower_timestamp": 9.0,
         "upper_timestamp": 10.0, "endpoint_states": [{"round": "BUY"}, {"round": "ACTIVE"}],
         "round_membership": {"candidates": [1], "status": "CANDIDATE"}},
    ]}
    bundle = timeline_view_from_replay(replay)
    assert bundle["projection"] == "replay_events_and_states_without_hud_values"
    assert len(bundle["seconds"]) == 30
    assert bundle["seconds"][12]["round_state"]["value"] == "ACTIVE"
    event = next(iter(bundle["events"].values()))
    assert event["native_transition"] == {"before": "BUY", "after": "ACTIVE"}
    with pytest.raises(PromotionError):
        timeline_view_from_replay({**replay, "formal_outputs": 1})
