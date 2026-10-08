"""Diagnostic hypothesis only; never a production boundary/event producer.

A source-qualified phase plus shared timer reset may describe a global round
without asserting player identity. This tests that hypothesis without changing
production acceptance, converting states, or consuming evaluation windows.
"""
from __future__ import annotations

import math
from typing import Any

from valorant_ai_coach.hud.round_lifecycle import (
    MAX_SAMPLE_GAP_SEC,
    MIN_START_CONFIRMATION_SEC,
    SEMANTIC_PHASE_CONFIDENCE_KEY,
)


def timer_confidence(observation: dict[str, Any]) -> float:
    value = observation['values'].get('round_time_remaining_sec')
    score = observation['quality']['roi_confidence'].get('round_timer_value')
    if (
        isinstance(value, bool) or not isinstance(value, (int, float))
        or not math.isfinite(value) or value < 0
        or isinstance(score, bool) or not isinstance(score, (int, float))
        or not math.isfinite(score) or not .90 <= score <= 1
    ):
        return 0
    return float(score)


def phase_confidence(observation: dict[str, Any]) -> float:
    value = observation['quality']['roi_confidence'].get(SEMANTIC_PHASE_CONFIDENCE_KEY)
    if (
        'buy_phase_banner' not in observation['state_flags']
        or observation['values'].get('buy_phase_visible') is not True
        or isinstance(value, bool) or not isinstance(value, (int, float))
        or not math.isfinite(value) or not .90 <= value <= 1
    ):
        return 0
    return float(value)


def compatible_current(observation: dict[str, Any]) -> bool:
    return (
        observation['primary_state'] in {'unknown', 'live_first_person'}
        and not observation['state_flags']
    )


class GlobalStartHypothesis:
    def __init__(self) -> None:
        self.previous: dict[str, Any] | None = None
        self.pending: dict[str, Any] | None = None
        self.armed = True
        self.phase_count = 0

    def advance(self, observation: dict[str, Any], *, discontinuity: bool = False) -> dict | None:
        previous = self.previous
        self.previous = observation
        timestamp = observation['time_sec']
        if discontinuity or (
            previous is not None
            and not 0 < timestamp - previous['time_sec'] <= MAX_SAMPLE_GAP_SEC
        ):
            self.pending = None
            self.armed = True
            self.phase_count = 0
            return None
        if phase_confidence(observation):
            self.phase_count += 1
            if self.phase_count >= 2:
                self.armed = True
        else:
            self.phase_count = 0
        if self.pending is not None:
            candidate = self.pending
            elapsed = timestamp - candidate['candidate_pts_sec']
            value = observation['values'].get('round_time_remaining_sec')
            if not compatible_current(observation) or elapsed > MAX_SAMPLE_GAP_SEC:
                self.pending = None
            elif value is None:
                candidate['neutral_timer_pts_sec'].append(timestamp)
                return None
            elif timer_confidence(observation) and (
                0 <= candidate['timer_after_sec'] - value <= elapsed + 1
            ):
                if elapsed >= MIN_START_CONFIRMATION_SEC:
                    self.pending = None
                    self.armed = False
                    return {**candidate, 'confirmation_pts_sec': timestamp,
                            'confirmation_timer_sec': value,
                            'confidence': min(
                                candidate['confidence'], timer_confidence(observation))}
                return None
            else:
                self.pending = None
        if (
            self.armed and previous is not None and phase_confidence(previous)
            and timer_confidence(previous) and timer_confidence(observation)
            and compatible_current(observation)
            and observation['values']['round_time_remaining_sec']
            > previous['values']['round_time_remaining_sec'] + 3
        ):
            self.pending = {
                'candidate_pts_sec': timestamp,
                'phase_pts_sec': previous['time_sec'],
                'timer_before_sec': previous['values']['round_time_remaining_sec'],
                'timer_after_sec': observation['values']['round_time_remaining_sec'],
                'confidence': min(phase_confidence(previous), timer_confidence(previous),
                                  timer_confidence(observation)),
                'neutral_timer_pts_sec': [],
                'primary_state_at_candidate': observation['primary_state'],
                'hypothesis_only': True,
            }
        return None
