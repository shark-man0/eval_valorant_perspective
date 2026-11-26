from fractions import Fraction

import cv2
import numpy as np

from scripts.map_learning.marker_tracks import Marker, Track, associate, observe
from scripts.map_learning.replay_marker_tracks import (
    classify_track,
    episode_ordinals,
    freeze_targets,
)


def marker(i, x, palette="WARM"):
    return Marker(
        str(i),
        i,
        Fraction(i, 5),
        (x, 90),
        palette,
        8.0,
        20,
        8,
        np.full(49, 1 / 7, dtype=np.float32),
    )


def test_detector_preserves_different_outline_palettes_before_attribution():
    image = np.zeros((140, 1920, 3), dtype=np.uint8)
    cv2.circle(image, (50, 60), 8, (150, 231, 255), 2)
    cv2.circle(image, (90, 60), 8, (221, 235, 53), 2)
    detections = observe(image, (0, 0, 140, 140), "recorded", 0, Fraction(0))
    assert {(m.center, m.palette) for m in detections} >= {((50, 60), "WARM"), ((90, 60), "CYAN")}


def test_flat_saturated_background_does_not_create_filled_rings():
    image = np.full((140, 1920, 3), (221, 235, 53), dtype=np.uint8)
    assert observe(image, (0, 0, 140, 140), "recorded", 0, Fraction(0)) == []


def test_tracks_precede_identity_and_never_create_an_observation_during_a_gap():
    layers = [
        [marker(0, 40), marker(0, 100, "CYAN")],
        [marker(1, 45), marker(1, 95, "CYAN")],
        [marker(2, 90, "CYAN")],
        [marker(3, 50), marker(3, 85, "CYAN")],
    ]
    tracks = associate(layers, 1)
    warm, cool = [
        next(t for t in tracks if t.measurements[0].palette == palette)
        for palette in ("WARM", "CYAN")
    ]
    assert [m.ordinal for m in warm.measurements] == [0, 1, 3]
    assert [m.ordinal for m in cool.measurements] == [0, 1, 2, 3]
    witnesses = {(m.sample_ref, m.center): (False, 0.4, 0.0, False) for m in warm.measurements}
    for m in warm.measurements[::2]:
        witnesses[m.sample_ref, m.center] = (False, 0.85, 0.15, False)
    assert classify_track(warm, witnesses, {"0": 1, "1": 1, "3": 1}) == warm.measurements[::2]
    assert classify_track(cool, {}, {}) == []


def test_anonymous_track_requires_repeatable_owner_evidence():
    t = Track([marker(i, 50) for i in range(3)])
    data = {(m.sample_ref, m.center): (False, 0.55, 0.03, False) for m in t.measurements}
    data["0", (50, 90)] = (True, 0.55, 0.03, False)
    assert not classify_track(t, data, {"0": 1, "1": 1, "2": 1})


def test_a_contested_observation_does_not_join_either_previous_track():
    observations = [[marker(0, 40), marker(0, 52)], [marker(1, 46)], [marker(2, 51)]]
    tracks = associate(observations, 1)
    assert sorted([m.ordinal for m in track.measurements] for track in tracks) == [[0], [0], [1, 2]]


def test_frozen_cohort_excludes_previously_recovered_seconds():
    timeline = {"seconds": [{"timestamp": i, "sample_refs": [str(i)]} for i in range(3)]}
    reject = {
        "comparison_evidence": {
            "operable_sample_refs": ["0", "1", "2"],
            "unresolved_portrait_sample_refs": ["0", "1"],
        }
    }
    incumbent = {
        "second_rows": [{"timestamp": i, "recorder_map_observations": []} for i in range(3)]
    }
    prior = {
        "second_rows": [
            {"timestamp": i, "recorder_map_observations": [{"position": 1}] if i == 1 else []}
            for i in range(3)
        ]
    }
    _, cohort = freeze_targets(timeline, reject, reject, incumbent, prior)
    assert cohort == {0: ("0",)}


def test_whole_episode_can_use_witnesses_outside_the_target_neighborhood():
    scope = tuple(str(i) for i in range(10))
    assert list(episode_ordinals(scope, {"5"}, False)) == [3, 4, 5, 6, 7]
    assert list(episode_ordinals(scope, {"5"}, True)) == list(range(len(scope)))
