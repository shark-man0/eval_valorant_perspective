"""Result view-model contract tests (Qt-free)."""

from __future__ import annotations

import json
import math
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from valorant_ai_coach.resources import resource_path
from valorant_ai_coach.rules import MockEvaluator
from valorant_ai_coach.settings import AppSettings, SettingsStore
from valorant_ai_coach.ui.backend import BackendFacade
from valorant_ai_coach.ui.contracts import EvaluationView
from valorant_ai_coach.ui.view_model import (
    clip_status,
    filter_evaluations,
    format_clock,
    label_counts,
    parse_time_range,
    time_range_text,
)


def view(
    label: str = "good",
    *,
    evaluation_id: str = "e1",
    category: str = "Aim",
    round_no: int | None = 1,
    needs_review: bool = False,
    clip_path: str | None = None,
) -> EvaluationView:
    return EvaluationView(
        evaluation_id=evaluation_id,
        label=label,
        title="t",
        rule_id="AIM-02",
        related_rule_ids=(),
        situation="s",
        evidence=(),
        missing_information=("x",) if label == "unscored" else (),
        reason="r",
        improvement="i" if label == "improve" else None,
        confidence=0.9,
        category=category,
        round_no=round_no,
        requires_round_context=False,
        decision_source="deterministic",
        clip_path=clip_path,
        needs_review=needs_review,
        unscored_reason_code="low_confidence" if label == "unscored" else None,
    )


SAMPLE = (
    view("good", evaluation_id="g1", category="Aim", round_no=1),
    view("improve", evaluation_id="i1", category="Move", round_no=1, needs_review=True),
    view("improve", evaluation_id="i2", category="Aim", round_no=2),
    view("unscored", evaluation_id="u1", category="Aim", round_no=2),
    view("unscored", evaluation_id="u2", category="Move", round_no=None),
)


def ids(items: list[EvaluationView]) -> list[str]:
    return [item.evaluation_id for item in items]


# --- counts -------------------------------------------------------------------------------


def test_label_counts_partition_every_evaluation() -> None:
    counts = label_counts(SAMPLE)
    assert counts == {"good": 1, "improve": 2, "unscored": 2}
    assert sum(counts.values()) == len(SAMPLE)


def test_label_counts_of_nothing_are_zero() -> None:
    assert label_counts(()) == {"good": 0, "improve": 0, "unscored": 0}


# --- filters ------------------------------------------------------------------------------


def test_default_filter_shows_scored_only_and_never_unscored() -> None:
    assert ids(filter_evaluations(SAMPLE)) == ["g1", "i1", "i2"]


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("good", ["g1"]),
        ("improve", ["i1", "i2"]),
        ("unscored", ["u1", "u2"]),
        ("review", ["i1"]),
        ("all", ["g1", "i1", "i2", "u1", "u2"]),
        ("scored", ["g1", "i1", "i2"]),
        ("not-a-label", []),
    ],
)
def test_label_filters(label: str, expected: list[str]) -> None:
    assert ids(filter_evaluations(SAMPLE, label=label)) == expected


def test_category_and_round_filters_combine_with_the_label_filter() -> None:
    assert ids(filter_evaluations(SAMPLE, label="all", category="Aim")) == ["g1", "i2", "u1"]
    assert ids(filter_evaluations(SAMPLE, label="all", round_no=2)) == ["i2", "u1"]
    assert ids(filter_evaluations(SAMPLE, label="improve", category="Aim", round_no=2)) == ["i2"]
    assert filter_evaluations(SAMPLE, label="good", category="Move") == []


def test_filtering_neither_mutates_nor_reorders_nor_alters_evaluations() -> None:
    before = tuple(SAMPLE)
    shown = filter_evaluations(SAMPLE, label="all")
    assert tuple(SAMPLE) == before
    assert shown == list(SAMPLE)
    assert all(a is b for a, b in zip(shown, SAMPLE, strict=True))


def test_filtered_counts_never_exceed_the_total() -> None:
    total = label_counts(SAMPLE)
    for label in ("good", "improve", "unscored"):
        assert len(filter_evaluations(SAMPLE, label=label)) == total[label]


# --- timestamp / clip presentation --------------------------------------------------------


@pytest.mark.parametrize(
    ("seconds", "text"),
    [(0, "00:00"), (59.4, "00:59"), (60, "01:00"), (3725, "62:05"), (-3, "00:00")],
)
def test_format_clock(seconds: float, text: str) -> None:
    assert format_clock(seconds) == text


def test_time_range_is_parsed_only_from_a_usable_stored_range() -> None:
    assert parse_time_range({"start_sec": 30, "end_sec": 31.5}) == (30.0, 31.5)
    assert parse_time_range({"start_sec": 5, "end_sec": 5}) == (5.0, 5.0)
    for bad in (
        None,
        {},
        "30-31",
        {"start_sec": 31, "end_sec": 30},
        {"start_sec": True, "end_sec": 3},
        {"start_sec": "1", "end_sec": 3},
        {"start_sec": math.nan, "end_sec": 3},
        {"start_sec": 1, "end_sec": math.inf},
        {"start_sec": 1},
    ):
        assert parse_time_range(bad) is None


def test_time_range_text() -> None:
    assert time_range_text(None) is None
    assert time_range_text((30.0, 31.5)) == "00:30–00:32（30.0–31.5秒）"


def test_clip_status_never_claims_a_clip_that_is_not_stored() -> None:
    assert clip_status(view("good", clip_path="/c/a.mp4")) == "クリップあり"
    assert clip_status(view("improve")) == "クリップなし"
    assert "評価対象外" in clip_status(view("unscored"))
    assert clip_status(replace(view("unscored"), clip_path="/c/a.mp4")) == "クリップあり"


# --- backend mapping from stored output ----------------------------------------------------


class MemoryCredentials:
    def get_password(self, _service: str, _username: str) -> str | None:
        return None

    def set_password(self, _service: str, _username: str, _password: str) -> None:
        return None

    def delete_password(self, _service: str, _username: str) -> None:
        return None


def stored_result(tmp_path: Path, case_id: str, match_id: str) -> Any:
    store = SettingsStore(tmp_path / "settings.json", credential_backend=MemoryCredentials())
    store.save(AppSettings.defaults(tmp_path))
    backend = BackendFacade(store)
    package = json.loads(
        resource_path(f"tests/cases/{case_id}/input.json").read_text(encoding="utf-8")
    )
    package["match_id"] = match_id
    package["source_video"]["path"] = str(tmp_path / "match.mp4")
    repository = backend.services.repository
    repository.create_match(
        match_id, package["source_video"]["path"], {"duration_sec": 120}, "completed"
    )
    repository.save_round_package(package)
    repository.save_analysis_result(MockEvaluator().evaluate(package))
    return backend.get_match_result(match_id), package


def test_scored_evaluations_expose_facts_and_the_stored_time_range(tmp_path: Path) -> None:
    result, package = stored_result(tmp_path, "TC-029", "M-VM-1")
    window = package["round_window"]
    assert result.evaluations
    for item in result.evaluations:
        assert item.label in {"good", "improve"}
        assert item.fact_refs
        assert item.time_range is not None
        start, end = item.time_range
        assert window["start_sec"] <= start <= end <= window["end_sec"]


def test_header_counts_equal_the_evaluations_actually_listed(tmp_path: Path) -> None:
    for case_id, match_id in (("TC-029", "M-VM-2"), ("TC-025", "M-VM-3")):
        result, _ = stored_result(tmp_path / case_id, case_id, match_id)
        counts = label_counts(result.evaluations)
        assert (result.good_count, result.improve_count, result.unscored_count) == (
            counts["good"],
            counts["improve"],
            counts["unscored"],
        )


def test_unscored_evaluation_carries_no_clip_improvement_or_time_range(tmp_path: Path) -> None:
    result, _ = stored_result(tmp_path, "TC-025", "M-VM-4")
    unscored = [item for item in result.evaluations if item.label == "unscored"]
    assert unscored
    for item in unscored:
        assert item.clip_path is None
        assert item.improvement is None
        assert item.time_range is None
        assert item.missing_information
        assert item.unscored_reason_code


def test_missing_provenance_stays_empty_instead_of_being_invented(tmp_path: Path) -> None:
    backend = BackendFacade.__new__(BackendFacade)
    backend._rule_category = {}
    backend._round_context = {}
    mapped = backend._evaluation_view({"evaluation_id": "x", "label": "good", "confidence": 0.9})
    assert mapped.fact_refs == ()
    assert mapped.time_range is None
    assert mapped.clip_path is None
