"""Extend measured recorder identity through unambiguous links in one view episode."""

from __future__ import annotations

from math import isfinite

import numpy as np

from valorant_ai_coach.temporal.replay import is_sha, read_json

MATCH_SCHEMA = "development_map_marker_temporal_match_v1"
FEATURES = ("whole", "upper_left", "upper_right", "lower_left", "lower_right", "center")
_ROUND_OPENINGS = {"observed_round_start", "observed_buy_to_active", "round_scope_changed"}
_REGIONS = (
    (slice(None), slice(None)),
    (slice(0, 4), slice(0, 4)),
    (slice(0, 4), slice(3, 7)),
    (slice(3, 7), slice(0, 4)),
    (slice(3, 7), slice(3, 7)),
    (slice(2, 5), slice(2, 5)),
)


def pair_features(a, b):
    left, right = np.asarray(a).reshape(7, 7), np.asarray(b).reshape(7, 7)
    values = []
    for ys, xs in _REGIONS:
        x, y = left[ys, xs].ravel(), right[ys, xs].ravel()
        denom = float(np.linalg.norm(x) * np.linalg.norm(y))
        values.append(float(np.dot(x, y)) / max(0.025, denom))
    return np.asarray(values)


def read_match_profile(path, physical):
    if path is None:
        return None
    profile = read_json(path)
    if (
        profile.get("schema") != MATCH_SCHEMA
        or profile.get("formal_outputs") != 0
        or profile.get("feature_order") != list(FEATURES)
        or len(profile.get("weights", [])) != len(FEATURES)
        or any(
            type(x) not in (float, int) or not isfinite(x)
            for x in [*profile.get("weights", []), profile.get("cutoff")]
        )
        or any(not is_sha(key) for key in profile.get("source_receipts", []))
        or physical in profile["training_matches"]
        or physical in profile["calibration_matches"]
        or set(profile["training_matches"]) & set(profile["calibration_matches"])
    ):
        raise ValueError("A disjoint frozen temporal matcher is required")
    return profile


def match_score(features, profile):
    return float(np.asarray(features) @ np.asarray(profile["weights"]))


def extension(track, witnesses, evidence, warm_counts, opening, opening_at, conflicts, profile):
    """Propagate only along individually measured, separated, matching transitions."""
    markers = track.measurements
    trusted = [
        i
        for i, m in enumerate(markers)
        if m.palette == "WARM"
        and evidence[m.sample_ref, m.center][0]
        and not evidence[m.sample_ref, m.center][3]
    ]
    round_anchors = {
        i
        for i in trusted
        if opening in _ROUND_OPENINGS and 0 <= float(markers[i].at - opening_at) <= 5
    }
    if not witnesses and not round_anchors:
        return {}
    seeds = []
    for i, marker in enumerate(markers):
        if i in round_anchors:
            seeds.append(i)
        elif marker in witnesses:
            direct, score, margin, conflict = evidence[marker.sample_ref, marker.center]
            if not conflict and (direct or (score >= 0.75 and margin >= 0.08)):
                seeds.append(i)
    winners = {}
    for i in seeds:
        start = markers[i]
        if (
            warm_counts.get(start.sample_ref, 0) != 1
            or (start.sample_ref, start.center) in conflicts
        ):
            continue
        for direction in (1,) if i in round_anchors else (-1, 1):
            risk = 0.0
            prev = start
            for j in range(i + direction, len(markers) if direction > 0 else -1, direction):
                current = markers[j]
                key = (
                    (prev.sample_ref, current.sample_ref)
                    if direction > 0
                    else (current.sample_ref, prev.sample_ref)
                )
                margin = track.link_margins.get(key, 0.0)
                if (
                    abs(current.ordinal - prev.ordinal) != 1
                    or abs(float(current.at - prev.at)) > 0.25
                    or margin < 0.16
                    or current.palette != "WARM"
                    or (current.sample_ref, current.center) in conflicts
                    or warm_counts.get(current.sample_ref, 0) != 1
                    or evidence[current.sample_ref, current.center][3]
                ):
                    break
                features = pair_features(prev.descriptor, current.descriptor)
                likeness = (
                    0.5 * float(np.dot(prev.descriptor, current.descriptor)) + 0.5 * features[0]
                )
                if likeness < 0.56 or (
                    profile is not None and (match_score(features, profile) < profile["cutoff"])
                ):
                    break
                risk += 0.025 + 0.15 * (1 - likeness) + 0.045 * (1 - min(1.0, margin))
                if risk > 1.45:
                    break
                winners.setdefault(
                    current.sample_ref,
                    {
                        "seed": start.sample_ref,
                        "round_start_seed": i in round_anchors,
                        "risk": risk,
                        "elapsed_seconds": abs(float(current.at - start.at)),
                    },
                )
                prev = current
    return winners
