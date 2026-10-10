"""Audit existing score glyph ancestry and support; never writes qualification."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import cv2


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run():
    root = Path('outputs/recognition-investigation/timer-glyph-cohort-v2')
    profile = Path('outputs/hud_profiles/round-global-timer-glyph-20261008')
    sidecar = profile / 'score-rowcontrast-late-result-diagnostic.templates.json'
    output = Path('e2e_reports/match_001/score_training_provenance_audit.json')
    if output.exists():
        raise ValueError('new output required')
    manifest_path, labels_path = root / 'manifest.json', root / 'training-blind-labels.json'
    manifest, labels = (json.loads(p.read_text()) for p in (manifest_path, labels_path))
    if (labels['manifest_sha256'] != digest(manifest_path)
            or not labels['all_four_training_pages_visually_reviewed'] or labels['holdout_used']):
        raise ValueError('frozen training review required')
    inputs = {str(p): digest(p) for p in (manifest_path, labels_path, sidecar, Path(__file__))}
    texts = {r['sample_index']: r['timer_text'] for r in labels['observations']}
    bank = {d: [] for d in '0123456789'}
    for row in manifest['observations']:
        if row['split'] != 'training' or not row['glyphs']:
            continue
        source = Path(row['source_frame'])
        inputs[str(source)] = digest(source)
        source_image = cv2.imread(str(source))
        if hashlib.sha256(source_image.tobytes()).hexdigest() != row['decoded_pixel_sha256']:
            raise ValueError('training physical source changed')
        digits = texts[row['sample_index']].replace(':', '')
        for digit, glyph in zip(digits, row['glyphs'], strict=True):
            path = root / glyph['path']
            inputs[str(path)] = digest(path)
            if inputs[str(path)] != glyph['sha256']:
                raise ValueError('training glyph changed')
            bank[digit].append((row, glyph, cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)))
    classes = []
    specs = json.loads(sidecar.read_text())['readers']
    for digit in bank:
        asset = profile / specs['ally_score']['templates'][digit]
        if specs['enemy_score']['templates'][digit] != specs['ally_score']['templates'][digit]:
            raise ValueError('this audit requires existing shared bank')
        inputs[str(asset)] = digest(asset)
        origins = [{'sample_index': row['sample_index'], 'time_sec': row['time_sec'],
                    'source_frame_sha256': inputs[row['source_frame']],
                    'source_pixel_sha256': row['decoded_pixel_sha256'], 'glyph': glyph['path']}
                   for row, glyph, _ in bank[digit] if glyph['sha256'] == inputs[str(asset)]]
        if not origins:
            raise ValueError('profile glyph has no exact frozen training ancestor')
        reference = cv2.GaussianBlur(cv2.imread(str(asset), cv2.IMREAD_GRAYSCALE), (3, 3), 0)
        scores = [float(cv2.matchTemplate(
            cv2.GaussianBlur(image, (3, 3), 0), reference, cv2.TM_CCOEFF_NORMED
        )[0, 0]) for _, _, image in bank[digit]]
        supported = {inputs[row['source_frame']] for (row, _, _), score
                     in zip(bank[digit], scores, strict=True) if score >= .90}
        classes.append({'digit': digit, 'asset_sha256': inputs[str(asset)], 'origins': origins,
                        'training_glyph_count': len(scores),
                        'supported_distinct_source_frames': len(supported),
                        'support_fraction': sum(s >= .90 for s in scores) / len(scores),
                        'minimum_ncc': min(scores),
                        'meets_prior_training_support_rule': len(supported) >= 3
                        and sum(s >= .90 for s in scores) / len(scores) >= .80})
    if any(digest(path) != value for path, value in inputs.items()):
        raise ValueError('training audit inputs changed')
    result = {'scope': 'Exact asset ancestry and fixed Gaussian training support only',
              'input_sha256': inputs, 'classes': classes, 'threshold': .90,
              'minimum_distinct_training_support': 3, 'minimum_support_fraction': .80,
              'holdout_used_for_fitting': False, 'qualification_created': False,
              'production_changed': False, 'profile_changed': False,
              'remaining': [
                  'Original timer glyph support is not whole score-field validation',
                  'Natural nominal score-absence negatives remain unproven',
                  'Positive score source holdout remains separate from lifecycle holdout',
              ]}
    output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({c['digit']: [len(c['origins']), c['supported_distinct_source_frames'],
                                  round(c['support_fraction'], 4)] for c in classes}))


if __name__ == '__main__':
    run()
