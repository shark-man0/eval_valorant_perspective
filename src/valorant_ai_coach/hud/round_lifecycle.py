"""Fail-closed round lifecycle over source observations, without evaluator input."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal

LifecycleState = Literal[
    "unobserved",
    "pre_round",
    "transient_ui_transition",
    "round_active",
    "round_end_candidate",
    "round_ended",
    "next_round_preparation",
]
MAX_SAMPLE_GAP_SEC = 1.0
MIN_START_CONFIRMATION_SEC = 0.05
SEMANTIC_PHASE_CONFIDENCE_KEY = "center_phase_banner_semantic_text"


def accepted_score_pair(observation: Mapping[str, Any]) -> tuple[int, int] | None:
    values = observation.get("values", {})
    pair = (values.get("score_ally"), values.get("score_enemy"))
    return pair if all(type(value) is int and value >= 0 for value in pair) else None


def score_is_continuous(previous: Mapping[str, Any], current: Mapping[str, Any]) -> bool:
    pair = accepted_score_pair(current)
    return pair is not None and pair == accepted_score_pair(previous)


def confidence(observation: Mapping[str, Any]) -> float:
    value = observation.get("quality", {}).get("hud_confidence", 0.0)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0.0
    return float(value) if math.isfinite(value) and 0 <= value <= 1 else 0.0


def preparation_confidence(observation: Mapping[str, Any]) -> float:
    """Use qualified global phase confidence only for preparation evidence.

    The producer's ROI confidence is emitted after semantic-text temporal
    corroboration. It never establishes current player identity or an active
    round, and the legacy HUD confidence path remains unchanged.
    """
    score = confidence(observation)
    values = observation.get("values", {})
    flags = observation.get("state_flags", ())
    quality = observation.get("quality", {})
    roi = quality.get("roi_confidence", {}) if isinstance(quality, Mapping) else {}
    value = roi.get(SEMANTIC_PHASE_CONFIDENCE_KEY) if isinstance(roi, Mapping) else None
    if (
        "buy_phase_banner" in flags
        and isinstance(values, Mapping)
        and values.get("buy_phase_visible") is True
        and isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and 0.90 <= value <= 1.0
    ):
        return max(score, float(value))
    return score


def is_discontinuous(
    previous: Mapping[str, Any] | None,
    current: Mapping[str, Any],
    evidence: Mapping[str, Any],
) -> bool:
    # Explicit source markers are supported; their absence is not proof that a
    # visually edited recording is continuous. No new cut detector is implied.
    if evidence.get("discontinuity") is True or evidence.get("content_jump") is True:
        return True
    if previous is None:
        return False
    gap = float(current["time_sec"]) - float(previous["time_sec"])
    return gap <= 0 or gap > MAX_SAMPLE_GAP_SEC


@dataclass(frozen=True)
class BoundaryDecision:
    kind: Literal["round_start", "round_end"]
    time_sec: float
    confidence: float
    attributes: dict[str, Any]


class RoundLifecycle:
    """Latch boundaries, retaining the first candidate PTS after corroboration.

    Candidate predicates remain the HUD detector's composite predicates. A start
    additionally needs a later live observation with a consistent accepted timer.
    A timeline-joined end already has separate score transition and banner PTS.
    Other end candidates require a second corroborating observation.
    """

    def __init__(self) -> None:
        self.state: LifecycleState = "unobserved"
        self._candidate: BoundaryDecision | None = None
        self._start_timer: float | None = None
        self._start_score: tuple[int, int] | None = None
        self._preparation_count = 0
        self._ended = False
        self._continuity_segment = 0

    def reset(self) -> None:
        self._continuity_segment += 1
        self.state = "unobserved"
        self._candidate = None
        self._start_timer = None
        self._start_score = None
        self._preparation_count = 0
        self._ended = False

    def advance(
        self,
        previous: Mapping[str, Any] | None,
        current: Mapping[str, Any],
        evidence: Mapping[str, Any],
        *,
        start_candidate: bool,
        end_candidate: bool,
    ) -> tuple[BoundaryDecision, ...]:
        if is_discontinuous(previous, current, evidence):
            self.reset()
            return ()
        timestamp = float(current["time_sec"])
        score = confidence(current)
        flags = set(current.get("state_flags", ()))
        phase = "buy_phase_banner" in flags
        menu = current.get("primary_state") == "buy_menu_open"
        trustworthy_preparation = preparation_confidence(current) >= 0.65 and (phase or menu)

        if self._candidate is not None and self._candidate.kind == "round_start":
            value = current.get("values", {}).get("round_time_remaining_sec")
            elapsed = timestamp - self._candidate.time_sec
            consistent = (
                current.get("primary_state") == "live_first_person"
                and not phase
                and score >= 0.65
                and type(value) in (int, float)
                and math.isfinite(value)
                and self._start_timer is not None
                and self._start_score is not None
                and accepted_score_pair(current) == self._start_score
                and 0 <= self._start_timer - value <= elapsed + 1.0
            )
            if consistent and elapsed >= MIN_START_CONFIRMATION_SEC:
                decision = self._candidate
                decision.attributes["evidence_provenance"]["confirmation_pts_sec"] = timestamp
                self._candidate = None
                self.state = "round_active"
                self._ended = False
                return (
                    BoundaryDecision(
                        decision.kind,
                        decision.time_sec,
                        min(decision.confidence, score),
                        decision.attributes,
                    ),
                )
            if not consistent:
                self._candidate = None
                self._start_timer = None
                self._start_score = None

        if trustworthy_preparation:
            self._preparation_count += 1
            # Opening a menu during an active round cannot rearm its start.
            # A confirmed buy-phase sequence can prepare a new round even when
            # the preceding end was unobserved; no end event is inferred.
            if self.state != "round_active" or (phase and self._preparation_count >= 2):
                self.state = "next_round_preparation" if self._ended else "pre_round"
        else:
            self._preparation_count = 0

        if (
            start_candidate
            and self.state
            in {
                "unobserved",
                "pre_round",
                "next_round_preparation",
                "round_ended",
            }
            and previous is not None
        ):
            prior_score = preparation_confidence(previous)
            timer = current.get("values", {}).get("round_time_remaining_sec")
            if (min(score, prior_score) >= 0.65 and score_is_continuous(previous, current)
                    and type(timer) in (int, float) and math.isfinite(timer) and timer >= 0):
                self._start_timer = float(timer)
                self._start_score = accepted_score_pair(current)
                self._candidate = self._decision(
                    "round_start",
                    timestamp,
                    min(score, prior_score),
                    [float(previous["time_sec"]), timestamp],
                    ["buy_to_live", "timer_reset", "score_continuity"],
                )
                provenance = self._candidate.attributes["evidence_provenance"]
                provenance["preparation_confidence"] = prior_score
                provenance["preparation_confidence_source"] = (
                    SEMANTIC_PHASE_CONFIDENCE_KEY
                    if prior_score > confidence(previous)
                    else "hud_confidence"
                )

        if end_candidate and self.state not in {"round_ended", "next_round_preparation"}:
            join_pts = evidence.get("round_end_evidence_pts", ())
            join_confidence = evidence.get("round_end_join_confidence", 0.0)
            joined = (
                evidence.get("round_end_joined") is True
                and isinstance(join_pts, (list, tuple))
                and len(set(join_pts)) >= 2
                and type(join_confidence) in (int, float)
                and math.isfinite(join_confidence)
                and min(score, join_confidence) >= 0.65
            )
            if joined:
                self._candidate = None
                self.state = "round_ended"
                self._ended = True
                return (
                    self._decision(
                        "round_end",
                        timestamp,
                        min(score, join_confidence),
                        list(join_pts),
                        ["score_transition", "phase_banner"],
                    ),
                )
            if previous is not None and min(score, confidence(previous)) >= 0.65:
                if self._candidate is not None and self._candidate.kind == "round_end":
                    decision = self._candidate
                    self._candidate = None
                    self.state = "round_ended"
                    self._ended = True
                    decision.attributes["evidence_provenance"]["confirmation_pts_sec"] = timestamp
                    return (
                        BoundaryDecision(
                            decision.kind,
                            decision.time_sec,
                            min(decision.confidence, score),
                            decision.attributes,
                        ),
                    )
                self.state = "round_end_candidate"
                self._candidate = self._decision(
                    "round_end",
                    timestamp,
                    min(score, confidence(previous)),
                    [float(previous["time_sec"]), timestamp],
                    ["phase_banner", "timer_stopped_or_disappeared"],
                )
        elif self._candidate is not None and self._candidate.kind == "round_end":
            self._candidate = None
            self.state = "round_active"
        return ()

    def _decision(
        self,
        kind: Literal["round_start", "round_end"],
        timestamp: float,
        score: float,
        pts: list[float],
        signals: list[str],
    ) -> BoundaryDecision:
        return BoundaryDecision(
            kind,
            timestamp,
            score,
            {
                "evidence_provenance": {
                "producer": "hud_analyzer",
                "continuity_segment": self._continuity_segment,
                    "pts_sec": sorted(set(pts)),
                    "signals": signals,
                    "confirmation_pts_sec": timestamp,
                },
            },
        )
