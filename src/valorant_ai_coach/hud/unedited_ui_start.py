"""Source-assured UI start candidates; release still needs reader qualification.

This tracker does not produce native events, attest reader accuracy, or supply
player-owned facts. Source assurance excludes edits, never recording loss.
"""
from __future__ import annotations

import math
from collections.abc import Mapping
from fractions import Fraction
from typing import Any

from .global_lifecycle import _display, _hash, _phase, _timer
from .round_lifecycle import MAX_SAMPLE_GAP_SEC, MIN_START_CONFIRMATION_SEC, BoundaryDecision
from .ui_transition import PendingUiStart
from .unedited_input import UneditedInputContract


class UneditedUiStartTracker:
    def __init__(self, contract: UneditedInputContract, *, native_step_ticks: int) -> None:
        if type(native_step_ticks) is not int or native_step_ticks <= 0:
            raise ValueError("positive native cadence required")
        self.contract = contract
        self.step = native_step_ticks
        self.previous_source: Mapping[str, Any] | None = None
        self.state = "unobserved"
        self.phase_pts: list[float] = []
        self.phase_score = 0.0
        self.phase_timer: float | None = None
        self.phase_timer_score = 0.0
        self.pending: PendingUiStart | None = None
        self.started = False

    def reset(self) -> None:
        self.state = "unobserved"
        self.phase_pts.clear()
        self.phase_timer = None
        self.phase_timer_score = 0.0
        self.phase_score = 0.0
        self.pending = None
        self.started = False

    def advance(
        self, row: Mapping[str, Any], *, phase_scan_valid: bool,
    ) -> BoundaryDecision | None:
        """Phase nonmatch proposes a transition; coherent clock corroborates it.

        A valid scan must be supplied by the image producer after geometry/ROI
        availability and occlusion checks. A failed scan is never phase absence.
        Returned decisions are candidates until separately qualified/replayed.
        """
        prior = self.previous_source
        self.previous_source = dict(row)
        observation = row["system_observation"]
        timestamp = observation.get("time_sec")
        ticks = row.get("source_pts_ticks")
        base = Fraction(row["source_time_base"])
        if (
            row.get("source_video_sha256") != self.contract.source_video_sha256
            or type(ticks) is not int or ticks < 0 or base <= 0
            or type(timestamp) not in (int, float) or not math.isfinite(timestamp)
            or row.get("source_pts_sec") != timestamp or float(ticks * base) != timestamp
            or not row.get("source_epoch")
            or not _hash(row.get("source_pixel_sha256"))
        ):
            self.reset()
            raise ValueError("assured source binding/PTS mismatch")
        if prior is not None and (
            ticks - prior["source_pts_ticks"] != self.step
            or row["source_epoch"] != prior["source_epoch"]
            or row["source_time_base"] != prior["source_time_base"]
            or timestamp - prior["source_pts_sec"] > MAX_SAMPLE_GAP_SEC
            or row["source_pixel_sha256"] == prior["source_pixel_sha256"]
        ):
            self.reset()
            return None
        evidence = row.get("system_evidence", {})
        if evidence.get("content_jump") is True or evidence.get("discontinuity") is True:
            self.reset()
            return None
        # A rejected current UI observation cannot close an already started round.
        # Keep duplicate suppression through menus, view changes and occlusion;
        # source discontinuities above still clear the latch. This start-only
        # tracker has no qualified end/rearm path and must not infer one here.
        if self.started:
            return None
        if not phase_scan_valid or observation.get("quality", {}).get("occluded_rois"):
            self.reset()
            return None
        phase = _phase(observation)
        if evidence.get('assured_phase_present') is True and not phase:
            # Source text is present but its temporal flag is unconfirmed.
            # This is neither a phase disappearance nor a preparation proof.
            self.reset()
            return None
        allowed_flags = {"buy_phase_banner"} if phase else set()
        if (
            observation.get("primary_state") not in {"unknown", "live_first_person"}
            or set(observation.get("state_flags", ())) - allowed_flags
        ):
            self.reset()
            return None
        timer, score = _timer(observation)
        display = _display(observation)
        if phase:
            if self.pending is not None:
                self.reset()
            self.phase_pts.append(timestamp)
            self.phase_score = min(self.phase_score or phase, phase)
            self.phase_timer = timer if display is not None else None
            self.phase_timer_score = score if display is not None else 0.0
            self.state = "pre_round"
            return None
        if self.pending is None:
            if (
                len(self.phase_pts) < 2
                or self.phase_pts[-1] - self.phase_pts[0] < MIN_START_CONFIRMATION_SEC
                or self.phase_timer is None or self.phase_timer_score <= 0
            ):
                return None
            self.pending = PendingUiStart(
                timestamp, self.phase_timer, min(self.phase_score, self.phase_timer_score),
                {"scope": "global_system", "producer": "unedited_ui_start_tracker",
                 "input_contract_sha256": self.contract.fingerprint,
                 "preparation_pts_sec": [self.phase_pts[0], self.phase_pts[-1]],
                 "reader_qualification_required": True},
            )
            self.state = "transient_ui_transition"
        proof = {
            "source_pixel_sha256": row["source_pixel_sha256"],
            "previous_source_pixel_sha256": prior["source_pixel_sha256"] if prior else None,
        }
        candidate = self.pending.advance(
            timestamp, timer, min(score, display["provenance"]["confidence"]) if display else 0.0,
            observation.get("values", {}).get("round_time_remaining_display"),
            1.0, display["provenance"] if display else None, proof,
        )
        if timestamp - self.pending.time_sec > MAX_SAMPLE_GAP_SEC:
            self.reset()
            return None
        if candidate is not None:
            self.started = True
            self.state = "round_active_candidate"
        return candidate
