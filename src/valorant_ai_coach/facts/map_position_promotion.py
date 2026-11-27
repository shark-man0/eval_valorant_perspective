"""Development candidates for Map position Facts from an exactly bound canonical Map report.

Input is a ``development_recorder_map_path_v1`` report that ``load_map_timeline`` accepted
against the canonical timeline (``temporal/map_canonical_pass.py``): one strictly bound
observation at most per second, measured on that second's own sample.

What this module decides, and what it refuses to infer:

* **Position per second.** A second is eligible only inside a confirmed Round whose state
  is not ENDED or INTERMISSION, with its own observed camera ``SELF`` and life ``ALIVE``
  (already required by the binding), and with one of two kinds of support:
  ``corroborated`` (the self-highlight ring and the Map library measurement agree) or
  ``temporally_supported`` (one method, and a strictly bound position one second before
  or after it, in the same Round, no farther than a run can reach in one second).
  An isolated single reading is never eligible.
* **Zone.** The Zone candidate the report attached on the exact reference image, mapped
  through the Zone file's aliases and prefixed with the Map slug. Otherwise ``None``.
* **Hold and change.** Built only from eligible positions of the same Round whose
  neighbours are at most ``max_gap_seconds`` apart. A hold is a run whose positions all stay
  within ``hold_radius_m`` of its first position for at least ``min_hold_seconds``.
  A change joins neighbouring positions that are at least ``change_min_m`` apart and
  reports only its first and last observed position and Zone.
  No continuous path, interpolated position or instantaneous speed is produced: one
  sample per second cannot show how the player moved between samples. The run-speed
  limit is used only as an upper bound to reject impossible neighbours.

Confidence values come from a calibration file
(``scripts/map_canonical/calibrate_positions.py``): for each support kind, the Wilson 95%
lower bound of its blind-reviewed precision, with unclear reviews counted as wrong. A
support kind without a calibration value is never eligible. Candidates stay
``qualification: development_candidate`` and ``formal_outputs: 0``; promotion to formal
Facts is a separate, approved step.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

SCHEMA = "development_map_position_candidates_v1"
CORROBORATED = "corroborated"
TEMPORAL = "temporally_supported"
ISOLATED = "isolated"
NOT_PLAYABLE = {"ENDED", "INTERMISSION"}


@dataclass(frozen=True)
class MapGeometry:
    """Map slug and reference-image pixels per metre (game knowledge scalars)."""

    map_id: str
    slug: str
    reference_px_per_m: float

    @classmethod
    def from_knowledge(cls, map_id: str, name: str, x_multiplier: float,
                       reference_size_px: int = 1024) -> MapGeometry:
        # Minimap normalised units per world unit (cm) times reference pixels.
        scale = abs(x_multiplier) * 100 * reference_size_px
        if not math.isfinite(scale) or scale <= 0:
            raise ValueError("Positive Map scale required")
        return cls(map_id, name.strip().lower().replace(" ", "_"), scale)


@dataclass(frozen=True)
class PromotionSettings:
    max_step_m: float = 8.0  # one second of running (6.75 m/s) plus measurement tolerance
    max_gap_seconds: int = 2
    hold_radius_m: float = 2.5
    min_hold_seconds: int = 3
    change_min_m: float = 5.0
    min_confidence: float = 0.60


def _zone(point: Mapping[str, Any], geometry: MapGeometry,
          aliases: Mapping[str, str]) -> str | None:
    name = point.get("zone_candidate")
    if not name:
        return None
    name = aliases.get(name, name)
    slug = name.strip().lower().replace(" / ", "_").replace(" ", "_").replace("(", "")
    slug = slug.replace(")", "")
    return slug if slug.startswith(geometry.slug + "_") else f"{geometry.slug}_{slug}"


def _distance_m(a: Sequence[float], b: Sequence[float], geometry: MapGeometry) -> float:
    return math.dist(a, b) / geometry.reference_px_per_m


def position_candidates(
    report: Mapping[str, Any], timeline: Mapping[str, Any],
    confirmed_rounds: Sequence[tuple[int, int, int]], geometry: MapGeometry, *,
    calibration: Mapping[str, float], aliases: Mapping[str, str] | None = None,
    settings: PromotionSettings | None = None,
) -> dict[str, Any]:
    """Per-second positions and hold/change/site-entry events, all development-only."""
    if (report.get("schema") != "development_recorder_map_path_v1"
            or report.get("qualified") is not False or report.get("formal_outputs") != 0
            or "canonical_pass" not in report):
        raise ValueError("An exactly bound canonical Map report is required")
    rules = settings or PromotionSettings()
    alias = dict(aliases or {})
    states = {row["timestamp"]: row for row in timeline["seconds"]}
    round_of: dict[int, int] = {}
    for number, start, end in confirmed_rounds:
        for second in range(int(start), int(end) + 1):
            round_of[second] = int(number)
    observed: dict[int, dict[str, Any]] = {}
    for row in report["second_rows"]:
        points = [p for p in row["recorder_map_observations"] if p.get("kind") == "selected"]
        if len(points) != 1 or points[0].get("map_id") != geometry.map_id:
            continue
        observed[int(row["timestamp"])] = points[0]

    positions: dict[int, dict[str, Any]] = {}
    for second, point in sorted(observed.items()):
        number = round_of.get(second)
        state = (states.get(second, {}).get("round_state") or {}).get("value")
        if number is None or state in NOT_PLAYABLE:
            continue
        methods = point.get("methods_agreeing") or [point.get("selection_method")]
        if len(set(methods)) >= 2:
            support = CORROBORATED
        else:
            support = ISOLATED
            for other in (second - 1, second + 1):
                near = observed.get(other)
                if (near is not None and round_of.get(other) == number
                        and _distance_m(point["map_reference_px"], near["map_reference_px"],
                                        geometry) <= rules.max_step_m):
                    support = TEMPORAL
                    break
        method_key = support if support == CORROBORATED else f"{support}:{methods[0]}"
        confidence = calibration.get(method_key)
        eligible = (support != ISOLATED and confidence is not None
                    and confidence >= rules.min_confidence)
        positions[second] = {
            "sec": second, "round_no": number, "map_id": geometry.map_id,
            "map_slug": geometry.slug,
            "map_reference_px": [round(v, 2) for v in point["map_reference_px"]],
            "zone_id": _zone(point, geometry, alias), "support": support,
            "support_detail": method_key, "confidence": confidence, "eligible": eligible,
            "spatial_context_available": eligible,
            "evidence_refs": [f"sample:{point['sample']['sample_sha256']}"],
            "canonical_pixel_verification": point.get("canonical_pixel_verification"),
        }

    eligible_seconds = sorted(s for s, p in positions.items() if p["eligible"])
    runs: list[list[int]] = []
    for second in eligible_seconds:
        if (runs and second - runs[-1][-1] <= rules.max_gap_seconds
                and positions[second]["round_no"] == positions[runs[-1][-1]]["round_no"]):
            runs[-1].append(second)
        else:
            runs.append([second])

    holds: list[dict[str, Any]] = []
    changes: list[dict[str, Any]] = []
    entries: list[dict[str, Any]] = []
    for run in runs:
        start = 0
        while start < len(run):
            anchor = positions[run[start]]["map_reference_px"]
            end = start
            while (end + 1 < len(run) and _distance_m(
                    positions[run[end + 1]]["map_reference_px"], anchor, geometry)
                    <= rules.hold_radius_m):
                end += 1
            if run[end] - run[start] >= rules.min_hold_seconds:
                members = [positions[s] for s in run[start:end + 1]]
                zones = {m["zone_id"] for m in members}
                holds.append({
                    "type": "position_hold", "round_no": members[0]["round_no"],
                    "start_sec": run[start], "end_sec": run[end],
                    "observed_seconds": len(members),
                    "zone_id": zones.pop() if len(zones) == 1 else None,
                    "confidence": min(m["confidence"] for m in members),
                    "evidence_refs": [r for m in members for r in m["evidence_refs"]],
                })
            start = end + 1
        moving: list[int] = []
        for first, second in zip(run, run[1:], strict=False):
            a, b = positions[first], positions[second]
            if _distance_m(a["map_reference_px"], b["map_reference_px"],
                           geometry) >= rules.change_min_m:
                moving = moving + [first, second] if not moving or moving[-1] != first else (
                    moving + [second])
            elif moving:
                changes.append(_change(moving, positions, geometry))
                moving = []
            site_before = a["zone_id"] if a["zone_id"] and "plant" in a["zone_id"] else None
            site_after = b["zone_id"] if b["zone_id"] and "plant" in b["zone_id"] else None
            if site_after and site_after != site_before:
                entries.append({
                    "type": "site_entry", "round_no": b["round_no"],
                    "before_sec": first, "after_sec": second, "zone_id": site_after,
                    "confidence": min(a["confidence"], b["confidence"]),
                    "evidence_refs": a["evidence_refs"] + b["evidence_refs"],
                })
        if moving:
            changes.append(_change(moving, positions, geometry))
    counts = {
        "strict_seconds": len(observed),
        "seconds_in_confirmed_playable_rounds": len(positions),
        "eligible_positions": len(eligible_seconds),
        "eligible_with_zone": sum(1 for s in eligible_seconds if positions[s]["zone_id"]),
        "position_hold": len(holds), "position_change": len(changes),
        "site_entry": len(entries),
    }
    for item in positions.values():
        counts[f"support_{item['support_detail']}"] = (
            counts.get(f"support_{item['support_detail']}", 0) + 1)
    return {
        "schema": SCHEMA, "qualification": "development_candidate", "formal_outputs": 0,
        "timeline_sha256": report.get("timeline_sha256"),
        "map_id": geometry.map_id, "map_slug": geometry.slug,
        "reference_px_per_m": round(geometry.reference_px_per_m, 4),
        "settings": rules.__dict__, "calibration": dict(calibration),
        "continuous_path_inferred": False, "instantaneous_speed_inferred": False,
        "positions": [positions[s] for s in sorted(positions)],
        "events": holds + changes + entries, "counts": counts,
    }


def _change(seconds: list[int], positions: Mapping[int, dict[str, Any]],
            geometry: MapGeometry) -> dict[str, Any]:
    first, last = positions[seconds[0]], positions[seconds[-1]]
    members = [positions[s] for s in seconds]
    return {
        "type": "position_change", "round_no": first["round_no"],
        "start_sec": seconds[0], "end_sec": seconds[-1], "observed_seconds": len(seconds),
        "from_zone_id": first["zone_id"], "to_zone_id": last["zone_id"],
        "displacement_m": round(_distance_m(first["map_reference_px"],
                                            last["map_reference_px"], geometry), 1),
        "confidence": min(m["confidence"] for m in members),
        "evidence_refs": [r for m in members for r in m["evidence_refs"]],
    }
