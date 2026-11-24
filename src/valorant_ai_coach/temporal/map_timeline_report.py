"""Bind a development Map path report to the common timeline without changing either."""

from __future__ import annotations

import math
from collections import Counter
from pathlib import Path
from typing import Any

from .evidence import freeze_native_sample, is_sha
from .map_recorder_path import VERSION, join_recorder_seconds, measured_native_edges
from .replay import file_sha, read_json


def load_map_timeline(
    report_path: Path, timeline_path: Path, timeline: dict[str, Any],
) -> dict[str, Any]:
    """Project the measured Map sidecar onto the exact unmodified timeline."""
    report = read_json(report_path)
    if (
        report.get("schema") != VERSION
        or report.get("qualified") is not False
        or report.get("formal_outputs") != 0
        or report.get("interpolated_samples") != 0
        or report.get("timeline_sha256") != file_sha(timeline_path)
        or timeline.get("qualification") != "development_only"
        or timeline.get("formal_outputs") != 0
    ):
        raise ValueError("Matching development Map path and timeline required")

    source = timeline["source"]["source_sha256"]
    native = timeline["native_frames"]
    points: dict[str, dict[str, Any]] = {}
    for segment in report["segments"]:
        if not segment:
            raise ValueError("Map trajectory segments must contain observations")
        for point in segment:
            sample = freeze_native_sample(point["sample"])
            key = sample["sample_sha256"]
            frame = native.get(key, {})
            coordinates = point.get("map_reference_px")
            if (
                key in points
                or sample != frame.get("sample")
                or frame.get("camera", {}).get("value") != "SELF"
                or frame.get("life", {}).get("value") != "ALIVE"
                or sample["source_sha256"] != source
                or point.get("qualified") is not False
                or point.get("position_authority") is not False
                or point.get("kind") not in ("selected", "measured_witness")
                or not isinstance(point.get("map_id"), str)
                or not point["map_id"]
                or not is_sha(point.get("reference_sha256"))
                or not isinstance(coordinates, list)
                or len(coordinates) != 2
                or any(type(value) not in (int, float) or not math.isfinite(value)
                       or value < 0 for value in coordinates)
            ):
                raise ValueError("Exact unqualified Map observation required")
            points[key] = point

    rows = join_recorder_seconds(report, timeline)
    if rows != report.get("second_rows"):
        raise ValueError("Map seconds do not match their native observations")
    edges_by_second: dict[int, list[tuple[str, str]]] = {}
    seconds_by_sample = {
        key: row["timestamp"] for row in timeline["seconds"] for key in row["sample_refs"]
        if key in points
    }
    for edge in sorted(measured_native_edges(report)):
        edges_by_second.setdefault(seconds_by_sample[edge[1]], []).append(edge)

    for row in rows:
        row["native_edges_ending_here"] = [
            [points[first], points[second]]
            for first, second in edges_by_second.get(row["timestamp"], ())
        ]
    return {
        "rows": rows,
        "summary": summarize_map_seconds(rows),
        "qualification": "development_only",
        "formal_outputs": 0,
    }


def summarize_map_seconds(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Count one-second observations and edges for development analysis."""
    named: Counter[str] = Counter()
    selected_zones: Counter[str] = Counter()
    position = selected_seconds = conflict_seconds = 0
    for row in rows:
        points = row["recorder_map_observations"]
        position += bool(points)
        named.update({f"{p['map_id']}/{p['zone_candidate']}"
                      for p in points if p.get("zone_candidate") is not None})
        selected = [p for p in points if p["kind"] == "selected"]
        if not selected:
            continue
        selected_seconds += 1
        references = {(p["map_id"], p["reference_sha256"]) for p in selected}
        names = {p["zone_candidate"] for p in selected if p.get("zone_candidate") is not None}
        if len(references) > 1 or len(names) > 1:
            conflict_seconds += 1
        elif len(names) == 1 and all(p.get("zone_candidate") is not None for p in selected):
            selected_zones[f"{selected[0]['map_id']}/{next(iter(names))}"] += 1
    return {
        "qualification": "development_only",
        "formal_outputs": 0,
        "seconds": len(rows),
        "seconds_with_position": position,
        "seconds_with_native_edge": sum(
            row["trajectory_coverage"] == "native_edge_observed" for row in rows
        ),
        "unknown_seconds": len(rows) - position,
        "named_zone_observed_seconds": dict(sorted(named.items())),
        "seconds_with_recorder_selection": selected_seconds,
        "seconds_with_support_only": position - selected_seconds,
        "seconds_with_conflicting_selected_zones": conflict_seconds,
        "unique_selected_zone_observed_seconds": dict(sorted(selected_zones.items())),
        "continuous_time_assumed": False,
    }
