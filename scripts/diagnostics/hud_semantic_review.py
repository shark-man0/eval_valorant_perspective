"""Offline HUD-box review accounting; never a recognizer, event, or GT writer.

Only explicit human observations may contribute to semantic confirmation. A
review packet is a targeted diagnostic cohort, never a population accuracy set.
"""
from __future__ import annotations

import math
from fractions import Fraction
from typing import Any

from scripts.temporal_gt.contract import canonical_hash

LABELS = {'CORRECT', 'INCORRECT', 'UNKNOWN'}
STATES = {'PLAYING', 'SPECTATOR', 'MENU', 'DEATH_CONFIRMED', 'HUD_HIDDEN',
          'TRANSITION', 'OVERLAY', 'UNKNOWN'}


def response_defaults(packet: dict[str, Any]) -> dict[str, Any]:
    """No detector/AI text or accepted geometry becomes a human answer."""
    return {'packet_sha256': canonical_hash(packet), 'origin': 'human_source_observation',
            'reviewer': '', 'cases': [
                {'case_id': c['case_id'], 'reviewed': False, 'state': 'UNKNOWN', 'notes': '',
                 'methods': {m: dict.fromkeys(v['positions'], 'UNKNOWN')
                             for m, v in c['methods'].items()}}
                for c in packet['cases']]}


def summarize_review(packet: dict[str, Any], response: dict[str, Any]) -> dict[str, Any]:
    if (response.get('packet_sha256') != canonical_hash(packet)
            or response.get('origin') != 'human_source_observation'):
        raise ValueError('bound packet and explicit human observation required')
    expected = {c['case_id']: c for c in packet['cases']}
    answers = response.get('cases', [])
    if (not isinstance(answers, list) or len(answers) != len(expected)
            or {a['case_id'] for a in answers} != set(expected)):
        raise ValueError('exact unique packet cases required')
    methods: dict[str, Any] = {}
    states: dict[str, Any] = {}
    reviewed = 0
    for answer in answers:
        case = expected[answer['case_id']]
        if (type(answer.get('reviewed')) is not bool or answer.get('state') not in STATES
                or set(answer.get('methods', {})) != set(case['methods'])):
            raise ValueError('explicit review status, state and method identities required')
        active = answer['reviewed']
        if active and (not isinstance(response.get('reviewer'), str)
                       or not response['reviewer'].strip()):
            raise ValueError('human reviewer required')
        if not active and answer['state'] != 'UNKNOWN':
            raise ValueError('unreviewed state must remain UNKNOWN')
        reviewed += active
        for method, detected in case['methods'].items():
            labels = answer['methods'][method]
            if set(labels) != set(detected['positions']) or any(
                    label not in LABELS for label in labels.values()):
                raise ValueError('exact frozen anchor identities and valid labels required')
            if not active and any(label != 'UNKNOWN' for label in labels.values()):
                raise ValueError('unreviewed anchors must remain UNKNOWN')
            counts = methods.setdefault(method, {'confirmed_correct': 0, 'confirmed_wrong': 0,
                                                  'unknown': 0, 'confirmed_anchor_positions': 0})
            counts['confirmed_anchor_positions'] += sum(
                label == 'CORRECT' for label in labels.values()) if active else 0
            verdict = ('confirmed_wrong' if active and 'INCORRECT' in labels.values() else
                       'confirmed_correct' if active and len(labels) >= 3
                       and all(v == 'CORRECT' for v in labels.values()) else 'unknown')
            state = states.setdefault(answer['state'], {}).setdefault(method, {
                'human_reviewed_cases': 0, 'geometry_accepted': 0, 'geometry_rejected': 0,
                'confirmed_correct': 0, 'confirmed_wrong': 0, 'unknown': 0,
            })
            state['human_reviewed_cases'] += active
            state['geometry_accepted' if detected['geometry_consistent']
                  else 'geometry_rejected'] += 1
            # A rejected candidate is not an accepted calibration or false calibration.
            if detected['geometry_consistent']:
                counts[verdict] += 1
                state[verdict] += 1
    for counts in methods.values():
        n = counts['confirmed_correct'] + counts['confirmed_wrong']
        counts['reviewed_output_agreement'] = counts['confirmed_correct'] / n if n else None
        counts['reviewed_output_denominator'] = n
    return {'reviewed_cases': reviewed, 'unreviewed_cases': len(expected) - reviewed,
            'methods': methods, 'states': states, 'population_accuracy': None,
            'targeted_selection': True, 'formal_events': [], 'production_qualified': False}


def position_stability(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Observed displacement only; absence and source gaps are not stable positions."""
    if len(rows) < 2:
        raise ValueError('at least two native witnesses required')
    if any(type(r['tick']) is not int or Fraction(r['time_base']) <= 0 for r in rows):
        raise ValueError('native integer PTS and positive rational timebase required')
    identity = {(r['source_sha256'], r['epoch'], r['time_base']) for r in rows}
    pts = [int(r['tick']) * Fraction(r['time_base']) for r in rows]
    if len(identity) != 1 or not all(b > a for a, b in zip(pts[:-1], pts[1:], strict=True)):
        raise ValueError('one acquisition/source/timebase and increasing native PTS required')
    names = {name for r in rows for name in r['result']['positions']}
    anchors = {}
    for name in sorted(names):
        boxes = [r['result']['positions'][name] for r in rows
                 if name in r['result']['positions']]
        if any(len(b) != 4 or not all(isinstance(v, (int, float)) and math.isfinite(v)
                                     and 0 <= v <= 1 for v in b)
               or b[0] >= b[2] or b[1] >= b[3] for b in boxes):
            raise ValueError('finite nonempty normalized boxes required')
        displacement = (max(math.hypot(b[0] - a[0], b[1] - a[1])
                            for a in boxes for b in boxes) if len(boxes) >= 2 else None)
        anchors[name] = {'present': len(boxes), 'witnesses': len(rows),
                         'observed_xy_displacement_norm': displacement,
                         'present_in_all_witnesses': len(boxes) == len(rows)}
    consistent = [r['result']['geometry_consistent'] for r in rows]
    return {'anchors': anchors,
            'geometry_toggles': sum(a != b for a, b in zip(
                consistent[:-1], consistent[1:], strict=True)),
            'all_witnesses_geometry_consistent': all(consistent),
            'continuity': 'UNVERIFIED', 'semantic_correctness': 'UNKNOWN'}
