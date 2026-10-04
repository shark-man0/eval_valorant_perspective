"""Offline scaffold experiment; never imported by the production detector.

Input NPZ is private: uint8 grayscale train/holdout/positive/missing/negative
stacks and training-derived uint8 support_regions. No timestamps or labels for
ability values are accepted. Output contains only aggregate metrics/hashes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from valorant_ai_coach.hud.value_identity import feature_score, isolated_features
from valorant_ai_coach.hud.weapon_identity import oriented_matches


def learn_candidate(training: np.ndarray, regions: np.ndarray) -> dict[str, Any]:
    """Freeze reference/mask using training only; never use evaluation cohorts."""
    if training.dtype != np.uint8 or training.ndim != 3 or len(training) < 3:
        raise ValueError("at least three uint8 grayscale training samples required")
    if regions.dtype != np.uint8 or regions.shape != training.shape[1:]:
        raise ValueError("support labels must match the grayscale crop")
    labels = np.unique(regions[regions > 0])
    if not 2 <= len(labels) <= 4 or not np.array_equal(labels, np.arange(1, len(labels) + 1)):
        raise ValueError("two to four independent consecutive support labels required")
    reference = np.median(training, axis=0).astype(np.uint8)
    features = isolated_features(reference, regions)
    recurrence = np.mean(
        np.stack(
            [oriented_matches(*features, *isolated_features(image, regions)) for image in training]
        ),
        axis=0,
    )
    mask = (features[0] & (recurrence >= 0.60)).astype(np.uint8) * 255
    populations = [int(np.count_nonzero(mask[regions == label])) for label in labels]
    if min(populations) < 32:
        raise ValueError("insufficient training reference population in a support group")
    return {
        "reference": reference,
        "features": features,
        "regions": regions.copy(),
        "mask": mask,
        "populations": populations,
    }


def candidate_score(image: np.ndarray, candidate: dict[str, Any]) -> float:
    if image.dtype != np.uint8 or image.shape != candidate["regions"].shape:
        raise ValueError("evaluation image must match training crop geometry")
    return float(
        feature_score(
            candidate["features"],
            isolated_features(image, candidate["regions"]),
            candidate["mask"],
            candidate["regions"],
        )
    )


def cohort_summary(images: np.ndarray, candidate: dict[str, Any]) -> dict[str, Any]:
    scores = np.array([candidate_score(image, candidate) for image in images])
    if not len(scores):
        return {"count": 0, "accepted": 0, "distribution": None}
    return {
        "count": len(scores),
        "accepted": int(np.count_nonzero(scores >= 0.90)),
        "distribution": dict(
            zip(
                ["min", "p10", "p25", "median", "p75", "p90", "max"],
                map(float, np.percentile(scores, [0, 10, 25, 50, 75, 90, 100])),
                strict=True,
            )
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("private_samples", type=Path)
    parser.add_argument("aggregate_output", type=Path)
    args = parser.parse_args()
    cv2.setNumThreads(3)
    with np.load(args.private_samples, allow_pickle=False) as samples:
        expected = {"train", "holdout", "positive", "missing", "negative", "support_regions"}
        if set(samples.files) != expected:
            raise ValueError("private archive must contain only grayscale cohorts/support labels")
        candidate = learn_candidate(samples["train"], samples["support_regions"])
        result = {
            "diagnostic_only": True,
            "threshold": 0.90,
            "learning": "training median; oriented ridge recurrence >= 0.60; all groups",
            "support_populations": candidate["populations"],
            "hashes": {
                name: hashlib.sha256(candidate[name].tobytes()).hexdigest()
                for name in ["reference", "mask", "regions"]
            },
            "cohorts": {
                name: cohort_summary(samples[name], candidate)
                for name in ["train", "holdout", "positive", "missing", "negative"]
            },
        }
    args.aggregate_output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
