"""Shared timeline -> Round Package -> RoundAnalyzer -> Match view -> storage (#31/#25/#26)."""

from __future__ import annotations

import json
from copy import deepcopy
from fractions import Fraction
from pathlib import Path

import pytest

from valorant_ai_coach.application.match_aggregation_service import aggregate_saved_match
from valorant_ai_coach.application.timeline_evaluation import (
    TimelineEvaluationError,
    build_round_package,
    check_consistency,
    evaluate_timeline,
    main,
    persist_evaluation,
    segment_rounds,
)
from valorant_ai_coach.schema_validation import SchemaValidator
from valorant_ai_coach.storage import SQLiteRepository
from valorant_ai_coach.temporal.application import build_application_timeline
from valorant_ai_coach.temporal.evidence import digest, freeze_native_sample
from valorant_ai_coach.temporal.game import DevelopmentGameTimeline, observation

SOURCE_VIDEO = {"path": "private:synthetic", "fps": 1.0, "width": 1, "height": 1,
                "duration_sec": 40.0}


def _row(second: int, round_no: int | None, state: str = "ACTIVE") -> dict:
    return {
        "timestamp": second,
        "round_number": {"value": round_no, "status": "CANDIDATE" if round_no else "UNKNOWN"},
        "round_state": {"value": state},
        "life_state": {"value": "ALIVE" if round_no else "UNKNOWN"},
        "camera_state": {"value": "SELF" if round_no else "UNKNOWN"},
        "event_candidates": [],
    }


def bundle_from(numbers: list[int | None]) -> dict:
    seconds = [_row(i, n) for i, n in enumerate(numbers)]
    return {
        "version": "development_application_timeline_v1",
        "qualification": "development_only",
        "formal_outputs": 0,
        "source": {"source_id": "synthetic", "source_sha256": "a" * 64,
                   "physical_match_id": "physical"},
        "recording": {"end_timestamp": float(len(numbers))},
        "seconds": seconds,
        "events": {},
    }


def test_segmentation_keeps_gaps_as_missing_and_never_bridges_rounds():
    bundle = bundle_from([None, 1, 1, None, 1, 2, 2, None, None, 3])
    rounds, conflicts = segment_rounds(bundle)
    assert [(r.round_no, r.start_sec, r.end_sec) for r in rounds] == [
        (1, 1, 5), (2, 5, 7), (3, 9, 10)
    ]
    assert rounds[0].missing_intervals == ((3, 4),)
    assert rounds[0].completeness == 0.75
    assert conflicts == ()


def test_interleaved_round_numbers_never_produce_overlapping_rounds():
    rounds, conflicts = segment_rounds(bundle_from([1, 1, 2, 1, 2, 2]))
    assert [(r.round_no, r.start_sec, r.end_sec) for r in rounds] == [(1, 0, 2), (2, 4, 6)]
    assert conflicts[0] == {"code": "round_number_interleaved", "rounds": [1, 2],
                            "contested_seconds": [2, 4]}
    windows = sorted((r.start_sec, r.end_sec) for r in rounds)
    assert all(a[1] <= b[0] for a, b in zip(windows, windows[1:], strict=False))
    rounds, _ = segment_rounds(bundle_from([1, 2, 1, 2]))
    assert [(r.round_no, r.start_sec, r.end_sec) for r in rounds] == [(1, 0, 1), (2, 3, 4)]
    # A Round whose every second is contested disappears and is reported.
    rounds, conflicts = segment_rounds(bundle_from([1, 2, 1, 1]))
    assert [r.round_no for r in rounds] == [1]
    assert {"code": "round_dropped_after_trim", "rounds": [2]} in conflicts


def test_packages_are_schema_valid_provisional_and_fact_free():
    bundle = bundle_from([1, 1, 1, 2, 2])
    rounds, _ = segment_rounds(bundle)
    package = build_round_package(bundle, rounds[0], match_id="M-1", source_video=SOURCE_VIDEO)
    SchemaValidator().validate_round_package(package)
    lifecycle = package["round_lifecycle"]
    assert {lifecycle[k]["status"] for k in ("start", "end")} == {"provisional"}
    assert all(lifecycle[k]["formal_event_id"] is None for k in ("start", "end"))
    assert package["deterministic_facts"] == [] and package["events"] == []
    # Existing Practical contract: an uncertain denominator claims no completeness.
    assert package["observation_quality"]["timeline_completeness"] == 0.0


def test_full_path_withholds_scoring_and_all_views_agree(tmp_path: Path):
    bundle = bundle_from([None, 1, 1, 1, None, 2, 2, 2, 2, 3, 3])
    before = deepcopy(bundle)
    evaluation = evaluate_timeline(bundle, match_id="DEV-match", source_video=SOURCE_VIDEO)
    assert bundle == before
    assert {a.admission for a in evaluation.analyses} == {"provisional_withheld"}
    assert all(a.output["evaluations"] == [] for a in evaluation.analyses)
    aggregation = evaluation.aggregation
    assert [r["round_no"] for r in aggregation["rounds"]] == [1, 2, 3]
    assert aggregation["completeness"]["status"] != "verified_complete"
    assert evaluation.unsegmented_seconds == 2
    repository = SQLiteRepository(tmp_path / "app.db")
    stored = persist_evaluation(
        repository, evaluation, source_video_path=tmp_path / "video.mp4",
        source=bundle["source"],
    )
    assert repository.get_match("DEV-match")["status"] == "completed"
    # The GUI and JSON export read exactly this function.
    assert aggregate_saved_match(repository, "DEV-match")["rounds"] == stored["rounds"]
    assert stored["rounds"] == [
        {**row, "status": "not_evaluated",
         "failure": "Practical/unknownまたは不正な境界のため採点保留"}
        for row in stored["rounds"]
    ]
    problems = check_consistency(evaluation)
    assert problems == []


def test_consistency_detects_a_tampered_view():
    evaluation = evaluate_timeline(
        bundle_from([1, 1, 2, 2]), match_id="M-x", source_video=SOURCE_VIDEO
    )
    tampered = deepcopy(evaluation.aggregation)
    tampered["rounds"] = tampered["rounds"][:1]
    problems = check_consistency(evaluation, tampered)
    assert {"code": "stored_view_differs", "field": "rounds"} in problems


@pytest.mark.parametrize(
    "change",
    [
        lambda b: b.update(qualification="qualified"),
        lambda b: b.update(formal_outputs=1),
        lambda b: b.update(seconds=[]),
    ],
)
def test_rejects_anything_but_a_development_bundle(change):
    bundle = bundle_from([1, 1])
    change(bundle)
    with pytest.raises(TimelineEvaluationError):
        evaluate_timeline(bundle, match_id="M-1", source_video=SOURCE_VIDEO)


def test_fact_provider_output_outside_the_round_is_rejected():
    class Outside:
        def facts_for(self, bundle, round_):
            return [], [{"fact_id": "F", "key": "weapon", "value": "Vandal",
                         "time_sec": 99.0, "confidence": 0.9, "source": "hud",
                         "provenance_event_ids": []}]

    bundle = bundle_from([1, 1])
    rounds, _ = segment_rounds(bundle)
    with pytest.raises(TimelineEvaluationError):
        build_round_package(bundle, rounds[0], match_id="M", source_video=SOURCE_VIDEO,
                            fact_provider=Outside())


def _real_bundle() -> dict:
    """The actual timeline engine and application projection, not a hand-made bundle."""
    engine = DevelopmentGameTimeline()
    for tick, signals, score in [
        (51, ["buy", "owner_hud"], [0, 0]),
        (56, ["active", "owner_hud"], [0, 0]),
        (71, ["death", "spectator"], [0, 0]),
        (81, ["buy", "owner_hud"], [1, 0]),
        (86, ["active", "owner_hud"], [1, 0]),
    ]:
        sample = freeze_native_sample({
            "source_id": "synthetic", "source_sha256": "a" * 64, "acquisition_id": "e",
            "native_epoch": "e", "native_pts_tick": tick, "native_time_base": "1/10",
            "frame_size_px": [32, 32], "acquired_frame_sha256": digest([tick]),
            "native_pixel_sha256": digest([tick, 1]),
        })
        engine.add(observation(
            sample=sample, producer="b" * 64, signals=signals,
            raw={"view_hp": {"display": "100", "confidence": 0.96}},
            context={"score": score}, map_candidates=[{"zone": "unqualified"}],
        ))
    return build_application_timeline(
        engine.rebuild(), duration=Fraction(4), origin=Fraction(51, 10),
        source={"video_id": "synthetic", "source_sha256": "a" * 64,
                "physical_match_id": "physical"},
    )


def test_real_application_bundle_runs_through_cli(tmp_path: Path):
    bundle = _real_bundle()
    path = tmp_path / "timeline_PRIVATE.json"
    path.write_text(json.dumps(bundle), encoding="utf-8")
    out = tmp_path / "out"
    code = main(["evaluate", "--timeline", str(path), "--output", str(out),
                 "--match-id", "DEV-cli", "--database", str(tmp_path / "app.db")])
    report = json.loads((out / "match_evaluation_PRIVATE.json").read_text(encoding="utf-8"))
    assert code == 0 and report["consistency_problems"] == []
    assert report["formal_outputs"] == 0 and report["qualification"] == "development_only"
    assert report["rounds_segmented"] == len(report["round_timelines"])
    assert (out / "match_evaluation_PRIVATE.md").read_text(encoding="utf-8").startswith("# ")
    assert "a" * 64 not in (out / "match_evaluation_PRIVATE.json").read_text(encoding="utf-8")
    with pytest.raises(TimelineEvaluationError):  # never overwrite an output
        main(["evaluate", "--timeline", str(path), "--output", str(out), "--match-id", "DEV-2"])


# --------------------------------------------------------- 2026-11-17 review


def _fact(fact_id: str, time_sec: float) -> dict:
    return {"fact_id": fact_id, "key": "weapon", "value": "Vandal", "time_sec": time_sec,
            "confidence": 0.9, "source": "hud", "provenance_event_ids": []}


def test_boundary_second_belongs_to_exactly_one_round():
    class AtBoundary:
        def facts_for(self, bundle, round_):
            return [], [_fact(f"F{round_.round_no}", float(round_.end_sec))]

    bundle = bundle_from([1, 1, 2, 2])
    rounds, _ = segment_rounds(bundle)
    with pytest.raises(TimelineEvaluationError):  # end is exclusive
        build_round_package(bundle, rounds[0], match_id="DEV-x", source_video=SOURCE_VIDEO,
                            fact_provider=AtBoundary())

    class SameIdTwice:
        def facts_for(self, bundle, round_):
            return [], [_fact("F-shared", float(round_.start_sec))]

    with pytest.raises(TimelineEvaluationError):
        evaluate_timeline(bundle, match_id="DEV-x", source_video=SOURCE_VIDEO,
                          fact_provider=SameIdTwice())


def test_development_results_never_overwrite_formal_results(tmp_path: Path):
    repository = SQLiteRepository(tmp_path / "app.db")
    repository.create_match("DEV-formal", tmp_path / "v.mp4", metadata={"origin": "pipeline"},
                            status="completed")
    evaluation = evaluate_timeline(bundle_from([1, 1, 2]), match_id="DEV-formal",
                                   source_video=SOURCE_VIDEO)
    with pytest.raises(TimelineEvaluationError):
        persist_evaluation(repository, evaluation, source_video_path=tmp_path / "v.mp4",
                           source={})
    assert repository.get_match("DEV-formal")["metadata"] == {"origin": "pipeline"}
    plain = evaluate_timeline(bundle_from([1, 1]), match_id="M-1", source_video=SOURCE_VIDEO)
    with pytest.raises(TimelineEvaluationError):  # outside the DEV- namespace
        persist_evaluation(repository, plain, source_video_path=tmp_path / "v.mp4", source={})
    dev = evaluate_timeline(bundle_from([1, 1]), match_id="DEV-a", source_video=SOURCE_VIDEO)
    persist_evaluation(repository, dev, source_video_path=tmp_path / "v.mp4", source={})
    with pytest.raises(TimelineEvaluationError):  # re-run needs explicit replacement
        persist_evaluation(repository, dev, source_video_path=tmp_path / "v.mp4", source={})
    persist_evaluation(repository, dev, source_video_path=tmp_path / "v.mp4", source={},
                       replace_development=True)


def test_p0_derived_samples_reach_the_selector_but_never_a_score():
    from valorant_ai_coach.application.timeline_evaluation import DerivedSampleFactProvider

    samples = [
        {"sec": 1.0, "facts": {"player_role": "duelist", "utility_available_count": 2,
                               "ultimate_available": False, "player_died": False},
         "events": ["ability_state"]},
        {"sec": 2.0, "facts": {"player_died": True, "utility_available_count": 2},
         "events": ["player_death", "made_up_event"]},
        {"sec": 5.0, "facts": {"numbers_state": "even"}, "events": ["state_snapshot", "kill"]},
    ]
    provider = DerivedSampleFactProvider(samples)
    bundle = bundle_from([1, 1, 1, 1, 2, 2])
    evaluation = evaluate_timeline(bundle, match_id="DEV-p0", source_video=SOURCE_VIDEO,
                                   fact_provider=provider)
    first, second = evaluation.packages
    assert {e["type"] for e in first["events"]} == {"ability_state", "player_death"}
    assert {e["type"] for e in second["events"]} == {"state_snapshot", "kill"}
    assert all(f["confidence"] == 0.0 for p in evaluation.packages
               for f in p["deterministic_facts"])
    assert provider.unsupported_events == {"made_up_event": 1}
    assert evaluation.rule_candidates[0]  # the production selector saw candidates
    assert all(a.output["evaluations"] == [] for a in evaluation.analyses)
    assert check_consistency(evaluation) == []
