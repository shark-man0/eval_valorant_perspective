"""Small NumPy learners for continual, mostly-unlabeled recognition.

* ``fit_ssl_projection``: self-supervised linear projection (PCA whitening,
  i.e. the optimal linear masked/denoising reconstruction) fitted on unlabeled
  crops of the TRAIN split only.
* ``PrototypeClassifier``: cosine nearest-class-mean with an explicit abstain
  margin. Anchors can come from external knowledge (official images), from
  cross-modal weak labels, or from human labels; their provenance is tracked.
* ``self_train``: confidence-gated pseudo-labelling on unlabeled TRAIN data.
  Pseudo-labels never leave the model; they are not promoted to ground truth.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

Array = NDArray[np.float64]


def l2_normalize(x: Array, axis: int = -1) -> Array:
    norm = np.linalg.norm(x, axis=axis, keepdims=True)
    return x / np.maximum(norm, 1e-12)


@dataclass(frozen=True)
class Projection:
    mean: Array
    components: Array  # (k, d)
    scale: Array  # (k,)

    def __call__(self, x: Array) -> Array:
        return l2_normalize(((x - self.mean) @ self.components.T) / self.scale)

    def arrays(self, prefix: str = "proj_") -> dict[str, Array]:
        return {f"{prefix}mean": self.mean, f"{prefix}components": self.components,
                f"{prefix}scale": self.scale}


def identity_projection(dim: int) -> Projection:
    return Projection(np.zeros(dim), np.eye(dim), np.ones(dim))


def fit_ssl_projection(unlabeled: Array, k: int = 64, eps: float = 1e-3, *,
                       whiten: bool = False) -> Projection:
    """Top-k principal subspace of unlabeled data (optimal linear reconstruction).

    Whitening is off by default: on DEVELOPMENT portraits it amplified
    low-variance directions in which the official-icon anchors are out of
    domain, and frozen-test consistency fell from 0.47 to 0.29.
    """
    if len(unlabeled) < 2:
        raise ValueError("Need unlabeled samples to fit a projection")
    mean = unlabeled.mean(axis=0)
    centered = unlabeled - mean
    _, singular, vt = np.linalg.svd(centered, full_matrices=False)
    k = min(k, vt.shape[0])
    if not whiten:
        return Projection(mean, vt[:k], np.ones(k))
    variance = singular[:k] ** 2 / max(1, len(unlabeled) - 1)
    return Projection(mean, vt[:k], np.sqrt(variance + eps))


@dataclass
class PrototypeClassifier:
    classes: tuple[str, ...]
    prototypes: Array  # (C, k), L2-normalized
    margin: float = 0.0

    @classmethod
    def fit(cls, z: Array, labels: list[str], classes: tuple[str, ...] | None = None,
            weights: Array | None = None) -> PrototypeClassifier:
        classes = classes or tuple(sorted(set(labels)))
        w = np.ones(len(labels)) if weights is None else weights
        protos = np.zeros((len(classes), z.shape[1]))
        index = {c: i for i, c in enumerate(classes)}
        for row, label, weight in zip(z, labels, w, strict=True):
            if label in index:
                protos[index[label]] += weight * row
        return cls(classes, l2_normalize(protos))

    def scores(self, z: Array) -> Array:
        return z @ self.prototypes.T

    def predict(self, z: Array) -> tuple[list[str | None], Array, Array]:
        """Labels (None = abstain), top score, top-minus-second margin."""
        s = self.scores(z)
        order = np.argsort(-s, axis=1)
        top = s[np.arange(len(s)), order[:, 0]]
        second = s[np.arange(len(s)), order[:, 1]] if s.shape[1] > 1 else np.zeros(len(s))
        gap = top - second
        labels = [self.classes[i] if g >= self.margin else None
                  for i, g in zip(order[:, 0], gap, strict=True)]
        return labels, top, gap


def choose_margin(classifier: PrototypeClassifier, z: Array, truth: list[str],
                  max_abstain: float = 0.2) -> float:
    """Largest-accuracy margin on VALIDATION within an abstain budget."""
    if len(z) == 0:
        return 0.0
    _, _, gap = classifier.predict(z)
    raw = np.argmax(classifier.scores(z), axis=1)
    correct = np.array([classifier.classes[i] == t for i, t in zip(raw, truth, strict=True)])
    best_margin, best_acc = 0.0, correct.mean()
    for margin in np.quantile(gap, np.linspace(0, max_abstain, 11)):
        kept = gap >= margin
        if kept.mean() < 1 - max_abstain or not kept.any():
            continue
        accuracy = correct[kept].mean()
        if accuracy > best_acc + 1e-9:
            best_margin, best_acc = float(margin), accuracy
    return best_margin


def self_train(anchor_z: Array, anchor_labels: list[str], unlabeled_z: Array,
               classes: tuple[str, ...], *, rounds: int = 3, min_gap: float = 0.05,
               max_per_class: int = 400, anchor_weight: float = 5.0
               ) -> tuple[PrototypeClassifier, dict[str, int]]:
    """Confidence-gated self-training. Returns the classifier and pseudo-label counts."""
    classifier = PrototypeClassifier.fit(anchor_z, anchor_labels, classes,
                                         np.full(len(anchor_labels), anchor_weight))
    counts: dict[str, int] = {}
    for _ in range(rounds):
        if len(unlabeled_z) == 0:
            break
        scores = classifier.scores(unlabeled_z)
        order = np.argsort(-scores, axis=1)
        top = scores[np.arange(len(scores)), order[:, 0]]
        gap = top - scores[np.arange(len(scores)), order[:, 1]]
        chosen_z, chosen_labels = [], []
        counts = {}
        for class_index, name in enumerate(classes):
            members = np.where((order[:, 0] == class_index) & (gap >= min_gap))[0]
            members = members[np.argsort(-gap[members])][:max_per_class]
            counts[name] = int(len(members))
            chosen_z.append(unlabeled_z[members])
            chosen_labels.extend([name] * len(members))
        z = np.vstack([anchor_z, *chosen_z])
        labels = list(anchor_labels) + chosen_labels
        weights = np.concatenate([np.full(len(anchor_labels), anchor_weight),
                                  np.ones(len(chosen_labels))])
        classifier = PrototypeClassifier.fit(z, labels, classes, weights)
    return classifier, counts
