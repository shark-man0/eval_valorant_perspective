"""Compare nested actual native observations in a missing interval, without resampling."""

from __future__ import annotations

from fractions import Fraction


def nested_ticks(native_ticks, frozen_ticks, *, time_base="1/15360"):
    """Keep the original 5 Hz PTS; insert nearest native midpoints for 10 and 20 Hz.

    A rate is a requested sampling budget, not a guarantee of unique frames. A slow
    or variable-rate source can contain fewer observations. No synthetic PTS or
    interpolated image enters any returned subset.
    """
    actual = sorted(set(native_ticks))
    frozen = sorted(set(frozen_ticks))
    if not actual or not frozen or not set(frozen) <= set(actual):
        raise ValueError("Original frozen PTS must be present in the native interval")
    base = Fraction(time_base)
    result = {"5": frozen}
    selected = frozen
    for rate in (10, 20):
        step = Fraction(1, rate)
        targets = [Fraction(tick) + step / base for tick in selected]
        selected = sorted(
            set(selected)
            | {
                min(actual, key=lambda tick: (abs(Fraction(tick) - target), tick))
                for target in targets
                if target <= actual[-1]
            }
        )
        result[str(rate)] = selected
    return {**result, "native": actual}
