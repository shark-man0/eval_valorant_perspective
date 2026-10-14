"""Regression tests for SQLite -> MatchAggregator -> GUI and JSON report.

Only repository synthetic Round Packages and MockAnalyzer are used; no real videos/API.
"""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from match_fixtures import MATCH, analysis_for
from test_practical_evaluation_integration import uncertain_package

from valorant_ai_coach.application.match_aggregation import (
    MatchAggregationError,
    MatchAggregator,
    RoundInput,
)
from valorant_ai_coach.application.match_aggregation_service import aggregate_saved_match
from valorant_ai_coach.application.pipeline import MatchAnalysisPipeline
from valorant_ai_coach.non_video.features import NonVideoFeatures
from valorant_ai_coach.storage import SQLiteRepository
from valorant_ai_coach.ui.backend import BackendFacade
from valorant_ai_coach.ui.view_model import format_match_summary


def saved(
    tmp_path: Path, cases: tuple[str, ...] = ("TC-006", "TC-017", "TC-026")
) -> tuple[SQLiteRepository, list[Any]]:
    repo = SQLiteRepository(tmp_path / "app.db")
    analyses = [analysis_for(case, round_no=i) for i, case in enumerate(cases, start=1)]
    repo.create_match(MATCH, "synthetic.mp4", status="completed")
    for item in analyses:
        repo.save_round_package(item.round_package)
        repo.save_analysis_result(item.output)
    repo.save_job_checkpoint(
        MATCH, "completed", {
            "completed_rounds": list(range(1, len(analyses) + 1)),
            "failed_rounds": [],
            "canonical_evaluation_set": "full_post_dedup_v1",
        }
    )
    return repo, analyses


def test_stored_match_has_exactly_the_live_evaluation_records(tmp_path: Path) -> None:
    repo, analyses = saved(tmp_path)
    live = MatchAggregator().aggregate([RoundInput.from_round_analysis(x) for x in analyses])
    restored = aggregate_saved_match(repo, MATCH)
    expected = [(x.evaluation_id, x.label, x.confidence) for x in live.evaluations]
    actual = [(x["evaluation_id"], x["label"], x["confidence"])
              for x in restored["evaluations"]]
    assert actual == expected
    assert len(restored["rounds"]) == 3
    assert restored["completeness"]["status"] == "unverifiable"
    assert restored["counting_basis"] == "evaluation_records_as_supplied"
    assert restored["storage_provenance"]["saved_evaluation_set"] == "full_post_dedup_v1"


def test_rule_counts_and_fact_event_provenance_round_trip(tmp_path: Path) -> None:
    repo, _ = saved(tmp_path)
    summary = aggregate_saved_match(repo, MATCH)
    expected = {rule["rule_id"]: rule["counts"] for rule in summary["rules"]}
    assert sum(sum(count.values()) for count in expected.values()) == len(
        summary["evaluations"]
    )
    for item in summary["evaluations"]:
        for fact in item["facts"]:
            assert fact["resolved"] is True
            assert isinstance(fact["provenance_event_ids"], list)


def test_reopen_is_deterministic_and_never_marks_unknown_expected_complete(
    tmp_path: Path,
) -> None:
    repo, _ = saved(tmp_path)
    first = aggregate_saved_match(repo, MATCH)
    reopened = aggregate_saved_match(SQLiteRepository(repo.path), MATCH)
    assert json.dumps(first, sort_keys=True) == json.dumps(reopened, sort_keys=True)
    assert reopened["completeness"]["expected_round_numbers"] is None
    assert reopened["completeness"]["status"] != "verified_complete"


def test_legacy_v1_keeps_existing_rows_but_does_not_invent_more(tmp_path: Path) -> None:
    repo, _ = saved(tmp_path, ("TC-006",))
    repo.save_job_checkpoint(MATCH, "completed", {"completed_rounds": [1]})
    old = aggregate_saved_match(repo, MATCH)
    assert len(old["evaluations"]) == len(repo.list_round_evaluations(MATCH, 1))
    assert old["storage_provenance"]["saved_evaluation_set"] == "legacy_or_unverified"


def test_no_completion_checkpoint_with_zero_rows_is_not_evaluated(tmp_path: Path) -> None:
    repo, analyses = saved(tmp_path, ("TC-006",))
    repo.save_analysis_result({**analyses[0].output, "evaluations": []})
    repo.save_job_checkpoint(MATCH, "analyzing", {})
    view = aggregate_saved_match(repo, MATCH)
    assert view["completeness"]["rounds_not_evaluated"] == [1]
    assert view["completeness"]["status"] == "incomplete"


def test_completed_round_can_legitimately_have_zero_evaluations(tmp_path: Path) -> None:
    repo, analyses = saved(tmp_path, ("TC-006",))
    repo.save_analysis_result({**analyses[0].output, "evaluations": []})
    result = aggregate_saved_match(repo, MATCH)
    assert result["rounds"][0]["status"] == "included"
    assert result["rounds"][0]["evaluation_count"] == 0
    assert result["completeness"]["status"] == "unverifiable"


def test_failed_round_is_excluded_even_if_stale_evaluations_remain(tmp_path: Path) -> None:
    repo, _ = saved(tmp_path, ("TC-006",))
    repo.save_job_checkpoint(MATCH, "partial", {
        "failed_rounds": [1], "completed_rounds": [], "round_diagnostics": {"1": "failed"}
    })
    view = aggregate_saved_match(repo, MATCH)
    assert view["completeness"]["rounds_not_evaluated"] == [1]
    assert view["evaluations"] == []
    assert view["completeness"]["status"] == "incomplete"


def test_failed_round_without_package_is_explicit_incomplete(tmp_path: Path) -> None:
    repo, _ = saved(tmp_path, ("TC-006",))
    repo.save_job_checkpoint(MATCH, "partial", {
        "failed_rounds": [2], "completed_rounds": [1]
    })
    value = aggregate_saved_match(repo, MATCH)
    assert value["completeness"]["status"] == "incomplete"
    assert "failed_round_package_missing" in value["completeness"]["blocking_reasons"]
    assert value["storage_provenance"]["missing_failed_round_packages"] == [2]


def test_orphan_evaluation_fails_closed(tmp_path: Path) -> None:
    repo, analyses = saved(tmp_path, ("TC-006",))
    orphan = deepcopy(analyses[0].output)
    orphan["round_no"] = 2
    orphan["evaluations"][0]["evaluation_id"] = "E-ORPHAN"
    repo.save_analysis_result(orphan)
    with pytest.raises(MatchAggregationError, match="Round Package"):
        aggregate_saved_match(repo, MATCH)


def test_corrupt_package_is_quarantined_not_counted(tmp_path: Path) -> None:
    repo, analyses = saved(tmp_path, ("TC-006",))
    damaged = deepcopy(analyses[0].round_package)
    damaged["observation_quality"]["timeline_completeness"] = 2
    repo.save_round_package(damaged)
    result = aggregate_saved_match(repo, MATCH)
    assert result["completeness"]["rounds_excluded_invalid"] == [1]
    assert result["evaluations"] == []
    assert result["completeness"]["status"] == "incomplete"


def test_practical_round_with_zero_evaluations_is_not_evaluated(tmp_path: Path) -> None:
    repo = SQLiteRepository(tmp_path / "practical.db")
    package = uncertain_package(start="unknown", end="unknown", round_no=2)
    repo.create_match(MATCH, "synthetic.mp4", status="completed")
    repo.save_round_package(package)
    repo.save_job_checkpoint(MATCH, "completed", {
        "completed_rounds": [2], "canonical_evaluation_set": "full_post_dedup_v1"
    })
    view = aggregate_saved_match(repo, MATCH)
    assert view["completeness"]["rounds_not_evaluated"] == [2]
    assert view["evaluations"] == []
    assert view["completeness"]["status"] == "incomplete"


def test_practical_round_with_stale_scored_rows_fails_closed(tmp_path: Path) -> None:
    repo, analyses = saved(tmp_path, ("TC-006",))
    package = uncertain_package(start="unknown", end="unknown", round_no=1)
    repo.save_round_package(package)
    assert analyses[0].output["evaluations"]
    with pytest.raises(MatchAggregationError, match="境界未確定"):
        aggregate_saved_match(repo, MATCH)


def test_report_json_includes_validated_match_view_without_changing_version(
    tmp_path: Path,
) -> None:
    repo, _ = saved(tmp_path, ("TC-006",))
    destination = tmp_path / "report.json"
    features = NonVideoFeatures(repo)
    features.export_report(MATCH, destination, "json")
    record = json.loads(destination.read_text(encoding="utf-8"))
    assert record["export_format_version"] == 1
    assert record["match_aggregation"]["schema_version"] == "match_aggregation.v1"
    assert record["match_aggregation"]["evaluations"][0]["evaluation_id"] is not None
    assert "source_video_path" not in json.dumps(record["match_aggregation"])
    assert record["match_aggregation_error"] is None


def test_report_fails_closed_on_missing_package_without_fabricated_counts(
    tmp_path: Path,
) -> None:
    repo, analyses = saved(tmp_path, ("TC-006",))
    orphan = deepcopy(analyses[0].output)
    orphan["round_no"] = 2
    orphan["evaluations"][0]["evaluation_id"] = "E-ORPHAN"
    repo.save_analysis_result(orphan)
    report = NonVideoFeatures(repo).report(MATCH)
    assert report["match_aggregation"] is None
    assert report["match_aggregation_error"]


def test_backend_history_and_presentation_read_same_saved_aggregation(
    tmp_path: Path,
) -> None:
    repo, _ = saved(tmp_path, ("TC-006",))
    backend = BackendFacade.__new__(BackendFacade)
    backend.services = SimpleNamespace(
        repository=repo,
        pipeline=SimpleNamespace(aggregator=SimpleNamespace(
            select_display_exemplars=lambda items: items
        )),
    )
    backend._rule_category = {"AIM-02": "Aim"}
    backend._round_context = {"AIM-02": False}
    view = backend.get_match_result(MATCH)
    assert view.match_aggregation is not None
    assert view.match_aggregation["match_id"] == MATCH
    assert len(view.match_aggregation["evaluations"]) == len(view.evaluations)
    rendered = format_match_summary(view.match_aggregation, view.match_aggregation_error)
    assert "Match集計:" in rendered and "Rule別" in rendered
    assert "完全性: unverifiable" in rendered


def test_summary_on_failure_does_not_echo_private_error_content() -> None:
    assert "SECRET" not in format_match_summary(None, "SECRET")
    assert format_match_summary(None, None) == ""

def test_new_full_set_does_not_emit_legacy_display_thinning_warning(
    tmp_path: Path,
) -> None:
    repo, _ = saved(tmp_path, ("TC-006", "TC-006", "TC-006"))
    full = aggregate_saved_match(repo, MATCH)
    assert len(full["evaluations"]) == 3
    assert not [i for i in full["issues"] if i["code"] == "display_limit_reached"]

    repo.save_job_checkpoint(MATCH, "completed", {"completed_rounds": [1, 2, 3]})
    old = aggregate_saved_match(repo, MATCH)
    assert len(old["evaluations"]) == 3
    assert any(i["code"] == "display_limit_reached" for i in old["issues"])


def test_corrupt_round_lifecycle_fails_closed_not_keyerror(tmp_path: Path) -> None:
    repo, analyses = saved(tmp_path, ("TC-006",))
    corrupt = deepcopy(analyses[0].round_package)
    corrupt["round_lifecycle"] = {"start": {}, "end": {}}
    repo.save_round_package(corrupt)
    with pytest.raises(MatchAggregationError, match="境界未確定または不正"):
        aggregate_saved_match(repo, MATCH)


def test_incomplete_round_with_invalid_lifecycle_is_quarantined(tmp_path: Path) -> None:
    repo, analyses = saved(tmp_path, ("TC-006",))
    empty = deepcopy(analyses[0].output)
    empty["evaluations"] = []
    repo.save_analysis_result(empty)
    corrupt = deepcopy(analyses[0].round_package)
    corrupt["round_lifecycle"] = {"start": {}}
    repo.save_round_package(corrupt)
    summary = aggregate_saved_match(repo, MATCH)
    assert summary["completeness"]["status"] == "incomplete"
    assert summary["completeness"]["rounds_excluded_invalid"] == [1]
    assert summary["evaluations"] == []


def test_pipeline_json_export_is_safe_when_match_aggregation_cannot_validate(
    tmp_path: Path,
) -> None:
    repo, analyses = saved(tmp_path, ("TC-006",))
    orphan = deepcopy(analyses[0].output)
    orphan["round_no"] = 2
    orphan["evaluations"][0]["evaluation_id"] = "E-ORPHAN"
    repo.save_analysis_result(orphan)
    pipeline = MatchAnalysisPipeline.__new__(MatchAnalysisPipeline)
    pipeline.repository = repo
    pipeline.data_dir = tmp_path
    export = pipeline._write_analysis_json(MATCH, [], [])
    record = json.loads(export.read_text(encoding="utf-8"))
    assert record["match_aggregation"] is None
    assert record["match_aggregation_error"]
    assert len(record["evaluations"]) == 2

def test_missing_completed_package_is_incomplete(tmp_path: Path) -> None:
    repo, _ = saved(tmp_path, ("TC-006",))
    repo.save_job_checkpoint(MATCH, "completed", {"completed_rounds": [1, 2]})
    result = aggregate_saved_match(repo, MATCH)
    assert result["completeness"]["status"] == "incomplete"
    assert "completed_round_package_missing" in result["completeness"]["blocking_reasons"]
    assert result["storage_provenance"]["missing_completed_round_packages"] == [2]
    assert len(result["evaluations"]) == 1
