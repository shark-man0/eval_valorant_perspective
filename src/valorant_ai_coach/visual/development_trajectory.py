"""Measured candidate paths; never a Production Fact/Event or a coaching score.

Edges join adjacent observations only. Their chords are a display convention,
not recovered movement between samples, walkable routes or line of sight.
Durations describe spans bracketed by observations, not continuous occupancy.
All distances use the public reference image pixels, never world metres.
"""

from __future__ import annotations

import math
from collections import Counter
from typing import Any, TypeGuard

from .development_position_review import observation_fingerprint


def _number(value: Any) -> TypeGuard[int | float]:
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value))


def analyze_candidate_path(
    records: list[dict[str, Any]], *, reference_size_px: tuple[float, float],
    max_gap_sec: float = .3, max_speed_norm_per_sec: float = .4,
    position_uncertainty_px: float = 14, quiet_window_sec: float = 1.0,
) -> dict[str, Any]:
    """Analyze supplied acquisition order without sorting, filling or assigning self.

    A caller-supplied uncertainty bound is a development sensitivity parameter,
    not a qualified accuracy bound. A window ending at each edge is classified:
    moving means endpoint displacement > twice that bound; low_displacement
    needs a complete contiguous window with diameter <= twice the bound.
    Neither proves an instantaneous stop, speed, ownership or tactical intent.
    """
    parameters = (*reference_size_px, max_gap_sec, max_speed_norm_per_sec,
                  position_uncertainty_px, quiet_window_sec)
    if any(not _number(x) or x <= 0 for x in parameters):
        raise ValueError("Finite positive geometry and analysis parameters required")
    samples: list[dict[str, Any]] = []
    segments: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    transitions: list[dict[str, Any]] = []
    previous: dict[str, Any] | None = None
    last_zone: dict[str, Any] | None = None
    window: list[dict[str, Any]] = []
    zone_spans: Counter[str] = Counter()
    region_spans: Counter[str] = Counter()
    interior_spans: Counter[str] = Counter()
    for index, record in enumerate(records):
        if (record.get("qualification") != "development_only"
                or record.get("ownership", {}).get("identity") != "UNKNOWN"
                or record.get("formal_self_position_fact") is not None):
            raise ValueError("Explicit UNKNOWN development envelopes required")
        time = record.get("time_sec")
        frame = record.get("frame_index")
        if not _number(time) or time < 0 or not isinstance(frame, int) or isinstance(frame, bool):
            raise ValueError("Finite source time and integer frame index required")
        keys = ("source_id", "acquisition_id", "context_sha256", "map_id", "geometry_version")
        if any(not isinstance(record.get(key), str) or not record[key] for key in keys):
            raise ValueError("Source, acquisition, context and geometry identity required")
        context = tuple(record[key] for key in keys)
        point: Any = record.get("map_position_norm")
        evidence = record.get("ownership_evidence") or {}
        review = record.get("position_review") or {}
        if review and (
            review.get("qualification") != "development_only"
            or review.get("ownership") != "UNKNOWN"
            or review.get("sample_scope") != "this_observation_only"
            or review.get("prediction_sha256") != observation_fingerprint(record)
        ):
            raise ValueError("Coordinate review must match this frozen prediction")
        reason = None
        if (evidence.get("block_position_candidate") is True
                or review.get("human_reviewed_role") in {"NONSELF", "SPECTATOR", "DEATH"}):
            reason = "independent_context_or_review_blocks_candidate"
        elif record.get("ownership", {}).get("view_eligible") is not True:
            reason = "view_not_self_eligible"
        elif (record.get("calibration", {}).get("status") != "ok"
              or not isinstance(record.get("map_segment"), int)):
            reason = "calibration_or_track_unknown"
        elif (not isinstance(point, (list, tuple)) or len(point) != 2
              or any(not _number(p) or not 0 <= p <= 1 for p in point)):
            reason = "position_unknown"
        zone = record.get("zone_resolution", {})
        zone_id = zone.get("zone_id")
        if (zone.get("qualification") != "development_only"
                or zone.get("ownership") != "UNKNOWN"
                or zone.get("boundary_state") != "clear"
                or zone.get("held_from_previous") is not False
                or not isinstance(zone_id, str)):
            zone_id = None
        sample = {
            "index": index, "time_sec": time, "frame_index": frame,
            "source_id": record["source_id"], "acquisition_id": record["acquisition_id"],
            "map_id": record["map_id"], "geometry_version": record["geometry_version"],
            "point_norm": list(point) if reason is None else None,
            "zone_id": zone_id if reason is None else None,
            "segment": None, "break_reason": reason,
            "appearance_reason": record.get("appearance", {}).get("reason", "unknown"),
            "appearance_similarity": record.get("appearance", {}).get("appearance_score"),
            "calibration_score": record.get("calibration", {}).get("confidence"),
            "observed_view": record.get("ownership", {}).get("observed_view", "unknown"),
            "marker_reference_evidence": record.get("marker_reference_evidence"),
            "ownership_evidence": evidence or None, "position_review": review or None,
            "ownership": "UNKNOWN", "qualification": "development_only",
        }
        region = record.get("development_region_candidate") or {}
        region_id = region.get("region_id")
        if (reason is not None or region.get("qualification") != "development_only"
                or region.get("ownership") != "UNKNOWN" or not isinstance(region_id, str)):
            region_id = None
        sample["region_candidate_id"] = region_id
        sample["region_candidate_evidence"] = region or None
        if reason is None and previous is not None:
            dt = time - previous["time_sec"]
            previous_record = records[previous["index"]]
            if context != tuple(previous_record[key] for key in keys):
                reason = "acquisition_or_geometry_change"
            elif frame <= previous["frame_index"] or not 0 < dt <= max_gap_sec + 1e-9:
                reason = "time_or_frame_discontinuity"
            elif record["map_segment"] != previous_record["map_segment"]:
                reason = "upstream_track_break"
            elif math.dist(point, previous["point_norm"]) / dt > max_speed_norm_per_sec:
                reason = "position_jump"
        if sample["point_norm"] is None:
            previous, last_zone, window = None, None, []
        else:
            if previous is None or reason is not None:
                segments.append({"segment": len(segments), "sample_indices": [],
                                 "observed_span_sec": 0.0,
                                 "source_id": record["source_id"],
                                 "acquisition_id": record["acquisition_id"],
                                 "qualification": "development_only", "ownership": "UNKNOWN"})
                previous, last_zone, window = None, None, []
                sample["break_reason"] = reason or "start_or_resume"
            sample["segment"] = len(segments)-1
            segment = segments[-1]
            segment["sample_indices"].append(index)
            window.append(sample)
            if previous is not None:
                dt = time-previous["time_sec"]
                distance = math.hypot(*[(point[k]-previous["point_norm"][k])
                                       * reference_size_px[k] for k in range(2)])
                while len(window) > 2 and time-window[1]["time_sec"] >= quiet_window_sec:
                    window.pop(0)
                complete = time-window[0]["time_sec"] >= quiet_window_sec-1e-9
                window_displacement = math.hypot(*[
                    (point[k]-window[0]["point_norm"][k])*reference_size_px[k] for k in range(2)])
                quiet = complete and all(
                    math.hypot(*[(a["point_norm"][k]-b["point_norm"][k])
                                 * reference_size_px[k] for k in range(2)])
                    <= 2*position_uncertainty_px for a in window for b in window)
                motion = ("moving_candidate" if complete and window_displacement
                          > 2*position_uncertainty_px
                          else "low_displacement_candidate" if quiet else "indeterminate")
                same_zone = zone_id is not None and zone_id == previous["zone_id"]
                edge = {"from_index": previous["index"], "to_index": index,
                        "segment": sample["segment"], "observed_span_sec": dt,
                        "chord_reference_px": distance, "motion": motion,
                        "ending_window_displacement_reference_px": window_displacement,
                        "zone_id": zone_id if same_zone else None,
                        "qualification": "development_only", "ownership": "UNKNOWN"}
                edges.append(edge)
                segment["observed_span_sec"] += dt
                if same_zone:
                    zone_spans[zone_id] += dt
                if region_id is not None and region_id == previous["region_candidate_id"]:
                    region_spans[region_id] += dt
                    before = previous.get("region_candidate_evidence") or {}
                    radius = region.get("assumed_error_radius_reference_px")
                    if (_number(radius) and radius >= 0
                            and before.get("assumed_error_radius_reference_px") == radius
                            and all(r.get("boundary_assessment") == "interior_under_assumption"
                                    and _number(r.get("boundary_clearance_reference_px"))
                                    and r["boundary_clearance_reference_px"] > radius
                                    for r in (before, region))):
                        interior_spans[region_id] += dt
            if zone_id is not None:
                if last_zone is not None and last_zone["zone_id"] != zone_id:
                    transitions.append({
                        "candidate_kind": "zone_change_bracket",
                        "from_zone_id": last_zone["zone_id"], "to_zone_id": zone_id,
                        "from_index": last_zone["index"], "to_index": index,
                        "segment": sample["segment"], "crossing_time": "UNKNOWN",
                        "qualification": "development_only", "ownership": "UNKNOWN",
                    })
                last_zone = sample
            previous = sample
        samples.append(sample)
    return {
        "qualification": "development_only", "ownership": "UNKNOWN",
        "formal_self_position_fact": None,
        "parameters": {"reference_size_px": list(reference_size_px),
                       "max_gap_sec": max_gap_sec,
                       "max_speed_norm_per_sec": max_speed_norm_per_sec,
                       "position_uncertainty_px": position_uncertainty_px,
                       "quiet_window_sec": quiet_window_sec},
        "samples": samples, "segments": segments, "edges": edges,
        "zone_change_brackets": transitions,
        "zone_observation_spans_sec": dict(zone_spans),
        "region_candidate_observation_spans_sec": dict(region_spans),
        "region_interior_spans_under_assumption_sec": dict(interior_spans),
        "coordinate_review_coverage": {
            "reviewed_position_observations": sum(
                s["point_norm"] is not None and bool(s["position_review"]) for s in samples),
            "unreviewed_position_observations": sum(
                s["point_norm"] is not None and not s["position_review"] for s in samples),
            "both_endpoints_reviewed_span_sec": sum(e["observed_span_sec"] for e in edges
                if samples[e["from_index"]]["position_review"]
                and samples[e["to_index"]]["position_review"]),
            "unreviewed_endpoint_span_sec": sum(e["observed_span_sec"] for e in edges
                if not samples[e["from_index"]]["position_review"]
                or not samples[e["to_index"]]["position_review"]),
            "transferable_coordinate_accuracy_bound": "unmeasured",
        },
        "motion_observation_spans_sec": {
            name: sum(e["observed_span_sec"] for e in edges if e["motion"] == name)
            for name in ("moving_candidate", "low_displacement_candidate", "indeterminate")},
        "position_unknown_observations": sum(s["point_norm"] is None for s in samples),
        "limitations": ["No interpolation; chords are not observed routes between samples.",
                        "Observation spans do not prove uninterrupted Zone occupancy.",
                        "UNKNOWN ownership; no tactical judgement or Production events.",
                        "Motion thresholds are sensitivity parameters, not qualified accuracy."],
    }
