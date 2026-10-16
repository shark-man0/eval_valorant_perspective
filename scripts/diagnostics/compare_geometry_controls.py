"""Evaluate separately reviewed fixed-geometry controls; never adopt a matcher."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import cv2

from scripts.diagnostics.diagnose_geometry_gradient_ncc import ALGORITHM, edge_anchors
from scripts.diagnostics.prospective_numeric_probe import verify_partition
from scripts.e2e.run_dataset_case import sha256_file
from valorant_ai_coach.hud.calibrate_temporal import _check_output_privacy
from valorant_ai_coach.hud.global_lifecycle import global_recognizer_fingerprint
from valorant_ai_coach.hud.layout import HudLayout
from valorant_ai_coach.hud.templates import HudTemplateProfile

LABELS = {'visible', 'absent', 'misaligned', 'unknown', 'unreviewed'}


def control_counts(rows: list[dict]) -> dict:
    """All three anchors are required; only explicit absence proves a negative.

    A qualitative "misaligned" label does not establish an offset beyond the
    existing layout's numerical tolerance. Keep it unscored until that separate
    quantitative evidence exists, rather than inventing an assertion boundary.
    """
    counts = {name: 0 for name in (
        'positive_accepted', 'positive_missing', 'negative_rejected',
        'negative_false_accept', 'unknown_unscored', 'unreviewed_unscored',
        'misaligned_unscored')}
    for row in rows:
        labels = row['labels']
        if (len(labels) != 3 or any(label not in LABELS for label in labels)
                or type(row['accepted']) is not bool):
            raise ValueError('three explicit geometry labels and boolean decision required')
        if all(label == 'visible' for label in labels):
            key = 'positive_accepted' if row['accepted'] else 'positive_missing'
        elif 'absent' in labels:
            key = 'negative_false_accept' if row['accepted'] else 'negative_rejected'
        else:
            key = ('unreviewed_unscored' if 'unreviewed' in labels else
                   'misaligned_unscored' if 'misaligned' in labels else 'unknown_unscored')
        counts[key] += 1
    return counts


def compare(candidate: Path, source_pool: Path, review_dir: Path, labels_path: Path,
            partition: Path, output: Path) -> dict:
    _check_output_privacy(output.resolve())
    if output.exists():
        raise FileExistsError('new private control comparison required')
    report_path = candidate / 'candidate_report.json'
    fingerprint_path = candidate / 'candidate_fingerprint.json'
    pool_path = source_pool / 'candidate_report.json'
    review_path, page = review_dir / 'review.json', review_dir / 'index.html'
    inputs = {p.resolve(): sha256_file(p) for p in (
        report_path, fingerprint_path, pool_path, review_path, page, labels_path,
        partition, Path(__file__), Path(__file__).with_name('diagnose_geometry_gradient_ncc.py'))}

    def digest(path):
        return inputs[path.resolve()]

    report, frozen, pool, review, human = [json.loads(p.read_text(encoding='utf-8'))
                                         for p in (report_path, fingerprint_path, pool_path,
                                                   review_path, labels_path)]
    if (review.get('kind') != 'blind_geometry_source_review_not_gt'
            or review.get('external_source_pool') is not True
            or review.get('model_scores_exposed') is not False
            or review.get('production_input') is not False
            or review.get('approved_ground_truth') is not False
            or review.get('candidate_report_sha256') != digest(report_path)
            or review.get('candidate_fingerprint_sha256') != digest(fingerprint_path)
            or review.get('source_inventory_sha256') != digest(pool_path)
            or review.get('partition_sha256') != digest(partition)
            or human.get('kind') != 'human_geometry_control_labels_not_identity_or_adoption'
            or human.get('review_sha256') != digest(review_path)
            or human.get('review_html_sha256') != digest(page)
            or not isinstance(human.get('trusted_reply_reference'), str)
            or not human['trusted_reply_reference'].strip()
            or human.get('production_adopted') is not False):
        raise ValueError('bound explicit human control review required')
    # This binds a declared human reply, not proof of authorship from JSON alone.
    # Authentication still requires the separate trusted conversation record.
    for name, expected in frozen.items():
        path = (candidate / name).resolve()
        if not path.is_relative_to(candidate.resolve()) or sha256_file(path) != expected:
            raise ValueError('frozen candidate changed or escaped')
        inputs[path] = expected
    layout_path = candidate / 'hud_layout.json'
    profile_path = candidate / 'hud_layout.templates.json'
    if not {'hud_layout.json', 'hud_layout.templates.json'} <= frozen.keys():
        raise ValueError('missing frozen profile/layout')
    layout, profile = HudLayout.load(layout_path), HudTemplateProfile.load(profile_path)
    names = sorted(profile.raw['anchors'])
    if (len(names) != 3 or (layout.calibration_policy or {}).get('min_detected_anchors', 3) != 3
            or any(profile.raw['anchors'][name]['threshold'] != .90 for name in names)):
        raise ValueError('unchanged three-anchor .90 profile required')
    for spec in profile.raw['anchors'].values():
        for key in ('template', 'mask'):
            asset = profile.resolve_asset(spec[key]).resolve()
            if asset not in inputs:
                raise ValueError('reference outside frozen inventory')
    end = json.loads(partition.read_text(encoding='utf-8'))['development']['end_sec_exclusive']
    verify_partition(partition, report['source_sha256'], end)
    if pool.get('source_sha256') != report['source_sha256']:
        raise ValueError('same source required')
    frames, sources = review['frames'], pool['validation_frames']
    labels = human['labels']
    if (not 1 <= len(frames) == len(sources) <= 64
            or [r['frame_number'] for r in frames] != list(range(1, len(frames) + 1))
            or set(labels) != {str(r['frame_number']) for r in frames}):
        raise ValueError('complete bounded review inventory required')
    reserved = {r['sha256'] for key in ('training_frames', 'validation_frames')
                for r in report.get(key, [])}
    images, truths, seen = [], [], {}
    for row, source in zip(frames, sources, strict=True):
        number = row['frame_number']
        truth = labels[str(number)]
        if set(truth) != set(names) or any(v not in LABELS for v in truth.values()):
            raise ValueError('explicit per-anchor labels required; no defaults')
        if (row['source_sha256'] != source['sha256'] or row['source_frame_pts']
                != source['source_frame_pts']
                or type(source['source_frame_pts']) not in (int, float)
                or not math.isfinite(source['source_frame_pts'])
                or not 0 <= source['source_frame_pts'] < end
                or source['sha256'] in reserved):
            raise ValueError('disjoint development source required')
        image_path = review_dir / f'source_{number:02d}.jpg'
        guide_path = review_dir / f'guide_{number:02d}.jpg'
        if (sha256_file(image_path) != source['sha256']
                or sha256_file(guide_path) != row['guide_sha256']):
            raise ValueError('review images changed')
        inputs[image_path.resolve()] = source['sha256']
        inputs[guide_path.resolve()] = row['guide_sha256']
        if source['sha256'] in seen and seen[source['sha256']] != truth:
            raise ValueError('conflicting labels on identical source images')
        seen[source['sha256']] = truth
        image = cv2.imread(str(image_path))
        if image is None or (image.shape[1], image.shape[0]) != layout.reference_resolution:
            raise ValueError('native review dimensions required')
        images.append(image)
        truths.append([truth[name] for name in names])
    fingerprint, recognizer = profile.fingerprint(layout_path), global_recognizer_fingerprint()
    # Match ALL reviewed images, including unknown/unreviewed ones, without labels.
    measurements = []
    for image in images:
        raw, _, _ = profile.detect_anchors(image, layout)
        gradient, _ = edge_anchors(image, layout, profile)
        measurements.append({name: layout.validate_calibration(
            image.shape[1], image.shape[0], detected_anchors=anchors,
            letterboxed=False, crop_applied=False).calibrated
            for name, anchors in (('raw', raw), ('gradient', gradient))})
    counts = {}
    for matcher in ('raw', 'gradient'):
        rows = [{'labels': truth, 'accepted': measured[matcher]}
                for truth, measured in zip(truths, measurements, strict=True)]
        unique = {source['sha256']: row for source, row in zip(sources, rows, strict=True)}
        counts[matcher] = {'frames': control_counts(rows),
                           'unique_images': control_counts(list(unique.values()))}
    if (any(sha256_file(p) != h for p, h in inputs.items())
            or fingerprint != profile.fingerprint(layout_path)
            or recognizer != global_recognizer_fingerprint()):
        raise ValueError('control comparison inputs changed')
    result = {'scope': 'declared_reviewed_geometry_controls_not_qualification',
              'algorithm': ALGORITHM, 'sample_count': len(frames),
              'unique_source_image_count': len(seen), 'counts': counts,
              'input_hashes': list(inputs.values()), 'profile_fingerprint': fingerprint,
              'recognizer_fingerprint': recognizer,
              'human_authorship_requires_external_trusted_record': True,
              'natural_negative_qualification_completed': False,
              'identity_evidence_generated': False, 'qualification_created': False,
              'production_adopted': False, 'events_generated': 0}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('candidate', 'source-pool', 'review-dir', 'labels', 'partition', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(compare(args.candidate, args.source_pool, args.review_dir,
                             args.labels, args.partition, args.output)))


if __name__ == '__main__':
    main()
