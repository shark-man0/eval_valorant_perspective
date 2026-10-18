"""Audit frozen static Role readings against separately frozen source reviews.

This is an offline evaluator, never a recognizer, qualifier or Event producer.
Labels are not passed back to recognition. Exact file/source bindings matter;
unknown truth and geometric-only roles cannot become qualification successes.
"""
from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from fractions import Fraction
from pathlib import Path

from scripts.diagnostics.verify_self_death_review import sha256_file
from valorant_ai_coach.experimental.death_episode_fields import _accepted
from valorant_ai_coach.experimental.subject_death import SourceBinding


def verify_decode_bindings(predictions: dict, review: dict, manifest: dict) -> None:
    """Bind every reviewed reading to the original native decode, not just its hash.

    This checks saved acquisition metadata; it does not reread private images or
    prove continuity, recognition accuracy, review independence or qualification.
    """
    rows = manifest.get('rows')
    if (not isinstance(rows, list) or not rows
            or type(manifest.get('processed_frames')) is not int
            or manifest['processed_frames'] != len(rows)
            or len(rows) != len(predictions['rows']) or len(rows) != len(review['labels'])
            or manifest.get('terminal_source_code_profile_asset_hashes_verified') is not True
            or manifest.get('qualifies_continuity') is not False
            or type(manifest.get('formal_events')) is not int
            or manifest['formal_events'] != 0):
        raise ValueError('complete verified static decode manifest required')
    for native, frame, label in zip(rows, predictions['rows'], review['labels'], strict=True):
        source = SourceBinding(**frame['source'])
        if (source.video_sha256 != native['source_video_sha256']
                or type(native['pts_ticks']) is not int
                or source.pts_ticks != native['pts_ticks']
                or source.time_base_num != native['time_base_num']
                or source.time_base_den != native['time_base_den']
                or source.segment_id != native['source_epoch']
                or source.pixel_sha256 != native['pixel_sha256']
                or label['source_encoded_sha256'] != native['encoded_sha256']):
            raise ValueError('reading/review does not match original native decode')


def audit_roles(predictions: dict, review: dict, *, row_origin: float, row_pitch: float) -> dict:
    """Count source-reviewed rows; layout coordinates are evaluation-only."""
    if any(type(x) not in (int, float) or not math.isfinite(x)
           for x in (row_origin, row_pitch)) or row_pitch <= 0:
        raise ValueError('explicit finite source-review row layout required')
    rows, labels = predictions['rows'], review['labels']
    if (type(predictions['frame_count']) is not int
            or len(rows) != predictions['frame_count'] or len(rows) != len(labels)
            or not rows or type(predictions.get('formal_events')) is not int
            or predictions['formal_events'] != 0
            or predictions.get('continuity_qualified') is not False
            or predictions.get('independent_qualification_granted') is not False
            or predictions.get('terminal_source_code_profile_asset_dependency_hashes_verified')
            is not True):
        raise ValueError('complete verified static candidate readings required')
    counts: Counter = Counter()
    strata: dict[str, Counter] = {}
    seen: set[tuple] = set()
    pixels: set[str] = set()
    for index, (frame, label) in enumerate(zip(rows, labels, strict=True), 1):
        source = SourceBinding(**frame['source'])
        if (type(frame['index']) is not int or type(label['index']) is not int
                or frame['index'] != index or label['index'] != index
                or source.video_sha256 != predictions['source_sha256']
                or source.video_sha256 != review['source_sha256']
                or source.code_fingerprint != predictions['reader_code_fingerprint']
                or source.profile_fingerprint != predictions['profile_fingerprint']
                or source.dependencies_fingerprint != predictions['dependencies_fingerprint']
                or type(label['source_pts_ticks']) is not int
                or source.pts_ticks != label['source_pts_ticks']
                or Fraction(source.time_base_num, source.time_base_den)
                != Fraction(label['source_time_base'])
                or source.pixel_sha256 != label['source_pixel_sha256']):
            raise ValueError('review/reading source, order or fingerprint mismatch')
        identity = (source.video_sha256, source.pts_ticks,
                    source.time_base_num, source.time_base_den)
        if identity in seen:
            raise ValueError('duplicate physical source frame')
        seen.add(identity)
        pixels.add(source.pixel_sha256)
        expected = label['expected_self_rows']
        slots = [item['row_from_top'] for item in expected]
        if (any(type(slot) is not int or slot < 1 for slot in slots)
                or len(set(slots)) != len(slots)
                or any(item['role'] not in {'killer', 'victim'} for item in expected)
                or type(label['additional_partial_row_unresolved']) is not bool):
            raise ValueError('unambiguous reviewed rows or explicit unresolved truth required')
        known = (label['known_native_or_nearby_episode_exposure']
                 or label['additional_known_full_image_context_pts_ticks'])
        bucket = strata.setdefault('known_episode_or_context' if known
                                   else 'no_known_episode_record_not_blind', Counter())
        current: Counter = Counter(frames=1, reviewed_self_rows=len(expected))
        matched: set[int] = set()
        for subject in frame['subjects']:
            if subject['source'] != frame['source']:
                raise ValueError('subject comes from another source reading')
            box = subject['marker_roi']
            if (len(box) != 4 or any(type(x) is not int or x < 0 for x in box)
                    or box[0] >= box[2] or box[1] >= box[3]
                    or subject['role'] not in {'killer', 'victim', 'unknown'}
                    or len(subject['marker_support']) != 3
                    or not all(_accepted(x) for x in subject['marker_support'])
                    or not _accepted(subject['yellow_fraction'])):
                raise ValueError('original accepted marker measurements required')
            center = (box[1] + box[3]) / 2
            matches = [n for n, item in enumerate(expected)
                       if abs(center - (row_origin + (item['row_from_top'] - 1) * row_pitch))
                       < row_pitch / 2]
            if len(matches) != 1 or matches[0] in matched:
                if not matches and label['additional_partial_row_unresolved']:
                    current['unreviewed_output_rows'] += 1
                else:
                    current['false_self_markers'] += 1
                    current['false_known_roles'] += int(subject['role'] != 'unknown')
                continue
            n = matches[0]
            matched.add(n)
            current['correct_self_markers'] += 1
            truth = expected[n]
            if subject['role'] != truth['role']:
                current['role_abstentions' if subject['role'] == 'unknown'
                        else 'wrong_roles'] += 1
                continue
            current['correct_roles'] += 1
            current['correct_' + truth['role']] += 1
            if (subject['role'] == 'victim' and subject['weapon_roi'] is not None
                    and _accepted(subject['weapon_support'])
                    and (subject['weapon_plate_fraction'] is None
                         or _accepted(subject['weapon_plate_fraction']))):
                current['numeric_victim_rows'] += 1
            name = subject['name_text']
            if name is not None:
                if not isinstance(name, str) or not name.strip() or not _accepted(
                    subject['name_confidence']
                ):
                    raise ValueError('original accepted name measurement required')
                current['correct_own_names' if name == truth['name_display']
                        else 'wrong_own_names'] += 1
        current['missed_self_markers'] += len(expected) - len(matched)
        current['missed_known_roles'] += len(expected) - current['correct_roles']
        if not expected and not label['additional_partial_row_unresolved']:
            current['reviewed_no_self_frames'] += 1
            current['true_negative_frames'] += int(not frame['subjects'])
        current['unresolved_truth_frames'] += int(label['additional_partial_row_unresolved'])
        counts.update(current)
        bucket.update(current)
    # Stable zero keys matter: absence is not an implied successful test.
    for key in ('false_self_markers', 'false_known_roles', 'wrong_roles',
                'unreviewed_output_rows', 'wrong_own_names', 'role_abstentions'):
        counts.setdefault(key, 0)
    counts['distinct_source_pixels'] = len(pixels)
    counts['repeated_pixel_frames'] = len(rows) - len(pixels)
    return {'scope': 'Static source-reviewed candidate field audit only',
            'counts': dict(counts), 'exposure_strata': {k: dict(v) for k, v in strata.items()},
            'independent_qualification_granted': False, 'continuity_qualified': False,
            'formal_events': 0, 'canonical_current': 'not_measured'}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('readings', 'review', 'manifest', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--row-origin', type=float, required=True)
    parser.add_argument('--row-pitch', type=float, required=True)
    args = parser.parse_args()
    paths = (args.readings, args.review, args.manifest)
    hashes = {str(p): sha256_file(p) for p in paths}
    readings = json.loads(args.readings.read_text(encoding='utf-8'))
    review = json.loads(args.review.read_text(encoding='utf-8'))
    manifest = json.loads(args.manifest.read_text(encoding='utf-8'))
    if (readings['review_sha256'] != hashes[str(args.review)]
            or readings['manifest_sha256'] != hashes[str(args.manifest)]
            or review['manifest_sha256'] != hashes[str(args.manifest)]):
        raise ValueError('exact frozen review and decode manifest required')
    verify_decode_bindings(readings, review, manifest)
    result = audit_roles(readings, review, row_origin=args.row_origin, row_pitch=args.row_pitch)
    if any(sha256_file(Path(p)) != h for p, h in hashes.items()):
        raise ValueError('audit inputs changed')
    result['input_sha256'] = hashes
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps(result['counts'], sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
