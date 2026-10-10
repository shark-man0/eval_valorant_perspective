"""Measure reviewed phase panel structures; never infer semantic absence."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import cv2
import numpy as np


def measure_structures(image, boxes):
    if image.dtype != np.uint8 or image.ndim != 3 or image.shape[2] != 3:
        raise ValueError('native uint8 BGR image required')
    if len(boxes) < 3 or len(set(tuple(b) for b in boxes)) != len(boxes):
        raise ValueError('at least three distinct reviewed structures required')
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    rows = []
    occupied = np.zeros(gray.shape, bool)
    for box in boxes:
        if (len(box) != 4 or any(type(v) is not int for v in box)
                or not 0 <= box[0] < box[2] <= image.shape[1]
                or not 0 <= box[1] < box[3] <= image.shape[0]):
            raise ValueError('native bounds required')
        x1, y1, x2, y2 = box
        if occupied[y1:y2, x1:x2].any():
            raise ValueError('independent structure bounds must not overlap')
        occupied[y1:y2, x1:x2] = True
        crop = gray[y1:y2, x1:x2]
        if min(crop.shape) < 3:
            raise ValueError('gradient context required')
        # Descriptive image statistics, with no classifier or acceptance gate.
        dx = cv2.Sobel(crop, cv2.CV_32F, 1, 0, ksize=3)[1:-1, 1:-1]
        dy = cv2.Sobel(crop, cv2.CV_32F, 0, 1, ksize=3)[1:-1, 1:-1]
        rows.append({'bounds': list(box), 'gray_std': float(crop.std()),
                     'gray_p10': float(np.percentile(crop, 10)),
                     'gray_p90': float(np.percentile(crop, 90)),
                     'mean_abs_dx': float(np.abs(dx).mean()),
                     'mean_abs_dy': float(np.abs(dy).mean())})
    return {'structures': rows, 'phase_present': None, 'phase_absent': None,
            'absence_checked': False, 'runtime_transition_authorized': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-report', type=Path, required=True)
    parser.add_argument('--source-directory', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--roi', type=int, nargs=4, action='append', required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('new output path required')
    started = time.monotonic()
    source_bytes = args.source_report.read_bytes()
    code_bytes = Path(__file__).read_bytes()
    source = json.loads(source_bytes)
    rows = []
    images = {}
    prior = None
    for index, row in enumerate(source['windows'][0]['rows'], start=1):
        path = args.source_directory / f'frame_{index:06d}.png'
        image = cv2.imread(str(path))
        if (image is None or image.shape != (1080, 1920, 3)
                or hashlib.sha256(path.read_bytes()).hexdigest() != row['frame_sha256']
                or hashlib.sha256(image.tobytes()).hexdigest() != row['source_pixel_sha256']
                or row['time_base'] != '1/15360'
                or prior is not None and row['source_pts_ticks'] - prior != 256):
            raise ValueError('source integrity or native cadence mismatch')
        images[str(path)] = row['frame_sha256']
        rows.append({'source_pts_ticks': row['source_pts_ticks'], 'pts_sec': row['pts_sec'],
                     'source_pixel_sha256': row['source_pixel_sha256'],
                     'measurements': measure_structures(image, args.roi)})
        prior = row['source_pts_ticks']
    if (args.source_report.read_bytes() != source_bytes
            or Path(__file__).read_bytes() != code_bytes
            or any(hashlib.sha256(Path(p).read_bytes()).hexdigest() != h
                   for p, h in images.items())):
        raise ValueError('terminal inputs changed')
    result = {'scope': 'exposed development structure measurements, not qualification',
              'source_video_sha256': source['source_video_sha256'],
              'source_report_sha256': hashlib.sha256(source_bytes).hexdigest(),
              'code_sha256': hashlib.sha256(code_bytes).hexdigest(),
              'native_roi_bounds': args.roi, 'native_png_sha256': images,
              'rows': rows, 'native_frames': len(rows),
              'wall_clock_sec': time.monotonic()-started,
              'qualification_created': False, 'canonical_current': None,
              'canonical_delta': None}
    args.output.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({'frames': len(rows), 'runtime_sec': result['wall_clock_sec']}))


if __name__ == '__main__':
    main()
