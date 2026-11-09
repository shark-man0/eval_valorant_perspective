"""Development-only ranking of weak current-view candidates.

Pseudo labels and model scores are diagnostics, never game-state facts. The
caller supplies neighboring observations from the same native epoch and a
physical-match split. No source identity or absolute recording time is a feature.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray

FEATURE_NAMES = (
    "centroid_signed_margin",
    "prototype_signed_margin",
    "neighbor_centroid_signed_margin",
    "neighbor_prototype_signed_margin",
    "neighbor_coverage",
)


def _signed_margin(raw: dict[str, Any], name: str) -> float:
    classifiers = raw.get("classifiers")
    item = classifiers.get(name) if isinstance(classifiers, dict) else None
    if not isinstance(item, dict):
        return 0.0
    value, margin = item.get("raw"), item.get("margin")
    if (
        not isinstance(margin, (int, float))
        or isinstance(margin, bool)
        or not math.isfinite(margin)
    ):
        return 0.0
    sign = 1.0 if value == "SELF" else -1.0 if value == "SPECTATOR" else 0.0
    return sign * min(max(float(margin), 0.0), 1.0)


def margin_features(
    raw: dict[str, Any],
    *,
    previous: dict[str, Any] | None = None,
    following: dict[str, Any] | None = None,
) -> tuple[float, ...]:
    """Use only two classifier channels and at most two supplied neighbors.

    Neighbors must be independently checked by the caller for same epoch,
    source, acquisition, and a relative gap of at most two seconds.
    """
    neighbors = [item for item in (previous, following) if item is not None]
    return (
        _signed_margin(raw, "centroid"),
        _signed_margin(raw, "three_prototypes"),
        sum(_signed_margin(item, "centroid") for item in neighbors) / len(neighbors)
        if neighbors
        else 0.0,
        sum(_signed_margin(item, "three_prototypes") for item in neighbors) / len(neighbors)
        if neighbors
        else 0.0,
        len(neighbors) / 2.0,
    )


def _credible_hp(raw: dict[str, Any]) -> int | None:
    hp = raw.get("view_hp")
    if not isinstance(hp, dict):
        return None
    value, confidence = hp.get("display"), hp.get("confidence")
    if (
        not isinstance(value, str)
        or not value.isascii()
        or not value.isdigit()
        or not isinstance(confidence, (int, float))
        or isinstance(confidence, bool)
        or not math.isfinite(confidence)
        or not 0.9 <= confidence <= 1
    ):
        return None
    parsed = int(value)
    return parsed if 1 <= parsed <= 150 else None


def temporal_hp_correspondence(
    raw: dict[str, Any],
    *,
    previous: dict[str, Any] | None = None,
    following: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Check repeated current HP pixels within caller-validated native neighbors.

    A mismatch may be damage or a view change, so only matching values provide
    support. Missing or differing values never prove spectator/death or negate
    another candidate. The caller must enforce same source/epoch and <=2s gap.
    """
    current = _credible_hp(raw)
    neighbors = [item for item in (previous, following) if item is not None]
    measured = [_credible_hp(item) for item in neighbors]
    return {
        "repeated_current_hp": current is not None and current in measured,
        "current_hp_measured": current is not None,
        "measured_neighbor_count": sum(value is not None for value in measured),
        "matching_neighbor_count": sum(value == current for value in measured if value is not None)
        if current is not None
        else 0,
        "diagnostic_only": True,
        "formal_authority": False,
    }


def limited_current_ui_pseudo_label(observation: dict[str, Any]) -> int | None:
    """Return an explicitly unreviewed proxy from restricted current UI cues.

    HP/owner and elimination-display cues are deliberately excluded from the
    model features. These cues remain correlated with the weak view recognizer;
    pseudo-label agreement is not a human correctness measure.
    """
    if observation.get("context", {}).get("unqualified_view_model") is not True:
        return None
    raw = observation.get("raw", {})
    signals = set(observation.get("signals", []))
    if (
        "owner_hud" in signals
        and raw.get("current_HUD_component_supported") is True
        and raw.get("owner_hypothesis_exclusions") == []
        and _credible_hp(raw) is not None
    ):
        return 1
    if {"recorder_elimination_display", "spectator"} <= signals:
        return 0
    return None


@dataclass(frozen=True)
class PseudoExample:
    physical_match: str
    features: tuple[float, ...]
    pseudo_label: int


@dataclass(frozen=True)
class ViewReranker:
    weights: tuple[float, ...]
    intercept: float
    train_matches: tuple[str, ...]
    positive_count: int
    negative_count: int

    def score(self, features: Sequence[float]) -> dict[str, Any]:
        if len(features) != len(FEATURE_NAMES) or any(not math.isfinite(v) for v in features):
            raise ValueError("Finite fixed-length view features required")
        logit = self.intercept + sum(
            w * float(x) for w, x in zip(self.weights, features, strict=True)
        )
        probability = 1.0 / (1.0 + math.exp(-max(-40.0, min(40.0, logit))))
        return {
            "score": probability,
            "feature_names": FEATURE_NAMES,
            "diagnostic_only": True,
            "formal_authority": False,
        }


def fit_pseudo_view_reranker(
    examples: Sequence[PseudoExample],
    *,
    train_matches: set[str],
    heldout_matches: set[str],
) -> ViewReranker:
    """Fit one fixed L2 logistic model with disjoint physical-match groups."""
    if not train_matches or not heldout_matches or train_matches & heldout_matches:
        raise ValueError("Disjoint nonempty physical-match split required")
    if any(example.physical_match not in train_matches | heldout_matches for example in examples):
        raise ValueError("Every example requires a declared physical match")
    selected = [example for example in examples if example.physical_match in train_matches]
    if any(
        len(example.features) != len(FEATURE_NAMES)
        or any(not math.isfinite(v) for v in example.features)
        or example.pseudo_label not in (0, 1)
        for example in selected
    ):
        raise ValueError("Invalid pseudo example")
    positives = sum(example.pseudo_label == 1 for example in selected)
    negatives = len(selected) - positives
    if positives < 2 or negatives < 2:
        raise ValueError("Both pseudo classes require at least two training examples")
    design = np.asarray([(*example.features, 1.0) for example in selected], dtype=np.float64)
    labels = np.asarray([example.pseudo_label for example in selected], dtype=np.float64)
    balance = np.where(
        labels == 1, len(selected) / (2 * positives), len(selected) / (2 * negatives)
    )
    coefficients: NDArray[np.float64] = np.zeros(design.shape[1], dtype=np.float64)
    penalty = np.diag([1.0] * len(FEATURE_NAMES) + [0.0])
    for _ in range(30):
        logits = np.clip(design @ coefficients, -40.0, 40.0)
        probabilities = 1.0 / (1.0 + np.exp(-logits))
        gradient = design.T @ (balance * (probabilities - labels)) + penalty @ coefficients
        curvature = balance * probabilities * (1.0 - probabilities)
        hessian = design.T @ (design * curvature[:, None]) + penalty
        step = np.linalg.solve(hessian, gradient)
        coefficients -= step
        if np.max(np.abs(step)) < 1e-7:
            break
    return ViewReranker(
        weights=tuple(float(v) for v in coefficients[:-1]),
        intercept=float(coefficients[-1]),
        train_matches=tuple(sorted(train_matches)),
        positive_count=positives,
        negative_count=negatives,
    )
