"""Opt-in geometry-only gradient NCC experiment; no runtime registration/adoption."""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path
from statistics import median

import cv2
import numpy as np

from scripts.diagnostics.prospective_numeric_probe import verify_partition
from scripts.e2e.run_dataset_case import sha256_file
from valorant_ai_coach.hud.calibrate_temporal import _check_output_privacy
from valorant_ai_coach.hud.global_lifecycle import global_recognizer_fingerprint
from valorant_ai_coach.hud.layout import HudLayout, NormalizedRoi
from valorant_ai_coach.hud.templates import HudTemplateProfile

ALGORITHM = {
    'name': 'diagnostic_signed_gradient_masked_ncc_v1', 'sobel_kernel': 3,
    'gradient_norm_floor': 16.0, 'mask_support_erosion_radius': 1,
    'minimum_mask_pixels': 64, 'ncc_threshold': .90, 'minimum_anchors': 3,
    'reference_selection': 'unchanged_existing_candidate',
    'negative_control': 'single_anchor_roi_blacked_per_validation_image',
}


def summarize_anchor_scores(rows, anchor_names):
    """Bounded score diagnostics, not accuracy, confidence or qualification.

    Retain repeated source entries in frame counts, but never count them as
    independent images. Controls are distinct by source AND removed anchor.
    No paths, pixels, timestamps or labels are copied to the aggregate.
    """
    names = tuple(sorted(anchor_names))
    result = {}
    for split in ('training', 'validation', 'transformed_control'):
        selected = [row for row in rows if row['split'] == split]
        unique = {}
        for row in selected:
            scores = row['gradient_scores']
            if set(scores) != set(names):
                raise ValueError('complete fixed anchor inventory required')
            for match in scores.values():
                if match is not None:
                    score = match['score']
                    if (isinstance(score, bool) or not isinstance(score, (int, float))
                            or not math.isfinite(score) or not 0 <= score <= 1):
                        raise ValueError('finite bounded diagnostic score required')
            key = (row['source_image_sha256'], row.get('removed_anchor'))
            previous = unique.get(key)
            if previous is not None and any(previous[field] != row[field] for field in (
                    'gradient_scores', 'raw_fresh_geometry', 'gradient_fresh_geometry')):
                raise ValueError('inconsistent duplicate measurement')
            unique[key] = row

        def aggregate(cases):
            combinations = Counter()
            anchors = {}
            for row in cases:
                failed = tuple(name for name in names if row['gradient_scores'][name] is None
                               or row['gradient_scores'][name]['score'] < .90)
                combinations[failed] += 1
            for name in names:
                values = [row['gradient_scores'][name]['score'] for row in cases
                          if row['gradient_scores'][name] is not None]
                anchors[name] = {
                    'accepted': sum(value >= .90 for value in values),
                    'below_threshold': sum(value < .90 for value in values),
                    'unscorable': len(cases) - len(values),
                    'score_min': min(values) if values else None,
                    'score_median': median(values) if values else None,
                    'score_max': max(values) if values else None,
                }
            return {
                'case_count': len(cases), 'anchors': anchors,
                'failed_anchor_combinations': [
                    {'anchors': list(combo), 'count': count}
                    for combo, count in sorted(combinations.items())],
                # An above-floor score alone does not establish valid geometry.
                'all_scores_accepted_but_geometry_rejected': sum(
                    not row['gradient_fresh_geometry'] and all(
                        row['gradient_scores'][name] is not None
                        and row['gradient_scores'][name]['score'] >= .90 for name in names)
                    for row in cases),
            }

        result[split] = {'frames': aggregate(selected),
                         'unique_cases': aggregate(list(unique.values()))}
    return result


def gradients(gray):
    if gray.ndim != 2 or gray.dtype != np.uint8:
        raise ValueError('native uint8 grayscale required')
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    norm = np.maximum(np.hypot(gx, gy), ALGORITHM['gradient_norm_floor'])
    return np.stack((gx / norm, gy / norm), axis=-1).astype(np.float32)


def gradient_match(search, reference, mask):
    """NCC on signed local directions, not a calibrated confidence score.

    Erode support so every 3x3 derivative dependency stays inside the original
    geometry mask. Excluded digit/icon pixels cannot enter through convolution.
    Constant/insufficient support abstains; undefined scores never become1.
    """
    if (mask.shape != reference.shape or mask.dtype != np.uint8
            or reference.ndim != 2 or search.ndim != 2
            or reference.dtype != np.uint8 or search.dtype != np.uint8
            or any(a > b for a, b in zip(reference.shape, search.shape, strict=True))):
        raise ValueError('compatible grayscale search/reference and uint8 mask required')
    support = cv2.erode((mask > 0).astype(np.uint8), np.ones((3, 3), np.uint8),
                        borderType=cv2.BORDER_CONSTANT, borderValue=0)
    population = int(np.count_nonzero(support))
    if population < ALGORITHM['minimum_mask_pixels']:
        return None
    template = gradients(reference)
    selected = template[support > 0]
    # NCC centers each feature channel independently.
    if float(np.sum(np.var(selected, axis=0))) < 1e-8:
        return None
    values = cv2.matchTemplate(gradients(search), template, cv2.TM_CCOEFF_NORMED,
                               mask=support)
    values = np.where(np.isfinite(values), values, -1.0)
    _, score, _, location = cv2.minMaxLoc(values)
    return {'score': max(0., min(1., float(score))), 'location': location,
            'mask_population': population}


def edge_anchors(image, layout, profile):
    detected, scores = {}, {}
    height, width = image.shape[:2]
    for name, spec in profile.raw['anchors'].items():
        reference = profile.load_template(name, spec['template'], spec['threshold']).image
        if reference.ndim == 3:
            reference = cv2.cvtColor(reference, cv2.COLOR_BGR2GRAY)
        mask = cv2.imread(str(profile.resolve_asset(spec['mask'])), cv2.IMREAD_GRAYSCALE)
        if mask is None or spec['threshold'] != .90:
            raise ValueError('existing masked .90 geometry references required')
        x1, y1, x2, y2 = profile._search_region(spec['search_region'], layout, width, height)
        search = cv2.cvtColor(image[y1:y2, x1:x2], cv2.COLOR_BGR2GRAY)
        match = gradient_match(search, reference, mask)
        scores[name] = match
        if match is not None and match['score'] >= .90:
            left, top = match['location']
            detected[name] = NormalizedRoi((x1 + left) / width, (y1 + top) / height,
                                          reference.shape[1] / width, reference.shape[0] / height)
    return detected, scores


def run(candidate: Path, partition_path: Path, output: Path):
    _check_output_privacy(output.resolve())
    if output.exists():
        raise FileExistsError('new private gradient experiment required')
    report_path = candidate / 'candidate_report.json'
    report = json.loads(report_path.read_text(encoding='utf-8'))
    if (report.get('candidate_assets_frozen_before_validation') is not True
            or report.get('production_adopted') is not False
            or report.get('identity_assets_generated') is not False):
        raise ValueError('frozen unadopted geometry candidate required')
    partition = json.loads(partition_path.read_text(encoding='utf-8'))
    end = partition['development']['end_sec_exclusive']
    verify_partition(partition_path, report['source_sha256'], end)
    layout_path = candidate / 'hud_layout.json'
    layout = HudLayout.load(layout_path)
    profile_path = layout_path.with_suffix('.templates.json')
    profile = HudTemplateProfile.load(profile_path)
    for name, spec in profile.raw['anchors'].items():
        for field, expected in (('template', 'template_sha256'), ('mask', 'mask_sha256')):
            if sha256_file(profile.resolve_asset(spec[field])) != report['anchors'][name][expected]:
                raise ValueError('reference differs from frozen geometry candidate')
    if (layout.calibration_policy or {}).get('min_detected_anchors', 3) != 3:
        raise ValueError('unchanged three-anchor calibration required')
    fingerprint = profile.fingerprint(layout_path)
    recognizer = global_recognizer_fingerprint()
    inputs = {p.resolve(): sha256_file(p) for p in (
        report_path, partition_path, layout_path, profile_path, Path(__file__))}
    inventory, seen = [], set()
    training_hashes = {row['sha256'] for row in report['training_frames']}
    for split in ('training', 'validation'):
        sources = report[f'{split}_frames']
        paths = sorted((candidate / f'{split}_frames').glob('*.jpg'))
        if not 3 <= len(sources) == len(paths) <= 128:
            raise ValueError('bounded complete source inventory required')
        for source, path in zip(sources, paths, strict=True):
            digest = sha256_file(path)
            if (digest != source['sha256'] or split == 'validation' and digest in training_hashes
                    or not 0 <= source['source_frame_pts'] < end):
                raise ValueError('source-bound development images and disjoint splits required')
            seen.add(digest)
            inputs[path.resolve()] = digest
            inventory.append((split, path, digest))
    output.mkdir(parents=True)
    frozen = {'algorithm': ALGORITHM, 'profile_fingerprint': fingerprint,
              'recognizer_fingerprint': recognizer,
              'source_video_sha256': report['source_sha256'],
              'inputs_sha256': {str(p): h for p, h in inputs.items()},
              'source_frame_count': len(inventory), 'unique_source_image_count': len(seen),
              'production_adopted': False, 'qualification_created': False}
    plan = output / 'frozen_experiment.json'
    plan.write_text(json.dumps(frozen, indent=2) + '\n', encoding='utf-8')
    plan_hash = sha256_file(plan)
    rows = []

    def measure(image):
        old, _, _ = profile.detect_anchors(image, layout)
        new, scores = edge_anchors(image, layout, profile)
        return {
            'raw_fresh_geometry': layout.validate_calibration(
                image.shape[1], image.shape[0], detected_anchors=old,
                letterboxed=False, crop_applied=False).calibrated,
            'gradient_fresh_geometry': layout.validate_calibration(
                image.shape[1], image.shape[0], detected_anchors=new,
                letterboxed=False, crop_applied=False).calibrated,
            'gradient_scores': scores,
        }

    for split, path, digest in inventory:
        image = cv2.imread(str(path))
        if image is None or (image.shape[1], image.shape[0]) != layout.reference_resolution:
            raise ValueError('native source image dimensions required')
        rows.append({'split': split, 'source_image_sha256': digest, **measure(image)})
        if split == 'validation':
            for name in profile.raw['anchors']:
                altered = image.copy()
                x1, y1, x2, y2 = layout.normalized_roi(name).pixel_bounds(
                    image.shape[1], image.shape[0])
                altered[y1:y2, x1:x2] = 0
                rows.append({'split': 'transformed_control', 'removed_anchor': name,
                             'source_image_sha256': digest, **measure(altered)})
    if (profile.fingerprint(layout_path) != fingerprint or sha256_file(plan) != plan_hash
            or global_recognizer_fingerprint() != recognizer
            or any(sha256_file(p) != h for p, h in inputs.items())):
        raise ValueError('experiment inputs changed')
    result = {'scope': 'exposed_development_geometry_comparison_not_qualification',
              'frozen_experiment_sha256': plan_hash, 'rows': rows,
              'anchor_diagnostics': summarize_anchor_scores(rows, profile.raw['anchors']),
              'summary': {split: {key: sum(row['split'] == split and row[key] for row in rows)
                                  for key in ('raw_fresh_geometry', 'gradient_fresh_geometry')}
                          for split in ('training', 'validation', 'transformed_control')},
              'unique_case_summary': {split: {
                  key: sum(row[key] for row in {
                      (r['source_image_sha256'], r.get('removed_anchor')): r
                      for r in rows if r['split'] == split}.values())
                  for key in ('raw_fresh_geometry', 'gradient_fresh_geometry')}
                  for split in ('training', 'validation', 'transformed_control')},
              'transformed_controls_completed': True,
              'natural_negative_qualification_completed': False, 'production_registered': False,
              'identity_evidence_generated': False, 'qualification_created': False,
              'events_generated': 0}
    (output / 'measurement.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    return result['summary']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('candidate', 'partition', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.candidate, args.partition, args.output)))


if __name__ == '__main__':
    main()
