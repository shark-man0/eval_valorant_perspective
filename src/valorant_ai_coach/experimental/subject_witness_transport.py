"""Transport frozen image measurements to typed, still-unqualified witnesses.

No image is recognized here and no source fingerprint is rewritten. In
particular a geometric role has no fabricated numeric confidence. Report
onset support comes from its recorded source frame, never confirmation time.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict
from typing import Any

from .subject_death import (
    DeathProbeDecision,
    SourceBinding,
    SubjectObservation,
    SubjectRelation,
    SubjectRole,
)


def _score(value: Any) -> float:
    if (type(value) not in (int, float) or not math.isfinite(value)
            or not 0 <= value <= 1):
        raise ValueError('finite actually recorded source support required')
    return float(value)


def _box(value: Any) -> tuple[int, int, int, int]:
    if (not isinstance(value, (list, tuple)) or len(value) != 4
            or any(type(v) is not int or v < 0 for v in value)
            or value[0] >= value[2] or value[1] >= value[3]):
        raise ValueError('recorded nonempty integer source ROI required')
    return value[0], value[1], value[2], value[3]


def _witness(source: SourceBinding, role: SubjectRole, score: float | None,
             method: str, roi: tuple[int, int, int, int]) -> SubjectObservation:
    payload = {'source': asdict(source), 'role': role, 'score': score,
               'method': method, 'roi': roi}
    evidence_id = hashlib.sha256(json.dumps(
        payload, sort_keys=True, allow_nan=False,
    ).encode('utf-8')).hexdigest()
    return SubjectObservation(evidence_id, source, role, SubjectRelation.UNKNOWN,
                              None, score, method, roi)


def transport_prediction(
    rows: list[dict[str, Any]], prediction_index: int, *,
    report_roi: tuple[int, int, int, int],
) -> DeathProbeDecision:
    """Preserve one actual prediction's source measurements, without authority.

    The caller binds the frozen trace/config artifacts before this operation.
    The result cannot certify their truth or confer Self/event qualification.
    Missing source frames, conflicting bindings and unsupported onset scores
    are errors, rather than opportunities to borrow nearby evidence.
    """
    if type(prediction_index) is not int or not 0 <= prediction_index < len(rows):
        raise ValueError('recorded prediction index required')
    prediction = rows[prediction_index]
    if prediction['status'] != 'prediction':
        raise ValueError('only an actually recorded image prediction can be transported')
    report_roi = _box(report_roi)
    source = SourceBinding(**prediction['source'])
    by_source: dict[SourceBinding, dict[str, Any]] = {}
    for row in rows[:prediction_index+1]:
        binding = SourceBinding(**row['source'])
        if binding in by_source:
            raise ValueError('duplicate physical source reading')
        by_source[binding] = row
    evidence = tuple(SourceBinding(**s) for s in prediction['evidence_sources'])
    if (not evidence or source not in evidence or len(set(evidence)) != len(evidence)
            or any(s.context != source.context or s.time > source.time or s not in by_source
                   for s in evidence)):
        raise ValueError('complete same-context original source evidence required')
    # Look up the original rational binding; never derive PTS from float seconds.
    onset_time = prediction['onset_time_sec']
    onsets = [s for s in evidence if float(s.time) == onset_time]
    if len(onsets) != 1 or prediction['confirmation_time_sec'] != float(source.time):
        raise ValueError('unambiguous recorded onset/confirmation bindings required')
    onset = onsets[0]
    onset_support = _score(by_source[onset]['report_support'])
    aggregate = _score(prediction['support'])
    if onset_support < .90 or aggregate < .90:
        raise ValueError('accepted original self-caption and prediction support required')
    victims = [s for s in prediction['subjects'] if s['role'] == 'victim']
    if len(victims) != 1:
        raise ValueError('one independently recorded victim role required')
    victim = victims[0]
    if SourceBinding(**victim['source']) != source:
        raise ValueError('victim measurements belong to another physical source frame')
    marker_scores = victim['marker_support']
    if not isinstance(marker_scores, (list, tuple)) or len(marker_scores) != 3:
        raise ValueError('three recorded structural marker supports required')
    marker_score = min(*(_score(v) for v in marker_scores), _score(victim['yellow_fraction']))
    if marker_score < .90:
        raise ValueError('accepted marker support required')
    weapon_roi = _box(victim['weapon_roi'])
    weapon_score = victim.get('weapon_support')
    if weapon_score is not None:
        weapon_score = _score(weapon_score)
        if weapon_score < .90:
            raise ValueError('accepted independent weapon NCC required')
        method = 'killfeed_weapon_template_ncc_v1'
    else:
        geometry = victim.get('weapon_geometry')
        if not isinstance(geometry, dict) or _box(geometry['roi']) != weapon_roi:
            raise ValueError('recorded geometric role witness required when NCC is absent')
        method = 'killfeed_weapon_glyph_geometry_v2'
    witnesses = (
        _witness(source, SubjectRole.SOURCE_PLAYER_BINDING, marker_score,
                 'killfeed_highlight_shape_color_v1', _box(victim['marker_roi'])),
        _witness(source, SubjectRole.VICTIM, weapon_score, method, weapon_roi),
        _witness(onset, SubjectRole.DEATH_TRANSITION, onset_support,
                 'fresh_self_referential_report_caption_ncc_v1', report_roi),
    )
    blockers = ['subject_role_transition_not_qualified', 'production_adoption_not_authorized']
    if weapon_score is None:
        blockers.append('victim_numeric_confidence_absent_structural_witness_only')
    numeric = [aggregate, marker_score, onset_support]
    if weapon_score is not None:
        numeric.append(weapon_score)
    return DeathProbeDecision('candidate', tuple(blockers), source,
                              float(onset.time), float(source.time), min(numeric), witnesses)
