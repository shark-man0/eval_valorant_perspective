"""Container timing diagnostics only; no image decoding or edit/continuity verdict."""

from __future__ import annotations

from collections import Counter
from fractions import Fraction
from typing import Any


def classify_packets(packets: list[dict[str, Any]], time_base: str, fps: str) -> dict[str, Any]:
    tick, rate = Fraction(time_base), Fraction(fps)
    if tick <= 0 or rate <= 0:
        raise ValueError("positive native timing required")
    pts = [p["pts"] for p in packets if type(p.get("pts")) is int]
    ordered = sorted(pts)
    steps = Counter(b - a for a, b in zip(ordered, ordered[1:], strict=False))
    nominal = 1 / rate / tick
    large = [d for d in steps if d > nominal + 2]
    dts = [p["dts"] for p in packets if type(p.get("dts")) is int]
    inconsistent = any(b <= a for a, b in zip(dts, dts[1:], strict=False))
    missing = len(packets) - len(pts)
    if missing or steps.get(0, 0) or inconsistent:
        category = "POSSIBLE_PTS_INCONSISTENCY"
    elif large:
        category = "POSSIBLE_FRAME_LOSS_OR_CONTAINER_ARTIFACT"
    elif len(pts) >= 2 and all(abs(d - nominal) <= 2 for d in steps):
        category = "NORMAL_CADENCE_WITHIN_TWO_TICKS"
    else:
        category = "INDETERMINATE"
    return {
        "scope": "container_packets_only",
        "category": category,
        "packet_count": len(packets),
        "missing_pts": missing,
        "duplicate_pts": steps.get(0, 0),
        "nonmonotonic_dts": inconsistent,
        "step_ticks_counts": {str(k): v for k, v in sorted(steps.items())},
        "nominal_step_ticks": str(nominal),
        "large_step_count": sum(steps[d] for d in large),
        "zero_duration_packet_count": sum(p.get("duration") == 0 for p in packets),
        "visual_continuity": "UNVERIFIED",
        "unedited_or_corrupted_verdict": "NOT_ESTABLISHED",
    }
