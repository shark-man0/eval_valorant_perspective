from fractions import Fraction

import numpy as np

from scripts.map_learning.global_marker_paths import solve
from scripts.map_learning.marker_tracks import Marker


def marker(i, x):
    return Marker(str(i), i, Fraction(i, 5), (x, 50), "WARM", 8.0, 14, 4, np.ones(49) / 7)


def test_complete_endpoint_evidence_resolves_a_local_branch():
    layers = [
        [marker(0, 10)],
        [marker(1, 15), marker(1, 4)],
        [marker(2, 22), marker(2, 1)],
        [marker(3, 28)],
    ]
    result = solve(layers, 1)
    assert [m[0].center[0] if m else None for m in result] == [10, 15, 22, 28]


def test_equal_crossing_paths_are_unresolved_and_gaps_are_not_filled():
    layers = [[marker(0, 10)], [marker(1, 8), marker(1, 12)], [marker(2, 10)]]
    assert solve(layers, 1)[1] is None
    assert solve([layers[0], [], layers[-1]], 1) == []


def test_partial_support_requires_both_neighboring_images_to_agree():
    import cv2

    from scripts.map_learning.partial_marker_support import partial_supported

    rng = np.random.default_rng(42)
    crop = rng.integers(0, 255, (80, 80, 3), dtype=np.uint8)
    first = np.zeros((120, 1920, 3), np.uint8)
    first[20:100, 20:100] = crop
    middle = cv2.warpAffine(first, np.float32([[1, 0, 2], [0, 1, 0]]), (1920, 120))
    last = cv2.warpAffine(first, np.float32([[1, 0, 4], [0, 1, 0]]), (1920, 120))
    a, b, c = marker(0, 50), marker(1, 52), marker(2, 54)
    assert partial_supported(first, middle, last, a, b, c)
    assert not partial_supported(first, middle, last, a, b, marker(2, 70))
