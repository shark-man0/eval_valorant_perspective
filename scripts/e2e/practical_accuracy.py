"""Separate practical time scoring; never imported by production detectors."""
from __future__ import annotations

import math
import re
from typing import Any

from valorant_ai_coach.rounds.boundaries import BoundaryObservation

PRACTICAL_TIME_TOLERANCE_SEC = 0.1


def evaluation_source_binding(
    prediction_doc: dict[str, Any], truth_doc: dict[str, Any],
) -> dict[str, Any]:
    """Reject cross-source scoring; legacy numeric comparisons stay unverified.

    A matching source does not attest independent label review or qualification.
    Package exports carry decoder hashes in actual boundary provenance; unknown
    endpoints have no source timestamp and cannot contribute source attestation.
    """
    hashes: set[str] = set()

    def include(value: Any) -> None:
        if value is None:
            return
        if not isinstance(value, str) or re.fullmatch(r'[0-9a-f]{64}', value) is None:
            raise ValueError('invalid practical evaluation source SHA256')
        hashes.add(value)

    include(prediction_doc.get('source_video_sha256'))
    observed = [b for b in prediction_doc['boundaries']
                if b.get('boundary_status') != 'unknown']
    bound_observations = 0
    for boundary in observed:
        proof = boundary.get('provenance', {})
        event_proof = proof.get('event', {}).get('attributes', {}).get('evidence_provenance', {})
        direct = proof.get('source_video_sha256')
        transported = event_proof.get('source_video_sha256')
        include(direct)
        include(transported)
        if direct is not None or transported is not None:
            bound_observations += 1
    if len(hashes) > 1:
        raise ValueError('practical predictions contain multiple source videos')
    source = next(iter(hashes), None)
    truth_source = truth_doc.get('source_video_sha256')
    # Reuse the same syntax check without including truth in prediction support.
    if truth_source is not None and (
        not isinstance(truth_source, str)
        or re.fullmatch(r'[0-9a-f]{64}', truth_source) is None
    ):
        raise ValueError('invalid practical truth source SHA256')
    if source is not None and truth_source is not None and source != truth_source:
        raise ValueError('practical prediction and truth source videos differ')
    covered = (prediction_doc.get('source_video_sha256') is not None
               or bound_observations == len(observed))
    verified = source is not None and truth_source is not None and covered
    return {
        'source_binding_verified': verified,
        'prediction_source_video_sha256': source,
        'truth_source_video_sha256': truth_source,
        'reason': ('same_source_hash' if verified else 'source_binding_incomplete'),
        'independent_label_review_verified': False,
        'scope': 'Source hash agreement only; numeric PASS is not independent precision proof',
    }


def evaluate_matched_boundary(
    prediction: BoundaryObservation | None, *, truth_kind: str,
    truth_time_sec: float | None,
) -> dict[str, Any]:
    """Score one externally associated boundary; not a multi-event matcher.

    Independent ground truth stays on the evaluator side. Callers must establish
    one-to-one correspondence before calling this function: a nearby observation
    of another kind or a duplicate must never become an extra PASS.
    """
    if truth_kind not in {"round_start", "round_end"}:
        raise ValueError("unsupported ground truth boundary kind")
    if truth_time_sec is not None and (
        type(truth_time_sec) not in (int, float)
        or not math.isfinite(truth_time_sec) or truth_time_sec < 0
    ):
        raise ValueError("ground truth time must be finite and nonnegative")
    result: dict[str, Any] = {
        "status": "NE", "absolute_error_sec": None,
        "tolerance_sec": PRACTICAL_TIME_TOLERANCE_SEC,
        "boundary_status": prediction.boundary_status if prediction else "unknown",
    }
    if truth_time_sec is None:
        result["reason"] = "no_independent_truth_time"
    elif prediction is None or prediction.boundary_status == "unknown":
        result.update(status="FAIL", reason="boundary_unavailable")
    elif prediction.kind != truth_kind:
        result.update(status="FAIL", reason="boundary_kind_mismatch")
    else:
        assert prediction.boundary_time_sec is not None
        error = abs(prediction.boundary_time_sec - truth_time_sec)
        # Absorb floating subtraction error only, never round a predicted time.
        within = error <= PRACTICAL_TIME_TOLERANCE_SEC or math.isclose(
            error, PRACTICAL_TIME_TOLERANCE_SEC, rel_tol=0, abs_tol=1e-12,
        )
        result.update(status="PASS" if within else "FAIL", absolute_error_sec=error,
                      reason="within_practical_tolerance" if within else "time_error")
    return result


def evaluate_boundary_set(
    predictions: list[BoundaryObservation], truths: list[dict[str, Any]], *,
    complete_review: bool = False, association_radius_sec: float = 1.0,
) -> dict[str, Any]:
    """Order-preserving, one-to-one evaluator association; never detector policy.

    Truth entries have independent id/kind/time_sec fields. Missing point truth
    stays NE: a window midpoint must not be substituted. The association radius
    only links candidate events; acceptance remains the separate ±0.1 criterion.
    Unmatched predictions are verified false positives only for complete reviews.
    """
    if (type(association_radius_sec) not in (int, float)
            or not math.isfinite(association_radius_sec)
            or association_radius_sec < PRACTICAL_TIME_TOLERANCE_SEC):
        raise ValueError('association radius must be finite and at least the time tolerance')
    if type(complete_review) is not bool:
        raise ValueError('complete review must be boolean')
    if any(not isinstance(t, dict) or not {'id', 'kind', 'time_sec'} <= t.keys()
           for t in truths):
        raise ValueError('truth entries require id, kind and independent time_sec')
    ids = [t.get('id') for t in truths]
    if any(not isinstance(t, str) or not t for t in ids) or len(set(ids)) != len(ids):
        raise ValueError('unique independent truth IDs required')
    for truth in truths:
        evaluate_matched_boundary(None, truth_kind=truth['kind'], truth_time_sec=truth['time_sec'])
    known = sorted((i for i, t in enumerate(truths) if t['time_sec'] is not None),
                   key=lambda i: truths[i]['time_sec'])
    observed = sorted((i for i, p in enumerate(predictions) if p.boundary_time_sec is not None),
                      key=lambda i: predictions[i].boundary_time_sec)

    # Bottom-up alignment avoids recursion limits on long recordings.
    empty: tuple[int, float, tuple[tuple[int, int], ...]] = (0, 0., ())
    following = [empty] * (len(observed) + 1)
    for i in range(len(known) - 1, -1, -1):
        current = [empty] * (len(observed) + 1)
        for j in range(len(observed) - 1, -1, -1):
            options = [following[j], current[j + 1]]
            truth, prediction = truths[known[i]], predictions[observed[j]]
            assert prediction.boundary_time_sec is not None
            error = abs(truth['time_sec'] - prediction.boundary_time_sec)
            if truth['kind'] == prediction.kind and error <= association_radius_sec:
                count, cost, matched = following[j + 1]
                options.append((count + 1, cost + error, ((known[i], observed[j]), *matched)))
            current[j] = min(options, key=lambda option: (-option[0], option[1], option[2]))
        following = current
    pairs = dict(following[0][2])
    rows = []
    for index, truth in enumerate(truths):
        prediction_index = pairs.get(index)
        prediction = predictions[prediction_index] if prediction_index is not None else None
        rows.append({'truth_id': truth['id'], 'prediction_index': prediction_index,
                     **evaluate_matched_boundary(prediction, truth_kind=truth['kind'],
                                                 truth_time_sec=truth['time_sec'])})
    unused = sorted(set(observed) - set(pairs.values()))
    # Missing point truth cannot certify exhaustive temporal review.
    exhaustive = complete_review and len(known) == len(truths)
    false_positives = len(unused) if exhaustive else None
    counts = {status: sum(r['status'] == status for r in rows) for status in ('PASS', 'FAIL', 'NE')}
    counts['FAIL' if exhaustive else 'NE'] += len(unused)
    return {
        'evaluation_kind': 'practical_boundary_accuracy',
        'time_tolerance_sec': PRACTICAL_TIME_TOLERANCE_SEC,
        'association_radius_sec': association_radius_sec,
        'complete_boundary_review_requested': complete_review,
        'complete_boundary_review': exhaustive, 'counts': counts, 'boundaries': rows,
        'unmatched_prediction_status': 'FAIL' if exhaustive else 'NE',
        'unmatched_prediction_indices': unused, 'false_positive_count': false_positives,
        'known_truth_count': len(known), 'matched_boundary_count': len(pairs),
        'boundary_detection_rate': len(pairs) / len(known) if known else None,
        'time_accuracy_rate': counts['PASS'] / len(known) if known else None,
        'confirmed_boundary_count': sum(p.boundary_status == 'confirmed' for p in predictions),
        'provisional_boundary_count': sum(p.boundary_status == 'provisional' for p in predictions),
        'unknown_boundary_count': sum(p.boundary_status == 'unknown' for p in predictions),
    }


def main(argv: list[str] | None = None) -> int:
    """Evaluate exported boundaries without changing the canonical evaluator."""
    import argparse
    import hashlib
    import json
    from pathlib import Path

    parser = argparse.ArgumentParser(description=__doc__)
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument('--packages', type=Path,
                        help='Saved JSON object with round_packages for evidence export')
    inputs.add_argument('--predictions', type=Path,
                        help='JSON object with boundaries (BoundaryObservation records)')
    parser.add_argument('--truth', type=Path, required=True,
                        help='Independent reviewed JSON object with boundaries: id/kind/time_sec')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--association-radius-sec', type=float, default=1.0)
    args = parser.parse_args(argv)
    prediction_path = args.packages if args.packages is not None else args.predictions
    prediction_bytes = prediction_path.read_bytes()
    truth_bytes = args.truth.read_bytes()
    prediction_doc, truth_doc = json.loads(prediction_bytes), json.loads(truth_bytes)
    if args.packages is not None:
        from .practical_export import export_package_boundaries

        prediction_doc = export_package_boundaries(prediction_doc['round_packages'])
    predictions = [BoundaryObservation.from_dict(row) for row in prediction_doc['boundaries']]
    source_binding = evaluation_source_binding(prediction_doc, truth_doc)
    report = evaluate_boundary_set(
        predictions, truth_doc['boundaries'],
        complete_review=truth_doc.get('complete_review', False),
        association_radius_sec=args.association_radius_sec,
    )
    report['inputs'] = {
        'predictions_sha256': hashlib.sha256(prediction_bytes).hexdigest(),
        'truth_sha256': hashlib.sha256(truth_bytes).hexdigest(),
    }
    if args.packages is not None:
        report['package_export'] = {k: v for k, v in prediction_doc.items() if k != 'boundaries'}
        report['inputs']['input_kind'] = 'round_packages'
    else:
        report['inputs']['input_kind'] = 'boundary_observations'
    report['canonical_evaluation_modified'] = False
    report['source_binding'] = source_binding
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8',
    )
    print(json.dumps({'evaluation_kind': report['evaluation_kind'], 'counts': report['counts'],
                      **{k: source_binding[k] for k in ('source_binding_verified',
                                                       'independent_label_review_verified')}}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
