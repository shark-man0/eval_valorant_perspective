"""Diagnostic-only edge similarity; no qualification threshold or runtime hook.

A bidirectional soft edge coverage penalizes missing and extra structure.
Unsigned Sobel orientation preserves contrast-polarity invariance. Spatial
weight is exp(-distance squared / 2), with a fixed two-pixel neighborhood:
this explicitly measures pixel-scale rendering jitter, not geometric alignment.
"""
from __future__ import annotations

import math
from typing import Any

import cv2
import numpy as np


def features(gray: np.ndarray, mask: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    if gray.ndim != 2 or gray.dtype != np.uint8 or mask.shape != gray.shape:
        raise ValueError("native uint8 gray image and same-sized mask required")
    edges = (cv2.Canny(gray, 60, 150) > 0) & (mask > 0)
    edges[:2, :] = edges[-2:, :] = False
    edges[:, :2] = edges[:, -2:] = False
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1)
    denominator = np.maximum(gx * gx + gy * gy, 1e-6)
    return edges, (gx * gx - gy * gy) / denominator, 2 * gx * gy / denominator


def _coverage(source: tuple[np.ndarray, np.ndarray, np.ndarray],
              target: tuple[np.ndarray, np.ndarray, np.ndarray]) -> float:
    edges, real, imaginary = source
    other, other_real, other_imaginary = target
    best = np.zeros(edges.shape, np.float32)
    height, width = edges.shape
    for dy in range(-2, 3):
        for dx in range(-2, 3):
            ys, xs = slice(max(0, -dy), min(height, height - dy)), slice(
                max(0, -dx), min(width, width - dx))
            yt, xt = slice(max(0, dy), min(height, height + dy)), slice(
                max(0, dx), min(width, width + dx))
            orientation = np.clip((1 + real[ys, xs] * other_real[yt, xt]
                                   + imaginary[ys, xs] * other_imaginary[yt, xt]) / 2, 0, 1)
            score = other[yt, xt] * orientation * math.exp(-(dx * dx + dy * dy) / 2)
            best[ys, xs] = np.maximum(best[ys, xs], score)
    return float(best[edges].mean()) if edges.any() else 0.0


def measure(template: np.ndarray, image: np.ndarray, mask: np.ndarray) -> dict[str, Any]:
    if template.shape != image.shape:
        raise ValueError("edge comparison does not rescale or align images")
    reference, observed = features(template, mask), features(image, mask)
    reference_count, observed_count = int(reference[0].sum()), int(observed[0].sum())
    if reference_count < 32:
        return {"status": "reference_structure_insufficient", "score": None,
                "reference_edge_count": reference_count, "observed_edge_count": observed_count}
    recall, precision = _coverage(reference, observed), _coverage(observed, reference)
    score = 2 * recall * precision / (recall + precision) if recall + precision > 0 else 0.0
    return {"status": "measured_not_qualified", "score": score,
            "reference_coverage": recall, "observed_coverage": precision,
            "reference_edge_count": reference_count, "observed_edge_count": observed_count}
