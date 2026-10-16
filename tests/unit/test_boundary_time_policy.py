"""Timing policy tests: no GT or detector thresholds are changed."""
from copy import deepcopy

import pytest

from scripts.e2e.boundary_time_policy import apply_policy


def inputs(*, point=False):
    bracket = {'last_absent_sec': 10.2, 'first_present_sec': 10.2 if point else 10.25}
    annotation = {'id': 'boundary', 'type': 'round_end', 'actor': 'system',
                  'evidence_bracket': bracket,
                  'tolerance_before_sec': .03, 'tolerance_after_sec': .05}
    assertions = {'required_point_events': [
        {'id': 'boundary', 'type': 'round_end', 'actor': 'system', 'round_id': 'observed-1',
         'acceptance_window': [10.17, 10.25 if point else 10.3],
         'required_event_attributes': {'source': 'qualified-synthetic'}},
        {'id': 'death', 'type': 'player_death', 'acceptance_window': [20, 21]},
    ], 'negative_assertions': [{'id': 'do-not-emit'}],
        'event_count_constraints': [{'min': 0, 'max': 0}],
        'ordering_constraints': [{'before': 'start', 'after': 'end'}],
        'discontinuities': [{'time_sec': 19}]}
    timeline = {'rounds': [{'round_id': 'observed-1', 'point_events': [annotation]}]}
    return assertions, timeline


@pytest.mark.parametrize('offset,passed', [
    (0, True), (.05, True), (.1, True), (.101, False),
    (-.05, True), (-.1, True), (-.101, False),
])
def test_exact_point_error_boundaries_without_rounding_or_epsilon(offset, passed):
    from decimal import Decimal

    assertions, timeline = inputs(point=True)
    adjusted, _ = apply_policy(assertions, timeline)
    lo, hi = adjusted['required_point_events'][0]['acceptance_window']
    actual = float(Decimal('10.2') + Decimal(str(offset)))
    assert (lo <= actual <= hi) is passed
    assert actual == float(Decimal('10.2') + Decimal(str(offset)))


def test_replace_old_padding_not_double_pad_and_do_not_invent_midpoint():
    assertions, timeline = inputs()
    before = deepcopy((assertions, timeline))
    adjusted, audit = apply_policy(assertions, timeline)
    assert adjusted['required_point_events'][0]['acceptance_window'] == [10.1, 10.35]
    assert audit[0]['raw_evidence_bracket'] == [10.2, 10.25]
    assert audit[0]['canonical_window'] == [10.17, 10.3]
    assert (assertions, timeline) == before
    expected = deepcopy(assertions)
    expected['required_point_events'][0]['acceptance_window'] = [10.1, 10.35]
    assert adjusted == expected  # actor, attributes, count, order, negatives, breaks all identical


def test_existing_tenth_second_padding_is_not_applied_twice():
    assertions, timeline = inputs()
    point = timeline['rounds'][0]['point_events'][0]
    point.update(tolerance_before_sec=.1, tolerance_after_sec=.1)
    assertions['required_point_events'][0]['acceptance_window'] = [10.1, 10.35]
    assert apply_policy(assertions, timeline)[0] == assertions


@pytest.mark.parametrize('value', [True, None, '0.1', float('nan'), float('inf'), -.1])
def test_malformed_or_negative_existing_padding_fails_closed(value):
    assertions, timeline = inputs()
    timeline['rounds'][0]['point_events'][0]['tolerance_before_sec'] = value
    with pytest.raises(ValueError):
        apply_policy(assertions, timeline)


def test_unknown_raw_annotation_and_stale_generated_window_are_rejected():
    assertions, timeline = inputs()
    with pytest.raises(ValueError, match='raw'):
        apply_policy(assertions, {'rounds': []})
    assertions['required_point_events'][0]['acceptance_window'] = [10, 11]
    with pytest.raises(ValueError, match='does not match'):
        apply_policy(assertions, timeline)


def test_duplicate_annotation_and_foreign_round_are_rejected():
    assertions, timeline = inputs()
    timeline['rounds'] *= 2
    with pytest.raises(ValueError, match='ambiguous'):
        apply_policy(assertions, timeline)
    timeline['rounds'] = timeline['rounds'][:1]
    timeline['rounds'][0]['round_id'] = 'foreign'
    with pytest.raises(ValueError, match='identity mismatch'):
        apply_policy(assertions, timeline)
