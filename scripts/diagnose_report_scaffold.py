"""Offline Report separator diagnostics; crops remain in the private NPZ input."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
from report_scaffold_diagnostic import learn_panel_separator_model, score_holdout


def diagnose(samples: dict[str, np.ndarray]) -> dict[str, Any]:
    required = {"training", "holdout", "negative"}
    if set(samples) != required:
        raise ValueError("expected training, holdout and negative grayscale stacks")
    shape = None
    for name, frames in samples.items():
        if frames.dtype != np.uint8 or frames.ndim != 3 or not len(frames):
            raise ValueError(f"invalid {name} grayscale stack")
        if shape is None:
            shape = frames.shape[1:]
        if frames.shape[1:] != shape:
            raise ValueError("cohort crop geometry differs")
    model = learn_panel_separator_model(samples["training"])
    result: dict[str, Any] = {
        "scope": "offline only; no production wiring or threshold override",
        "sample_counts": {name: len(value) for name, value in samples.items()},
        "training": {
            "sufficient": model.sufficient,
            "reason": model.reason,
            "accepted": sum(row["accepted"] for row in model.training_scores),
            "group_count": len(model.groups),
            "diagnostics": model.diagnostics,
        },
        "support_hashes": [
            hashlib.sha256(group.support.astype(np.uint8).tobytes()).hexdigest()
            for group in model.groups
        ],
    }
    for name in ("holdout", "negative"):
        if not model.sufficient:
            result[name] = {
                "evaluated": False,
                "count": len(samples[name]),
                "reason": "training model insufficient",
            }
            continue
        measured = score_holdout(model, samples[name])
        # Per-image scores are private. The negative cohort never validates a model.
        result[name] = {
            "evaluated": True,
            "count": len(samples[name]),
            "accepted": sum(row["accepted"] for row in measured["scores"]),
            "group_support": measured.get("groups", []),
        }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("private_samples", type=Path)
    parser.add_argument("aggregate_output", type=Path)
    args = parser.parse_args()
    with np.load(args.private_samples, allow_pickle=False) as data:
        report = diagnose({name: data[name] for name in data.files})
    args.aggregate_output.write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
