"""Numeric end hypothesis without banner recovery; never emits round events.

Freeze before replay: abnormal clock decrease, adjacent stable one-point score
step, then observed coherent clock support within one second. Missing readings
are not support. This describes correlation, not end timestamp semantics.
"""
from __future__ import annotations

import re
from fractions import Fraction

from scripts.diagnostics.global_numeric_transitions import describe
from valorant_ai_coach.hud.global_lifecycle import _display, _score, _timer
from valorant_ai_coach.hud.round_lifecycle import MIN_START_CONFIRMATION_SEC


def inspect(rows, time_base: Fraction, step: int):
    numeric = describe(rows, time_base, step)
    result = {'patterns': [], 'rejections': [], 'released_events': 0,
              'qualification_created': False, 'active_round_proven': False,
              'missing_raw_phase_presence_frames': 0}
    for row in rows:
        if (not row.get('source_epoch') or row.get('source_time_base') != str(time_base)
                or re.fullmatch(r'[0-9a-f]{64}', row.get('source_pixel_sha256', '')) is None):
            raise ValueError('complete native source provenance required')
        ui, obs = row['native_ui_measurements'], row['observation']
        result['missing_raw_phase_presence_frames'] += 'phase_present' not in ui
        if any(ui.get(key) is True for key in ('content_jump', 'discontinuity')):
            result['rejections'].append('source_break')
            return result
        if (ui.get('phase_scan_valid') is not True or ui.get('phase_present') is True
                or obs['quality'].get('occluded_rois')
                or obs.get('primary_state') not in {'unknown', 'live_first_person'}
                or set(obs.get('state_flags', ())) - {'combat_report_visible', 'round_end_banner'}
                or obs['values'].get('buy_phase_visible') is True):
            result['rejections'].append('conflicting_or_unavailable_context')
            return result
    for candidate in numeric['conditional_patterns']:
        tick = candidate['clock_change_tick']
        before = next(p for p in numeric['score_plateaus']
                      if p['first_tick'] <= tick <= p['last_tick'])
        after = next(p for p in numeric['score_plateaus']
                     if p['first_tick'] == candidate['score_change_tick'])
        if before['minimum_duration_tick'] is None:
            result['rejections'].append('prior_score_not_stable')
            continue
        support = []
        for row in rows:
            current_tick = row['source_pts_ticks']
            if current_tick < tick:
                continue
            if (current_tick - tick) * time_base > 1:
                result['rejections'].append('corroboration_timeout')
                break
            if any(tick < c['after']['tick'] <= current_tick for c in numeric['clock_changes']):
                result['rejections'].append('additional_clock_transition')
                break
            obs = row['observation']
            values, confidence = obs['values'], obs['quality']['roi_confidence']
            if current_tick >= candidate['score_stability_tick'] and any(
                type(values.get(key)) is int and _score(confidence.get(conf_key))
                and values[key] != expected
                for key, conf_key, expected in zip(
                    ('score_ally', 'score_enemy'), ('score_ally_value', 'score_enemy_value'),
                    after['values'], strict=True,
                )
            ):
                result['rejections'].append('contradictory_accepted_score')
                break
            timer, quality = _timer(obs)
            if timer is not None and quality and _display(obs) is not None:
                support.append({'tick': current_tick, 'seconds': timer,
                                'display': values['round_time_remaining_display'],
                                'confidence': quality})
            if (current_tick >= candidate['score_stability_tick'] and len(support) >= 2
                    and (support[-1]['tick'] - support[0]['tick']) * time_base
                    >= Fraction(str(MIN_START_CONFIRMATION_SEC))):
                result['patterns'].append({
                    **candidate, 'confirmation_tick': current_tick,
                    'observed_clock_support': support,
                    'score_before': before['values'], 'score_after': after['values'],
                    'scope': ('Observed numeric correlation only; '
                              'no event time or active-round proof'),
                    'unknown_clock_frames_are_not_corroboration': True,
                })
                break
    return result
