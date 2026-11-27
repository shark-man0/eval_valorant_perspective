"""Add measured, corroborated self-ring runs without replacing baseline observations.

The detector and its parameters are the unchanged #194 self-ring reader. This module
only accepts its unique measurements with current reference alignment, on the same
native samples as an admitted recorder-view episode. Runs stop at every absent,
ambiguous, unregistered or contradictory observation. No point is propagated.
"""

from __future__ import annotations

import math
from collections import Counter

import numpy as np

from valorant_ai_coach.temporal.evidence import digest, native_time
from valorant_ai_coach.temporal.map_path_quality import measure_path_quality
from valorant_ai_coach.temporal.map_recorder_path import (
    join_recorder_seconds,
    measure_operable_coverage,
)
from valorant_ai_coach.temporal.map_reference_support import clearly_outside_atlas
from valorant_ai_coach.temporal.map_view_episodes import map_view_episodes

METHOD = "development_current_self_ring_complement_v1"


def complement(
    timeline,
    baseline,
    measurements,
    *,
    map_id,
    reference_sha256,
    atlas_distances,
    operable,
    receipt_sha256,
):
    """Return a separate development report and explicit reasons for abstention.

    ``measurements`` must be produced by the exact-pixel replay, including its current
    ROI digest and a verified single-map reference fit. It is not a label stream.
    """
    if (
        baseline.get("formal_outputs") != 0
        or baseline.get("qualified") is not False
        or baseline.get("interpolated_samples") != 0
    ):
        raise ValueError("An unqualified measured-only development baseline is required")
    existing = {p["sample"]["sample_sha256"]: p for s in baseline["segments"] for p in s}
    native = timeline["native_frames"]
    segments, evidence = [], {}
    counts = Counter()
    for episode in map_view_episodes(timeline):
        run = []

        def flush(episode=episode):
            nonlocal run
            if len(run) < 3:
                counts["short_run_points"] += len(run)
            elif any(p[2] for p in run):
                counts["baseline_conflict_run_points"] += len(run)
            else:
                anchor = digest([METHOD, episode.episode_ref, run[0][0], run[-1][0]])
                additions = []
                for ordinal, (key, point, _) in enumerate(run, 1):
                    if key in existing:
                        if additions:
                            segments.append(additions)
                            additions = []
                        continue
                    point.update(support_count=ordinal, track_anchor=anchor)
                    additions.append(point)
                    evidence[key] = {
                        "center_frame_px": measurements[key]["center_frame_px"],
                        "run_endpoints": [run[0][0], run[-1][0]],
                        "run_length": len(run),
                        "receipt_sha256": receipt_sha256,
                    }
                if additions:
                    segments.append(additions)
            run = []

        for key in episode.current_samples:
            row = measurements.get(key, {})
            fit = row.get("fit")
            ring = row.get("ring", {})
            sample = native[key]["sample"]
            reason = None
            if key not in operable:
                reason = "no_current_operability"
            elif ring.get("status") != "UNIQUE":
                reason = "ring_" + ring.get("status", "pixels_unavailable").lower()
            elif not fit or len(fit.get("map_name_candidates", ())) != 1:
                reason = "no_current_registration"
            elif fit.get("roi_pixel_sha256") != row.get("roi_pixel_sha256"):
                raise ValueError("Current ring and registration use different pixels")
            if reason:
                flush()
                counts[reason] += 1
                continue
            reference = fit["map_name_candidates"][0]
            if (
                reference["map_id"] != map_id
                or not 0 <= reference["fit_residual_p95_reference_px"] <= 8
            ):
                raise ValueError("Unexpected map or unverified current fit")
            matrix = np.asarray(reference["reference_to_roi_homography_candidate"], dtype=float)
            center = ring["center_roi_px"]
            placed = np.linalg.solve(matrix, np.asarray([*center, 1.0]))
            coordinate = (placed[:2] / placed[2]).tolist()
            if clearly_outside_atlas(atlas_distances, coordinate):
                flush()
                counts["outside_current_floor"] += 1
                continue
            conflict = False
            if key in existing:
                prior = matrix @ np.asarray([*existing[key]["map_reference_px"], 1.0])
                conflict = math.dist(prior[:2] / prior[2], center) > 6
                counts["baseline_disagrees" if conflict else "baseline_agrees"] += 1
            point = {
                "sample": sample,
                "candidate_index": 0,
                "support_count": 1,
                "kind": "selected",
                "map_id": map_id,
                "reference_sha256": reference_sha256,
                "map_reference_px": coordinate,
                "fit_residual_p95_reference_px": reference["fit_residual_p95_reference_px"],
                "selection_method": METHOD,
                "track_anchor": "",
                "recorder_agent_uuid_candidate": None,
                "qualified": False,
                "position_authority": False,
                "zone_candidate": None,
                "callout_candidate": None,
            }
            if run:
                previous = native[run[-1][0]]["sample"]
                elapsed = float(native_time(sample) - native_time(previous))
                distance = math.dist(
                    row["center_frame_px"], measurements[run[-1][0]]["center_frame_px"]
                )
                prior_placed = matrix @ np.asarray([*run[-1][1]["map_reference_px"], 1.0])
                world_distance_native = math.dist(prior_placed[:2] / prior_placed[2], center)
                if (
                    not 0 < elapsed <= 0.25
                    or distance > (4 + 44 * elapsed) * sample["frame_size_px"][0] / 1920
                    or world_distance_native
                    > (4 + 44 * elapsed) * sample["frame_size_px"][0] / 1920
                ):
                    flush()
                    counts["measurement_jump_or_gap"] += 1
            run.append((key, point, conflict))
        flush()
    result = {
        **baseline,
        "segments": sorted(
            [*baseline["segments"], *segments], key=lambda s: native_time(s[0]["sample"])
        ),
    }
    result["second_rows"] = join_recorder_seconds(result, timeline)
    result["operable_coverage"] = measure_operable_coverage(
        result, timeline["seconds"], result["second_rows"], operable
    )
    result["path_quality"] = measure_path_quality(
        result, timeline["seconds"], result["second_rows"], operable
    )
    result["ring_complement"] = {
        "method": METHOD,
        "counts": dict(counts),
        "added_evidence": evidence,
        "formal_outputs": 0,
        "receipt_sha256": receipt_sha256,
    }
    return result
