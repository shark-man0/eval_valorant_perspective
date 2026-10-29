"""Opt-in temporal learning probes. Proxy scores cannot adopt a recognizer.

Physical-match split is mandatory. Teacher agreement is not correctness; absent
human labels remain UNKNOWN. Models never replace the common rule-based engine.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

import numpy as np
from numpy.typing import NDArray

from .evidence import digest, native_time, source_scope
from .game import SIGNALS

FEATURE_SIGNALS = tuple(sorted(SIGNALS))


def features(row: dict[str, Any]) -> NDArray[np.float64]:
    signals = set(row["signals"])
    context = row["context"]
    timer = context.get("timer_seconds")
    score = context.get("score")
    return np.asarray(
        [float(s in signals) for s in FEATURE_SIGNALS]
        + [
            float(timer is not None),
            float(timer or 0) / 100,
            float(score is not None),
            sum(score or [0, 0]) / 50,
        ],
        dtype=np.float64,
    )


def compare_temporal_learning(
    result: dict[str, Any],
    *,
    physical_matches: dict[str, str],
    train_groups: set[str],
    compare_groups: set[str],
) -> dict[str, Any]:
    if not train_groups or not compare_groups or train_groups & compare_groups:
        raise ValueError("Disjoint nonempty physical-match train/comparison groups required")
    groups: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in result["observations"]:
        sample = row["sample"]
        if sample["source_sha256"] not in physical_matches:
            raise ValueError("Explicit physical-match identity required; do not infer it")
        groups[(*source_scope(sample), row["producer_fingerprint"])].append(row)
    partitions: dict[str, list[tuple[NDArray[np.float64], NDArray[np.float64]]]] = {
        "train": [],
        "compare": [],
    }
    observed_groups: dict[str, set[str]] = {"train": set(), "compare": set()}
    for rows in groups.values():
        rows.sort(key=lambda r: native_time(r["sample"]))
        group = physical_matches[rows[0]["sample"]["source_sha256"]]
        partition = (
            "train" if group in train_groups else "compare" if group in compare_groups else None
        )
        if partition is None:
            continue
        observed_groups[partition].add(group)
        for before, after in zip(rows, rows[1:], strict=False):
            if 0 < native_time(after["sample"]) - native_time(before["sample"]) <= 2 and not (
                after["continuity"].get("discontinuity") is True
                or after["continuity"].get("source_discontinuity") is True
            ):
                partitions[partition].append((features(before), features(after)))
    if observed_groups["train"] & observed_groups["compare"]:
        raise ValueError("Physical-match leakage")
    if not all(partitions.values()):
        return {"status": "INSUFFICIENT_DATA", "adopted": False}
    train_x, train_y = (np.stack(items) for items in zip(*partitions["train"], strict=True))
    test_x, test_y = (np.stack(items) for items in zip(*partitions["compare"], strict=True))
    # Self-supervised next-observation prediction, fixed ridge=1; no heldout tuning.
    design = np.column_stack([train_x, np.ones(len(train_x))])
    test_design = np.column_stack([test_x, np.ones(len(test_x))])
    weights = np.linalg.solve(design.T @ design + np.eye(design.shape[1]), design.T @ train_y)
    predicted = np.clip(test_design @ weights, 0, 1)
    pretext = {
        "persistence_mse": float(np.mean((test_x - test_y) ** 2)),
        "ridge_mse": float(np.mean((predicted - test_y) ** 2)),
        "train_pairs": len(train_x),
        "comparison_pairs": len(test_x),
        "meaning": "next measured feature prediction, not recognition accuracy",
    }
    # Weak labels are the frozen rule engine's outputs, kept explicitly non-GT.
    sample_observations: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in result["observations"]:
        sample_observations[row["sample"]["sample_sha256"]].append(row)
    weak: dict[str, Any] = {}
    for domain in ("round", "life", "camera"):
        train_rows, test_rows = [], []
        for frame in result["frames"]:
            source_rows = sample_observations[frame["sample"]["sample_sha256"]]
            combined = {
                "signals": sorted({v for r in source_rows for v in r["signals"]}),
                "context": {k: v for r in source_rows for k, v in r["context"].items()},
            }
            label = frame[domain]["value"]
            if label == "UNKNOWN":
                continue
            group = physical_matches[frame["sample"]["source_sha256"]]
            point = (
                features(combined),
                label,
                source_scope(frame["sample"]),
                native_time(frame["sample"]),
            )
            if group in train_groups:
                train_rows.append(point)
            elif group in compare_groups:
                test_rows.append(point)
        if not train_rows or not test_rows:
            weak[domain] = {
                "status": "INSUFFICIENT_KNOWN_TEACHER_STATES",
                "recognition_accuracy": None,
            }
            continue
        labels = sorted({row[1] for row in train_rows})
        centroids = {
            label: np.mean([r[0] for r in train_rows if r[1] == label], axis=0) for label in labels
        }
        predictions = []
        for training_point in test_rows:
            distances = {y: float(np.sum((training_point[0] - centroids[y]) ** 2)) for y in labels}
            predictions.append(min(distances, key=lambda y: distances[y]))
        # Train transitions and test memory never cross acquisition or missing gaps.
        transitions: Counter[tuple[str, str]] = Counter()
        for left, right in zip(train_rows, train_rows[1:], strict=False):
            if left[2] == right[2] and 0 < right[3] - left[3] <= 2:
                transitions[left[1], right[1]] += 1
        previous, previous_point = None, None
        reranked = []
        for point in test_rows:
            x = point[0]
            if (
                previous_point is None
                or previous_point[2] != point[2]
                or not 0 < point[3] - previous_point[3] <= 2
            ):
                previous = None
            scores = {y: float(np.sum((x - centroids[y]) ** 2)) for y in labels}
            if previous is not None:
                total = sum(transitions[previous, y] for y in labels)
                for y in labels:
                    scores[y] += 0.1 * -float(
                        np.log((transitions[previous, y] + 1) / (total + len(labels)))
                    )
            previous = min(scores, key=lambda y: scores[y])
            previous_point = point
            reranked.append(previous)
        weak[domain] = {
            "known_teacher_points": len(test_rows),
            "nearest_centroid_teacher_agreement": sum(
                p == r[1] for p, r in zip(predictions, test_rows, strict=True)
            )
            / len(test_rows),
            "reranker_teacher_agreement": sum(
                p == r[1] for p, r in zip(reranked, test_rows, strict=True)
            )
            / len(test_rows),
            "recognition_accuracy": None,
            "labels_are_rule_predictions_not_GT": True,
        }
    return {
        "status": "DEVELOPMENT_PROXY_ONLY",
        "pretext": pretext,
        "weak_and_rerank": weak,
        "train_physical_matches": len(observed_groups["train"]),
        "comparison_physical_matches": len(observed_groups["compare"]),
        "split_fingerprint": digest(
            {"train": sorted(train_groups), "compare": sorted(compare_groups)}
        ),
        "model_fingerprint": digest(weights.tolist()),
        "adopted": False,
        "reason": "No reviewed superiority; retain rule/default recognizers",
        "formal_outputs": 0,
    }
