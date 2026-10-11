"""Compare archived native numeric predictions against existing pixel-bound reviews.

Post-prediction reviews remain development evidence. No qualification is created,
and no expected value is passed to a recognizer or used to select a candidate.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

FIELDS = ('round_time_remaining_display', 'score_ally', 'score_enemy')


def outcome(actual: object, expected: object) -> str:
    return 'unknown' if actual is None else 'correct' if actual == expected else 'wrong'


def compare_reviews(current: dict, previous: dict, review: dict) -> dict:
    """Join exact source ticks/pixels; reject missing, changed or duplicated inputs."""
    digest = current['source_video_sha256']
    if previous['source_video_sha256'] != digest or review['source_video_sha256'] != digest:
        raise ValueError('review/source video mismatch')
    current_rows = {r['source_pts_ticks']: r for r in current['source_rows']}
    previous_rows = {r['source_pts_ticks']: r for r in previous['rows']}
    if (len(current_rows) != len(current['source_rows'])
            or len(previous_rows) != len(previous['rows'])):
        raise ValueError('duplicate source PTS')
    seen: set[int] = set()
    counts = {field: {'previous': Counter(), 'current': Counter(), 'transitions': Counter()}
              for field in FIELDS}
    details = []
    for label in review['labels']:
        tick = label['source_pts_ticks']
        if type(tick) is not int or tick in seen:
            raise ValueError('duplicate or invalid reviewed PTS')
        seen.add(tick)
        if tick not in current_rows or tick not in previous_rows:
            raise ValueError('reviewed source PTS missing')
        now, before = current_rows[tick], previous_rows[tick]
        if (now['source_pixel_sha256'] != label['source_pixel_sha256']
                or before['source_pixel_sha256'] != label['source_pixel_sha256']
                or now['source_pts_sec'] != label['pts_sec']
                or before['pts_sec'] != label['pts_sec']):
            raise ValueError('reviewed pixels or time changed')
        if set(label['expected']) != set(FIELDS):
            raise ValueError('explicit reviewed timer/score fields required')
        row = {'source_pts_ticks': tick, 'pts_sec': label['pts_sec'],
               'source_pixel_sha256': label['source_pixel_sha256'], 'fields': {}}
        for field in FIELDS:
            expected = label['expected'][field]
            if (field == 'round_time_remaining_display' and not isinstance(expected, str)
                    or field != 'round_time_remaining_display'
                    and (type(expected) is not int or expected < 0)):
                raise ValueError('invalid reviewed numeric value')
            actual = now['system_observation']['values'].get(field)
            prior = before['observation']['values'].get(field)
            for value in (actual, prior):
                if value is not None and (
                    field == 'round_time_remaining_display' and not isinstance(value, str)
                    or field != 'round_time_remaining_display' and type(value) is not int
                ):
                    raise ValueError('invalid prediction value type')
            prior_outcome, current_outcome = outcome(prior, expected), outcome(actual, expected)
            counts[field]['previous'][prior_outcome] += 1
            counts[field]['current'][current_outcome] += 1
            counts[field]['transitions'][f'{prior_outcome} -> {current_outcome}'] += 1
            row['fields'][field] = {'previous': prior, 'current': actual,
                                    'previous_outcome': prior_outcome,
                                    'current_outcome': current_outcome}
        details.append(row)
    if not details:
        raise ValueError('nonempty explicit review required')
    metrics = {}
    for field, values in counts.items():
        metrics[field] = {
            'outcomes': {key: {'previous': values['previous'][key],
                              'current': values['current'][key],
                              'delta': values['current'][key] - values['previous'][key]}
                         for key in ('correct', 'unknown', 'wrong')},
            'transitions': dict(values['transitions']),
        }
    return {
        'scope': __doc__, 'source_video_sha256': digest,
        'review_provenance': review['review_provenance'], 'reviewed_frames': len(details),
        'current_profile_fingerprint': current['profile_fingerprint'],
        'previous_profile_fingerprint': previous['profile_fingerprint'],
        'current_recognizer_fingerprint': current['recognizer_fingerprint'],
        'previous_recognizer_fingerprint': previous['recognizer_fingerprint'],
        'comparison': metrics, 'rows': details, 'qualification_created': False,
        'independent_holdout_proven': False, 'canonical_e2e_reexecuted': False,
        'limitations': ['Post-prediction source review',
                        'Training overlap not exhaustively excluded',
                        'Different profiles and temporal input ranges',
                        'This active-context numeric review has no absent-value controls'],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--current', type=Path, required=True)
    parser.add_argument('--previous', type=Path, required=True)
    parser.add_argument('--review', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    contents = {str(p): p.read_bytes() for p in (args.current, args.previous, args.review)}
    review = json.loads(contents[str(args.review)])
    expected_hash = review['input_sha256'].get(args.previous.as_posix())
    if expected_hash != hashlib.sha256(contents[str(args.previous)]).hexdigest():
        raise ValueError('previous prediction differs from reviewed input binding')
    report = compare_reviews(*(json.loads(contents[str(p)]) for p in
                               (args.current, args.previous, args.review)))
    report['input_sha256'] = {path: hashlib.sha256(raw).hexdigest()
                              for path, raw in contents.items()}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    print(json.dumps(report['comparison']))


if __name__ == '__main__':
    main()
