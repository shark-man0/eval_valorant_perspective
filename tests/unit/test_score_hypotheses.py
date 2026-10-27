"""Offline proposals do not weaken the production Score acceptance path."""

from __future__ import annotations

import numpy as np
import pytest

from scripts.diagnostics.score_hypotheses import (
    generate_score_hypotheses,
    rank_score_hypotheses,
    selective_score,
)
from tests.unit.test_timer_glyphs import _templates
from valorant_ai_coach.hud.score_glyphs import StrictScoreGlyphReader


@pytest.mark.parametrize(
    "roi",
    [
        np.empty((0, 2), np.uint8),
        np.zeros((8, 8, 4), np.uint8),
        np.zeros((600, 600), np.uint8),
        np.zeros((8, 8), float),
    ],
)
def test_input_budget_before_reader_access(roi: np.ndarray) -> None:
    with pytest.raises(ValueError, match="unbounded"):
        generate_score_hypotheses(roi, None)  # type: ignore[arg-type]


@pytest.mark.parametrize("level", [0, 128, 255])
def test_blank_has_no_safe_number(level: int) -> None:
    reader = StrictScoreGlyphReader(_templates(), comparison_preprocessing="gaussian3x3_v1")
    out = generate_score_hypotheses(np.full((45, 44, 3), level, np.uint8), reader)
    safe = selective_score(None, out["candidates"], source_valid=True, geometry_valid=True)
    assert safe["value"] is None
    assert out["formal_events"] == []


def proposal(text: str, **kwargs: object) -> dict:
    route = (
        dict(
            min_ncc=0.95,
            min_gap=0.06,
            complete_components=True,
            layout_supported=True,
            border_foreground=False,
            unassigned_foreground_fraction=0.0,
        )
        | kwargs
    )
    return {"text": text, "routes": [route | {"method": m} for m in ["rowcontrast", "white"]]}


@pytest.mark.parametrize(
    "flag",
    [
        "border_foreground",
        "layout_supported",
        "complete_components",
        "unassigned_foreground_fraction",
        "min_ncc",
        "min_gap",
    ],
)
def test_unsafe_subset_or_partial_cannot_rescue(flag: str) -> None:
    bad = {
        "border_foreground": True,
        "layout_supported": False,
        "complete_components": False,
        "unassigned_foreground_fraction": 0.1,
        "min_ncc": 0.89,
        "min_gap": 0.039,
    }[flag]
    out = selective_score(
        None, [proposal("1", **{flag: bad})], source_valid=True, geometry_valid=True
    )
    assert out["value"] is None


def test_baseline_geometry_and_ambiguity() -> None:
    assert (
        selective_score("12", [proposal("1")], source_valid=True, geometry_valid=True)["value"]
        == "12"
    )
    assert selective_score("12", [], source_valid=True, geometry_valid=False)["value"] is None
    assert (
        selective_score(
            None, [proposal("1"), proposal("2")], source_valid=True, geometry_valid=True
        )["value"]
        is None
    )
    assert (
        selective_score(None, [proposal("1")], source_valid=True, geometry_valid=True)[
            "formal_events"
        ]
        == []
    )
    with pytest.raises(ValueError, match="source"):
        selective_score("1", [], source_valid=False, geometry_valid=True)


def test_rerank_keeps_the_same_candidate_set() -> None:
    report = {
        "candidates": [
            {"text": "3", "ncc": 0.9, "edge": 0.7},
            {"text": "8", "ncc": 0.8, "edge": 0.95},
        ]
    }
    assert rank_score_hypotheses(report)[0]["text"] == "3"
    assert rank_score_hypotheses(report, method="edge")[0]["text"] == "8"
    assert (
        rank_score_hypotheses(report, method="learned", learned_scores={"8": 2, "9": 4})[0]["text"]
        == "8"
    )
    with pytest.raises(ValueError):
        rank_score_hypotheses(report, method="learned", learned_scores={"8": float("nan")})


def test_coverage_rank_penalizes_discarded_second_digit() -> None:
    report = {
        "candidates": [
            {"text": "1", "routes": [{"ncc": 0.98, "unassigned_foreground_fraction": 0.5}]},
            {"text": "12", "routes": [{"ncc": 0.95, "unassigned_foreground_fraction": 0.0}]},
        ]
    }
    assert rank_score_hypotheses(report, method="coverage_ncc")[0]["text"] == "12"


def test_all_classes_and_segmentations_remain_bounded() -> None:
    from tests.unit.test_score_glyphs import render

    reader = StrictScoreGlyphReader(_templates(), comparison_preprocessing="gaussian3x3_v1")
    report = generate_score_hypotheses(render("12"), reader)
    assert 1 <= len(report["candidates"]) <= 20
    for mask in report["masks"]:
        for component in mask["components"]:
            assert {v["digit"] for v in component["digits"]} == set("0123456789")
    assert not any(c["accepted"] for c in report["candidates"])
    with pytest.raises(ValueError):
        generate_score_hypotheses(render("12"), reader, methods=("white", "white"))
