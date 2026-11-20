"""Quality measurements for advisory native Map paths and one-second output."""

from __future__ import annotations

from fractions import Fraction
from statistics import median
from typing import Any

from .evidence import native_time
from .map_recorder_path import VERSION, measured_native_edges


def measure_path_quality(
    path: dict[str, Any], timeline_seconds: list[dict[str, Any]],
    second_rows: list[dict[str, Any]], operable: set[str],
) -> dict[str, Any]:
    if path.get("schema") != VERSION or path.get("qualified") is not False:
        raise ValueError("Development native path required")
    points = {p["sample"]["sample_sha256"]: p for s in path["segments"] for p in s}
    ticks = {key: native_time(p["sample"]) for key, p in points.items()}
    edges = measured_native_edges(path, operable)
    parents: dict[str, str] = {}
    durations: dict[str, Fraction] = {}

    def root(key: str) -> str:
        parent = parents.setdefault(key, key)
        while parent != parents[parent]:
            parents[parent] = parents[parents[parent]]
            parent = parents[parent]
        parents[key] = parent
        return parent

    for a, b in sorted(edges, key=lambda e: (ticks[e[1]], ticks[e[0]], e)):
        parents[root(b)] = root(a)
        elapsed = durations.get(a, Fraction(0)) + ticks[b] - ticks[a]
        durations[b] = max(durations.get(b, Fraction(0)), elapsed)
    connected: dict[str, Fraction] = {}
    for key, elapsed in durations.items():
        representative = root(key)
        connected[representative] = max(connected.get(representative, Fraction(0)), elapsed)
    gaps: list[int] = []
    gap = zones = callouts = 0
    previous = None
    for source, output in zip(timeline_seconds, second_rows, strict=True):
        second = source["timestamp"]
        if second != output["timestamp"]:
            raise ValueError("Mismatched one-second Map rows")
        refs = set(source["sample_refs"])
        available = bool(refs) and refs <= operable
        observations = output["recorder_map_observations"]
        if available and not observations:
            if gap and previous is not None and second != previous + 1:
                gaps.append(gap)
                gap = 0
            gap += 1
        elif gap:
            gaps.append(gap)
            gap = 0
        if available:
            zones += any(p.get("zone_candidate") is not None for p in observations)
            callouts += any(p.get("callout_candidate") is not None for p in observations)
        previous = second
    if gap:
        gaps.append(gap)
    spans = [float(n) for n in connected.values()]
    return {
        "native_edges": len(edges),
        "connected_segments": len(spans),
        "longest_observed_chain_seconds": max(spans, default=0.0),
        "median_observed_chain_seconds": median(spans) if spans else 0.0,
        "missing_operable_seconds": sum(gaps),
        "longest_missing_operable_run_seconds": max(gaps, default=0),
        "named_zone_seconds": zones,
        "callout_candidate_seconds": callouts,
        "continuous_time_assumed": False,
    }
