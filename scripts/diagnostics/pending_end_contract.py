"""Frozen pending-end hypothesis; never emits events or qualifies a lifecycle.

One-second correlation budget is a conservative training hypothesis, not an
established game guarantee. Independent controls/qualification must precede any
production adoption. Original missing values and timestamps remain untouched.
"""
from __future__ import annotations

import re
from fractions import Fraction

from scripts.diagnostics.global_numeric_transitions import describe
from valorant_ai_coach.hud.global_lifecycle import _score
from valorant_ai_coach.hud.round_lifecycle import MIN_START_CONFIRMATION_SEC

MAX_CORROBORATION_SEC = Fraction(1)


def inspect(rows, time_base: Fraction, step: int):
    result = {'patterns': [], 'rejections': [], 'released_events': 0,
              'qualification_created': False, 'active_round_proven': False}
    # The numeric descriptor also verifies every native PTS and observation PTS.
    numeric = describe(rows, time_base, step)
    for row in rows:
        if (not row.get('source_epoch') or row.get('source_time_base') != str(time_base)
                or re.fullmatch(r'[0-9a-f]{64}', row.get('source_pixel_sha256', '')) is None):
            raise ValueError('complete native source provenance required')
        ui = row['native_ui_measurements']
        if any(ui.get(key) is True for key in ('content_jump', 'discontinuity')):
            result['rejections'].append('source_break')
            return result
        obs = row['observation']
        if (ui.get('phase_scan_valid') is not True or obs['quality'].get('occluded_rois')
                or obs.get('primary_state') not in {'unknown', 'live_first_person'}
                or set(obs.get('state_flags', ())) - {'combat_report_visible', 'round_end_banner'}
                or obs['values'].get('buy_phase_visible') is True):
            result['rejections'].append('conflicting_or_unavailable_context')
            return result
    for candidate in numeric['conditional_patterns']:
        clock_tick = candidate['clock_change_tick']
        score_tick = candidate['score_change_tick']
        before = next(p for p in numeric['score_plateaus']
                      if p['first_tick'] <= clock_tick <= p['last_tick'])
        after = next(p for p in numeric['score_plateaus'] if p['first_tick'] == score_tick)
        if before['minimum_duration_tick'] is None:
            result['rejections'].append('prior_score_not_stable')
            continue
        first_result = None
        result_confidence = 1.0
        for row in rows:
            tick = row['source_pts_ticks']
            if tick < candidate['score_stability_tick']:
                continue
            if (tick - clock_tick) * time_base > MAX_CORROBORATION_SEC:
                result['rejections'].append('corroboration_timeout')
                break
            values = row['observation']['values']
            confidence = row['observation']['quality']['roi_confidence']
            contradiction = any(
                type(values.get(key)) is int and _score(confidence.get(conf_key))
                and values[key] != expected
                for key, conf_key, expected in zip(
                    ('score_ally', 'score_enemy'), ('score_ally_value', 'score_enemy_value'),
                    after['values'], strict=True,
                )
            )
            if contradiction:
                result['rejections'].append('contradictory_accepted_score')
                break
            if any(clock_tick < c['after']['tick'] <= tick for c in numeric['clock_changes']):
                result['rejections'].append('additional_clock_transition')
                break
            ui = row['native_ui_measurements']
            accepted = (ui.get('round_result_matched') is True
                        and _score(ui.get('round_result_confidence')))
            if not accepted:
                first_result, result_confidence = None, 1.0
                continue
            if first_result is None:
                first_result = tick
            result_confidence = min(result_confidence, ui['round_result_confidence'])
            if (tick - first_result) * time_base >= Fraction(str(MIN_START_CONFIRMATION_SEC)):
                result['patterns'].append({
                    'clock_change_tick': clock_tick, 'score_change_tick': score_tick,
                    'score_stability_tick': candidate['score_stability_tick'],
                    'result_first_tick': first_result, 'result_stability_tick': tick,
                    'result_min_confidence': result_confidence,
                    'score_min_confidence': min(before['confidence'], after['confidence']),
                    'current_score_values': [values.get(k) for k in ('score_ally', 'score_enemy')],
                    'historical_score_evidence': after['values'],
                    'scope': 'Conditional pending-end pattern; no active-round or event proof',
                })
                break
    return result
