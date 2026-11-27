"""Exact sampled-frame human view labels; no automatic or interval ownership."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from .development_position_review import observation_fingerprint


def compare_view_review(
    record: dict[str, Any], review: dict[str, Any], *, frame_sha256: str,
) -> dict[str, Any]:
    """Import a reviewed frame or explicit frame set, never an inferred time range.

    A clip response must enumerate the actual sampled frame hashes. Frames
    between samples, even within a short clip, remain unreviewed. Matching a
    recorder's agent is never accepted as a human view label.
    """
    keys = ("source_id", "acquisition_id", "time_sec", "frame_index", "map_id",
            "geometry_version")
    if (record.get("qualification") != "development_only"
            or record.get("ownership", {}).get("identity") != "UNKNOWN"
            or record.get("formal_self_position_fact") is not None
            or review.get("status") != "human_confirmed"
            or review.get("label_origin") != "source_frame_view_review"
            or review.get("not_used_for_fitting") is not True
            or any(k not in record or review.get(k) != record[k] for k in keys)
            or review.get("frame_sha256") != frame_sha256
            or review.get("prediction_sha256") != observation_fingerprint(record)
            or review.get("role") not in {
                "SELF_LIVE", "SELF_PURCHASE", "SELF_PHASE_UNKNOWN", "PURCHASE",
                "SPECTATOR", "DEATH", "UNKNOWN"}):
        raise ValueError("Exact independent human frame-view review required")
    return {
        "qualification": "development_only", "ownership": "UNKNOWN",
        "sample_scope": "this_observation_only", "human_view_role": review["role"],
        "frame_sha256": frame_sha256, "prediction_sha256": review["prediction_sha256"],
        "review_sha256": hashlib.sha256(json.dumps(
            review, sort_keys=True, allow_nan=False).encode("utf-8")).hexdigest(),
        "automatic_self_ownership": False,
    }
