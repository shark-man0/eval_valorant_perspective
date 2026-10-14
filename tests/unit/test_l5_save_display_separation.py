"""L-5 contract: canonical persistence, UI exemplars and clip budgets are distinct.

Synthetic dictionaries only. No footage, remote API, or quality labels are invented.
"""
from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace
from typing import Any

import pytest

from valorant_ai_coach.application.pipeline import MatchAnalysisPipeline
from valorant_ai_coach.non_video.features import NonVideoFeatures
from valorant_ai_coach.rules import EvaluationAggregator
from valorant_ai_coach.storage import SQLiteRepository
from valorant_ai_coach.ui.backend import BackendFacade


def aggregator(*, display_limit: int = 3) -> EvaluationAggregator:
    return EvaluationAggregator(
        {"rules": [
            {"id": "AIM-02", "aggregation_policy": {
                "deduplicate_same_rule_within_seconds": 35,
                "max_display_exemplars_per_match": display_limit,
            }},
            {"id": "MOV-01", "aggregation_policy": {
                "deduplicate_same_rule_within_seconds": 35,
                "max_display_exemplars_per_match": display_limit,
            }},
        ]},
        {"dedup_groups": {}},
    )


def evaluation(
    identity: str, label: str, start: float, confidence: float = 0.9,
    *, rule: str = "AIM-02",
) -> dict[str, Any]:
    scored = label in {"good", "improve"}
    return {
        "evaluation_id": identity,
        "clip_id": f"clip-{identity}" if scored else None,
        "primary_rule_id": rule,
        "related_rule_ids": [],
        "label": label,
        "decision_source": "hybrid",
        "confidence": confidence,
        "fact_refs": [f"F-{identity}"],
        "evidence_range": {"start_sec": start, "end_sec": start + 1},
        "display_clip": {"start_sec": max(0, start - 3), "end_sec": start + 4}
        if scored else None,
        "evidence": [],
        "missing_information": [] if scored else ["情報不足"],
        "unscored_reason_code": None if scored else "missing_required_fact",
        "improvement": "改善" if label == "improve" else None,
    }


def aggregate_rounds(
    *rounds: tuple[int, list[dict[str, Any]]],
    instance: EvaluationAggregator | None = None,
) -> dict[int, list[dict[str, Any]]]:
    pipeline = MatchAnalysisPipeline.__new__(MatchAnalysisPipeline)
    pipeline.aggregator = instance or aggregator()
    inputs = [
        SimpleNamespace(output={"round_no": number, "evaluations": deepcopy(items)})
        for number, items in rounds
    ]
    return pipeline._aggregate_round_evaluations(inputs)


def store(
    repository: SQLiteRepository, by_round: dict[int, list[dict[str, Any]]]
) -> None:
    repository.create_match("M-L5", "synthetic.mp4", status="completed")
    for number, values in by_round.items():
        repository.save_analysis_result(
            {"match_id": "M-L5", "round_no": number, "evaluations": values}
        )


def test_later_improve_survives_canonical_store_and_preempts_ui_sample(tmp_path: Any) -> None:
    items = [
        evaluation("g1", "good", 100),
        evaluation("g2", "good", 300),
        evaluation("g3", "good", 500),
        evaluation("i1", "improve", 700, 0.95),
    ]
    complete = aggregate_rounds((1, items))
    repo = SQLiteRepository(tmp_path / "store.db")
    store(repo, complete)
    saved = repo.get_match_result("M-L5")
    assert saved is not None
    assert len(saved["evaluations"]) == 4
    assert saved["good_count"] == 3 and saved["improve_count"] == 1
    visible = aggregator().select_display_exemplars(saved["evaluations"])
    assert len(visible) == 3
    assert [item["evaluation_id"] for item in visible] == ["g1", "g2", "i1"]
    assert NonVideoFeatures(repo).report("M-L5")["counts"]["improve"] == 1


def test_d1b_weak_good_is_unscored_without_hiding_three_strong_items() -> None:
    values = [
        evaluation("weak", "good", 100, 0.5),
        evaluation("g1", "good", 300),
        evaluation("g2", "good", 500),
        evaluation("i1", "improve", 700),
    ]
    complete = aggregate_rounds((1, values))[1]
    assert len(complete) == 4
    assert complete[0]["label"] == "unscored"
    assert complete[0]["clip_id"] is None
    shown = aggregator().select_display_exemplars(complete)
    assert {item["evaluation_id"] for item in shown} == {"g1", "g2", "i1"}
    assert len(shown) == 3


def test_unscored_full_display_budget_is_not_a_storage_budget() -> None:
    items = [evaluation(f"u{i}", "unscored", i * 100 + 100) for i in range(4)]
    items.append(evaluation("strong", "improve", 700))
    complete = aggregator().aggregate(items)
    displayed = aggregator().select_display_exemplars(complete)
    assert len(complete) == 5
    assert len(displayed) == 3
    assert "strong" in {item["evaluation_id"] for item in displayed}


def test_all_labels_are_counted_from_full_set(tmp_path: Any) -> None:
    values = [
        evaluation("g", "good", 100),
        evaluation("i", "improve", 300),
        evaluation("u1", "unscored", 500),
        evaluation("u2", "unscored", 700),
    ]
    by_round = aggregate_rounds((1, values))
    repo = SQLiteRepository(tmp_path / "data.db")
    store(repo, by_round)
    result = repo.get_match_result("M-L5")
    assert result is not None
    assert (result["good_count"], result["improve_count"], result["unscored_count"]) == (1, 1, 2)
    assert len(aggregator(display_limit=2).select_display_exemplars(result["evaluations"])) == 2


def test_duplicate_same_label_merges_references_and_preserves_weakest_confidence() -> None:
    early = evaluation("early", "good", 100, 0.8)
    strong = evaluation("strong", "good", 105, 0.95)
    merged = aggregator().aggregate([early, strong])
    assert len(merged) == 1
    assert merged[0]["evaluation_id"] == "strong"
    assert merged[0]["confidence"] == pytest.approx(0.8)
    assert set(merged[0]["fact_refs"]) == {"F-early", "F-strong"}


def test_cross_round_evaluations_do_not_deduplicate(tmp_path: Any) -> None:
    by_round = aggregate_rounds(
        (1, [evaluation("one", "good", 100)]),
        (2, [evaluation("two", "good", 100)]),
    )
    assert {number: len(items) for number, items in by_round.items()} == {1: 1, 2: 1}
    repo = SQLiteRepository(tmp_path / "app.db")
    store(repo, by_round)
    assert len(repo.list_evaluations("M-L5")) == 2


def test_persisted_counts_survive_repository_reopen(tmp_path: Any) -> None:
    path = tmp_path / "persisted.db"
    repo = SQLiteRepository(path)
    full = aggregate_rounds((1, [
        evaluation(f"e{i}", "good", 100 * (i + 1)) for i in range(5)
    ]))
    store(repo, full)
    reloaded = SQLiteRepository(path)
    assert reloaded.schema_version == repo.schema_version == 1
    assert len(reloaded.list_evaluations("M-L5")) == 5
    assert len(aggregator().select_display_exemplars(reloaded.list_evaluations("M-L5"))) == 3


def test_ui_view_reports_complete_counts_and_limited_cards(tmp_path: Any) -> None:
    repo = SQLiteRepository(tmp_path / "ui.db")
    store(repo, aggregate_rounds((1, [
        evaluation(f"e{i}", "good", 100 * (i + 1)) for i in range(5)
    ])))
    backend = BackendFacade.__new__(BackendFacade)
    backend.services = SimpleNamespace(
        repository=repo,
        pipeline=SimpleNamespace(aggregator=aggregator()),
    )
    backend._rule_category = {"AIM-02": "Aim"}
    backend._round_context = {"AIM-02": False}
    view = backend.get_match_result("M-L5")
    assert len(view.evaluations) == view.good_count == 5
    assert len(view.display_evaluations) == 3
    assert set(x.evaluation_id for x in view.display_evaluations) <= {
        x.evaluation_id for x in view.evaluations
    }


def test_clip_budget_is_independent_of_display_budget() -> None:
    instance = aggregator(display_limit=1)
    full = instance.aggregate([
        evaluation(f"e{i}", "improve" if i == 3 else "good", 100 * (i + 1))
        for i in range(4)
    ])
    shown = instance.select_display_exemplars(full)
    clips = instance.select_clip_exemplars(full, max_clips_per_rule=2)
    assert len(full) == 4 and len(shown) == 1 and len(clips) == 2
    assert "e3" in [item["evaluation_id"] for item in clips]
    assert len(instance.select_clip_exemplars(full, max_clips_per_rule=0)) == 0
    with pytest.raises(ValueError):
        instance.select_clip_exemplars(full, max_clips_per_rule=-1)


def test_old_truncated_storage_remains_readable_without_invented_records(tmp_path: Any) -> None:
    repo = SQLiteRepository(tmp_path / "legacy.db")
    # Simulate a v1 database where an older aggregator already dropped a later IMPROVE.
    store(repo, {1: [
        evaluation("g1", "good", 100),
        evaluation("g2", "good", 300),
        evaluation("g3", "good", 500),
    ]})
    result = SQLiteRepository(tmp_path / "legacy.db").get_match_result("M-L5")
    assert result is not None
    assert result["good_count"] == 3 and result["improve_count"] == 0
    assert len(result["evaluations"]) == 3


def test_empty_aggregate_and_practical_unscored_round() -> None:
    instance = aggregator()
    assert instance.aggregate([]) == []
    assert instance.select_display_exemplars([]) == []
    assert instance.select_clip_exemplars([]) == []
    assert aggregate_rounds((1, []))[1] == []


def test_display_selection_does_not_mutate_canonical_records() -> None:
    instance = aggregator(display_limit=1)
    full = [evaluation("g", "good", 100), evaluation("i", "improve", 200)]
    previous = deepcopy(full)
    selected = instance.select_display_exemplars(full)
    assert full == previous
    assert selected[0]["evaluation_id"] == "i"
    selected[0]["confidence"] = 0.1
    assert full == previous
