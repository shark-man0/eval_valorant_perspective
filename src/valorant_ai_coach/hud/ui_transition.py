"""Pending system UI transition; no player facts or inferred clock values."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from .round_lifecycle import MIN_START_CONFIRMATION_SEC, BoundaryDecision


@dataclass
class PendingUiStart:
    time_sec: float
    phase_timer: float
    confidence: float
    provenance: dict[str, Any]
    stable_since: float | None = None
    previous_timer: float | None = None
    previous_timer_pts: float | None = None
    accepted_count: int = 0
    stable_confidence: float = 1.0
    samples: list[dict[str, Any]] = field(default_factory=list)

    def advance(
        self,
        timestamp: float,
        timer: float | None,
        timer_confidence: float,
        display: Any,
        continuity_confidence: float,
        display_provenance: dict[str, Any] | None,
        scene_proof: Mapping[str, Any],
    ) -> BoundaryDecision | None:
        self.confidence = min(self.confidence, continuity_confidence)
        # Keep every observed display/value, including the ones that cannot
        # form a coherent active clock. Do not format or repair OCR text.
        self.samples.append(
            {
                "pts_sec": timestamp,
                "observed_seconds": timer,
                "observed_display": display,
                "reader_confidence": timer_confidence,
                "display_provenance": display_provenance,
                "source_pixel_sha256": scene_proof["source_pixel_sha256"],
                "previous_source_pixel_sha256": scene_proof["previous_source_pixel_sha256"],
            }
        )
        if timer is None or timer_confidence <= 0 or timer <= self.phase_timer + 3:
            self.stable_since = None
            self.previous_timer = None
            self.previous_timer_pts = None
            self.accepted_count = 0
            return None
        consistent = (
            self.previous_timer is not None
            and self.previous_timer_pts is not None
            and 0 <= self.previous_timer - timer <= timestamp - self.previous_timer_pts + 1
        )
        if not consistent:
            self.stable_since = timestamp
            self.accepted_count = 0
            self.stable_confidence = 1.0
        self.previous_timer = timer
        self.previous_timer_pts = timestamp
        self.accepted_count += 1
        self.stable_confidence = min(self.stable_confidence, timer_confidence)
        if (
            self.accepted_count < 2
            or self.stable_since is None
            or timestamp - self.stable_since < MIN_START_CONFIRMATION_SEC
        ):
            return None
        self.provenance.update(
            confirmation_pts_sec=timestamp,
            pts_sec=[sample["pts_sec"] for sample in self.samples],
            clock_display_samples=[dict(sample) for sample in self.samples],
            coherent_clock_begin_pts_sec=self.stable_since,
            coherent_clock_observation_count=self.accepted_count,
        )
        return BoundaryDecision(
            "round_start",
            self.time_sec,
            min(self.confidence, self.stable_confidence),
            {"evidence_provenance": self.provenance},
        )
