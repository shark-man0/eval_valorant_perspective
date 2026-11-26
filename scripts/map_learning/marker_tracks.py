"""Anonymous minimap observations and multi-marker association for development replay."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from fractions import Fraction
from functools import lru_cache

import cv2
import numpy as np

_PALETTES = ("WARM", "CYAN", "RED")
_ANGLES = np.arange(24) * (math.tau / 24)


@dataclass(frozen=True)
class Marker:
    sample_ref: str
    ordinal: int
    at: Fraction
    center: tuple[int, int]
    palette: str
    radius: float
    sectors: int
    opposite: int
    descriptor: np.ndarray = field(repr=False, compare=False)


@dataclass
class Track:
    measurements: list[Marker]


def _masks(image):
    hue, saturation, value = cv2.split(cv2.cvtColor(image, cv2.COLOR_BGR2HSV))
    return (
        (hue >= 17) & (hue <= 42) & (saturation >= 20) & (saturation <= 155) & (value >= 155),
        (hue >= 73) & (hue <= 105) & (saturation >= 55) & (value >= 135),
        ((hue <= 10) | (hue >= 172)) & (saturation >= 100) & (value >= 155),
    )


def _vote(mask, scale):
    """Measure annular support at every possible center, excluding filled blobs."""
    binary = mask.astype(np.float32)
    radius = max(2, round(8 * scale))
    extent = radius + max(1, round(2 * scale))
    ring = np.zeros((extent * 2 + 1, extent * 2 + 1), dtype=np.float32)
    cv2.circle(ring, (extent, extent), radius, 1, max(1, round(3 * scale)))
    interior = np.zeros_like(ring)
    cv2.circle(interior, (extent, extent), max(1, round(5 * scale)), 1, -1)
    return cv2.filter2D(binary, -1, ring / ring.sum()) - cv2.filter2D(
        binary,
        -1,
        interior * (1.15 / interior.sum()),
    )


@lru_cache(maxsize=8)
def _ring_offsets(scale):
    radii = np.asarray([6.5, 7.5, 8.5, 9.5]) * scale
    distances = radii[:, None, None] + np.asarray([-scale, 0, scale])[None, :, None]
    return (
        radii,
        np.rint(distances * np.cos(_ANGLES)).astype(int),
        np.rint(
            distances * np.sin(_ANGLES),
        ).astype(int),
    )


def _geometry(mask, xs, ys, scale):
    radii, dx, dy = _ring_offsets(scale)
    supported = mask[ys[:, None, None, None] + dy, xs[:, None, None, None] + dx].any(axis=2)
    sectors = supported.sum(axis=-1)
    opposite = (supported[:, :, :12] & supported[:, :, 12:]).sum(axis=-1)
    # Prefer the fuller ring on equal combined evidence, and then the smaller radius.
    best = ((sectors + opposite) * 25 + sectors).argmax(axis=1)
    index = np.arange(len(xs))
    return sectors[index, best], opposite[index, best], radii[best]


def _appearance(gray, x, y, scale):
    half = max(2, round(5 * scale))
    patch = gray[y - half : y + half + 1, x - half : x + half + 1]
    small = cv2.resize(patch, (7, 7), interpolation=cv2.INTER_AREA).astype(np.float32)
    small -= small.mean()
    return (small / max(15.0, float(np.linalg.norm(small)))).ravel()


def observe(image, bounds, sample_ref, ordinal, at):
    """Return every geometric proposal with its palette and local matching feature."""
    left, top, right, bottom = bounds
    roi = image[top:bottom, left:right]
    scale = image.shape[1] / 1920
    extent = math.ceil(11 * scale) + 1
    if min(roi.shape[:2]) <= 2 * extent:
        return []
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    result = []
    for palette, mask in zip(_PALETTES, _masks(roi), strict=True):
        votes = _vote(mask, scale)
        neighborhood = max(3, 2 * round(3 * scale) + 1)
        maxima = cv2.dilate(votes, np.ones((neighborhood, neighborhood), np.uint8))
        peaks = (votes >= 0.11) & (votes == maxima)
        peaks[:extent] = peaks[-extent:] = False
        peaks[:, :extent] = peaks[:, -extent:] = False
        peak_y, peak_x = np.nonzero(peaks)
        best_sectors, best_opposite, radii = _geometry(mask, peak_x, peak_y, scale)
        proposals = []
        for y, x, sectors, opposite, radius in zip(
            peak_y,
            peak_x,
            best_sectors,
            best_opposite,
            radii,
            strict=True,
        ):
            if sectors >= 9 and opposite >= 2:
                proposals.append(
                    (int(sectors), int(opposite), float(votes[y, x]), int(x), int(y), float(radius))
                )
        for sectors, opposite, _, x, y, radius in sorted(proposals, reverse=True):
            result.append(
                Marker(
                    sample_ref,
                    ordinal,
                    at,
                    (x + left, y + top),
                    palette,
                    radius,
                    sectors,
                    opposite,
                    _appearance(gray, x, y, scale),
                )
            )
    return result


def representatives(markers, scale):
    """Consolidate detection duplicates only for association, keeping the original pool."""
    candidates = sorted(markers, key=lambda m: (m.sectors + m.opposite, m.sectors), reverse=True)
    unique = []
    for marker in candidates:
        if all(
            other.palette != marker.palette or math.dist(other.center, marker.center) > 5 * scale
            for other in unique
        ):
            unique.append(marker)
    return unique


def _cost(track, current, scale):
    last = track.measurements[-1]
    elapsed = float(current.at - last.at)
    if elapsed <= 0 or elapsed > 0.61:
        return math.inf
    # Use only actual observations. The prediction is an association query.
    within = (4 + 44 * elapsed) * scale
    if math.dist(last.center, current.center) > within:
        return math.inf
    resemblance = float(np.dot(last.descriptor, current.descriptor))
    if last.palette != current.palette and resemblance < 0.80:
        return math.inf
    if current.ordinal > last.ordinal + 1 and (
        resemblance < 0.65 or last.palette != current.palette
    ):
        return math.inf
    prediction = last.center
    if len(track.measurements) >= 2:
        prev = track.measurements[-2]
        prior_elapsed = float(last.at - prev.at)
        if 0 < prior_elapsed <= 0.25:
            rate = min(1.0, elapsed / prior_elapsed) * 0.65
            prediction = tuple(
                a + (a - b) * rate for a, b in zip(last.center, prev.center, strict=True)
            )
    location = math.dist(prediction, current.center) / within
    return 0.72 * location + 0.28 * (1 - resemblance) + 0.2 * (last.palette != current.palette)


def associate(layers, scale):
    """Associate multiple anonymous marker tracks. Ambiguity forks new tracks."""
    tracks = []
    active = []
    for pool in layers:
        if not pool:
            continue
        candidates = representatives(pool, scale)
        active = [t for t in active if candidates[0].at - t.measurements[-1].at <= Fraction(3, 5)]
        preferences = [[] for _ in candidates]
        choices = [[] for _ in active]
        for i, track in enumerate(active):
            for j, marker in enumerate(candidates):
                score = _cost(track, marker, scale)
                if score <= 0.77:
                    choices[i].append((score, j))
                    preferences[j].append((score, i))
        matches = set()
        matched_tracks = set()
        for i, options in enumerate(choices):
            options.sort()
            if not options or (len(options) > 1 and options[1][0] - options[0][0] < 0.10):
                continue
            score, j = options[0]
            preferences[j].sort()
            rivals = preferences[j]
            if rivals[0][1] != i or (len(rivals) > 1 and rivals[1][0] - score < 0.10):
                continue
            active[i].measurements.append(candidates[j])
            matches.add(j)
            matched_tracks.add(i)
        # An unmatched track can survive a missed measurement. A contested
        # measurement ends the old trajectory rather than letting it swap later.
        active = [track for i, track in enumerate(active) if i in matched_tracks or not choices[i]]
        for j, marker in enumerate(candidates):
            if j not in matches:
                track = Track([marker])
                tracks.append(track)
                active.append(track)
    return tracks
