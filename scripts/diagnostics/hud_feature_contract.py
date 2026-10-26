"""Offline learned-feature evidence gates. No production events or repaired pixels."""
from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Sequence
from fractions import Fraction
from pathlib import Path
from typing import Any, cast

import cv2
import numpy as np
from numpy.typing import NDArray

from scripts.temporal_gt.contract import canonical_hash

ROLES = frozenset({"SSL_TRAIN", "DEVELOPMENT_TRAIN", "DEVELOPMENT_VALIDATION",
                   "DEVELOPMENT_FROZEN_TEST"})
FRAME_FIELDS = ("source_id", "source_sha256", "tick", "time_base", "epoch",
                "encoded_sha256", "pixel_sha256")


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _hash(value: Any) -> bool:
    return (isinstance(value, str) and len(value) == 64
            and all(c in "0123456789abcdef" for c in value))


def validate_frame(frame: dict[str, Any]) -> None:
    if (not all(k in frame for k in FRAME_FIELDS)
            or not isinstance(frame["source_id"], str) or not frame["source_id"]
            or not isinstance(frame["epoch"], str) or not frame["epoch"]
            or type(frame["tick"]) is not int
            or not all(_hash(frame[k]) for k in (
                "source_sha256", "encoded_sha256", "pixel_sha256"))):
        raise ValueError("invalid_native_identity")
    try:
        base = Fraction(frame["time_base"])
    except (ValueError, ZeroDivisionError, TypeError) as error:
        raise ValueError("invalid_native_time_base") from error
    if base <= 0:
        raise ValueError("invalid_native_time_base")


def validate_split(records: Sequence[dict[str, Any]], *,
                   allowed_development: dict[str, str]) -> str:
    """Check physical-match, source, exact-image and role leakage before fitting.

    allowed_development must come from a verified registry receipt, never from
    this image manifest. Group equality is a curator attestation, not a SHA test.
    """
    groups: dict[str, str] = {}
    sources: dict[str, tuple[str, str]] = {}
    images: dict[str, str] = {}
    if not records:
        raise ValueError("empty_feature_dataset")
    for row in records:
        validate_frame(row["frame"])
        frame, group, role = row["frame"], row["physical_match_id"], row["role"]
        if (not isinstance(group, str) or not group or role not in ROLES
                or allowed_development.get(frame["source_id"]) != frame["source_sha256"]):
            raise ValueError("unadmitted_or_unassigned_source")
        if group in groups and groups[group] != role:
            raise ValueError("physical_match_split_leakage")
        groups[group] = role
        identity = (group, role)
        if frame["source_sha256"] in sources and sources[frame["source_sha256"]] != identity:
            raise ValueError("source_split_leakage")
        sources[frame["source_sha256"]] = identity
        # Parent image hashes detect exact copies even when the ROI differs.
        image = frame["pixel_sha256"]
        if image in images and images[image] != role:
            raise ValueError("image_split_leakage")
        images[image] = role
        if not _hash(row["profile_sha256"]) or not _hash(row["patch_sha256"]):
            raise ValueError("missing_feature_binding")
    return canonical_hash(list(records))


def verify_patch(row: dict[str, Any], *, profile_sha256: str) -> NDArray[np.uint8]:
    validate_frame(row["frame"])
    if row["profile_sha256"] != profile_sha256:
        raise ValueError("feature_profile_mismatch")
    path = Path(row["path"])
    if file_hash(path) != row["patch_sha256"]:
        raise ValueError("feature_encoded_hash_mismatch")
    image = cv2.imread(str(path))
    if (image is None or image.dtype != np.uint8 or image.ndim != 3
            or image.shape[2] != 3 or min(image.shape[:2]) < 2
            or hashlib.sha256(image.tobytes()).hexdigest() != row["patch_pixel_sha256"]):
        raise ValueError("feature_pixel_hash_mismatch")
    x, y, xx, yy = row["roi"]
    if (not all(type(v) is int for v in (x, y, xx, yy))
            or not (0 <= x < xx <= row["source_width"]
                    and 0 <= y < yy <= row["source_height"])
            or image.shape[:2] != (yy-y, xx-x)):
        raise ValueError("feature_roi_mismatch")
    return cast(NDArray[np.uint8], image)


def verify_weights(path: Path, expected_sha256: str, *, max_bytes: int) -> None:
    if (not _hash(expected_sha256) or path.stat().st_size > max_bytes
            or file_hash(path) != expected_sha256):
        raise ValueError("feature_weights_mismatch")


def adjacent_change(before: dict[str, Any], after: dict[str, Any],
                    first: NDArray[np.float32], second: NDArray[np.float32], *,
                    expected_step: int) -> dict[str, Any]:
    """An image-change diagnostic only. A scalar is never a semantic End."""
    for frame in (before, after):
        validate_frame(frame)
    if (type(expected_step) is not int or expected_step <= 0
            or any(frame.get("discontinuity", False) is not False
                   for frame in (before, after))
            or any(before[k] != after[k] for k in (
                "source_id", "source_sha256", "time_base", "epoch"))
            or after["tick"] - before["tick"] != expected_step):
        return {"state": "UNKNOWN", "reason": "native_pair_discontinuity", "change": None}
    if (first.ndim != 1 or first.shape != second.shape or not first.size
            or not np.isfinite(first).all() or not np.isfinite(second).all()):
        raise ValueError("invalid_feature_vector")
    denominator = float(np.linalg.norm(first) * np.linalg.norm(second))
    if denominator <= 1e-12:
        return {"state": "UNKNOWN", "reason": "zero_feature_norm", "change": None}
    change = 1.0 - float(np.dot(first, second)) / denominator
    return {"state": "UNCONFIRMED_IMAGE_CHANGE", "change": max(0., min(2., change)),
            "interval_ticks": [before["tick"], after["tick"]], "internal_End_tick": None}


def guarded_score(reader_value: str | None, learned_value: str | None, *,
                  source_valid: bool, geometry_valid: bool) -> dict[str, Any]:
    if source_valid is not True:
        raise ValueError("unverified_feature_source")
    value = (reader_value if geometry_valid is True and reader_value is not None
             and re.fullmatch(r"(?:0|[1-9][0-9]?)", reader_value) is not None
             and reader_value == learned_value else None)
    return {"value": value, "state": "UNKNOWN" if value is None else "DEVELOPMENT_AGREEMENT",
            "semantic_correctness_verified": False, "formal_events": []}


def deterministic_kmeans(features: NDArray[np.float32], clusters: int, *,
                         seed: int = 271027, iterations: int = 40
                         ) -> tuple[NDArray[np.int64], NDArray[np.float32]]:
    if (features.ndim != 2 or not np.isfinite(features).all()
            or not 1 <= clusters <= len(features) or iterations < 1):
        raise ValueError("invalid_cluster_input")
    rng = np.random.default_rng(seed)
    centres = features[rng.choice(len(features), clusters, replace=False)].copy()
    labels = np.zeros(len(features), dtype=np.int64)
    for _ in range(iterations):
        distance = ((features[:, None, :] - centres[None, :, :]) ** 2).sum(axis=2)
        labels = np.asarray(distance.argmin(axis=1), dtype=np.int64)
        updated = np.stack([features[labels == i].mean(axis=0) if np.any(labels == i)
                            else centres[i] for i in range(clusters)]).astype(np.float32)
        if np.array_equal(updated, centres):
            break
        centres = updated
    return labels, centres


def cluster_entropy(counts: Sequence[int]) -> float:
    total = sum(counts)
    return -sum((x/total)*math.log2(x/total) for x in counts if x > 0) if total else 0.
