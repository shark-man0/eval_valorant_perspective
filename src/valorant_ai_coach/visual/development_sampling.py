"""Content-blind bounded targets for DEVELOPMENT coarse/dense Map comparisons."""

from __future__ import annotations

import math
from fractions import Fraction


def map_sampling_targets(
    duration_sec: float, *, stride_sec: int = 30, maximum: int = 180,
) -> dict[str, list[float]]:
    """Plan targets before decoding; targets are never represented as native PTS.

    The decoder must independently resolve and verify actual native frames. A
    missing/failed target remains in the denominator. Dense windows depend only
    on the source duration, never the detector's successes or suggested motion.
    """
    if (type(duration_sec) not in (int, float) or not math.isfinite(duration_sec)
            or duration_sec <= 0 or type(stride_sec) is not int or stride_sec <= 0
            or type(maximum) is not int or not 3 <= maximum <= 1000):
        raise ValueError("Finite duration and bounded positive sampling parameters required")
    duration = Fraction(str(duration_sec))
    end = duration-10
    if end <= 30:
        return {"coarse": [], "dense_starts": []}
    stride = max(stride_sec, math.ceil((end-30)/(maximum-1)))
    coarse = [float(30+i*stride) for i in range(maximum) if 30+i*stride < end]
    dense = sorted({coarse[i] for i in (0, len(coarse)//3, 2*len(coarse)//3)
                    if coarse[i]+2 < end})
    return {"coarse": coarse, "dense_starts": dense}
