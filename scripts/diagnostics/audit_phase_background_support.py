"""Audit background-reference texture support; never classify phase absence."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np

from valorant_ai_coach.hud.scene_domains import _ncc
from valorant_ai_coach.hud.weapon_identity import masked_score


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-report', type=Path, required=True)
    parser.add_argument('--reference-tick', type=int, required=True)
    parser.add_argument('--panel-box', type=int, nargs=4, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('new output required')
    x1, y1, x2, y2 = args.panel_box
    if not 0 <= x1 < x2 <= 1920 or not 0 <= y1 < y2 <= 1080 or x2-x1 < 3:
        raise ValueError('valid native panel bounds required')
    raw = args.source_report.read_bytes()
    source = json.loads(raw)
    paths = {int(Path(p).stem.removeprefix('frame_')): Path(p)
             for p in source['native_png_sha256']}
    metadata = {r['source_pts_ticks']: r for r in source['windows'][0]['rows']}
    dependencies = [Path(__file__), Path('src/valorant_ai_coach/hud/weapon_identity.py'),
                    Path('src/valorant_ai_coach/hud/scene_domains.py')]
    hashes = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in dependencies}

    def read(tick):
        path = paths[tick]
        image = cv2.imread(str(path))
        if (image is None or image.shape != (1080, 1920, 3)
                or hashlib.sha256(path.read_bytes()).hexdigest()
                != source['native_png_sha256'][str(path)]
                or hashlib.sha256(image.tobytes()).hexdigest()
                != metadata[tick]['source_pixel_sha256']):
            raise ValueError('native source binding mismatch')
        return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)[y1:y2, x1:x2]

    reference = read(args.reference_tick)
    # Three fixed, disjoint horizontal portions, with no contrast-based mask mining.
    columns = np.array_split(np.arange(reference.shape[1]), 3)
    masks = []
    for selected in columns:
        mask = np.zeros(reference.shape, np.uint8)
        mask[:, selected] = 255
        masks.append(mask)
    rows = []
    for tick, meta in metadata.items():
        image = read(tick)
        rows.append({'source_pts_ticks': tick, 'source_pts_sec': meta['source_pts_sec'],
                     'gray_std': float(image.std()),
                     'group_gray_std': [float(image[m > 0].std()) for m in masks],
                     'existing_masked_ncc': [masked_score(reference, image, m) for m in masks],
                     'shadow_whole_crop_ncc': _ncc(reference, image)})
    if (args.source_report.read_bytes() != raw
            or any(hashlib.sha256(Path(p).read_bytes()).hexdigest() != h
                   for p, h in {**hashes, **source['native_png_sha256']}.items())):
        raise ValueError('terminal source changed')
    result = {'scope': 'exposed absence-reference feasibility; no reference/profile generation',
              'source_report_sha256': hashlib.sha256(raw).hexdigest(),
              'code_sha256': hashes, 'panel_box': args.panel_box,
              'reference_source_pts_ticks': args.reference_tick,
              'reference_source_pixel_sha256': metadata[args.reference_tick]['source_pixel_sha256'],
              'reference_group_gray_std': [float(reference[m > 0].std()) for m in masks],
              'group_column_ranges': [[int(c[0]), int(c[-1])+1] for c in columns],
              'existing_masked_contrast_floor': 5, 'ncc_floor': .90,
              'native_frames': len(rows), 'rows': rows,
              'all_group_support_frames': sum(all(v >= .90 for v in r['existing_masked_ncc'])
                                              for r in rows),
              'phase_absent': None, 'runtime_authorized': False,
              'qualification_created': False, 'canonical_current': None, 'canonical_delta': None}
    args.output.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({'frames': len(rows), 'reference_std': result['reference_group_gray_std'],
                      'all_group_support_frames': result['all_group_support_frames']}))


if __name__ == '__main__':
    main()
