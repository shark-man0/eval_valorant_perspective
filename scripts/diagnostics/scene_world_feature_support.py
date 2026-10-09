"""Shared reviewed-world feature identities; descriptive, never a proof.

Only actually matched reference pixels are called world-supported; the rest of
an ROI remains unknown. A region's whole-crop NCC need not survive perspective
motion. Both source frames must independently match the same reviewed world
features, with the existing patch NCC/FB/RANSAC checks and distributed support.
This still cannot prove uninterrupted time, or reject view-preserving edits.
"""

from __future__ import annotations


def common_world_feature_support(previous, current, previous_metrics, current_metrics):
    coherent = all(
        m["accepted_reference_tracks"] >= 3
        and m["model_inliers"] >= 0.90 * m["accepted_reference_tracks"]
        for m in (previous_metrics, current_metrics)
    )

    def identities(tracks):
        return {
            (t["region"], *t["reference_xy"]): t
            for t in tracks
            if t["model_inlier"] and t["patch_ncc"] >= 0.90 and t["fb_error_px"] <= 1
        }

    before, after = identities(previous), identities(current)
    shared = sorted(before.keys() & after.keys()) if coherent else []

    def cells(points):
        return {
            (int(t["current_xy"][1] / 120), int(t["current_xy"][0] / (640 / 3))) for t in points
        }

    previous_cells = cells([before[k] for k in shared])
    current_cells = cells([after[k] for k in shared])

    def distributed(points):
        return (
            len(points) >= 3
            and len({p[0] for p in points}) >= 2
            and len({p[1] for p in points}) >= 2
            and all(0 <= row <= 2 and 0 <= col <= 2 for row, col in points)
        )

    regions = sorted({key[0] for key in shared})
    return {
        "supported_regions": regions,
        "previous_witness_cells_full_image": sorted([list(p) for p in previous_cells]),
        "current_witness_cells_full_image": sorted([list(p) for p in current_cells]),
        "shared_world_feature_count": len(shared),
        "distributed_descriptive_support": (
            len(regions) >= 3 and distributed(previous_cells) and distributed(current_cells)
        ),
        "minimum_patch_ncc": None
        if not shared
        else min(min(before[key]["patch_ncc"], after[key]["patch_ncc"]) for key in shared),
        "world_scope": "Only linked reviewed reference patches; remaining pixels unknown",
        "runtime_proof_authorized": False,
    }
