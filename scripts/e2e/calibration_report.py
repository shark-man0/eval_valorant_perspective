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
    rows = value.get("anchors", [])
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
