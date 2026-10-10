"""Numeric correlation is not a released boundary or a qualified reader."""
from copy import deepcopy
from fractions import Fraction

import pytest

from scripts.diagnostics.numeric_end_feasibility import inspect
from tests.unit.test_pending_end_contract import source


def test_observed_numeric_pattern_needs_no_banner_and_preserves_input():
    rows = source()
    for row in rows:
        row['native_ui_measurements']['round_result_matched'] = False
    before = deepcopy(rows)
    result = inspect(rows, Fraction(1, 100), 1)
    assert len(result['patterns']) == 1
    assert result['released_events'] == 0
    assert result['active_round_proven'] is False
    assert rows == before


def test_unknown_clock_is_not_repeated_support():
    rows = source()
    for row in rows[9:]:
        row['observation']['values']['round_time_remaining_sec'] = None
    assert not inspect(rows, Fraction(1, 100), 1)['patterns']


@pytest.mark.parametrize('bad', ['phase', 'spectator', 'source_break', 'score', 'clock'])
def test_contradictions_before_confirmation_reject(bad):
    rows = source()
    if bad == 'phase':
        rows[12]['native_ui_measurements']['phase_present'] = True
    elif bad == 'spectator':
        rows[12]['observation']['primary_state'] = 'spectator'
    elif bad == 'source_break':
        rows[12]['native_ui_measurements']['discontinuity'] = True
    elif bad == 'score':
        for row in rows[10:]:
            row['observation']['values']['score_enemy'] = 6
    else:
        rows[12]['observation']['values']['round_time_remaining_sec'] = 65
        rows[12]['observation']['values']['round_time_remaining_display'] = '1:05'
    assert not inspect(rows, Fraction(1, 100), 1)['patterns']


def test_missing_native_frame_is_not_bridged():
    rows = source()
    del rows[12]
    with pytest.raises(ValueError):
        inspect(rows, Fraction(1, 100), 1)
