"""Fit a development portrait-similarity metric on exact, weak TRAIN crops."""

from __future__ import annotations

import argparse
from fractions import Fraction
from pathlib import Path

import cv2
import numpy as np

from valorant_ai_coach.recordings.catalog import RecordingCatalog
from valorant_ai_coach.temporal.evidence import is_sha, native_time
from valorant_ai_coach.temporal.map_recorder_knowledge import _DISC, _vector
from valorant_ai_coach.temporal.replay import file_sha, read_json, write_private

if __package__:
    from .crop_lineage import load_crop_lineage
else:
    from crop_lineage import load_crop_lineage

SCHEMA = "map_local_portrait_metric_v1"
_Y, _X = np.nonzero(_DISC)
# Overlapping regions retain face evidence when one side of a marker is masked.
_REGIONS = np.stack(
    [(abs(_Y - y) <= 3) & (abs(_X - x) <= 3) for y, x in ((3, 3), (3, 7), (5, 5), (7, 3), (7, 7))]
)


def region_similarity(a, b):
    """Compare normalized interior regions at two independently measured centers."""
    shape = (*a.shape[:-1], -1, 3)
    a, b = a.reshape(shape), b.reshape(shape)
    result = []
    for region in _REGIONS:
        x, y = a[..., region, :], b[..., region, :]
        x = x - x.mean(axis=-2, keepdims=True)
        y = y - y.mean(axis=-2, keepdims=True)
        denom = np.sqrt(np.sum(x * x, axis=(-1, -2)) * np.sum(y * y, axis=(-1, -2)))
        result.append(np.sum(x * y, axis=(-1, -2)) / np.maximum(denom, 1e-8))
    return np.stack(result, axis=-1)


def _features(crops):
    if crops.dtype != np.uint8 or crops.ndim != 4 or crops.shape[1:] != (25, 25, 3):
        raise ValueError("Expected 25 by 25 uint8 native BGR center crops")
    return [_vector(crop[7:18, 7:18]) for crop in crops]


def fit_metric(catalog, receipt_path, excluded):
    """Estimate region reliability using adjacent views and weak contrast pairs."""
    source_sha = file_sha(receipt_path)
    receipt = read_json(receipt_path)
    if receipt["schema"] != "map_cnn_training_receipt_v2":
        raise ValueError("Exact crop lineage is required to measure adjacent portraits")
    rng = np.random.default_rng(119)
    physical = set()
    per_match = []
    for record in receipt["recordings"]:
        rid = record["recording_id"]
        catalog.guard([rid], "training")
        recording = catalog.state.recordings[rid]
        match = recording.physical_match_id
        if (
            recording.split != "DEVELOPMENT"
            or recording.learning.get("split") != "TRAIN"
            or recording.source_sha256 != record["source_sha256"]
            or match in physical
            or match in excluded
        ):
            raise ValueError("Distinct DEVELOPMENT TRAIN matches outside evaluation are required")
        physical.add(match)
        patches = Path(record["patches"])
        if file_sha(patches) != record["sha256"]:
            raise ValueError("Training crop archive changed")
        with np.load(patches, allow_pickle=False) as arrays:
            lineage = load_crop_lineage(
                Path(record["lineage"]), record["lineage_sha256"], recording.source_sha256, arrays
            )
            positives = _features(arrays["positive"])
            negatives = [x for x in _features(arrays["background"]) if x is not None]
        frames = lineage["samples"]
        rows = sorted(
            (
                (frames[r["sample_sha256"]], f)
                for r, f in zip(lineage["rows"]["positive"], positives, strict=True)
                if f is not None
            ),
            key=lambda row: native_time(row[0]),
        )
        pairs = [
            (a, b)
            for (first, a), (second, b) in zip(rows, rows[1:], strict=False)
            if (
                0 < native_time(second) - native_time(first) <= Fraction(2, 5)
                and first["acquisition_id"] == second["acquisition_id"]
                and first["native_epoch"] == second["native_epoch"]
                and first["native_pixel_sha256"] != second["native_pixel_sha256"]
            )
        ]
        if not pairs or not negatives:
            raise ValueError("Each TRAIN match needs adjacent positives and background controls")
        a, b = np.asarray(pairs).transpose(1, 0, 2)
        background = np.asarray(negatives)[rng.integers(len(negatives), size=len(a))]
        per_match.append(
            {
                "agent": record["recorder_agent_uuid"],
                "anchors": a,
                "adjacent": b,
                "background": background,
            }
        )
    if len(per_match) < 2 or len({row["agent"] for row in per_match}) < 2:
        raise ValueError("At least two TRAIN matches with distinct Agent labels are required")
    separation = []
    for row in per_match:
        a, b = row["anchors"], row["adjacent"]
        other = np.concatenate([p["anchors"] for p in per_match if p["agent"] != row["agent"]])
        contrast = other[rng.integers(len(other), size=len(a))]
        positive = region_similarity(a, b)
        negative = np.maximum(
            region_similarity(a, row["background"]),
            region_similarity(a, contrast),
        )
        separation.append(np.quantile(positive - negative, 0.25, axis=0))
    # Shrink toward equal weighting so a small corpus cannot erase a region.
    reliability = np.mean(separation, axis=0)
    reliability = np.exp(4 * (reliability - reliability.max()))
    weights = 0.5 / len(reliability) + 0.5 * reliability / reliability.sum()
    if file_sha(receipt_path) != source_sha:
        raise ValueError("Training receipt changed during fit")
    return {
        "schema": SCHEMA,
        "formal_outputs": 0,
        "training_receipt_sha256": source_sha,
        "training_physical_matches": sorted(physical),
        "adjacent_weak_pairs": sum(len(row["anchors"]) for row in per_match),
        "weights": weights.tolist(),
    }


def read_metric(path, evaluation_match):
    sha = file_sha(path)
    receipt = read_json(path)
    matches = receipt["training_physical_matches"]
    weights = np.asarray(receipt["weights"], dtype=float)
    if (
        receipt["schema"] != SCHEMA
        or receipt["formal_outputs"] != 0
        or not is_sha(receipt["training_receipt_sha256"])
        or not isinstance(matches, list)
        or len(set(matches)) != len(matches)
        or len(matches) < 2
        or evaluation_match in matches
        or weights.shape != (len(_REGIONS),)
        or not np.isfinite(weights).all()
        or (weights <= 0).any()
        or not np.isclose(weights.sum(), 1)
        or file_sha(path) != sha
    ):
        raise ValueError("A pinned portrait metric from disjoint TRAIN matches is required")
    return weights, sha


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("recording-catalog", "training-receipt", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--exclude-recording-id", action="append", default=[])
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists() or any((p / ".git").exists() for p in output.parents):
        raise ValueError("Choose a new private output path outside Git worktrees")
    cv2.setNumThreads(1)
    catalog = RecordingCatalog(args.recording_catalog)
    excluded = {
        catalog.state.recordings[rid].physical_match_id for rid in args.exclude_recording_id
    }
    write_private(output, fit_metric(catalog, args.training_receipt, excluded))


if __name__ == "__main__":
    main()
