"""Source-assured global lifecycle; end requires separately qualified inputs."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .global_lifecycle import GlobalLifecycleQualification, _score
from .round_lifecycle import BoundaryDecision
from .unedited_ui_end import END_CONTEXT_FLAGS, UneditedUiEndTracker
from .unedited_ui_start import UneditedUiStartTracker

# A combat report is neither player ownership nor a veto on independently
# qualified global result/score pixels. Other conflicting display flags retain
# their fail-closed guards; this exception applies only to a qualified end.
GLOBAL_END_CONTEXT_FLAGS = END_CONTEXT_FLAGS


class UneditedRoundLifecycle:
    def __init__(
        self, start: UneditedUiStartTracker, qualification: GlobalLifecycleQualification,
    ) -> None:
        self.start = start
        self.qualification = qualification
        self.ended = False
        if 'ui_end_transition' in qualification.components and not {
            'timer', 'score', 'round_result',
        } <= qualification.components:
            raise ValueError('UI end transition requires qualified timer, score and result')
        self.pending_end = (
            UneditedUiEndTracker(native_step_ticks=start.step)
            if 'ui_end_transition' in qualification.components else None
        )

    @property
    def state(self) -> str:
        if self.start.started:
            if self.pending_end is not None and self.pending_end.pending:
                return 'round_end_candidate'
            return 'round_active'
        if self.ended and self.start.state == 'pre_round':
            return 'next_round_preparation'
        return self.start.state

    def advance(
        self, row: Mapping[str, Any], *, phase_scan_valid: bool,
    ) -> BoundaryDecision | None:
        previous = self.start.previous_source
        try:
            decision = self.start.advance(row, phase_scan_valid=phase_scan_valid)
        except ValueError:
            self.ended = False
            if self.pending_end is not None:
                self.pending_end.reset()
            raise
        if decision is not None:
            self.ended = False
            if self.pending_end is not None:
                self.pending_end.reset()
            return decision
        if self.start.state == 'unobserved':
            self.ended = False
        if not self.start.started or previous is None:
            if self.pending_end is not None:
                self.pending_end.reset()
            return None
        if self.pending_end is not None:
            decision = self.pending_end.advance(row, phase_scan_valid=phase_scan_valid)
            if decision is None:
                return None
            decision.attributes['evidence_provenance'].update(
                input_contract_sha256=self.start.contract.fingerprint,
            )
            self.start.reset()
            self.start.state = 'round_ended'
            self.ended = True
            return decision
        if not {'score', 'round_result'} <= self.qualification.components:
            return None
        current = row['system_observation']
        evidence = row['system_evidence']
        result_score = _score(evidence.get('assured_round_result_confidence'))
        if (
            not phase_scan_valid or current['quality'].get('occluded_rois')
            or evidence.get('assured_phase_present') is True
            or current['primary_state'] not in {'unknown', 'live_first_person'}
            or set(current.get('state_flags', ())) - GLOBAL_END_CONTEXT_FLAGS
            or evidence.get('assured_round_result_present') is not True or not result_score
        ):
            return None
        # Preserve the existing global end predicate: distinct adjacent frames,
        # accepted scores changing by exactly one point and semantic result on
        # the current frame. No inferred score or earlier timestamp is supplied.
        observations = (previous['system_observation'], current)
        if (
            previous['system_evidence'].get('assured_phase_scan_valid') is not True
            or previous['system_evidence'].get('assured_phase_present') is True
            or observations[0]['quality'].get('occluded_rois')
            or observations[0]['primary_state'] not in {'unknown', 'live_first_person'}
            or set(observations[0].get('state_flags', ())) - GLOBAL_END_CONTEXT_FLAGS
        ):
            return None
        scores = [o['values'].get(k) for o in observations
                  for k in ('score_ally', 'score_enemy')]
        confidences = [_score(o['quality']['roi_confidence'].get(k))
                       for o in observations for k in ('score_ally_value', 'score_enemy_value')]
        if (
            not all(type(n) is int and n >= 0 for n in scores)
            or not all(confidences)
            or sorted([scores[2] - scores[0], scores[3] - scores[1]]) != [0, 1]
        ):
            return None
        self.start.reset()
        self.start.state = 'round_ended'
        self.ended = True
        return BoundaryDecision(
            'round_end', row['source_pts_sec'], min(result_score, *confidences),
            {'evidence_provenance': {
                'scope': 'global_system', 'producer': 'unedited_round_lifecycle',
                'input_contract_sha256': self.start.contract.fingerprint,
                'signals': ['qualified_round_result', 'accepted_score_transition'],
                'pts_sec': [previous['source_pts_sec'], row['source_pts_sec']],
                'confirmation_pts_sec': row['source_pts_sec'],
            }},
        )
