"""Localize native image changes without granting UI/continuity evidence.

Use already-exposed saved source pixels. Timer exclusion and reviewed background
boxes are explicit image inputs; no validation labels, clock values or GT enter
the measurements. Undefined NCC remains unavailable, including blank phase crops.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np

from valorant_ai_coach.hud.scene_domains import _ncc
from valorant_ai_coach.hud.scene_source_binding import SceneSourceBinding


def measure_pair(previous, current, *, phase_box, timer_box, background_boxes):
    if (
        previous.shape != current.shape or previous.dtype != np.uint8
        or current.dtype != np.uint8 or previous.ndim != 3 or previous.shape[2] != 3
    ):
        raise ValueError('equal native uint8 BGR images required')
    height, width = previous.shape[:2]
    for box in (phase_box, timer_box, *background_boxes):
        if (
            len(box) != 4 or any(type(v) is not int for v in box)
            or not 0 <= box[0] < box[2] <= width or not 0 <= box[1] < box[3] <= height
        ):
            raise ValueError('native pixel bounds required')
    delta = cv2.absdiff(previous, current).max(axis=2)
    included = np.ones((height, width), dtype=bool)
    x1, y1, x2, y2 = timer_box
    included[y1:y2, x1:x2] = False
    phase = np.zeros_like(included)
    x1, y1, x2, y2 = phase_box
    phase[y1:y2, x1:x2] = True
    if np.any(phase & ~included):
        raise ValueError('phase and timer measurement bounds must be disjoint')
    outside = included & ~phase
    # The value eight is a descriptive change-size bin, not an acceptance gate.
    changed = np.asarray((delta >= 8) & included, dtype=np.uint8)
    count, _, stats, _ = cv2.connectedComponentsWithStats(changed, connectivity=8)
    components = sorted(stats[1:count].tolist(), key=lambda row: row[4], reverse=True)[:5]
    gray_a = cv2.cvtColor(previous, cv2.COLOR_BGR2GRAY)
    gray_b = cv2.cvtColor(current, cv2.COLOR_BGR2GRAY)
    backgrounds = []
    for box in background_boxes:
        x1, y1, x2, y2 = box
        if np.any(~outside[y1:y2, x1:x2]):
            raise ValueError('background measurements must exclude timer and phase')
        a, b = gray_a[y1:y2, x1:x2], gray_b[y1:y2, x1:x2]
        backgrounds.append({
            'bounds': list(box), 'previous_std': float(a.std()), 'current_std': float(b.std()),
            'unwarped_ncc': _ncc(a, b),
            'mean_max_channel_absdiff': float(delta[y1:y2, x1:x2].mean()),
        })
    return {
        'phase_bounds': list(phase_box), 'timer_excluded_bounds': list(timer_box),
        'changed_bin_lower_bound': 8,
        'changed_pixels_inside_phase': int(np.count_nonzero(changed & phase)),
        'changed_pixels_outside_phase_and_timer': int(np.count_nonzero(changed & outside)),
        'outside_mean_max_channel_absdiff': float(delta[outside].mean()),
        'outside_gray_ncc': _ncc(gray_a[outside], gray_b[outside]),
        'phase_current_std': float(gray_b[phase].std()),
        'phase_gray_ncc': _ncc(gray_a[phase], gray_b[phase]),
        'largest_change_components_xywh_area': components,
        'reviewed_background_measurements': backgrounds,
        'phase_absence_authorized': False, 'runtime_continuity_authorized': False,
        'qualification_created': False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-report', type=Path, required=True)
    parser.add_argument('--source-directory', type=Path, required=True)
    parser.add_argument('--scene-profile', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--phase-box', type=int, nargs=4, required=True)
    parser.add_argument('--timer-box', type=int, nargs=4, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('refuse to overwrite evidence')
    source_bytes = args.source_report.read_bytes()
    source = json.loads(source_bytes)
    binding = SceneSourceBinding.load(args.scene_profile)
    profile = json.loads(args.scene_profile.read_bytes())
    if len(profile['references']) != 1:
        raise ValueError('one explicit reviewed-domain source required for this audit')
    boxes = [tuple(v * 3 for v in box)
             for box in profile['references'][0]['world_boxes_640x360']]
    dependencies = [Path(__file__), Path('src/valorant_ai_coach/hud/scene_domains.py'),
                    Path('src/valorant_ai_coach/hud/scene_source_binding.py')]
    hashes = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in dependencies}
    rows = []
    previous = None
    previous_tick = None
    images = {}
    for index, row in enumerate(source['windows'][0]['rows'], start=1):
        path = args.source_directory / f'frame_{index:06d}.png'
        content = path.read_bytes()
        image = cv2.imread(str(path))
        if (
            hashlib.sha256(content).hexdigest() != row['frame_sha256']
            or image is None or image.shape != (1080, 1920, 3)
            or hashlib.sha256(image.tobytes()).hexdigest() != row['source_pixel_sha256']
            or previous_tick is not None and row['source_pts_ticks'] - previous_tick != 256
            or row['time_base'] != '1/15360'
        ):
            raise ValueError('saved native source binding/coverage mismatch')
        images[str(path)] = row['frame_sha256']
        if previous is not None:
            rows.append({
                'previous_source_pts_ticks': previous_tick,
                'source_pts_ticks': row['source_pts_ticks'],
                'source_pts_sec': row['pts_sec'],
                'measurements': measure_pair(previous, image, phase_box=args.phase_box,
                                            timer_box=args.timer_box, background_boxes=boxes),
            })
        previous, previous_tick = image, row['source_pts_ticks']
    binding.verify()
    if args.source_report.read_bytes() != source_bytes or any(
        hashlib.sha256(Path(p).read_bytes()).hexdigest() != h
        for p, h in {**hashes, **images}.items()
    ):
        raise ValueError('terminal audit inputs changed')
    result = {
        'scope': 'previously exposed source images; localization only, not qualification',
        'source_video_sha256': source['source_video_sha256'],
        'source_report_sha256': hashlib.sha256(source_bytes).hexdigest(),
        'source_profile_sha256': binding.profile_sha256,
        'code_sha256': hashes, 'native_png_sha256': images, 'rows': rows,
        'qualification_created': False, 'runtime_behavior_changed': False,
    }
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'native_images': len(images), 'measured_pairs': len(rows),
                      'report': str(args.output)}))


if __name__ == '__main__':
    main()
