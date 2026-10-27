"""Bounded active-review proposals with a separate, uniform audit channel.

Selection reduces a proposed queue, not measured human effort. Appearance/time
redundancy never merges physical markers or propagates semantic labels.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import asdict, dataclass
from fractions import Fraction
from typing import Any

import numpy as np

from .development_learning_dataset import FrameRecord, Label, Split, _is_sha256, validate_dataset
from .development_marker_features import _digest

IMPORTANCE = {
    "raw_geometry": 0.25,
    "deathlike": 0.25,
    "known_regression": 0.40,
    "close_marker": 0.15,
    "player_nonplayer_conflict": 0.20,
}


@dataclass(frozen=True, slots=True)
class ReviewCandidate:
    frame: FrameRecord
    patch_sha256: str
    feature: tuple[float, ...]
    feature_fingerprint: str
    generator_fingerprint: str
    cluster_id: int
    cluster_fingerprint: str
    margin: float
    known_distance: float
    teacher_labels: tuple[Label, ...]
    flags: tuple[str, ...] = ()
    map_hint: str = "UNKNOWN"
    annotation_status: str = "UNREVIEWED"

    def validate(self) -> None:
        self.frame.validate()
        if self.frame.split not in {Split.SSL_TRAIN, Split.DEVELOPMENT_TRAIN}:
            raise ValueError("Review selection cannot consume validation/frozen data")
        if (
            not all(
                _is_sha256(v)
                for v in (
                    self.patch_sha256,
                    self.feature_fingerprint,
                    self.generator_fingerprint,
                    self.cluster_fingerprint,
                )
            )
            or not isinstance(self.feature, tuple)
            or not 1 <= len(self.feature) <= 4096
            or any(type(v) not in (float, int) or not math.isfinite(v) for v in self.feature)
            or type(self.cluster_id) is not int
            or not -1 <= self.cluster_id <= 15
            or any(
                type(v) not in (float, int) or not math.isfinite(v) or not 0 <= v <= 2
                for v in (self.margin, self.known_distance)
            )
            or not 1 <= len(self.teacher_labels) <= 8
            or not isinstance(self.teacher_labels, tuple)
            or not isinstance(self.flags, tuple)
            or any(not isinstance(label, Label) for label in self.teacher_labels)
            or len(set(self.flags)) != len(self.flags)
            or any(flag not in IMPORTANCE for flag in self.flags)
            or not isinstance(self.map_hint, str)
            or not 1 <= len(self.map_hint) <= 100
            or self.annotation_status not in {"UNREVIEWED", "HUMAN_CONFIRMED", "OUT_OF_SCOPE"}
        ):
            raise ValueError("Bounded native review candidate and feature provenance required")

    @property
    def fingerprint(self) -> str:
        return _digest(asdict(self))


@dataclass(frozen=True, slots=True)
class ReviewPolicy:
    hard_slots: int = 8
    audit_slots: int = 2
    seed: int = 270127
    per_physical_group: int = 2
    per_cluster: int = 2
    temporal_seconds: float = 0.5
    near_similarity: float = 0.995

    def validate(self) -> None:
        if (
            any(
                type(v) is not int
                for v in (
                    self.hard_slots,
                    self.audit_slots,
                    self.seed,
                    self.per_physical_group,
                    self.per_cluster,
                )
            )
            or self.hard_slots < 0
            or self.audit_slots < 0
            or not 1 <= self.hard_slots + self.audit_slots <= 10
            or not 0 <= self.seed < 2**31
            or not 1 <= self.per_physical_group <= 10
            or not 1 <= self.per_cluster <= 10
            or type(self.temporal_seconds) not in (float, int)
            or not math.isfinite(self.temporal_seconds)
            or not 0 <= self.temporal_seconds <= 2
            or type(self.near_similarity) not in (float, int)
            or not math.isfinite(self.near_similarity)
            or not 0.9 <= self.near_similarity <= 1
        ):
            raise ValueError("Fixed review policy with at most ten total slots required")

    @property
    def fingerprint(self) -> str:
        self.validate()
        return _digest(
            {
                "method": "diverse_active_review_v1",
                **asdict(self),
                "hard_role": "DEVELOPMENT_TRAIN",
                "importance": IMPORTANCE,
                "semantic_label_propagation": False,
            }
        )


def _priority(candidate: ReviewCandidate) -> float:
    # A ranking heuristic, never an error probability or actor confidence.
    return (
        0.35 * (1 - min(candidate.margin / 0.08, 1))
        + 0.25 * (len(set(candidate.teacher_labels)) > 1)
        + 0.20 * (Label.UNKNOWN in candidate.teacher_labels)
        + 0.20 * min(candidate.known_distance / 0.35, 1)
        + sum(IMPORTANCE[flag] for flag in candidate.flags)
    )


def select_review(
    candidates: list[ReviewCandidate],
    *,
    policy: ReviewPolicy,
    simulate_existing_reveal: bool = False,
) -> dict[str, Any]:
    """Select hard cases and an independent uniform draw before hard ranking.

    Hard slots are semantic-training-eligible only. Audit draws may also inspect
    SSL_TRAIN and retain their original role. A simulation reveals existing human
    labels to a learner; it neither downgrades annotations nor performs reviews.
    Every candidate and suppressed member retains its original provenance.
    """
    policy.validate()
    if not 1 <= len(candidates) <= 8192 or type(simulate_existing_reveal) is not bool:
        raise ValueError("Bounded candidates and explicit simulation mode required")
    for candidate in candidates:
        candidate.validate()
    validate_dataset([c.frame for c in candidates])
    if len({(c.feature_fingerprint, len(c.feature)) for c in candidates}) != 1:
        raise ValueError("One fixed feature view required for comparable review distances")
    ids = [c.fingerprint for c in candidates]
    by_id = {key: c for key, c in zip(ids, candidates, strict=True)}
    status = "HUMAN_CONFIRMED" if simulate_existing_reveal else "UNREVIEWED"
    eligible = sorted(key for key, c in by_id.items() if c.annotation_status == status)
    # Exact duplicate content is a review group, not a semantic/physical label.
    unique: list[str] = []
    hashes: dict[str, str] = {}
    suppressed: dict[str, str] = {}
    for key in eligible:
        patch = by_id[key].patch_sha256
        if patch in hashes:
            suppressed[key] = hashes[patch]
        else:
            hashes[patch] = key
            unique.append(key)
    k = min(policy.audit_slots, len(unique))
    audit = (
        [
            unique[int(i)]
            for i in np.random.default_rng(policy.seed).choice(len(unique), k, replace=False)
        ]
        if k
        else []
    )
    audit_frames = {by_id[key].frame.frame_sha256 for key in audit}
    hard = [
        key
        for key in unique
        if key not in audit
        and by_id[key].frame.frame_sha256 not in audit_frames
        and by_id[key].frame.split is Split.DEVELOPMENT_TRAIN
    ]
    priorities = {key: _priority(by_id[key]) for key in hard}
    # Greedy appearance redundancy only within a native acquisition/time window.
    reps: list[str] = []
    buckets: dict[tuple[str, str, str], list[str]] = {}
    units = {}
    times = {}
    for key in hard:
        c = by_id[key]
        v = np.asarray(c.feature, dtype=np.float64)
        units[key] = v / max(float(np.linalg.norm(v)), 1e-12)
        times[key] = Fraction(c.frame.native_pts_tick) * Fraction(c.frame.native_time_base)
    window = Fraction(str(policy.temporal_seconds))
    for key in sorted(hard, key=lambda key: (-priorities[key], key)):
        c = by_id[key]
        group = c.frame.source_sha256, c.frame.acquisition_id, c.frame.native_epoch
        prior = buckets.setdefault(group, [])
        near = next(
            (
                p
                for p in prior
                if abs(times[key] - times[p]) <= window
                and float(units[key] @ units[p]) >= policy.near_similarity
            ),
            None,
        )
        if near is not None:
            suppressed[key] = near
        else:
            prior.append(key)
            reps.append(key)
    selected: list[str] = []
    groups: Counter[str] = Counter()
    clusters: Counter[int] = Counter()
    used_frames: set[str] = set()
    maps: set[str] = set()
    while len(selected) < policy.hard_slots:
        allowed = [
            key
            for key in reps
            if key not in selected
            and groups[by_id[key].frame.leakage_group_id] < policy.per_physical_group
            and clusters[by_id[key].cluster_id] < policy.per_cluster
            and by_id[key].frame.frame_sha256 not in used_frames
        ]
        if not allowed:
            break

        def score(key: str) -> tuple[float, str]:
            c = by_id[key]
            diversity = (
                0.05 * (not groups[c.frame.leakage_group_id])
                + 0.05 * (not clusters[c.cluster_id])
                + 0.02 * (c.map_hint != "UNKNOWN" and c.map_hint not in maps)
            )
            return -(priorities[key] + diversity), key

        key = min(allowed, key=score)
        selected.append(key)
        c = by_id[key]
        groups[c.frame.leakage_group_id] += 1
        clusters[c.cluster_id] += 1
        used_frames.add(c.frame.frame_sha256)
        maps.add(c.map_hint)
    result = {
        "policy_fingerprint": policy.fingerprint,
        "input_fingerprint": _digest(sorted(ids)),
        "mode": "RETROSPECTIVE_LABEL_REVEAL" if simulate_existing_reveal else "PROPOSED_REVIEW",
        "hard_ids": selected,
        "audit_ids": audit,
        "audit_sampling": {
            "method": "uniform_without_replacement_before_hard_ranking",
            "population": len(unique),
            "draws": k,
            "per_item_inclusion_probability": k / len(unique) if unique else None,
        },
        "selected": [
            {
                "item_id": key,
                "channel": "hard" if key in selected else "audit",
                "candidate": asdict(by_id[key]),
                "priority": priorities.get(key),
                "score_is_probability": False,
                "human_center_verified": False,
            }
            for key in selected + audit
        ],
        "raw_inputs": len(candidates),
        "unique_item_ids": len(by_id),
        "eligible_annotation_status": status,
        "eligible_items": len(eligible),
        "exact_unique_review_items": len(unique),
        "redundancy_suppressed": suppressed,
        "hard_representatives_after_near_dedup": len(reps),
        "selected_count": len(selected) + len(audit),
        "original_candidates_or_coordinates_removed": 0,
        "semantic_labels_propagated": 0,
        "new_human_reviews_performed": 0,
        "human_review_time_sec": None,
        "ownership": "UNKNOWN",
        "formal_outputs": 0,
        "scope": "Review queue only. Audit needs actual labels before estimating any error. "
        "Appearance/time groups do not establish physical identity or label equivalence.",
    }
    result["selection_fingerprint"] = _digest(result)
    return result
