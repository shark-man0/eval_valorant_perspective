"""Screen bound development scene measurements before independent validation.

This diagnostic gate cannot qualify a world mask, continuity, UI or runtime.
It never improves a rejected source proposal or edits profile geometry.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from pathlib import Path

import cv2
import numpy as np

from scripts.diagnostics.validate_native_scene_entrance import verify_files
from valorant_ai_coach.hud.global_lifecycle import global_recognizer_fingerprint
from valorant_ai_coach.hud.scene_domains import _validate
from valorant_ai_coach.hud.scene_source_binding import SceneSourceBinding


def projected_exclusion(box, model):
    _validate(np.zeros((360, 640), np.uint8), [box])
    matrix = np.asarray(model, float)
    if matrix.shape != (2, 3) or not np.isfinite(matrix).all():
        raise ValueError('finite affine projection required')
    x1, y1, x2, y2 = box
    yy, xx = np.mgrid[y1:y2, x1:x2]
    mx = (matrix[0, 0]*xx + matrix[0, 1]*yy + matrix[0, 2]).astype(np.float32)
    my = (matrix[1, 0]*xx + matrix[1, 1]*yy + matrix[1, 2]).astype(np.float32)
    allowed = np.ones((360, 640), np.float32)
    allowed[:28] = 0
    allowed[28:120, 224:416] = 0
    valid = cv2.remap(allowed, mx, my, cv2.INTER_LINEAR)
    return {'source_box_640x360': list(box), 'source_pixels': int(valid.size),
            'projected_pixels_touching_exclusion_or_image_boundary':
                int(np.count_nonzero(valid != 1))}


def training_support(rows, reference_pixels):
    seen_pixels, seen_ticks = set(), set()
    nonself_matches, self_matches, links = set(), set(), 0
    first_stop = None
    previous_tick = None
    for row in rows:
        pixel, tick = row['source_pixel_sha256'], row['source_pts_ticks']
        if (not isinstance(pixel, str) or re.fullmatch(r'[0-9a-f]{64}', pixel) is None
                or type(tick) is not int or pixel in seen_pixels or tick in seen_ticks):
            raise ValueError('distinct native source pixels and ticks required')
        if previous_tick is not None and tick-previous_tick != 256:
            raise ValueError('complete native training cadence required')
        previous_tick = tick
        seen_pixels.add(pixel)
        seen_ticks.add(tick)
        proposal, observed = row['proposal'], row['observed']
        if type(proposal['diagnostic_initialization_proposed']) is not bool:
            raise ValueError('explicit diagnostic proposal boolean required')
        if proposal['diagnostic_initialization_proposed']:
            (self_matches if pixel in reference_pixels else nonself_matches).add(pixel)
        link = observed['descriptive_scene_link']
        if type(link) is not bool or observed['runtime_proof_authorized'] is not False:
            raise ValueError('descriptive scene measurements only')
        if first_stop is not None and link:
            raise ValueError('terminated episode cannot rejoin')
        links += int(link)
        if observed['reason'] not in {
            'image_supported_observed_seed', 'image_supported_initialization_pending',
            'descriptive_observed_scene_link',
        } and first_stop is None:
            first_stop = {'source_pts_ticks': tick, 'reason': observed['reason']}
    # Reference-self comparison cannot count as independent training support.
    ready = len(nonself_matches) >= 3 and links >= 3
    return {'source_frames': len(rows), 'reference_self_matches': len(self_matches),
            'distinct_nonself_initialization_matches': len(nonself_matches),
            'observed_scene_links': links, 'first_episode_stop': first_stop,
            'appearance_training_minimum_met': ready,
            'minimum_nonself_training_matches': 3, 'minimum_observed_scene_links': 3,
            'qualification_created': False, 'runtime_authorized': False,
            'current_world_semantics_qualified': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--training-report', type=Path, required=True)
    parser.add_argument('--source-cohort', type=Path, required=True)
    parser.add_argument('--profile', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('new gate report required')
    started = time.monotonic()
    training_bytes = args.training_report.read_bytes()
    cohort_bytes = args.source_cohort.read_bytes()
    code_bindings = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in (
        Path(__file__), Path('scripts/diagnostics/validate_native_scene_entrance.py'),
    )}
    training, cohort = json.loads(training_bytes), json.loads(cohort_bytes)
    binding = SceneSourceBinding.load(args.profile)
    profile = json.loads(args.profile.read_bytes())
    declaration = training['declaration']
    if (declaration['source_report_sha256'] != hashlib.sha256(cohort_bytes).hexdigest()
            or declaration['source_profile_sha256'] != binding.profile_sha256
            or declaration['recognizer_fingerprint'] != global_recognizer_fingerprint()):
        raise ValueError('stale source/profile/code development evidence')
    actual = cohort['windows'][0]['rows']
    if len(actual) != len(training['rows']):
        raise ValueError('complete source development sequence required')
    if not actual or len({row['source_epoch'] for row in actual}) != 1 or any(
        row['source_time_base'] != '1/15360' for row in actual
    ):
        raise ValueError('single native source epoch and time base required')
    for saved, measured in zip(actual, training['rows'], strict=True):
        if any(saved[key] != measured[key] for key in ('source_pts_ticks', 'source_pixel_sha256')):
            raise ValueError('source measurement provenance mismatch')
        if measured['proposal']['profile_sha256'] != binding.profile_sha256:
            raise ValueError('proposal belongs to another profile')
    verify_files(cohort['native_png_sha256'])
    verify_files(code_bindings)
    reference_pixels = {r['source_pixel_sha256'] for r in profile['references']}
    summary = training_support(training['rows'], reference_pixels)
    boxes = {r['id']: r['world_boxes_640x360'] for r in profile['references']}
    projection_rows = []
    for row in training['rows']:
        for proposal in row['proposal']['proposals']:
            model = proposal['reference_to_current_affine']
            if model is not None:
                projection_rows.append({'source_pts_ticks': row['source_pts_ticks'],
                                        'reference_id': proposal['reference_id'],
                                        'regions': [projected_exclusion(box, model)
                                                    for box in boxes[proposal['reference_id']]]})
    binding.verify()
    if (args.training_report.read_bytes() != training_bytes
            or args.source_cohort.read_bytes() != cohort_bytes
            or declaration['recognizer_fingerprint'] != global_recognizer_fingerprint()):
        raise ValueError('terminal gate inputs changed')
    verify_files(cohort['native_png_sha256'])
    verify_files(code_bindings)
    result = {'scope': 'diagnostic appearance training screen, never qualification',
              'training_report_sha256': hashlib.sha256(training_bytes).hexdigest(),
              'source_cohort_sha256': hashlib.sha256(cohort_bytes).hexdigest(),
              'source_profile_sha256': binding.profile_sha256, 'summary': summary,
              'code_sha256': code_bindings,
              'projected_exclusion_diagnostics': projection_rows,
              'wall_clock_sec': time.monotonic()-started,
              'canonical_current': None, 'canonical_delta': None}
    args.output.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(summary))
    # Distinguish a completed rejection from a successful development screen.
    raise SystemExit(0 if summary['appearance_training_minimum_met'] else 2)


if __name__ == '__main__':
    main()
