"""Small reproducible learning utilities; semantic labels require human evidence."""

from __future__ import annotations

import hashlib
import io
import json
import zipfile
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np

from .development_learning_dataset import (
    FrameLabel,
    FrameRecord,
    Use,
    validate_dataset,
    validate_use,
)
from .development_marker_features import AppearanceCentroids, Array, _digest, _private_model_output


def fit_centroids(
    features: Array, frames: list[FrameRecord], labels: list[FrameLabel], *,
    feature_fingerprint: str, maximum_distance: float, minimum_margin: float,
) -> tuple[AppearanceCentroids, dict[str, Any]]:
    """Fit only human-confirmed development-train patch labels; no pseudo GT."""
    if (not isinstance(features, np.ndarray) or features.ndim != 2
            or not 2 <= len(features) <= 4096 or not 1 <= features.shape[1] <= 4096
            or len(frames) != len(features) or len(labels) != len(features)
            or not np.isfinite(features).all()):
        raise ValueError("Bounded paired features, native frames and human labels required")
    validate_dataset(frames, labels)
    for frame, label in zip(frames, labels, strict=True):
        validate_use(frame, Use.SUPERVISED_TRAIN, label, dataset_frames=frames)
    names = sorted({label.label.value for label in labels})
    if len(names) < 2:
        raise ValueError("At least two confirmed semantic classes required")
    norms = np.linalg.norm(features, axis=1, keepdims=True)
    if (norms <= 1e-12).any():
        raise ValueError("Nonzero finite learning features required")
    unit = features/norms
    centers = np.stack([unit[[i for i, label in enumerate(labels)
                              if label.label.value == name]].mean(axis=0) for name in names])
    model = AppearanceCentroids(centers, names, feature_fingerprint,
                               maximum_distance=maximum_distance, minimum_margin=minimum_margin)
    receipt = {"method": "human_appearance_centroids_v1", "training_patches": len(frames),
               "physical_groups": len({f.leakage_group_id for f in frames}),
               "labels": {name: sum(label.label.value == name for label in labels)
                          for name in names},
               "dataset_fingerprint": _digest([asdict(f) for f in frames]),
               "human_labels_fingerprint": _digest([asdict(label) for label in labels]),
               "feature_fingerprint": feature_fingerprint,
               "classifier_fingerprint": model.fingerprint,
               "ownership": "UNKNOWN", "qualification": "development_only", "formal_outputs": 0}
    return model, receipt


def save_centroids(model: AppearanceCentroids, output: Path) -> str:
    """Write a new local tensor/JSON snapshot; never pickle or overwrite."""
    _private_model_output(output)
    metadata = {"version": 1, "labels": list(model.labels),
                "feature_fingerprint": model.feature_fingerprint,
                "maximum_distance": model.maximum_distance, "minimum_margin": model.minimum_margin,
                "classifier_fingerprint": model.fingerprint}
    buffer = io.BytesIO()
    np.savez_compressed(buffer, centers=model.centers,
                        metadata=np.frombuffer(
                            json.dumps(metadata, sort_keys=True).encode(), np.uint8))
    content = buffer.getvalue()
    with output.open("xb") as stream:
        stream.write(content)
    return hashlib.sha256(content).hexdigest()


def load_centroids(path: Path, expected_sha256: str) -> AppearanceCentroids:
    """Verify exact snapshot bytes and bounded expansion before NumPy parsing."""
    if not path.is_file() or path.stat().st_size > 2*1024**2:
        raise ValueError("Bounded local classifier snapshot required")
    content = path.read_bytes()
    if hashlib.sha256(content).hexdigest() != expected_sha256:
        raise ValueError("Classifier bytes changed")
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        if (set(archive.namelist()) != {"centers.npy", "metadata.npy"}
                or len(archive.infolist()) != 2
                or sum(member.file_size for member in archive.infolist()) > 2*1024**2):
            raise ValueError("Bounded tensor-only classifier members required")
    with np.load(io.BytesIO(content), allow_pickle=False) as snapshot:
        raw = snapshot["metadata"]
        if raw.dtype != np.uint8 or raw.ndim != 1 or len(raw) > 16384:
            raise ValueError("Small JSON classifier metadata required")
        metadata = json.loads(raw.tobytes())
        if (set(metadata) != {"version", "labels", "feature_fingerprint", "maximum_distance",
                             "minimum_margin", "classifier_fingerprint"}
                or metadata["version"] != 1):
            raise ValueError("Known classifier format required")
        model = AppearanceCentroids(snapshot["centers"], metadata["labels"],
                                    metadata["feature_fingerprint"],
                                    maximum_distance=metadata["maximum_distance"],
                                    minimum_margin=metadata["minimum_margin"])
    if model.fingerprint != metadata["classifier_fingerprint"]:
        raise ValueError("Classifier fingerprint mismatch")
    return model


def cluster_features(
    features: Array, frames: list[FrameRecord], *, clusters: int = 6, seed: int = 270027,
) -> dict[str, Any]:
    """Bounded deterministic spherical K-means; cluster meaning stays UNKNOWN.

    Fit uses admitted train-only inputs. Empty clusters retain their prior center;
    no semantic supervision or temporal positives are supplied to clustering.
    """
    if (not isinstance(features, np.ndarray) or features.ndim != 2
            or not 2 <= len(features) <= 8192 or len(frames) != len(features)
            or not 1 <= features.shape[1] <= 4096 or not np.isfinite(features).all()
            or type(clusters) is not int or not 2 <= clusters <= min(16, len(features))
            or type(seed) is not int or not 0 <= seed < 2**31):
        raise ValueError("Bounded finite train features and cluster parameters required")
    validate_dataset(frames)
    if any(f.split.value not in {"SSL_TRAIN", "DEVELOPMENT_TRAIN"} for f in frames):
        raise ValueError("Clustering fit cannot consume validation or frozen test")
    norms = np.linalg.norm(features, axis=1, keepdims=True)
    if (norms <= 1e-12).any():
        raise ValueError("Nonzero clustering features required")
    unit = features/norms
    rng = np.random.default_rng(seed)
    centers = unit[rng.choice(len(unit), clusters, replace=False)].copy()
    previous = None
    for _iteration in range(50):
        assignments = np.argmax(unit@centers.T, axis=1)
        if previous is not None and np.array_equal(previous, assignments):
            break
        previous = assignments.copy()
        for k in range(clusters):
            members = unit[assignments == k]
            if len(members):
                center = members.mean(axis=0)
                norm = np.linalg.norm(center)
                if norm > 1e-12:
                    centers[k] = center/norm
    # Reassign after the last center update, including a maximum-iteration exit.
    assignments = np.argmax(unit@centers.T, axis=1)
    return {"assignments": assignments.tolist(), "centers": centers.tolist(),
            "cluster_semantics": ["UNKNOWN"]*clusters, "iterations": _iteration+1,
            "method": "spherical_kmeans_train_only_v1", "seed": seed,
            "dataset_fingerprint": _digest([asdict(f) for f in frames]),
            "ownership": "UNKNOWN", "qualification": "development_only", "formal_outputs": 0}
