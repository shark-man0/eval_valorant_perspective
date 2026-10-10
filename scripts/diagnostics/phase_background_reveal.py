"""Current-image background extrapolation diagnostics; no absence authorization."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import cv2
import numpy as np


def _samples(image, boxes):
    samples = []
    occupied = np.zeros(image.shape[:2], bool)
    for box in boxes:
        if (len(box) != 4 or any(type(v) is not int for v in box)
                or not 0 <= box[0] < box[2] <= image.shape[1]
                or not 0 <= box[1] < box[3] <= image.shape[0]):
            raise ValueError('native bounds required')
        x1, y1, x2, y2 = box
        if occupied[y1:y2, x1:x2].any():
            raise ValueError('independent regions required')
        occupied[y1:y2, x1:x2] = True
        yy, xx = np.mgrid[y1:y2, x1:x2]
        design = np.column_stack((np.ones(xx.size), xx.ravel()/image.shape[1],
                                  yy.ravel()/image.shape[0]))
        samples.append((design, image[y1:y2, x1:x2].reshape(-1, 3).astype(float)))
    return samples, occupied


def _residual(design, pixels, coefficients):
    error = np.abs(pixels - design @ coefficients).max(axis=1)
    return {'mean_max_channel_residual': float(error.mean()),
            'p90_max_channel_residual': float(np.percentile(error, 90)),
            'maximum_channel_residual': float(error.max())}


def measure_reveal(image, context_boxes, target_boxes):
    if image.dtype != np.uint8 or image.ndim != 3 or image.shape[2] != 3:
        raise ValueError('uint8 native BGR image required')
    if len(context_boxes) < 3 or len(target_boxes) < 3:
        raise ValueError('multiple independent context and target structures required')
    contexts, context_mask = _samples(image, context_boxes)
    targets, target_mask = _samples(image, target_boxes)
    if np.any(context_mask & target_mask):
        raise ValueError('target pixels cannot fit their own background')
    design = np.concatenate([row[0] for row in contexts])
    pixels = np.concatenate([row[1] for row in contexts])
    coefficients, _, rank, _ = np.linalg.lstsq(design, pixels, rcond=None)
    if rank != 3:
        raise ValueError('background plane unavailable')
    held_out = []
    for index, (x, y) in enumerate(contexts):
        other = [row for j, row in enumerate(contexts) if j != index]
        c, _, r, _ = np.linalg.lstsq(np.concatenate([row[0] for row in other]),
                                    np.concatenate([row[1] for row in other]), rcond=None)
        held_out.append({'bounds': list(context_boxes[index]), 'rank': int(r),
                         'residual': _residual(x, y, c) if r == 3 else None})
    return {'model': 'descriptive current-image BGR affine plane',
            'coefficients': coefficients.tolist(), 'context_leave_one_region_out': held_out,
            'targets': [{'bounds': list(box), **_residual(x, y, coefficients)}
                        for box, (x, y) in zip(target_boxes, targets, strict=True)],
            'phase_absent': None, 'runtime_authorized': False,
            'scene_continuity_proven': False, 'qualification_created': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-report', type=Path, required=True)
    parser.add_argument('--source-directory', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--context-roi', type=int, nargs=4, action='append', required=True)
    parser.add_argument('--target-roi', type=int, nargs=4, action='append', required=True)
    parser.add_argument('--panel-roi', type=int, nargs=4, required=True)
    parser.add_argument('--text-roi', type=int, nargs=4, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('new output required')
    started = time.monotonic()
    source_bytes, code_bytes = args.source_report.read_bytes(), Path(__file__).read_bytes()
    source = json.loads(source_bytes)
    rows, controls, images = [], [], {}
    prior = None
    for index, row in enumerate(source['windows'][0]['rows'], start=1):
        path = args.source_directory / f'frame_{index:06d}.png'
        image = cv2.imread(str(path))
        if (image is None or image.shape != (1080, 1920, 3)
                or hashlib.sha256(path.read_bytes()).hexdigest() != row['frame_sha256']
                or hashlib.sha256(image.tobytes()).hexdigest() != row['source_pixel_sha256']
                or row['time_base'] != '1/15360'
                or prior is not None and row['source_pts_ticks'] - prior != 256):
            raise ValueError('native source binding mismatch')
        measured = measure_reveal(image, args.context_roi, args.target_roi)
        rows.append({'source_pts_ticks': row['source_pts_ticks'], 'pts_sec': row['pts_sec'],
                     'source_pixel_sha256': row['source_pixel_sha256'], 'measurement': measured})
        images[str(path)] = row['frame_sha256']
        prior = row['source_pts_ticks']
        # First exposed frame only: artificial sensitivity controls, never holdout labels.
        if index == 1:
            _samples(image, [args.panel_roi])
            _samples(image, [args.text_roi])
            context_pixels = np.concatenate([y for _, y in _samples(image, args.context_roi)[0]])
            fill = np.median(context_pixels, axis=0).astype(np.uint8)
            for name, box, value in [('black_panel', args.panel_roi, 0),
                                     ('white_panel', args.panel_roi, 255),
                                     ('context_color_panel', args.panel_roi, fill),
                                     ('context_color_text_only', args.text_roi, fill)]:
                modified = image.copy()
                x1, y1, x2, y2 = box
                modified[y1:y2, x1:x2] = value
                controls.append({'kind': name, 'role': 'synthetic sensitivity only',
                                 'parent_source_pixel_sha256': row['source_pixel_sha256'],
                                 'modified_pixel_sha256': hashlib.sha256(
                                     modified.tobytes()).hexdigest(),
                                 'measurement': measure_reveal(modified, args.context_roi,
                                                               args.target_roi)})
    if (args.source_report.read_bytes() != source_bytes
            or Path(__file__).read_bytes() != code_bytes
            or any(hashlib.sha256(Path(p).read_bytes()).hexdigest() != h
                   for p, h in images.items())):
        raise ValueError('terminal inputs changed')
    result = {'scope': 'exposed background reveal/synthetic sensitivity, not qualification',
              'source_video_sha256': source['source_video_sha256'],
              'source_report_sha256': hashlib.sha256(source_bytes).hexdigest(),
              'code_sha256': hashlib.sha256(code_bytes).hexdigest(),
              'context_boxes': args.context_roi, 'target_boxes': args.target_roi,
              'panel_box': args.panel_roi, 'text_box': args.text_roi,
              'native_png_sha256': images, 'rows': rows, 'synthetic_controls': controls,
              'wall_clock_sec': time.monotonic()-started, 'qualification_created': False,
              'canonical_current': None, 'canonical_delta': None}
    args.output.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({'native_frames': len(rows), 'controls': len(controls),
                      'runtime_sec': result['wall_clock_sec']}))


if __name__ == '__main__':
    main()
