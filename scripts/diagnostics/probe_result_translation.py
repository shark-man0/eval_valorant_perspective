"""Frozen shared-translation feasibility; no threshold, template or runtime change.

Every semantic group uses the SAME candidate translation inside the existing
layout ROI. Group-specific maxima cannot corroborate each other. Final scoring
uses the original fixed-position matcher, including its contrast floor.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import cv2
import numpy as np

from valorant_ai_coach.hud.global_lifecycle import global_recognizer_fingerprint
from valorant_ai_coach.hud.layout import HudLayout
from valorant_ai_coach.hud.semantic_text import SemanticTextReference
from valorant_ai_coach.hud.templates import HudTemplateProfile


def locate(reference: SemanticTextReference, image: np.ndarray) -> dict:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    height, width = reference.reference.shape
    if gray.dtype != np.uint8 or gray.ndim != 2 or (
        gray.shape[0] < height or gray.shape[1] < width
    ):
        raise ValueError('uint8 source ROI must contain the complete reference')
    maps = []
    floating = gray.astype(np.float32)
    for mask in reference.masks:
        scores = cv2.matchTemplate(gray, reference.reference, cv2.TM_CCOEFF_NORMED, mask=mask)
        binary = (mask > 0).astype(np.float32)
        count = float(binary.sum())
        means = cv2.matchTemplate(floating, binary, cv2.TM_CCORR) / count
        squares = cv2.matchTemplate(floating * floating, binary, cv2.TM_CCORR) / count
        contrast = np.sqrt(np.maximum(0, squares - means * means))
        scores = np.clip(np.nan_to_num(scores, nan=0, posinf=0, neginf=0), 0, 1)
        scores[contrast < 5] = 0
        maps.append(scores)
    shared = np.min(np.stack(maps), axis=0)
    y, x = np.unravel_index(int(np.argmax(shared)), shared.shape)
    x, y = int(x), int(y)
    # The accelerated maps only select a common candidate. They never replace
    # the established direct float64 NCC/support/contrast acceptance function.
    measured = reference.measure(gray[y:y + height, x:x + width])
    return {
        'shared_xy': [x, y], 'score': measured['score'],
        'accepted': measured['presence'] is True, 'groups': measured['groups'],
        'per_group_independent_maxima_diagnostic_only': [float(m.max()) for m in maps],
        'search_candidate_count': int(shared.size), 'threshold': reference.threshold,
        'runtime_transition_authorized': False,
    }


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--layout', type=Path, required=True)
    parser.add_argument('--templates', type=Path, required=True)
    parser.add_argument('--source-report', type=Path, required=True)
    parser.add_argument('--archive-directory', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('new output required')
    initial = {path: path.read_bytes() for path in
               (args.layout, args.templates, args.source_report, Path(__file__))}
    layout = HudLayout.load(args.layout)
    profile = HudTemplateProfile.load(args.templates)
    fingerprint = profile.fingerprint(args.layout)
    code = global_recognizer_fingerprint()
    reference = profile._semantic_text['round_end_template']
    roi = layout.normalized_roi(profile.raw['signals']['round_end_template']['roi'])
    spec = profile.raw['signals']['round_end_template']
    source = json.loads(initial[args.source_report])
    results = []
    paths = []
    started = time.perf_counter()
    for index, row in enumerate(source['rows'], 1):
        path = args.archive_directory / f'frame_{index:02d}.png'
        if digest(path) != row['frame_sha256']:
            raise ValueError('source encoded hash mismatch')
        image = cv2.imread(str(path))
        if (image is None or
                hashlib.sha256(image.tobytes()).hexdigest() != row['source_pixel_sha256']):
            raise ValueError('source pixel hash mismatch')
        left, top, right, bottom = roi.pixel_bounds(image.shape[1], image.shape[0])
        crop = image[top:bottom, left:right]
        x1, y1, x2, y2 = spec['roi_bounds']
        # Existing profile uses normalized left/top/right/bottom coordinates.
        a, b, c, d = round(x1 * crop.shape[1]), round(y1 * crop.shape[0]), (
            round(x2 * crop.shape[1])), round(y2 * crop.shape[0])
        fixed = reference.measure(crop[b:d, a:c])
        translated = locate(reference, crop)
        results.append({'pts_sec': row['pts_sec'], 'source_pts_ticks': row['source_pts_ticks'],
                        'frame_sha256': row['frame_sha256'],
                        'source_pixel_sha256': row['source_pixel_sha256'],
                        'fixed_score': fixed['score'], 'fixed_accepted': fixed['presence'] is True,
                        'translation': translated})
        paths.append((path, row['frame_sha256']))
    if (profile.fingerprint(args.layout) != fingerprint
            or global_recognizer_fingerprint() != code
            or any(path.read_bytes() != content for path, content in initial.items())
            or any(digest(path) != expected for path, expected in paths)):
        raise ValueError('terminal source/profile/code binding changed')
    result = {
        'scope': __doc__, 'source_video_sha256': source['source_video_sha256'],
        'profile_fingerprint': fingerprint,
        'recognizer_fingerprint': code,
        'input_sha256': {str(path): hashlib.sha256(content).hexdigest()
                         for path, content in initial.items()},
        'shared_translation_only': True, 'scale_rotation_search': False,
        'processed_frames': len(results), 'rows': results,
        'comparison': {'accepted_result_frames': {
            'previous': sum(r['fixed_accepted'] for r in results),
            'current': sum(r['translation']['accepted'] for r in results),
            'scope': 'Fixed vs shared-translation diagnostic; not boundary or PASS count.',
        }},
        'wall_clock_sec': time.perf_counter() - started,
        'previous_comparable_runtime': None, 'runtime_delta': None,
        'qualification_created': False, 'released_events': 0,
        'canonical_current': None, 'canonical_delta': None,
    }
    counts = result['comparison']['accepted_result_frames']
    counts['delta'] = counts['current'] - counts['previous']
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'frames': result['processed_frames'], 'acceptance': counts,
                      'wall_clock_sec': result['wall_clock_sec']}))


if __name__ == '__main__':
    main()
