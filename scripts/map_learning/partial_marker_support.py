"""Verify a partially visible current marker with independent temporal pixel tracks."""

from __future__ import annotations

import math

import cv2
import numpy as np


def flow_agrees(previous, current, before, center, scale):
    # Local context contains rim and neighboring pixels, avoiding the player's
    # interior portrait as the only matching evidence.
    x, y = before
    extent = round(15 * scale)
    mask = np.zeros(previous.shape, np.uint8)
    cv2.circle(mask, (x, y), extent, 255, -1)
    cv2.circle(mask, (x, y), max(2, round(6 * scale)), 0, -1)
    seeds = cv2.goodFeaturesToTrack(previous, 32, 0.02, max(2, round(2 * scale)), mask=mask)
    if seeds is None or len(seeds) < 6:
        return False
    moved, ok, _ = cv2.calcOpticalFlowPyrLK(previous, current, seeds, None)
    if moved is None:
        return False
    back, back_ok, _ = cv2.calcOpticalFlowPyrLK(current, previous, moved, None)
    if back is None:
        return False
    valid = ok.ravel().astype(bool) & back_ok.ravel().astype(bool)
    valid &= np.linalg.norm((back - seeds)[:, 0], axis=1) <= 0.5 * scale
    if valid.sum() < 6:
        return False
    displacement = np.median((moved - seeds)[valid, 0], axis=0)
    proposed = np.asarray(before) + displacement
    spread = np.linalg.norm((moved - seeds)[valid, 0] - displacement, axis=1)
    return (
        float(np.quantile(spread, 0.8)) <= 1.5 * scale
        and math.dist(proposed, center) <= 1.5 * scale
    )


def partial_supported(before_image, image, after_image, left, marker, right):
    if marker.sectors < 12 or marker.opposite < 3:
        return False
    scale = image.shape[1] / 1920
    grays = [
        cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) for frame in (before_image, image, after_image)
    ]
    return flow_agrees(grays[0], grays[1], left.center, marker.center, scale) and flow_agrees(
        grays[2], grays[1], right.center, marker.center, scale
    )
