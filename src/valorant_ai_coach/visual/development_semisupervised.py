"""Capped pseudo-weight centroids; unchanged human-negative prototypes and guard."""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict
from typing import Any

import numpy as np

from .development_learning_dataset import (
    FrameLabel,
    FrameRecord,
    Label,
    LabelOrigin,
    validate_dataset,
)
from .development_marker_features import AppearanceCentroids, Array, _digest
from .development_marker_learning import fit_centroids
from .development_pseudo_labels import PseudoLabel, PseudoPolicy, PseudoState, consensus_label


def fit_semisupervised_centroids(
    human_features: Array,
    human_frames: list[FrameRecord],
    human_labels: list[FrameLabel],
    pseudo_features: Array,
    pseudo_records: list[PseudoLabel],
    *,
    policy: PseudoPolicy,
    feature_fingerprint: str,
    pseudo_weight: float = 0.1,
    maximum_class_mass_ratio: float = 0.25,
) -> tuple[AppearanceCentroids, dict[str, Any]]:
    """Semantic pseudo training is DEVTRAIN only; SSL roles never change.

    Validate admission and leakage before fitting. Do not interpret the small
    validation admission gate or the training negative guard as generalization.
    The caller must account for all human labels that trained the pseudo teachers.
    """
    policy.validate()
    if (
        type(pseudo_weight) not in (float, int)
        or not np.isfinite(pseudo_weight)
        or not 0 < pseudo_weight <= 0.25
        or type(maximum_class_mass_ratio) not in (float, int)
        or not np.isfinite(maximum_class_mass_ratio)
        or not 0 < maximum_class_mass_ratio <= 0.5
    ):
        raise ValueError("Explicit small pseudo weight and capped class mass required")
    baseline, human_receipt = fit_centroids(
        human_features,
        human_frames,
        human_labels,
        feature_fingerprint=feature_fingerprint,
        maximum_distance=policy.maximum_distance,
        minimum_margin=policy.minimum_margin,
    )
    if (
        not isinstance(pseudo_features, np.ndarray)
        or pseudo_features.ndim != 2
        or pseudo_features.shape != (len(pseudo_records), human_features.shape[1])
        or len(pseudo_records) > 512
        or not np.isfinite(pseudo_features).all()
    ):
        raise ValueError("Bounded paired finite pseudo features required")
    for record in pseudo_records:
        record.validate()
        if (
            record.state is not PseudoState.PSEUDO_ADMITTED_FOR_TRAINING
            or record.policy_fingerprint != policy.fingerprint
            or record.label not in policy.training_classes
            or consensus_label(record.votes, policy) is not record.label
        ):
            raise ValueError("Only fixed-policy admitted pseudo training records permitted")
    validate_dataset(
        human_frames + [r.frame for r in pseudo_records],
        human_labels
        + [
            FrameLabel(r.frame.frame_sha256, r.label, LabelOrigin.PSEUDO, r.frame.roi_xywh)
            for r in pseudo_records
        ],
    )
    if len({r.patch_sha256 for r in pseudo_records}) != len(pseudo_records):
        raise ValueError("Exact duplicate pseudo patches cannot amplify supervision")
    if any(n > 2 for n in Counter(r.frame.source_sha256 for r in pseudo_records).values()) or len(
        {r.frame.frame_sha256 for r in pseudo_records}
    ) != len(pseudo_records):
        raise ValueError("Pseudo training requires source and native-frame diversity caps")
    human_counts = Counter(label.label.value for label in human_labels)
    counts = Counter(r.label.value for r in pseudo_records)
    if any(n > 2 * human_counts[name] for name, n in counts.items()):
        raise ValueError("Pseudo count exceeds paired human class budget")
    units = human_features / np.linalg.norm(human_features, axis=1, keepdims=True)
    norms = np.linalg.norm(pseudo_features, axis=1, keepdims=True)
    if (norms <= 1e-12).any():
        raise ValueError("Nonzero pseudo features required")
    pseudo_units = pseudo_features / np.maximum(norms, 1e-12)
    centers = baseline.centers.copy()
    effective_mass: dict[str, float] = {}
    for i, name in enumerate(baseline.labels):
        ids = [j for j, r in enumerate(pseudo_records) if r.label.value == name]
        if not ids:
            continue
        mass = min(pseudo_weight * len(ids), maximum_class_mass_ratio * human_counts[name])
        effective_mass[name] = mass
        members = units[[j for j, label in enumerate(human_labels) if label.label.value == name]]
        centers[i] = (members.sum(axis=0) + mass * pseudo_units[ids].mean(axis=0)) / (
            len(members) + mass
        )
    candidate = AppearanceCentroids(
        centers,
        list(baseline.labels),
        feature_fingerprint,
        maximum_distance=policy.maximum_distance,
        minimum_margin=policy.minimum_margin,
    )
    before = baseline.classify(human_features, feature_fingerprint=feature_fingerprint)
    after = candidate.classify(human_features, feature_fingerprint=feature_fingerprint)
    regressions = [
        i
        for i, (label, b, a) in enumerate(zip(human_labels, before, after, strict=True))
        if label.label is not Label.PLAYER
        and b["appearance_class_candidate"] == label.label.value
        and a["appearance_class_candidate"] != label.label.value
    ]
    model = baseline if regressions else candidate
    return model, {
        "method": "capped_pseudo_centroids_v1",
        "human_fit": human_receipt,
        "pseudo_training_records": len(pseudo_records),
        "pseudo_weight": pseudo_weight,
        "effective_class_mass": effective_mass,
        "pseudo_origin": "PSEUDO, not human GT",
        "pseudo_dataset_fingerprint": _digest([asdict(r) for r in pseudo_records]),
        "human_negative_regression_indices": regressions,
        "candidate_rolled_back": bool(regressions),
        "semi_supervised_applied": bool(pseudo_records) and not regressions,
        "teacher_human_budget_must_be_accounted_for": True,
        "classifier_fingerprint": model.fingerprint,
        "policy_fingerprint": policy.fingerprint,
        "ownership": "UNKNOWN",
        "qualification": "development_only",
        "formal_outputs": 0,
    }
