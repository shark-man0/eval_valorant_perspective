"""Non-destructive candidate-window selection; associations stay unqualified."""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from .development_marker_center import (
    CENTER_FEATURE_FINGERPRINT,
    CenterReadout,
    center_rule,
)
from .development_marker_features import CLASSES, Array, _digest, bound_patches
from .development_marker_topk import _native


def select_center_candidates(
    frame: Array,
    sample: dict[str, Any],
    pool: dict[str, Any],
    *,
    features: Array,
    feature_binding_sha256: str,
    center_model: CenterReadout | None = None,
    semantic_model: CenterReadout | None = None,
    semantic_features: Array | None = None,
    semantic_feature_fingerprint: str | None = None,
    maximum_selected: int = 5,
) -> dict[str, Any]:
    """Select existing centers only; keep complete raw pool and all rank indices.

    Seed-relative nearby-window groups are review/selection hypotheses. They do
    not identify physical objects or owners. Distinct/ambiguous shapes can keep
    multiple alternative representatives instead of being forcibly merged.
    """
    frozen = _native(frame, sample)
    if (
        pool.get("sample") != frozen
        or pool.get("ownership") != "UNKNOWN"
        or pool.get("formal_outputs") != 0
        or pool.get("pool_sha256") != _digest({k: v for k, v in pool.items() if k != "pool_sha256"})
        or type(maximum_selected) is not int
        or not 1 <= maximum_selected <= 10
    ):
        raise ValueError("Exact current unqualified pool required")
    candidates = pool["candidates"]
    if not 1 <= len(candidates) <= 320:
        raise ValueError("One to 320 current windows required")
    centers = [p["center_frame_px"] for p in candidates]
    bindings, patches = [], []
    for start in range(0, len(centers), 128):
        part, binding = bound_patches(frame, frozen, centers[start : start + 128])
        patches.extend(part)
        bindings.append(binding)
    if feature_binding_sha256 != _digest(bindings) or len(features) != len(candidates):
        raise ValueError("Current native feature-window binding required")
    support = center_rule(features)
    if center_model is not None:
        if center_model.mode != "weak_center":
            raise ValueError("Separate weak center readout required")
        weak = center_model.scores(features, feature_fingerprint=CENTER_FEATURE_FINGERPRINT)[:, 0]
        support = 0.5 * support + 0.5 * np.clip(weak, 0, 1)
    scores = support.copy()
    semantics = ["UNKNOWN"] * len(centers)
    eligible = np.ones(len(centers), dtype=bool)
    if semantic_model is not None:
        if (
            semantic_model.mode != "human_semantics"
            or semantic_features is None
            or semantic_feature_fingerprint is None
            or len(semantic_features) != len(centers)
        ):
            raise ValueError("Separate paired semantic features/readout required")
        predicted = semantic_model.scores(
            semantic_features, feature_fingerprint=semantic_feature_fingerprint
        )
        novelty = np.sqrt(
            np.mean(((semantic_features - semantic_model.mean) / semantic_model.scale) ** 2, axis=1)
        )
        scores += (
            0.5
            * np.clip(predicted[:, :2].max(axis=1) - predicted[:, 2:].max(axis=1), -1, 1)
            * (np.minimum(1.0, 3 / np.maximum(novelty, 1.0)))
        )
        for i, row in enumerate(predicted):
            class_order = np.argsort(-row, kind="stable")
            if novelty[i] <= 3 and row[class_order[0]] - row[class_order[1]] >= 0.1:
                semantics[i] = CLASSES[int(class_order[0])]
                eligible[i] = semantics[i] not in {"UI", "BACKGROUND"}
    order = sorted(range(len(scores)), key=lambda i: (-float(scores[i]), i))
    # Centered image contrast, not a color-only or temporal ownership cue.
    appearance = np.stack([p.astype(np.float64).ravel() for p in patches])
    appearance -= appearance.mean(axis=1, keepdims=True)
    appearance /= np.maximum(np.linalg.norm(appearance, axis=1, keepdims=True), 1e-12)
    groups: list[list[int]] = []
    for index in order:
        group = next(
            (
                g
                for g in groups
                if math.dist(centers[index], centers[g[0]]) <= 2
                and float(appearance[index] @ appearance[g[0]]) >= 0.9
            ),
            None,
        )
        if group is None:
            groups.append([index])
        else:
            group.append(index)
    representatives = []
    group_records = []
    for group in groups:
        available = [i for i in group if eligible[i]]
        diameter = max(
            (math.dist(centers[i], centers[j]) for i in group for j in group), default=0.0
        )
        ambiguous = (
            diameter > 2.5
            and len(available) > 1
            and (abs(float(scores[available[0]] - scores[available[1]])) < 0.1)
        )
        chosen = available if ambiguous else available[:1]
        representatives.extend(chosen)
        group_records.append(
            {
                "indices": group,
                "representative_indices": chosen,
                "diameter_px": diameter,
                "physical_equivalence": "UNKNOWN",
                "ambiguous_alternatives_retained": ambiguous,
            }
        )
    representatives.sort(key=lambda i: (-float(scores[i]), i))
    return {
        "pool_sha256": pool["pool_sha256"],
        "feature_binding_sha256": feature_binding_sha256,
        "center_model_fingerprint": center_model.fingerprint if center_model else None,
        "semantic_model_fingerprint": semantic_model.fingerprint if semantic_model else None,
        "ranked_indices": order,
        "selection_indices": representatives[:maximum_selected],
        "group_representative_indices": representatives,
        "groups": group_records,
        "center_support": support.tolist(),
        "scores": scores.tolist(),
        "semantic_class_candidates": semantics,
        "UNKNOWN": semantics.count("UNKNOWN"),
        "score_kind": "uncalibrated_center_and_semantic_support",
        "coordinates_modified": False,
        "qualification": "development_only",
        "ownership": "UNKNOWN",
        "formal_outputs": 0,
    }


def retain_parent_with_center_alternative(
    pool: dict[str, Any],
    selection: dict[str, Any],
    *,
    minimum_center_support: float,
) -> dict[str, Any]:
    """Conservative second policy: preserve parents and at most one new window.

    Thresholds must be fixed from TRAIN/validation before comparison. Separation
    by2px describes window alternatives, not physical identity or a true center.
    """
    if (
        selection.get("pool_sha256") != pool.get("pool_sha256")
        or pool.get("pool_sha256") != _digest({k: v for k, v in pool.items() if k != "pool_sha256"})
        or type(minimum_center_support) not in (int, float)
        or not math.isfinite(minimum_center_support)
        or not 0 <= minimum_center_support <= 2
        or selection.get("ownership") != "UNKNOWN"
        or selection.get("formal_outputs") != 0
    ):
        raise ValueError("Bound unqualified selection and fixed center threshold required")
    points = [p["center_frame_px"] for p in pool["candidates"]]
    n = pool["parent_count"]
    chosen = []
    for i in selection["group_representative_indices"]:
        if (
            i >= n
            and selection["semantic_class_candidates"][i] not in {"UI", "BACKGROUND"}
            and selection["center_support"][i] >= minimum_center_support
            and all(math.dist(points[i], p) > 2 for p in points[:n])
        ):
            chosen = [i]
            break
    return {
        "pool_sha256": pool["pool_sha256"],
        "selection_indices": list(range(n)) + chosen,
        "parent_prefix_preserved": True,
        "minimum_center_support": minimum_center_support,
        "alternative_identity": "UNKNOWN",
        "qualification": "development_only",
        "ownership": "UNKNOWN",
        "formal_outputs": 0,
    }
