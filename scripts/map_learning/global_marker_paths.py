"""Forward/backward optimization between observed recorder anchors."""

from __future__ import annotations

import math

import numpy as np


def transition(left, right, scale):
    elapsed = float(right.at - left.at)
    if not 0 < elapsed <= 0.25 or left.palette != right.palette:
        return math.inf
    reach = (4 + 44 * elapsed) * scale
    distance = math.dist(left.center, right.center)
    if distance > reach:
        return math.inf
    similarity = float(np.dot(left.descriptor, right.descriptor))
    if similarity < 0.35:
        return math.inf
    return distance / reach + 0.7 * (1 - similarity)


def solve(layers, scale):
    """Return only nodes that beat every competing complete path at that time."""
    if len(layers) < 3 or any(not layer for layer in layers):
        return []
    if len(layers[0]) != 1 or len(layers[-1]) != 1:
        raise ValueError("Two unique observed endpoint anchors are required")
    edges = [
        np.asarray([[transition(a, b, scale) for b in right] for a in left])
        for left, right in zip(layers, layers[1:], strict=False)
    ]
    forward = [np.zeros(1)]
    for edge in edges:
        forward.append(np.min(forward[-1][:, None] + edge, axis=0))
    if not np.isfinite(forward[-1][0]):
        return []
    backward = [np.zeros(1)]
    for edge in reversed(edges):
        backward.append(np.min(edge + backward[-1][None, :], axis=1))
    backward.reverse()
    result = []
    for layer, first, last in zip(layers, forward, backward, strict=True):
        totals = first + last
        order = np.argsort(totals, kind="stable")
        best = int(order[0])
        margin = float(totals[order[1]] - totals[best]) if len(order) > 1 else math.inf
        if margin < 0.5 or not np.isfinite(totals[best]):
            result.append(None)
        else:
            result.append((layer[best], margin))
    # A surviving node is insufficient when an adjacent hypothesis is unresolved.
    return result
