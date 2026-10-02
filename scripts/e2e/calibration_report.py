"""Allowlist calibration telemetry again at the Git export trust boundary."""

import math
import re

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
    return result


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
    return result
