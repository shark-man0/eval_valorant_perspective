"""Evaluator-only boundary timing policy; never imported by recognizers."""
from __future__ import annotations

import math
from copy import deepcopy
from decimal import Decimal
from typing import Any

POLICY_VERSION = 'round-boundary-bracket-0.1-v1'
TOLERANCE = Decimal('0.1')
KINDS = {'round_start', 'round_end'}


def number(value: Any) -> Decimal:
    if type(value) not in (float, int) or not math.isfinite(value):
        raise ValueError('finite numeric timestamp required')
    return Decimal(str(value))


def apply_policy(assertions: dict, timeline: dict) -> tuple[dict, list[dict]]:
    """Replace padding around raw witness brackets, never pad a padded window.

    Existing per-item tolerances must reconstruct the generated canonical window.
    Missing/ambiguous raw annotations fail closed; no midpoint GT is invented.
    This returns an in-memory evaluator view, leaving all inputs unchanged.
    """
    annotations = {}
    for round_ in timeline['rounds']:
        for point in round_.get('point_events', []):
            if point['type'] not in KINDS:
                continue
            if point['id'] in annotations:
                raise ValueError('ambiguous round boundary annotation')
            annotations[point['id']] = (round_['round_id'], point)
    adjusted = deepcopy(assertions)
    audit = []
    for req in adjusted['required_point_events']:
        if req['type'] not in KINDS:
            continue
        if req['id'] not in annotations:
            raise ValueError('raw round boundary annotation required')
        rid, point = annotations.pop(req['id'])
        if (rid, point['type'], point['actor']) != (req['round_id'], req['type'], req['actor']):
            raise ValueError('boundary annotation identity mismatch')
        bracket = point['evidence_bracket']
        start, end = number(bracket['last_absent_sec']), number(bracket['first_present_sec'])
        before, after = number(point['tolerance_before_sec']), number(point['tolerance_after_sec'])
        if not 0 <= start <= end or min(before, after) < 0:
            raise ValueError('ordered nonnegative bracket and padding required')
        canonical = [float(start-before), float(end+after)]
        given = req['acceptance_window']
        if len(given) != 2 or any(
            abs(float(number(a))-b) > 4*max(math.ulp(float(a)), math.ulp(b))
            for a, b in zip(given, canonical, strict=True)
        ):
            raise ValueError('canonical window does not match raw bracket and per-item padding')
        window = [float(max(Decimal(0), start-TOLERANCE)), float(end+TOLERANCE)]
        req['acceptance_window'] = window
        audit.append({'assertion_id': req['id'], 'raw_evidence_bracket': [float(start), float(end)],
                      'canonical_window': given, 'evaluation_window': window,
                      'padding_replaced_not_added': True})
    if annotations:
        raise ValueError('raw boundary annotations missing from generated assertions')
    return adjusted, audit
