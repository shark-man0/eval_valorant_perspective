"""Synthetic contracts for development-only view candidate ranking."""

from __future__ import annotations

import pytest

from valorant_ai_coach.temporal.development_view_reranker import (
    PseudoExample,
    fit_pseudo_view_reranker,
    limited_current_ui_pseudo_label,
    margin_features,
    temporal_hp_correspondence,
)


def _raw(cls: str, margin: float, hp: str | None = None) -> dict[str, object]:
    return {
        "classifiers": {
            "centroid": {"raw": cls, "margin": margin},
            "three_prototypes": {"raw": cls, "margin": margin / 2},
        },
        "view_hp": {"display": hp, "confidence": 0.98 if hp else 0.0},
        "current_HUD_component_supported": True,
        "owner_hypothesis_exclusions": [],
    }


def test_margin_features_use_supplied_neighbors_without_identity_fields() -> None:
    current = _raw("SELF", 0.8)
    current["source_id"] = "source-a"
    features = margin_features(current, previous=_raw("SPECTATOR", 0.4))
    current["source_id"] = "source-b"
    current["native_pts_tick"] = 10**9
    assert features == margin_features(current, previous=_raw("SPECTATOR", 0.4))
    assert features == (0.8, 0.4, -0.4, -0.2, 0.5)


def test_pseudo_labels_are_narrow_and_not_human_truth() -> None:
    positive = {
        "context": {"unqualified_view_model": True},
        "raw": _raw("SELF", 0.7, "100"),
        "signals": ["owner_hud"],
    }
    negative = {
        "context": {"unqualified_view_model": True},
        "raw": _raw("SPECTATOR", 0.7),
        "signals": ["recorder_elimination_display", "spectator"],
    }
    assert limited_current_ui_pseudo_label(positive) == 1
    assert limited_current_ui_pseudo_label(negative) == 0
    positive["raw"]["owner_hypothesis_exclusions"] = ["combat_report_visible"]
    assert limited_current_ui_pseudo_label(positive) is None
    negative["signals"] = ["spectator"]
    assert limited_current_ui_pseudo_label(negative) is None


def test_temporal_correspondence_only_supports_repeated_hp() -> None:
    current = _raw("SELF", 0.5, "87")
    matched = temporal_hp_correspondence(
        current, previous=_raw("SELF", 0.4, "87"), following=_raw("SELF", 0.4, "72")
    )
    assert matched["repeated_current_hp"] is True
    assert matched["matching_neighbor_count"] == 1
    assert matched["formal_authority"] is False
    mismatch = temporal_hp_correspondence(current, following=_raw("SELF", 0.4, "72"))
    assert mismatch["repeated_current_hp"] is False
    assert mismatch["measured_neighbor_count"] == 1
    assert "negative" not in mismatch


def test_pseudo_model_enforces_match_split_and_only_scores() -> None:
    examples = [
        PseudoExample("train-a", margin_features(_raw("SELF", 0.8)), 1),
        PseudoExample("train-a", margin_features(_raw("SPECTATOR", 0.8)), 0),
        PseudoExample("train-b", margin_features(_raw("SELF", 0.7)), 1),
        PseudoExample("train-b", margin_features(_raw("SPECTATOR", 0.7)), 0),
        PseudoExample("heldout", margin_features(_raw("SELF", 0.6)), 1),
    ]
    with pytest.raises(ValueError, match="Disjoint"):
        fit_pseudo_view_reranker(examples, train_matches={"train-a"}, heldout_matches={"train-a"})
    model = fit_pseudo_view_reranker(
        examples, train_matches={"train-a", "train-b"}, heldout_matches={"heldout"}
    )
    changed_heldout = [
        *examples[:-1], PseudoExample("heldout", margin_features(_raw("SPECTATOR", 0.9)), 0)
    ]
    unchanged = fit_pseudo_view_reranker(
        changed_heldout, train_matches={"train-a", "train-b"}, heldout_matches={"heldout"}
    )
    assert (model.weights, model.intercept) == (unchanged.weights, unchanged.intercept)
    assert model.train_matches == ("train-a", "train-b")
    positive = model.score(margin_features(_raw("SELF", 0.8)))
    negative = model.score(margin_features(_raw("SPECTATOR", 0.8)))
    assert positive["score"] > negative["score"]
    assert positive["diagnostic_only"] is True
    assert positive["formal_authority"] is False
