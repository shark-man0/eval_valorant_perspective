"""Streaming global end evidence, enabled only by ui_end_transition qualification.

The one-second association horizon is a frozen development hypothesis, not an
attestation. A qualification must independently review the whole temporal path,
including timestamp semantics. The event uses the first observed score change,
never a validation window or an inferred earlier end time.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from fractions import Fraction
from typing import Any

from .global_lifecycle import _display, _score, _timer
from .round_lifecycle import MAX_SAMPLE_GAP_SEC, MIN_START_CONFIRMATION_SEC, BoundaryDecision

END_CONTEXT_FLAGS = frozenset({'round_end_banner', 'combat_report_visible'})
MAX_END_CORROBORATION_SEC = Fraction(1)
MIN_END_SUPPORT_SEC = Fraction(str(MIN_START_CONFIRMATION_SEC))


@dataclass
class ScoreRun:
    values: tuple[int, int]
    first: dict[str, Any]
    last: dict[str, Any]
    count: int
    confidence: float

    def stable(self, base: Fraction) -> bool:
        return (self.count >= 2 and
                (self.last['tick'] - self.first['tick']) * base >= MIN_END_SUPPORT_SEC)


def _sample(row: Mapping[str, Any], **facts: Any) -> dict[str, Any]:
    return {'tick': row['source_pts_ticks'], 'pts_sec': row['source_pts_sec'],
            'source_pixel_sha256': row['source_pixel_sha256'], **facts}


class UneditedUiEndTracker:
    """Consumes source-validated, active-round rows; never repairs current values.

    UneditedUiStartTracker validates the exact source/cadence before this class
    is called. Its lifecycle owner resets this collector on every source break,
    start and completed end. UI conflicts discard evidence without ending the
    active round. Missing OCR cannot count toward consecutive score/result runs.
    """

    def __init__(self, *, native_step_ticks: int) -> None:
        if type(native_step_ticks) is not int or native_step_ticks <= 0:
            raise ValueError('positive native cadence required')
        self.step = native_step_ticks
        self.reset()

    def reset(self) -> None:
        self.previous_clock: dict[str, Any] | None = None
        self.scores: ScoreRun | None = None
        self.clock_change: dict[str, Any] | None = None
        self.before: ScoreRun | None = None
        self.after: ScoreRun | None = None
        self.result_first: dict[str, Any] | None = None
        self.result_last: dict[str, Any] | None = None
        self.result_count = 0
        self.result_confidence = 1.0
        self.score_stability: dict[str, Any] | None = None

    @property
    def pending(self) -> bool:
        return self.clock_change is not None

    def advance(
        self, row: Mapping[str, Any], *, phase_scan_valid: bool,
    ) -> BoundaryDecision | None:
        obs = row['system_observation']
        evidence = row['system_evidence']
        values = obs['values']
        if (not phase_scan_valid or evidence.get('assured_phase_scan_valid') is not True
                or evidence.get('assured_phase_present') is True
                or obs['quality'].get('occluded_rois')
                or obs['primary_state'] not in {'unknown', 'live_first_person'}
                or set(obs.get('state_flags', ())) - END_CONTEXT_FLAGS
                or values.get('buy_phase_visible') is True):
            self.reset()
            return None
        base = Fraction(row['source_time_base'])
        tick = row['source_pts_ticks']
        if (self.clock_change is not None and
                (tick - self.clock_change['after']['tick']) * base > MAX_END_CORROBORATION_SEC):
            self.reset()
            return None  # Timeout cannot be extended by later score/result reads.

        timer, timer_score = _timer(obs)
        display = _display(obs)
        if timer is not None and timer_score and display is not None:
            clock = _sample(row, seconds=timer,
                            observed_display=values['round_time_remaining_display'],
                            confidence=min(timer_score, display['provenance']['confidence']))
            previous = self.previous_clock
            if previous is not None:
                elapsed = float((tick - previous['tick']) * base)
                decrease = previous['seconds'] - timer
                changed = elapsed <= MAX_SAMPLE_GAP_SEC and (decrease < 0 or decrease > elapsed + 1)
                if changed:
                    if self.pending:
                        self.reset()
                        return None  # Even a second decrease contradicts the pending proposal.
                    if decrease > 0 and self.scores is not None and self.scores.stable(base):
                        self.clock_change = {'before': previous, 'after': clock}
                        self.before = self.scores
            self.previous_clock = clock

        pair = tuple(values.get(k) for k in ('score_ally', 'score_enemy'))
        confidences = [_score(obs['quality']['roi_confidence'].get(k))
                       for k in ('score_ally_value', 'score_enemy_value')]
        accepted = [type(v) is int and v >= 0 and bool(c)
                    for v, c in zip(pair, confidences, strict=True)]
        if self.after is not None and any(
            valid and value != expected
            for valid, value, expected in zip(accepted, pair, self.after.values, strict=True)
        ):
            self.reset()
            return None  # Includes contradictions while the new score is still stabilizing.
        old_run = self.scores
        if all(accepted):
            sample = _sample(row, values=list(pair), confidence=min(confidences))
            if old_run is not None and pair == old_run.values:
                old_run.last = sample
                old_run.count += 1
                old_run.confidence = min(old_run.confidence, *confidences)
            else:
                self.scores = ScoreRun((int(pair[0]), int(pair[1])), sample, sample,
                                       1, min(confidences))
                if self.clock_change is not None and self.after is None:
                    before = self.before
                    # Require adjacent accepted old/new scores and a native
                    # score update strictly after the observed clock transition.
                    if (before is None or old_run is not before
                            or old_run.last['tick'] != tick - self.step
                            or tick <= self.clock_change['after']['tick']
                            or sorted([pair[i] - before.values[i] for i in range(2)]) != [0, 1]):
                        self.reset()
                        return None
                    self.after = self.scores
        else:
            self.scores = None
            if self.after is not None and self.score_stability is None:
                self.reset()
                return None
        if self.after is None:
            return None
        if self.score_stability is None:
            if not self.after.stable(base):
                return None
            self.score_stability = _sample(row)

        result_score = _score(evidence.get('assured_round_result_confidence'))
        if evidence.get('assured_round_result_present') is not True or not result_score:
            self.result_first = self.result_last = None
            self.result_count = 0
            self.result_confidence = 1.0
            return None
        current = _sample(row, confidence=result_score)
        self.result_first = self.result_first or current
        self.result_last = current
        self.result_count += 1
        self.result_confidence = min(self.result_confidence, result_score)
        if (self.result_count < 2 or
                (tick - self.result_first['tick']) * base < MIN_END_SUPPORT_SEC):
            return None
        assert self.clock_change is not None and self.before is not None
        provenance = {
            'scope': 'global_system', 'producer': 'unedited_ui_end_tracker',
            'temporal_contract': 'ui_end_transition_v1',
            'signals': ['accepted_clock_decrease', 'accepted_score_transition',
                        'qualified_stable_round_result'],
            'clock_change': self.clock_change,
            'score_before': {'first': self.before.first, 'last': self.before.last,
                             'confidence': self.before.confidence},
            'score_after': {'first': self.after.first, 'last': self.after.last,
                            'confidence': self.after.confidence},
            'score_stability': self.score_stability,
            'result_first': self.result_first, 'result_confirmation': current,
            'confirmation_pts_sec': row['source_pts_sec'],
            'pts_sec': [self.clock_change['after']['pts_sec'], self.after.first['pts_sec'],
                        self.result_first['pts_sec'], row['source_pts_sec']],
            'timestamp_rule': 'first_observed_score_change',
        }
        decision = BoundaryDecision(
            'round_end', self.after.first['pts_sec'],
            min(self.before.confidence, self.after.confidence, self.result_confidence,
                self.clock_change['before']['confidence'],
                self.clock_change['after']['confidence']),
            {'evidence_provenance': provenance},
        )
        self.reset()
        return decision
