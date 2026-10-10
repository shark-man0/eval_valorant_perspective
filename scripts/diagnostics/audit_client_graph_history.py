"""Measure client graph appearance, without authorizing content continuity.

This color probe intentionally has no graph-recognition or absence contract.
Transparent HUD pixels can include world/weapon colors. All input remains
exposed development data; no clock, phase value or validation label is read.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import cv2
import numpy as np

from valorant_ai_coach.hud.scene_domains import _ncc


def graph_color_probe(image, bounds):
    if image.dtype != np.uint8 or image.shape != (1080, 1920, 3):
        raise ValueError('native BGR image required')
    if (len(bounds) != 4 or any(type(v) is not int for v in bounds)
            or not 0 <= bounds[0] < bounds[2] <= 1920
            or not 0 <= bounds[1] < bounds[3] <= 1080):
        raise ValueError('valid native bounds required')
    x1, y1, x2, y2 = bounds
    # Signed subtraction avoids uint8 wrap-around falsely selecting warm pixels.
    bgr = image[y1:y2, x1:x2].astype(np.int16)
    return ((bgr[:, :, 0] - bgr[:, :, 2] > 20)
            & (bgr[:, :, 1] - bgr[:, :, 2] > 20)
            & (bgr[:, :, 0] > 120) & (bgr[:, :, 1] > 120)).astype(np.uint8) * 255


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-report', type=Path, required=True)
    parser.add_argument('--bounds', type=int, nargs=4, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('new output required')
    raw = args.source_report.read_bytes()
    source = json.loads(raw)
    files = source['native_png_sha256']
    paths = {int(Path(p).stem.removeprefix('frame_')): Path(p) for p in files}
    dependencies = [Path(__file__), Path('src/valorant_ai_coach/hud/scene_domains.py')]
    hashes = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in dependencies}
    started = time.monotonic()
    rows, previous, prior_tick = [], None, None
    for row in source['windows'][0]['rows']:
        path = paths[row['source_pts_ticks']]
        image = cv2.imread(str(path))
        if (image is None or hashlib.sha256(path.read_bytes()).hexdigest() != files[str(path)]
                or hashlib.sha256(image.tobytes()).hexdigest() != row['source_pixel_sha256']
                or row['source_time_base'] != '1/15360'
                or prior_tick is not None and row['source_pts_ticks'] - prior_tick != 256):
            raise ValueError('native source binding mismatch')
        mask = graph_color_probe(image, args.bounds)
        rows.append({'source_pts_ticks': row['source_pts_ticks'],
                     'source_pts_sec': row['source_pts_sec'],
                     'source_pixel_sha256': row['source_pixel_sha256'],
                     'color_probe_pixels': int(np.count_nonzero(mask)),
                     'color_probe_ncc': _ncc(previous, mask) if previous is not None else None,
                     'color_probe_changed_pixels': int(np.count_nonzero(previous != mask))
                     if previous is not None else None})
        previous, prior_tick = mask, row['source_pts_ticks']
    if (args.source_report.read_bytes() != raw
            or any(hashlib.sha256(Path(p).read_bytes()).hexdigest() != h
                   for p, h in {**files, **hashes}.items())):
        raise ValueError('terminal probe input changed')
    result = {'scope': 'exposed native client graph color probe; not graph recognition',
              'source_report_sha256': hashlib.sha256(raw).hexdigest(),
              'source_video_sha256': source['source_video_sha256'],
              'code_sha256': hashes, 'bounds': args.bounds, 'rows': rows,
              'parameters': {'channel_difference': 20, 'blue_green_min_exclusive': 120},
              'native_frames': len(rows), 'wall_clock_sec': time.monotonic()-started,
              'qualification_created': False, 'runtime_continuity_authorized': False,
              'canonical_current': None, 'canonical_delta': None}
    args.output.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({'native_frames': len(rows), 'runtime_sec': result['wall_clock_sec']}))


if __name__ == '__main__':
    main()
