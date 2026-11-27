from fractions import Fraction

import pytest

from scripts.map_learning.gap_cadence import nested_ticks


def test_sampling_preserves_original_offset_pts_and_never_manufactures_frames():
    # The saved acquisition can be offset from the nearest integer-second grid.
    ticks = list(range(256, 15360, 256))
    original = list(range(512, 15360, 3072))
    rates = nested_ticks(ticks, original)
    assert rates["5"] == original
    assert set(original) <= set(rates["10"]) <= set(rates["20"]) <= set(rates["native"])
    assert all(type(t) is int for values in rates.values() for t in values)


def test_slow_variable_source_keeps_its_actual_observations():
    ticks = [0, 1000, 2900, 4500, 6500, 10100, 12000, 15000]
    rates = nested_ticks(ticks, [0, 2900, 6500, 10100, 12000])
    assert len(rates["20"]) <= len(ticks)
    assert rates["native"] == ticks
    assert all(Fraction(t, 15360) < 1 for t in rates["20"])
    with pytest.raises(ValueError):
        nested_ticks(ticks, [3072])
