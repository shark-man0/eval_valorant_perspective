"""Allowlist calibration telemetry again at the Git export trust boundary."""

import math
import re
import statistics

from valorant_ai_coach.hud.diagnostics import ANCHORS, COUNTS, REASONS


def object_or_empty(value):
    return value if isinstance(value, dict) else {}


def number(value, *, count=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if not math.isfinite(value) or value < 0:
        return None
    if count:
        return value if isinstance(value, int) else None
    return value if value <= 1 else None


def sanitize_calibration(value):
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        return {"available": False}
    result = {
        "available": True,
        "schema_version": 1,
        "profile_present": value.get("profile_present") is True,
    }
    counts = object_or_empty(value.get("counts"))
    result["counts"] = {key: number(counts.get(key), count=True) for key in COUNTS}
    for key in ("fresh_geometry_success_rate", "effective_geometry_success_rate"):
        result[key] = number(value.get(key))
    reasons = object_or_empty(value.get("reasons"))
    result["reasons"] = {key: number(reasons[key], count=True) for key in REASONS if key in reasons}
    identity = object_or_empty(value.get("identity_reasons"))
    result["identity_evidence_policy"] = (
        "independent_current_frame_structures_v1" if "identity_reasons" in value else None
    )
    result["identity_reasons"] = {
        key: number(identity[key], count=True)
        for key in (
            "geometry_invalid",
            "spectator_exclusion_unverified",
            "competing_view_evidence",
            "structure_evidence_insufficient",
            "independent_hud_structures",
        )
        if key in identity
    }
    rows = value.get("anchors", [])
    for section, keys in {
        "identity_missing": ("hp_hud_structure", "ability_bar_structure", "weapon_ammo_structure"),
        "spectator_checks": (
            "not_evaluated",
            "reference_unavailable",
            "roi_unavailable",
            "geometry_mismatch",
            "roi_unobservable",
            "panel_structure_present",
            "panel_structure_excluded",
            "panel_structure_ambiguous",
            "panel_structure_mismatch",
        ),
    }.items():
        counts = object_or_empty(value.get(section))
        result[section] = {key: number(counts[key], count=True) for key in keys if key in counts}
    automatic = object_or_empty(value.get("automatic_identity_generation"))
    if automatic:
        result["automatic_identity_generation"] = sanitize_identity_generation(automatic)
    generation = object_or_empty(value.get("temporal_generation"))
    if generation:
        digest = generation.get("generated_assets_sha256")
        result["temporal_generation"] = {
            "sample_count": number(generation.get("sample_count"), count=True),
            "anchor_count": number(generation.get("anchor_count"), count=True),
            "generated_assets_sha256": digest
            if isinstance(digest, str) and re.fullmatch(r"[a-f0-9]{64}", digest)
            else None,
            "anchors": {
                name: {
                    "selected_ratio": number(
                        object_or_empty(object_or_empty(generation.get("anchors")).get(name)).get(
                            "selected_ratio"
                        )
                    ),
                    "selected_pixels": number(
                        object_or_empty(object_or_empty(generation.get("anchors")).get(name)).get(
                            "selected_pixels"
                        ),
                        count=True,
                    ),
                }
                for name in ANCHORS
            },
        }
    if not isinstance(rows, list):
        rows = []
    result["anchors"] = []
    for name in ANCHORS:
        source = next(
            (row for row in rows if isinstance(row, dict) and row.get("anchor_name") == name), {}
        )
        row = {"anchor_name": name}
        for key in ("configured", "required", "mask_presence", "asset_readable"):
            row[key] = source.get(key) is True
        for key in ("threshold", "geometry_success_rate_when_accepted"):
            row[key] = number(source.get(key))
        for key in (
            "accepted_count",
            "rejected_count",
            "unscored_count",
            "missing_during_insufficient_anchors",
            "accepted_during_geometry_success",
        ):
            row[key] = number(source.get(key), count=True)
        for key in ("content_hash", "mask_content_hash"):
            item = source.get(key)
            row[key] = (
                item if isinstance(item, str) and re.fullmatch(r"[a-f0-9]{64}", item) else None
            )
        dims = source.get("dimensions")
        row["dimensions"] = (
            dims
            if isinstance(dims, list)
            and len(dims) == 2
            and all(isinstance(x, int) and not isinstance(x, bool) and 0 < x <= 65536 for x in dims)
            else None
        )
        scores = object_or_empty(source.get("match_confidence"))
        row["match_confidence"] = {key: number(scores.get(key)) for key in ("min", "median", "max")}
        result["anchors"].append(row)
    compact_diagnostics(result)
    return result


def representatives(rows, *, limit=6):
    """Deterministic representatives of reasons, plus strongest training evidence."""
    chosen = []
    if rows:
        chosen.append(
            max(
                rows,
                key=lambda r: r.get("training_accept_count") or r.get("portrait_frame_score") or 0,
            )
        )
    seen = set()
    for row in rows:
        reason = (
            row.get("structural_rejection_reason")
            or row.get("support_rejection_reason")
            or next(
                (
                    key
                    for key, count in object_or_empty(row.get("final_rejections")).items()
                    if count
                ),
                None,
            )
            or row.get("reason")
        )
        if reason not in seen:
            seen.add(reason)
            if row not in chosen:
                chosen.append(row)
    return chosen[:limit]


def compact_diagnostics(calibration):
    """Only called on the fresh sanitized copy, never on raw/local telemetry."""
    refs = object_or_empty(
        object_or_empty(calibration.get("automatic_identity_generation")).get("references")
    )
    weapon = object_or_empty(refs.get("weapon_ammo_structure"))
    generation = object_or_empty(weapon.get("weapon_ammo_generation"))
    candidates = generation.get("candidates", [])
    keep = representatives(candidates)
    generation["candidates"] = keep
    weapon["omitted_candidate_count"] = (
        (weapon.get("omitted_candidate_count") or 0) + len(candidates) - len(keep)
    )
    panel = object_or_empty(refs.get("spectator_panel"))
    generation = object_or_empty(panel.get("spectator_generation"))
    samples = generation.get("samples", [])
    generation["portrait_statistics"] = {}
    for key in (
        "portrait_candidate_count",
        "portrait_geometry_count",
        "portrait_supported_count",
        "portrait_occupancy_rejected",
        "portrait_frame_score",
    ):
        values = [s[key] for s in samples if s.get(key) is not None]
        generation["portrait_statistics"][key] = dict(
            count=len(values),
            min=min(values) if values else None,
            median=statistics.median(values) if values else None,
            max=max(values) if values else None,
        )
    keep_samples = representatives(samples)
    generation["samples"] = keep_samples
    generation["omitted_sample_count"] = len(samples) - len(keep_samples)
    supports = generation.get("candidate_support", [])
    values = [s["training_support"] for s in supports if s.get("training_support") is not None]
    minimums = {s["minimum_required"] for s in supports if s.get("minimum_required") is not None}
    generation["candidate_support_summary"] = dict(
        count=len(values),
        min=min(values) if values else None,
        median=statistics.median(values) if values else None,
        max=max(values) if values else None,
        minimum_required=next(iter(minimums)) if len(minimums) == 1 else None,
        below_minimum_count=sum(
            s["training_support"] < s["minimum_required"]
            for s in supports
            if s.get("training_support") is not None and s.get("minimum_required") is not None
        ),
    )
    ordered = sorted(supports, key=lambda s: s.get("training_support") or 0, reverse=True)
    keep_supports = []
    if ordered:
        # Keep strongest and weakest candidates before the remaining examples.
        for support in [ordered[0], ordered[-1], *ordered]:
            if support not in keep_supports:
                keep_supports.append(support)
            if len(keep_supports) == 6:
                break
    generation["candidate_support"] = keep_supports
    generation["omitted_candidate_support_count"] = len(supports) - len(keep_supports)
    if (
        len(keep) < len(candidates)
        or len(keep_samples) < len(samples)
        or len(keep_supports) < len(supports)
    ):
        calibration["detail_truncated"] = True


def sanitize_identity_generation(value):
    references = object_or_empty(value.get("references"))
    result = {
        "version": value.get("version") if value.get("version") in (1, 2) else None,
        "identity_reference_ready": value.get("identity_reference_ready")
        if isinstance(value.get("identity_reference_ready"), bool)
        else None,
        "sample_count": number(value.get("sample_count"), count=True),
        "geometry_mode": value.get("geometry_mode")
        if value.get("geometry_mode") in ("generated", "inherited")
        else None,
        "references": {},
    }
    for name in (
        "hp_hud_structure",
        "ability_bar_structure",
        "weapon_ammo_structure",
        "spectator_clear",
        "spectator_panel",
    ):
        source = object_or_empty(references.get(name))
        row = {
            key: number(source.get(key), count=True)
            for key in (
                "training_count",
                "holdout_count",
                "training_accept_count",
                "holdout_accept_count",
                "candidate_count",
                "structural_rejected",
                "support_rejected",
                "holdout_rejected",
                "cluster_count",
                "omitted_candidate_count",
            )
        }
        row["holdout_median"] = number(source.get("holdout_median"))
        row["status"] = (
            source.get("status")
            if source.get("status") in ("generated", "inherited", "insufficient_evidence")
            else None
        )
        digest = source.get("content_hash")
        row["content_hash"] = (
            digest if isinstance(digest, str) and re.fullmatch(r"[a-f0-9]{64}", digest) else None
        )
        dims = source.get("dimensions")
        row["dimensions"] = (
            dims
            if isinstance(dims, list)
            and len(dims) == 2
            and all(isinstance(x, int) and not isinstance(x, bool) and 0 < x <= 65536 for x in dims)
            else None
        )
        result["references"][name] = row
        if name == "weapon_ammo_structure":
            row["weapon_ammo_generation"] = {
                "matcher": source.get("matcher")
                if source.get("matcher") in ("oriented_edges_v1", "masked_ncc")
                else None,
                "rejection_counts": {
                    k: number(object_or_empty(source.get("rejection_counts")).get(k), count=True)
                    for k in (
                        "seed_support_insufficient",
                        "fixed_edges_insufficient",
                        "edge_arrangement_invalid",
                        "edge_density_invalid",
                        "mask_contrast_insufficient",
                        "edge_support_insufficient",
                        "training_support_insufficient",
                    )
                },
                "candidates": [
                    sanitize_candidate(c)
                    for c in source.get("candidates", [])[:64]
                    if isinstance(c, dict)
                ]
                if isinstance(source.get("candidates"), list)
                else [],
                "selected_candidate": sanitize_candidate(
                    object_or_empty(source.get("selected_candidate"))
                ),
                "mask_presence": source.get("mask_presence") is True,
                "mask_content_hash": source.get("mask_content_hash")
                if isinstance(source.get("mask_content_hash"), str)
                and re.fullmatch(r"[a-f0-9]{64}", source["mask_content_hash"])
                else None,
            }
        if name == "spectator_panel":
            keys = (
                "observable",
                "boundary",
                "portrait",
                "textlike",
                "boundary_portrait",
                "portrait_textlike",
                "boundary_textlike",
                "all_components",
            )
            reasons = (
                "geometry_rejected",
                "contrast_rejected",
                "blur_rejected",
                "structural_rejected",
                "candidate",
            )
            samples = source.get("samples", [])
            supports = source.get("candidate_support", [])
            row["spectator_generation"] = {
                "matcher": source.get("matcher")
                if source.get("matcher") == "edge_recall_precision_v1"
                else None,
                "candidate_support": [
                    {
                        k: number(s.get(k), count=True)
                        for k in ("sample_index", "training_support", "minimum_required")
                    }
                    for s in supports[:64]
                    if isinstance(s, dict)
                ]
                if isinstance(supports, list)
                else [],
                "evidence_counts": {
                    k: number(object_or_empty(source.get("evidence_counts")).get(k), count=True)
                    for k in keys
                },
                "rejection_counts": {
                    k: number(object_or_empty(source.get("rejection_counts")).get(k), count=True)
                    for k in reasons[:-1]
                },
                "final_rejection_counts": {
                    k: number(
                        object_or_empty(source.get("final_rejection_counts")).get(k), count=True
                    )
                    for k in (
                        "text_alignment_insufficient",
                        "boundary_span_insufficient",
                        "relative_position_mismatch",
                        "component_pixels_insufficient",
                    )
                },
                "samples": [
                    {
                        **{k: s.get(k) is True for k in keys},
                        "sample_index": number(s.get("sample_index"), count=True),
                        "portrait_candidate_count": number(
                            s.get("portrait_candidate_count"), count=True
                        ),
                        "portrait_supported_count": number(
                            s.get("portrait_supported_count"), count=True
                        ),
                        "portrait_frame_score": number(s.get("portrait_frame_score")),
                        "portrait_geometry_count": number(
                            s.get("portrait_geometry_count"), count=True
                        ),
                        "portrait_occupancy_rejected": number(
                            s.get("portrait_occupancy_rejected"), count=True
                        ),
                        "portrait_side_scores": [number(v) for v in s["portrait_side_scores"]]
                        if isinstance(s.get("portrait_side_scores"), list)
                        and len(s["portrait_side_scores"]) == 4
                        else None,
                        "training": s.get("training") is True,
                        "reason": s.get("reason") if s.get("reason") in reasons else None,
                        "final_gates": {
                            k: object_or_empty(s.get("final_gates")).get(k) is True
                            for k in (
                                "portrait",
                                "text_alignment",
                                "boundary_span",
                                "component_pixels",
                            )
                        },
                        "final_rejections": {
                            k: number(object_or_empty(s.get("final_rejections")).get(k), count=True)
                            for k in (
                                "text_alignment_insufficient",
                                "boundary_span_insufficient",
                                "relative_position_mismatch",
                                "component_pixels_insufficient",
                            )
                        },
                    }
                    for s in samples[:64]
                    if isinstance(s, dict)
                ]
                if isinstance(samples, list)
                else [],
            }
    return result


def sanitize_candidate(source):
    result = {
        k: number(source.get(k), count=True)
        for k in (
            "training_cluster_size",
            "training_accept_count",
            "holdout_accept_count",
            "edge_count",
            "mask_population",
        )
    }
    result.update(
        {
            k: number(source.get(k))
            for k in (
                "temporal_variance",
                "edge_persistence",
                "stable_pixel_ratio",
                "dynamic_pixel_ratio",
                "mask_pixel_ratio",
                "holdout_prevalence",
                "stable_edge_ratio",
                "orientation_consistency",
            )
        }
    )
    bounds = source.get("roi_bounds")
    result["roi_bounds"] = (
        bounds
        if isinstance(bounds, list)
        and len(bounds) == 4
        and all(number(v) is not None for v in bounds)
        else None
    )
    dims = source.get("dimensions")
    result["dimensions"] = (
        dims
        if isinstance(dims, list)
        and len(dims) == 2
        and all(isinstance(v, int) and not isinstance(v, bool) and 0 < v <= 65536 for v in dims)
        else None
    )
    result["reason"] = (
        source.get("reason")
        if source.get("reason")
        in (
            "structural_rejected",
            "support_rejected",
            "training_candidate",
            "holdout_rejected",
            "selected",
        )
        else None
    )
    for key, allowed in (
        (
            "structural_rejection_reason",
            (
                "fixed_edges_insufficient",
                "edge_arrangement_invalid",
                "edge_density_invalid",
                "mask_contrast_insufficient",
                "edge_support_insufficient",
            ),
        ),
        ("support_rejection_reason", ("training_support_insufficient",)),
    ):
        result[key] = source.get(key) if source.get(key) in allowed else None
    for key in ("training_similarity", "holdout_similarity"):
        values = object_or_empty(source.get(key))
        result[key] = {k: number(values.get(k)) for k in ("min", "median", "max")}
        result[key]["count"] = number(values.get("count"), count=True)
    result["structural_gates"] = {
        k: object_or_empty(source.get("structural_gates")).get(k) is True
        for k in (
            "line_support",
            "spatial_spread",
            "nonparallel",
            "separated_layout",
            "arrangement",
            "edge_density",
            "edge_support",
        )
    }
    for key in ("line_count", "edge_component_count", "localized_component_count"):
        result[key] = number(source.get(key), count=True)
    for key, size in (
        ("orientation_histogram", 8),
        ("spatial_edge_spread", 2),
        ("component_centroid_spread", 2),
        ("edge_occupancy_grid", 16),
    ):
        value = source.get(key)
        result[key] = (
            [number(v) for v in value] if isinstance(value, list) and len(value) == size else None
        )
    return result
