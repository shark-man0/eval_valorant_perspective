"""Synthetic temporal controls independent of the observed video's values/PTS."""
from copy import deepcopy
from fractions import Fraction

import pytest

from scripts.diagnostics.pending_end_contract import inspect


def source():
    rows = []
    for i in range(35):
        timer = 51 if i < 8 else 12
        enemy = 4 if i < 10 else 5
        rows.append({'source_pts_ticks': i, 'pts_sec': i / 100,
                     'source_epoch': 'synthetic', 'source_time_base': '1/100',
                     'source_pixel_sha256': f'{i:064x}',
                     'native_ui_measurements': {'phase_scan_valid': True,
                                               'round_result_matched': 20 <= i <= 30,
                                               'round_result_confidence': .95},
                     'observation': {'time_sec': i / 100, 'primary_state': 'unknown',
                                     'state_flags': ['combat_report_visible'], 'values': {
                                         'score_ally': 2, 'score_enemy': enemy,
                                         'round_time_remaining_sec': timer,
                                         'round_time_remaining_display': f'0:{timer:02d}',
                                         'round_time_remaining_display_provenance': {
                                             'reader': 'round_timer', 'sources': ['synthetic'],
                                             'confidence': .95, 'cross_checked': False,
                                         }}, 'quality': {'occluded_rois': [], 'roi_confidence': {
                                             'score_ally_value': .95, 'score_enemy_value': .95,
                                             'round_timer_value': .95}}}})
    return rows


def test_delayed_corroboration_preserves_missing_current_values_without_event():
    rows = source()
    for row in rows[18:]:
        row['observation']['values']['score_ally'] = None
        row['observation']['values']['score_enemy'] = None
    before = deepcopy(rows)
    result = inspect(rows, Fraction(1, 100), 1)
    assert len(result['patterns']) == 1
    p = result['patterns'][0]
    assert p['clock_change_tick'] == 8 and p['result_stability_tick'] == 25
    assert p['current_score_values'] == [None, None]
    assert p['historical_score_evidence'] == [2, 5]
    assert rows == before and result['released_events'] == 0
    assert not result['active_round_proven'] and not result['qualification_created']


@pytest.mark.parametrize('bad', ['cut', 'context', 'phase', 'contradiction',
                               'brief_result', 'weak_result', 'no_result'])
def test_no_pattern_when_evidence_is_unsafe_or_insufficient(bad):
    rows = source()
    if bad == 'cut':
        rows[19]['native_ui_measurements']['discontinuity'] = True
    elif bad == 'context':
        rows[19]['observation']['primary_state'] = 'spectator'
    elif bad == 'phase':
        rows[19]['observation']['values']['buy_phase_visible'] = True
    elif bad == 'contradiction':
        rows[19]['observation']['values']['score_enemy'] = 4
    else:
        for i, row in enumerate(rows):
            ui = row['native_ui_measurements']
            if bad == 'brief_result':
                ui['round_result_matched'] = i == 20
            elif bad == 'weak_result':
                ui['round_result_confidence'] = .89
            else:
                ui['round_result_matched'] = False
    assert not inspect(rows, Fraction(1, 100), 1)['patterns']


@pytest.mark.parametrize('bad', ['gap', 'epoch', 'repeated_pixels', 'missing_provenance'])
def test_invalid_native_links_cannot_be_combined(bad):
    rows = source()
    if bad == 'gap':
        del rows[19]
    elif bad == 'epoch':
        rows[19]['source_epoch'] = 'other'
    elif bad == 'repeated_pixels':
        rows[19]['source_pixel_sha256'] = rows[18]['source_pixel_sha256']
    else:
        del rows[19]['source_pixel_sha256']
    with pytest.raises(ValueError):
        inspect(rows, Fraction(1, 100), 1)


def test_deadline_is_measured_from_clock_evidence_and_never_extended():
    rows = source()
    for i, row in enumerate(rows):
        row['source_time_base'] = '1/10'
        row['pts_sec'] = row['observation']['time_sec'] = i / 10
    result = inspect(rows, Fraction(1, 10), 1)
    assert not result['patterns']
    assert 'corroboration_timeout' in result['rejections']


def test_additional_clock_transition_before_score_stability_invalidates_pending():
    rows = source()
    for row in rows[11:]:
        row['observation']['values']['round_time_remaining_sec'] = 58
        row['observation']['values']['round_time_remaining_display'] = '0:58'
    result = inspect(rows, Fraction(1, 100), 1)
    assert not result['patterns']
    assert 'additional_clock_transition' in result['rejections']


def test_result_jitter_cannot_accumulate_duration_across_nonmatches():
    rows = source()
    for i, row in enumerate(rows):
        row['native_ui_measurements']['round_result_matched'] = i in {20, 21, 28, 29}
    assert not inspect(rows, Fraction(1, 100), 1)['patterns']
