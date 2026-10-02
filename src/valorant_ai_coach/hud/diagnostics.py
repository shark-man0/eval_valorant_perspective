"""Image-free calibration telemetry; never used as recognition evidence."""

from __future__ import annotations

import hashlib
import math
from collections import Counter
from collections.abc import Mapping
from statistics import median
from typing import Any

import cv2
import numpy as np

from .layout import CalibrationResult, HudLayout
from .templates import HudTemplateProfile

ANCHORS = ("round_timer", "top_match_bar", "player_hp_armor", "abilities")
REASONS = (
    "invalid_resolution",
    "resolution_mismatch",
    "aspect_ratio_mismatch",
    "reference_resolution_missing",
    "letterbox_present",
    "letterbox_unknown",
    "crop_present",
    "crop_unknown",
    "insufficient_anchors",
    "insufficient_anchor_inliers",
    "anchor_position_mismatch",
    "anchor_scale_mismatch",
    "frame_resolution_changed",
    "layout_uncalibrated",
    "crop_unknown_or_present",
    "calibration_required",
)
COUNTS = (
    "frames",
    "fresh_geometry_success",
    "effective_geometry_success",
    "retained_geometry_frames",
    "geometry_invalid_unknown",
    "geometry_valid_state_unknown",
    "live_identity_evidence_insufficient",
    "insufficient_anchors_frames",
)


class CalibrationTelemetry:
    def __init__(self, profile: HudTemplateProfile | None, layout: HudLayout) -> None:
        self.anchors: dict[str, dict[str, Any]] = {}
        self.scores: dict[str, list[float]] = {name: [] for name in ANCHORS}
        self.counts: Counter[str] = Counter()
        self.reasons: Counter[str] = Counter()
        self.identity_reasons: Counter[str] = Counter()
        self.spectator_checks: Counter[str] = Counter()
        self.identity_missing: Counter[str] = Counter()
        self.required = set((layout.calibration_policy or {}).get("required_anchors", ANCHORS))
        profile_raw = getattr(profile, "raw", {})
        self.identity_generation = (
            profile_raw.get("automatic_identity_generation")
            if isinstance(profile_raw, Mapping)
            else None
        )
        self.generation = (
            profile_raw.get("temporal_generation") if isinstance(profile_raw, Mapping) else None
        )
        specs = profile_raw.get("anchors", {}) if isinstance(profile_raw, Mapping) else {}
        for name in ANCHORS:
            spec = specs.get(name, {})
            if not isinstance(spec, Mapping):
                spec = {}
            threshold = spec.get("threshold", 0.9)
            row: dict[str, Any] = {
                "anchor_name": name,
                "configured": bool(spec),
                "required": name in self.required,
                "threshold": float(threshold)
                if isinstance(threshold, (float, int)) and math.isfinite(threshold)
                else None,
                "mask_presence": "mask" in spec,
                "dimensions": None,
                "content_hash": None,
                "mask_content_hash": None,
                "asset_readable": False,
                "accepted_count": 0,
                "rejected_count": 0,
                "unscored_count": 0,
                "missing_during_insufficient_anchors": 0,
                "accepted_during_geometry_success": 0,
            }
            if profile and isinstance(spec.get("template"), str):
                try:
                    path = profile.resolve_asset(spec["template"])
                    row["content_hash"] = hashlib.sha256(path.read_bytes()).hexdigest()
                    image = cv2.imdecode(
                        np.frombuffer(path.read_bytes(), np.uint8), cv2.IMREAD_GRAYSCALE
                    )
                    if image is not None:
                        row["dimensions"] = [int(image.shape[1]), int(image.shape[0])]
                        row["asset_readable"] = True
                    if isinstance(spec.get("mask"), str):
                        row["mask_content_hash"] = hashlib.sha256(
                            profile.resolve_asset(spec["mask"]).read_bytes()
                        ).hexdigest()
                except (OSError, ValueError, cv2.error):
                    pass  # Never export paths or exception strings.
            self.anchors[name] = row
        self.profile_present = profile is not None

    def record(
        self,
        accepted: Mapping[str, Any],
        scores: Mapping[str, float],
        fresh: CalibrationResult,
        effective: CalibrationResult,
        state: str,
        identity_count: int,
    ) -> None:
        self.counts["frames"] += 1
        self.counts["fresh_geometry_success"] += fresh.calibrated
        self.counts["effective_geometry_success"] += effective.calibrated
        self.counts["retained_geometry_frames"] += effective.calibrated and not fresh.calibrated
        self.counts["geometry_invalid_unknown"] += not effective.calibrated and state == "unknown"
        self.counts["geometry_valid_state_unknown"] += effective.calibrated and state == "unknown"
        self.counts["live_identity_evidence_insufficient"] += identity_count < 3
        insufficient = "insufficient_anchors" in fresh.reasons
        self.counts["insufficient_anchors_frames"] += insufficient
        self.reasons.update(reason for reason in fresh.reasons if reason in REASONS)
        for name, row in self.anchors.items():
            row["accepted_count"] += name in accepted
            row["rejected_count"] += name not in accepted
            row["missing_during_insufficient_anchors"] += (
                insufficient and name in self.required and name not in accepted
            )
            row["accepted_during_geometry_success"] += name in accepted and fresh.calibrated
            score = scores.get(name)
            if score is not None and math.isfinite(score):
                self.scores[name].append(score)
            else:
                row["unscored_count"] += 1

    def snapshot(self) -> dict[str, Any]:
        total = self.counts["frames"]
        rows = []
        for name, row in self.anchors.items():
            values = self.scores[name]
            rows.append(
                {
                    **row,
                    "match_confidence": {
                        "min": min(values) if values else None,
                        "median": median(values) if values else None,
                        "max": max(values) if values else None,
                    },
                    "geometry_success_rate_when_accepted": (
                        row["accepted_during_geometry_success"] / row["accepted_count"]
                        if row["accepted_count"]
                        else None
                    ),
                }
            )
        return {
            "schema_version": 1,
            "profile_present": self.profile_present,
            "counts": {name: self.counts[name] for name in COUNTS},
            "fresh_geometry_success_rate": self.counts["fresh_geometry_success"] / total
            if total
            else None,
            "effective_geometry_success_rate": self.counts["effective_geometry_success"] / total
            if total
            else None,
            "reasons": dict(self.reasons),
            "identity_reasons": dict(self.identity_reasons),
            "identity_missing": dict(self.identity_missing),
            "spectator_checks": dict(self.spectator_checks),
            "temporal_generation": self.generation,
            "automatic_identity_generation": self.identity_generation,
            "anchors": rows,
        }
