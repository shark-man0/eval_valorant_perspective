"""Replay frozen background challenges; not lifecycle qualification."""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import cv2

from valorant_ai_coach.hud.global_lifecycle import global_recognizer_fingerprint
from valorant_ai_coach.hud.score_glyphs import StrictScoreGlyphReader


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run():
    started = time.perf_counter()
    root = Path('e2e_reports/match_001')
    plan_path = root / 'score_enlarged_background_controls_complete_plan.json'
    review_path = root / 'score_enlarged_background_controls_review.json'
    previous_path = root / 'score_enlarged_background_controls_results.json'
    output = root / 'score_background_current_reader_replay.json'
    if output.exists():
        raise ValueError('new output required')
    plan, review, previous = [json.loads(p.read_text()) for p in (
        plan_path, review_path, previous_path,
    )]
    if (digest(plan_path) != previous['plan_sha256']
            or digest(review_path) != previous['pre_prediction_review_sha256']
            or review['plan_sha256'] != digest(plan_path)
            or review['expected_numeric_present'] is not False
            or review['natural_score_field_absence'] is not False):
        raise ValueError('frozen negative review binding mismatch')
    profile = Path('outputs/hud_profiles/round-global-timer-glyph-20261008')
    sidecar = profile / 'score-rowcontrast-late-result-diagnostic.templates.json'
    inputs = {str(p): digest(p) for p in (
        plan_path, review_path, previous_path, sidecar, Path(__file__),
    )}
    specs = json.loads(sidecar.read_text())['readers']
    readers = {}
    for role in ('ally_score', 'enemy_score'):
        spec = specs[role]
        if spec['glyph_threshold'] != .90 or spec['glyph_margin'] != .04:
            raise ValueError('unchanged strict thresholds required')
        templates = {}
        for digit, relative in spec['templates'].items():
            asset = profile / relative
            inputs[str(asset)] = digest(asset)
            templates[digit] = [cv2.imread(str(asset), cv2.IMREAD_GRAYSCALE)]
        readers[role] = StrictScoreGlyphReader(
            templates, comparison_preprocessing=spec['comparison_preprocessing'],
            foreground_preprocessing=spec['foreground_preprocessing'],
        )
    fingerprint = global_recognizer_fingerprint()
    rows = []
    counts = {role: {'unknown': 0, 'false_accept': 0} for role in readers}
    for row in plan['rows']:
        source = Path(row['source_frame'])
        inputs[str(source)] = digest(source)
        image = cv2.imread(str(source))
        if (inputs[str(source)] != row['frame_sha256']
                or hashlib.sha256(image.tobytes()).hexdigest() != row['pixel_sha256']):
            raise ValueError('frozen physical negative source changed')
        x1, y1, x2, y2 = row['bounds_px']
        crop = image[y1:y2, x1:x2]
        if crop.shape != (45, 44, 3):
            raise ValueError('original core-reader crop size required')
        readings = {}
        for role, reader in readers.items():
            reading = reader.read(image, crop)
            counts[role]['unknown' if reading.value is None else 'false_accept'] += 1
            readings[role] = {'value': reading.value, 'confidence': reading.confidence,
                              'sources': list(reading.sources)}
        rows.append({**row, 'readings': readings})
    if (any(digest(p) != h for p, h in inputs.items())
            or fingerprint != global_recognizer_fingerprint()):
        raise ValueError('replay inputs changed')
    result = {
        'scope': 'Frozen off-HUD background core-reader challenges only',
        'input_sha256': inputs, 'recognizer_fingerprint': fingerprint,
        'distinct_physical_frames': len({r['frame_sha256'] for r in rows}),
        'counts': counts, 'rows': rows, 'wall_clock_sec': time.perf_counter() - started,
        'previous': previous['counts']['prototype'],
        'delta_per_role': {role: {
            'unknown': count['unknown'] - previous['counts']['prototype']['unknown'],
            'false_accept': count['false_accept'],
        } for role, count in counts.items()},
        'natural_nominal_field_absence_verified': False,
        'independent_new_holdout': False, 'qualification_created': False,
        'production_changed': False, 'canonical_current': None, 'canonical_delta': None,
    }
    output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'counts': counts, 'distinct_physical_frames':
                      result['distinct_physical_frames']}))


if __name__ == '__main__':
    run()
