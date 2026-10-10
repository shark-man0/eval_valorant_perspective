"""Measure fixed native adjacent regions without classifying source continuity."""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from fractions import Fraction
from pathlib import Path

import cv2
import numpy as np


def measure_regions(previous, current, regions):
    if (previous.shape != (1080, 1920, 3) or current.shape != previous.shape
            or previous.dtype != np.uint8 or current.dtype != np.uint8):
        raise ValueError('native uint8 BGR images required')
    results = []
    for role, boxes in regions.items():
        for box in boxes:
            if (len(box) != 4 or any(type(v) is not int for v in box)
                    or not 0 <= box[0] < box[2] <= 1920
                    or not 0 <= box[1] < box[3] <= 1080):
                raise ValueError('native region bounds required')
            x1, y1, x2, y2 = box
            # Never read phase/timer pixels, including for normalization.
            for a, b, c, d in ((738, 135, 1183, 281), (860, 20, 1060, 90)):
                if x1 < c and a < x2 and y1 < d and b < y2:
                    raise ValueError('phase/timer exclusion required')
            left, right = previous[y1:y2, x1:x2], current[y1:y2, x1:x2]
            gray = [cv2.cvtColor(p, cv2.COLOR_BGR2GRAY) for p in (left, right)]
            contrast = [float(p.std()) for p in gray]
            delta = np.max(np.abs(left.astype(np.int16)-right.astype(np.int16)), axis=2)
            ncc = (float(cv2.matchTemplate(*gray, cv2.TM_CCOEFF_NORMED)[0, 0])
                   if min(contrast) >= 1 else None)
            results.append({'role': role, 'box': box, 'gray_std': contrast,
                            'scene_ncc': ncc,
                            'masked_reference_ncc': ncc if min(contrast) >= 5 else None,
                            'mean_max_channel_absdiff': float(delta.mean()),
                            'fraction_changed_ge_8': float(np.mean(delta >= 8))})
    return {'regions': results, 'runtime_authorized': False,
            'source_continuity': None, 'foreground_membership_qualified': False}


def audit(declaration):
    def verify():
        for path, digest in declaration['file_sha256'].items():
            if hashlib.sha256(Path(path).read_bytes()).hexdigest() != digest:
                raise ValueError('frozen dependency changed')
    verify()
    source = json.loads(Path(declaration['source_report']).read_bytes())
    rows = source['windows'][0]['rows']
    paths = {int(Path(p).stem.removeprefix('frame_')): Path(p)
             for p in source['native_png_sha256']}
    previous, prior = None, None
    measurements = []
    for row in rows:
        tick = row['source_pts_ticks']
        path = paths[tick]
        if str(path) not in declaration['file_sha256']:
            raise ValueError('every native image must be frozen')
        image = cv2.imread(str(path))
        if (image is None or hashlib.sha256(image.tobytes()).hexdigest()
                != row['source_pixel_sha256']):
            raise ValueError('native pixel binding mismatch')
        if row['source_video_sha256'] != source['source_video_sha256']:
            raise ValueError('source video binding mismatch')
        if float(tick*Fraction(row['source_time_base'])) != row['source_pts_sec']:
            raise ValueError('source timestamp mismatch')
        if prior is not None:
            if (tick-prior['source_pts_ticks'] != declaration['native_step_ticks']
                    or row['source_epoch'] != prior['source_epoch']
                    or row['source_time_base'] != prior['source_time_base']):
                raise ValueError('one complete native epoch required')
            measurements.append({
                'previous_pts_ticks': prior['source_pts_ticks'], 'source': row,
                'appearance': measure_regions(previous, image, declaration['regions'])})
        previous, prior = image, row
    verify()
    return {'scope': 'exposed adjacent appearance; fixed regions are not semantic masks',
            'source_video_sha256': source['source_video_sha256'], 'native_frames': len(rows),
            'rows': measurements, 'qualification_created': False, 'runtime_behavior_changed': False,
            'canonical_current': None, 'canonical_delta': None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--declaration', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('new output required')
    raw = args.declaration.read_bytes()
    started = time.monotonic()
    result = audit(json.loads(raw))
    if args.declaration.read_bytes() != raw:
        raise ValueError('declaration changed')
    result['declaration_sha256'] = hashlib.sha256(raw).hexdigest()
    result['wall_clock_sec'] = time.monotonic()-started
    args.output.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({'native_frames': result['native_frames'],
                      'adjacent_pairs': len(result['rows']),
                      'wall_clock_sec': result['wall_clock_sec']}))


if __name__ == '__main__':
    main()
