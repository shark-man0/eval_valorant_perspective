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
* **Zone.** The position is classified against the Zone polygons of its exact reference
  image. ``zone_status`` is ``inside`` only when one polygon covers it and every polygon
  boundary is at least ``coordinate_error_m`` away (the 95th percentile of the
  disagreement between the two measurement methods); then ``zone_id`` is that Zone,
  mapped through the Zone file's aliases and prefixed with the Map slug. ``boundary``
  (too close to a boundary), ``outside_registered`` (outside every registered Zone) and
  ``no_zone_reference`` all leave ``zone_id`` as ``None``.
* **Hold and change.** Built only from eligible positions of the same Round whose
  neighbours are at most ``max_gap_seconds`` apart and whose every timeline sample in
  between is the recorder's own live view (camera ``SELF`` and life ``ALIVE`` observed).
  A death, a spectated or replay view, or a revive therefore always ends the run, even
  inside the gap allowance. A hold is a run whose positions all stay
  within ``hold_radius_m`` of its first position for at least ``min_hold_seconds``.
  A change joins neighbouring positions that are at least ``change_min_m`` apart and
  reports only its first and last observed position and Zone; it is kept only when its
  first and last positions are at least ``change_min_m + coordinate_error_m`` apart, so a
  change near the threshold that measurement error could explain is not reported.
  No continuous path, interpolated position or instantaneous speed is produced: one
  sample per second cannot show how the player moved between samples. The run-speed
  limit is used only as an upper bound to reject impossible neighbours.
* **Site entry.** A step of a run to a position ``inside`` a plant Zone whose latest earlier
  position in the run that is not a ``boundary`` reading is ``inside`` a known Zone that is
  not a plant Zone. A plant arrival from an unknown Zone (outside every registered Zone,
  only boundary readings, or the start of a run) is not an entry; it is counted under
  ``diagnostics.site_arrival_unconfirmed`` only.

Confidence values come from a calibration file
(``scripts/map_canonical/calibrate_positions.py``): for each support kind, the Wilson 95%
lower bound of its blind-reviewed precision, with unclear reviews counted as wrong. A
support kind without a calibration value is never eligible. Candidates stay
``qualification: development_candidate`` and ``formal_outputs: 0``; promotion to formal
Facts is a separate, approved step.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCHEMA = "development_map_position_candidates_v2"
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
    # 95th percentile of the self-ring / Map library disagreement on the 36 recordings:
    # the Zone boundary margin and the extra displacement a change must show.
    coordinate_error_m: float = 1.25


ZoneSet = Mapping[str, Mapping[str, Sequence[Sequence[float]]]]


def _own_live(row: Mapping[str, Any] | None) -> bool:
    if row is None:
        return False
    camera, life = row.get("camera_state") or {}, row.get("life_state") or {}
    return (camera.get("value") == "SELF" and camera.get("status") == "OBSERVED"
            and life.get("value") == "ALIVE" and life.get("status") == "OBSERVED")


def _slug(name: str, geometry: MapGeometry, aliases: Mapping[str, str]) -> str:
    name = aliases.get(name, name)
    slug = name.strip().lower().replace(" / ", "_").replace(" ", "_").replace("(", "")
    slug = slug.replace(")", "")
    return slug if slug.startswith(geometry.slug + "_") else f"{geometry.slug}_{slug}"


class _Zones:
    """Zone polygons per reference image, classified with a metric boundary margin."""

    def __init__(self, zones: ZoneSet) -> None:
        from shapely.geometry import Polygon

        self._by_reference = {
            reference: {name: Polygon(vertices) for name, vertices in polygons.items()}
            for reference, polygons in zones.items()
        }

    def classify(self, point: Mapping[str, Any], margin_px: float) -> tuple[str, str | None,
                                                                            float | None]:
        from shapely.geometry import Point

        polygons = self._by_reference.get(point.get("reference_sha256") or "")
        if not polygons:
            return "no_zone_reference", None, None
        here = Point(point["map_reference_px"])
        covering = [name for name, poly in polygons.items() if poly.covers(here)]
        nearest = min(poly.boundary.distance(here) for poly in polygons.values())
        if nearest < margin_px:
            return "boundary", None, nearest
        if len(covering) == 1:
            return "inside", covering[0], nearest
        return ("outside_registered" if not covering else "boundary"), None, nearest


def _is_plant(zone_id: str | None) -> bool:
    return bool(zone_id) and "plant" in str(zone_id)


def _distance_m(a: Sequence[float], b: Sequence[float], geometry: MapGeometry) -> float:
    return math.dist(a, b) / geometry.reference_px_per_m


def position_candidates(
    report: Mapping[str, Any], timeline: Mapping[str, Any],
    confirmed_rounds: Sequence[tuple[int, int, int]], geometry: MapGeometry, *,
    calibration: Mapping[str, float], aliases: Mapping[str, str] | None = None,
    settings: PromotionSettings | None = None, zones: ZoneSet | None = None,
) -> dict[str, Any]:
    """Per-second positions and hold/change/site-entry events, all development-only."""
    if (report.get("schema") != "development_recorder_map_path_v1"
            or report.get("qualified") is not False or report.get("formal_outputs") != 0
            or "canonical_pass" not in report):
        raise ValueError("An exactly bound canonical Map report is required")
    rules = settings or PromotionSettings()
    alias = dict(aliases or {})
    zone_set = _Zones(zones) if zones is not None else None
    margin_px = rules.coordinate_error_m * geometry.reference_px_per_m
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
        round_no = round_of.get(second)
        state = (states.get(second, {}).get("round_state") or {}).get("value")
        if round_no is None or state in NOT_PLAYABLE:
            continue
        methods = point.get("methods_agreeing") or [point.get("selection_method")]
        if len(set(methods)) >= 2:
            support = CORROBORATED
        else:
            support = ISOLATED
            for other in (second - 1, second + 1):
                near = observed.get(other)
                if (near is not None and round_of.get(other) == round_no
                        and _distance_m(point["map_reference_px"], near["map_reference_px"],
                                        geometry) <= rules.max_step_m):
                    support = TEMPORAL
                    break
        method_key = support if support == CORROBORATED else f"{support}:{methods[0]}"
        confidence = calibration.get(method_key)
        eligible = (support != ISOLATED and confidence is not None
                    and confidence >= rules.min_confidence)
        if zone_set is not None:
            zone_status, zone_name, margin = zone_set.classify(point, margin_px)
        else:  # the report's own Zone candidate, classified with the report's margin
            zone_name = point.get("zone_candidate")
            zone_status, margin = ("inside" if zone_name else "report_unknown"), None
        positions[second] = {
            "sec": second, "round_no": round_no, "map_id": geometry.map_id,
            "map_slug": geometry.slug,
            "map_reference_px": [round(v, 2) for v in point["map_reference_px"]],
            "zone_id": _slug(zone_name, geometry, alias) if zone_name else None,
            "zone_status": zone_status,
            "zone_boundary_distance_m": (None if margin is None
                                         else round(margin / geometry.reference_px_per_m, 2)),
            "support": support,
            "support_detail": method_key, "confidence": confidence, "eligible": eligible,
            "spatial_context_available": eligible,
            "evidence_refs": [f"sample:{point['sample']['sample_sha256']}"],
            "canonical_pixel_verification": point.get("canonical_pixel_verification"),
        }

    eligible_seconds = sorted(s for s, p in positions.items() if p["eligible"])
    runs: list[list[int]] = []
    broken_by_view = 0
    for second in eligible_seconds:
        if runs:
            last = runs[-1][-1]
            close = (second - last <= rules.max_gap_seconds
                     and positions[second]["round_no"] == positions[last]["round_no"])
            # Position s is measured on samples s and s+1, so a link last -> second needs
            # every sample from last to second + 1 to be the recorder's own live view.
            live = all(_own_live(states.get(k)) for k in range(last, second + 2))
            if close and live:
                runs[-1].append(second)
                continue
            broken_by_view += close and not live
        runs.append([second])

    holds: list[dict[str, Any]] = []
    changes: list[dict[str, Any]] = []
    entries: list[dict[str, Any]] = []
    unconfirmed: dict[str, int] = {}
    arrivals: list[dict[str, Any]] = []
    for run in runs:
        head = positions[run[0]]
        if _is_plant(head["zone_id"]):
            unconfirmed["run_starts_in_plant"] = unconfirmed.get("run_starts_in_plant", 0) + 1
            arrivals.append({"after_sec": run[0], "before_sec": None,
                             "zone_id": head["zone_id"], "reason": "run_starts_in_plant"})
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
                member_zones = {m["zone_id"] for m in members}
                holds.append({
                    "type": "position_hold", "round_no": members[0]["round_no"],
                    "start_sec": run[start], "end_sec": run[end],
                    "observed_seconds": len(members),
                    "zone_id": member_zones.pop() if len(member_zones) == 1 else None,
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
            if _is_plant(b["zone_id"]) and b["zone_id"] != a["zone_id"]:
                # The last position of this run before the step that is not a boundary
                # reading decides where the player came from.
                index = run.index(first)
                while index > 0 and positions[run[index]]["zone_status"] == "boundary":
                    index -= 1
                a = positions[run[index]]
                if a["zone_status"] != "inside" or _is_plant(a["zone_id"]):
                    reason = ("from_plant_zone" if _is_plant(a["zone_id"])
                              else f"from_{a['zone_status']}")
                    unconfirmed[reason] = unconfirmed.get(reason, 0) + 1
                    arrivals.append({"after_sec": second, "before_sec": a["sec"],
                                     "zone_id": b["zone_id"], "reason": reason})
                    continue
                entries.append({
                    "type": "site_entry", "round_no": b["round_no"],
                    "before_sec": a["sec"], "after_sec": second, "zone_id": b["zone_id"],
                    "from_zone_id": a["zone_id"],
                    "confidence": min(a["confidence"], b["confidence"]),
                    "evidence_refs": a["evidence_refs"] + b["evidence_refs"],
                })
        if moving:
            changes.append(_change(moving, positions, geometry))
    kept = rules.change_min_m + rules.coordinate_error_m
    within_error = [c for c in changes if c["displacement_m"] < kept]
    changes = [c for c in changes if c["displacement_m"] >= kept]
    counts = {
        "strict_seconds": len(observed),
        "seconds_in_confirmed_playable_rounds": len(positions),
        "eligible_positions": len(eligible_seconds),
        "eligible_with_zone": sum(1 for s in eligible_seconds if positions[s]["zone_id"]),
        "position_hold": len(holds), "position_change": len(changes),
        "site_entry": len(entries),
        "runs": len(runs), "runs_split_by_view_change": broken_by_view,
    }
    for item in positions.values():
        if item["eligible"]:
            key = f"eligible_zone_{item['zone_status']}"
            counts[key] = counts.get(key, 0) + 1
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
        "diagnostics": {"site_arrival_unconfirmed": dict(sorted(unconfirmed.items())),
                        "position_change_within_coordinate_error": len(within_error),
                        "site_arrivals_unconfirmed": arrivals},
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


def load_candidates_for_evaluation(candidates_path: Path, report_path: Path,
                                   timeline_sha256: str) -> dict[str, Any]:
    """Read development candidates for the evaluation report, bound to the exact Map report.

    The candidates must name the SHA-256 of the Map report file the evaluation reads and the
    same canonical timeline. They stay development-only: no rule or score consumes them.
    """
    candidates: dict[str, Any] = json.loads(candidates_path.read_text(encoding="utf-8"))
    if (candidates.get("schema") != SCHEMA
            or candidates.get("qualification") != "development_candidate"
            or candidates.get("formal_outputs") != 0
            or candidates.get("continuous_path_inferred") is not False
            or candidates.get("instantaneous_speed_inferred") is not False):
        raise ValueError("Development Map position candidates v2 required")
    report_sha256 = hashlib.sha256(report_path.read_bytes()).hexdigest()
    if (candidates.get("provenance") or {}).get("report_sha256") != report_sha256:
        raise ValueError("The candidates were built from another Map report")
    if candidates.get("timeline_sha256") != timeline_sha256:
        raise ValueError("The candidates belong to another timeline")
    return candidates


def summarize_round_candidates(candidates: Mapping[str, Any], round_no: int) -> dict[str, Any]:
    """Counts of one Round's development candidates, for a human-readable report."""
    positions = [p for p in candidates["positions"]
                 if p["round_no"] == round_no and p["eligible"]]
    events = [e for e in candidates["events"] if e["round_no"] == round_no]
    zones: dict[str, int] = {}
    for position in positions:
        if position["zone_id"]:
            zones[position["zone_id"]] = zones.get(position["zone_id"], 0) + 1
    kinds: dict[str, int] = {}
    for event in events:
        kinds[event["type"]] = kinds.get(event["type"], 0) + 1
    return {
        "qualification": "development_candidate", "formal_outputs": 0,
        "eligible_position_seconds": len(positions),
        "zone_seconds": dict(sorted(zones.items())),
        "events": dict(sorted(kinds.items())),
        "site_entries": [{"after_sec": e["after_sec"], "zone_id": e["zone_id"],
                          "from_zone_id": e["from_zone_id"]}
                         for e in events if e["type"] == "site_entry"],
    }
