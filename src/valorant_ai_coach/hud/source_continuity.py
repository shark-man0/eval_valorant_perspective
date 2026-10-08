"""Opt-in composite source evidence for qualified system lifecycle events.

Camera correspondence alone is insufficient. Every attested link also needs
accepted current/prior timer evidence and a physically consistent transition.
Unknown input breaks the segment; this producer never fills a player fact.
Different PTS for identical source pixels do not corroborate new evidence.
"""
from __future__ import annotations

import hashlib
import math
from collections.abc import Mapping
from typing import Any

import cv2
import numpy as np
from numpy.typing import NDArray

from .global_lifecycle import GlobalLifecycleQualification, _phase, _timer
from .round_lifecycle import MAX_SAMPLE_GAP_SEC

ImageU8 = NDArray[np.uint8]
SourceSnapshot = tuple[float, float | None, float, float, ImageU8, tuple[int, ...], str]


class CompositeSourceContinuity:
    METHOD = "camera_grid_timer_phase_v2"

    def __init__(self, qualification: GlobalLifecycleQualification) -> None:
        if not {"timer", "purchase_phase", "continuity"} <= qualification.components:
            raise ValueError("qualified timer, phase and continuity components required")
        self.qualification = qualification
        self.previous: SourceSnapshot | None = None
        self.epoch = 0
        self.origin = ""
        self.last_reason = "unobserved"

    @staticmethod
    def camera_image(image: ImageU8) -> ImageU8:
        if image.dtype != np.uint8 or image.ndim != 3 or image.shape[2] != 3:
            raise ValueError("uint8 BGR image required")
        if min(image.shape[:2]) < 32:
            raise ValueError("source image too small")
        small = cv2.resize(image, (640, 360), interpolation=cv2.INTER_AREA)
        return np.ascontiguousarray(cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)[72:288, 128:576])

    @staticmethod
    def camera_support(before: ImageU8, after: ImageU8) -> list[tuple[int, int, float]]:
        witnesses = []
        for row in range(3):
            for column in range(3):
                ys = slice(row * 72, (row + 1) * 72)
                xs = slice(round(column * 448 / 3), round((column + 1) * 448 / 3))
                previous, current = before[ys, xs], after[ys, xs]
                if min(float(previous.std()), float(current.std())) < 1.0:
                    continue
                score = float(cv2.matchTemplate(previous, current, cv2.TM_CCOEFF_NORMED)[0, 0])
                if math.isfinite(score) and score >= 0.90:
                    witnesses.append((row, column, score))
        return witnesses

    def advance(
        self, image: ImageU8, observation: Mapping[str, Any], evidence: Mapping[str, Any],
        *, geometry_valid: bool,
    ) -> dict[str, Any]:
        timestamp = observation.get("time_sec")
        if geometry_valid is not True:
            self.previous = None
            self.epoch += 1
            self.last_reason = "invalid_geometry"
            return {}
        if (
            isinstance(timestamp, bool) or not isinstance(timestamp, (int, float))
            or not math.isfinite(timestamp)
        ):
            self.previous = None
            self.epoch += 1
            self.last_reason = "invalid_source_pts"
            return {}
        try:
            camera = self.camera_image(image)
        except (ValueError, cv2.error):
            self.previous = None
            self.epoch += 1
            self.last_reason = "invalid_source_image"
            return {}
        timer, timer_score = _timer(observation)
        phase = _phase(observation)
        pixel_hash = hashlib.sha256(image.tobytes()).hexdigest()
        previous = self.previous
        self.previous = (
            float(timestamp), timer, timer_score, phase, camera, image.shape, pixel_hash,
        )
        if previous is None:
            self.origin = hashlib.sha256(camera.tobytes() + repr(timestamp).encode()).hexdigest()
            self.last_reason = "initial_frame"
            return {}
        prior_pts, prior_timer, prior_score, prior_phase, prior_camera, shape, prior_hash = previous
        gap = float(timestamp) - prior_pts
        reason = None
        if evidence.get("content_jump") is True or evidence.get("discontinuity") is True:
            reason = "explicit_discontinuity"
        elif shape != image.shape or not 0 < gap <= MAX_SAMPLE_GAP_SEC:
            reason = "invalid_geometry_shape_or_gap"
        elif pixel_hash == prior_hash:
            reason = "duplicate_source_pixels"
        elif timer is None or prior_timer is None or timer_score == 0 or prior_score == 0:
            reason = "accepted_timer_pair_unavailable"
        elif not (
            0 <= prior_timer - timer <= gap + 1.0
            or (prior_phase > 0 and phase == 0 and timer > prior_timer + 3.0)
        ):
            reason = "timer_transition_inconsistent"
        witnesses = self.camera_support(prior_camera, camera) if reason is None else []
        if reason is None and (
            len(witnesses) < 3 or len({r for r, _, _ in witnesses}) < 2
            or len({c for _, c, _ in witnesses}) < 2
        ):
            reason = "insufficient_spatial_camera_support"
        if reason is not None:
            self.epoch += 1
            self.origin = hashlib.sha256(camera.tobytes() + repr(timestamp).encode()).hexdigest()
            self.last_reason = reason
            return {}
        self.last_reason = "attested_composite_link"
        return {
            "segment": f"{self.METHOD}:{self.origin}:{self.epoch}",
            "confidence": min(prior_score, timer_score, *(score for _, _, score in witnesses)),
            "qualification_sha256": self.qualification.report_sha256,
            "source_pts_sec": float(timestamp),
            "previous_source_pts_sec": prior_pts,
            "source_pixel_sha256": pixel_hash,
            "previous_source_pixel_sha256": prior_hash,
            "method": self.METHOD,
            "camera_witness_cells": [[r, c] for r, c, _ in witnesses],
            "camera_witness_ncc": [score for _, _, score in witnesses],
        }
