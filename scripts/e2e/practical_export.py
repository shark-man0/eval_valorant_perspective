"""Export saved Package evidence separately from canonical trace events."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from valorant_ai_coach.rounds.boundaries import BoundaryObservation
from valorant_ai_coach.schema_validation import SchemaValidator


def export_package_boundaries(packages: list[dict[str, Any]]) -> dict[str, Any]:
    """Read existing evidence without inventing boundaries at fragment edges.

    Formal events keep their existing status; this export is not qualification.
    Package endpoint metadata supplies provisional/unknown records. Adjacent
    packages may share the same formal event: identical IDs are exported once,
    while conflicting records are rejected. Distinct formal IDs remain distinct
    even at the same timestamp so the accuracy evaluator can detect duplicates.
    """
    validator = SchemaValidator()
    for package in packages:
        validator.validate_round_package(package)
    if packages and any((p['match_id'], p['source_video']) !=
                        (packages[0]['match_id'], packages[0]['source_video']) for p in packages):
        raise ValueError('boundary export requires one match and source')
    ordered = sorted(packages, key=lambda p: p['round_window']['start_sec'])
    if any(a['round_window']['end_sec'] > b['round_window']['start_sec']
           for a, b in zip(ordered, ordered[1:], strict=False)):
        raise ValueError('overlapping packages cannot establish unique boundary association')
    formal: dict[str, BoundaryObservation] = {}
    formal_keys: set[tuple[str, float]] = set()
    for package in ordered:
        for event in package['events']:
            if event['type'] not in {'round_start', 'round_end'}:
                continue
            proof = event['attributes'].get('evidence_provenance', {})
            timestamp = event['time_sec']
            confirmation = proof.get('confirmation_pts_sec')
            times = list(proof.get('pts_sec', [])) + [timestamp]
            if confirmation is not None:
                times.append(confirmation)
            boundary = BoundaryObservation(
                event['type'], 'confirmed', timestamp, confirmation,
                tuple(sorted(set(times))), event['confidence'],
                {'transport': 'existing_round_package_event', 'event': deepcopy(event)},
            )
            event_id = event['event_id']
            if event_id in formal and formal[event_id] != boundary:
                raise ValueError('conflicting formal event ID across packages')
            formal[event_id] = boundary
            formal_keys.add((event['type'], timestamp))
    candidates: dict[tuple[str, float], BoundaryObservation] = {}
    unknowns: list[BoundaryObservation] = []
    partitions = []
    for package in ordered:
        lifecycle = package.get('round_lifecycle')
        statuses = {}
        for name, kind in (('start', 'round_start'), ('end', 'round_end')):
            endpoint = lifecycle[name] if lifecycle else None
            status = endpoint['status'] if endpoint else (
                'confirmed' if any(e['type'] == kind for e in package['events']) else 'unknown'
            )
            statuses[name] = status
            if status == 'provisional':
                boundary = BoundaryObservation.from_dict(endpoint['candidate'])
                if boundary.boundary_status != 'provisional':
                    raise ValueError('provisional endpoint must carry a provisional observation')
                key = (kind, boundary.boundary_time_sec)
                if key in formal_keys:
                    continue
                if key in candidates and candidates[key] != boundary:
                    raise ValueError('conflicting provisional evidence across packages')
                candidates[key] = boundary
            elif status == 'unknown':
                unknowns.append(BoundaryObservation(
                    kind, 'unknown', None, None, (), None,
                    {'reason': 'package_endpoint_unknown', 'match_id': package['match_id'],
                     'interval_no': package['round_no'], 'endpoint': name},
                ))
        partitions.append({'interval_no': package['round_no'],
                           'window': deepcopy(package['round_window']), **statuses})
    observed = sorted([*formal.values(), *candidates.values()],
                      key=lambda b: (b.boundary_time_sec, b.kind))
    return {
        'scope': 'Existing Package evidence export; not reader qualification or GT',
        'boundaries': [b.to_dict() for b in [*observed, *unknowns]],
        'package_count': len(packages),
        'provisional_package_count': sum(
            'provisional' in (p['start'], p['end']) for p in partitions),
        'uncertain_package_count': sum((p['start'], p['end']) != ('confirmed', 'confirmed')
                                       for p in partitions),
        'partitions': partitions,
    }
