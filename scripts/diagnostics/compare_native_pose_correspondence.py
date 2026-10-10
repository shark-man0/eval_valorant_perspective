"""Fixed-region pose correspondence diagnostic; never continuity/ownership proof."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np

from valorant_ai_coach.hud.weapon_identity import masked_score


def compare_pose(previous, current, boxes):
    if (previous.shape != (1080, 1920, 3) or current.shape != previous.shape
            or previous.dtype != np.uint8 or current.dtype != np.uint8):
        raise ValueError('native BGR images required')
    a, b = (cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) for image in (previous, current))
    source, target, regions, scores, counts = [], [], [], [], []
    for region, box in enumerate(boxes):
        if (len(box) != 4 or any(type(v) is not int for v in box)
                or not 0 <= box[0] < box[2] <= 1920
                or not 0 <= box[1] < box[3] <= 1080):
            raise ValueError('native region bounds required')
        x1, y1, x2, y2 = box
        left, right = a[y1:y2, x1:x2], b[y1:y2, x1:x2]
        p = cv2.goodFeaturesToTrack(left, 100, .01, 5)
        local = {'region': region, 'selected': 0 if p is None else len(p), 'accepted': 0}
        counts.append(local)
        if p is None:
            continue
        q, status, _ = cv2.calcOpticalFlowPyrLK(left, right, p, None,
                                               winSize=(21, 21), maxLevel=3)
        if q is None or status is None or not np.isfinite(q).all():
            continue
        back, reciprocal, _ = cv2.calcOpticalFlowPyrLK(right, left, q, None,
                                                     winSize=(21, 21), maxLevel=3)
        if back is None or reciprocal is None:
            continue
        for pp, qq, bp, valid, reverse in zip(
            p.reshape(-1, 2), q.reshape(-1, 2), back.reshape(-1, 2),
            status.reshape(-1), reciprocal.reshape(-1), strict=True,
        ):
            if (not valid or not reverse or not np.isfinite(bp).all()
                    or np.linalg.norm(pp-bp) > 1):
                continue
            px, py = np.round(pp).astype(int)
            qx, qy = np.round(qq).astype(int)
            if not (8 <= px < left.shape[1]-8 and 8 <= py < left.shape[0]-8
                    and 8 <= qx < right.shape[1]-8 and 8 <= qy < right.shape[0]-8):
                continue
            patch, other = left[py-7:py+8, px-7:px+8], right[qy-7:qy+8, qx-7:qx+8]
            score = masked_score(patch, other, np.full(patch.shape, 255, np.uint8))
            if score < .90:
                continue
            source.append((pp+[x1, y1]).tolist())
            target.append((qq+[x1, y1]).tolist())
            regions.append(region)
            scores.append(score)
            local['accepted'] += 1
    matrix, inliers = None, None
    if len(source) >= 3 and len(set(regions)) >= 3:
        cv2.setRNGSeed(0)
        matrix, inliers = cv2.estimateAffinePartial2D(
            np.float32(source), np.float32(target), method=cv2.RANSAC, ransacReprojThreshold=2,
        )
    available = matrix is not None and inliers is not None and np.isfinite(matrix).all()
    accepted = int(inliers.sum()) if available else 0
    return {'regions': counts, 'source_points': source, 'current_points': target,
            'point_regions': regions, 'patch_ncc': scores,
            'partial_affine': matrix.tolist() if available else None,
            'ransac_inliers': inliers.reshape(-1).tolist() if available else None,
            'candidate_count': len(source), 'inlier_count': accepted,
            'inlier_ratio': accepted/len(source) if source else None,
            'descriptive_geometric_quorum': bool(available and accepted >= .90*len(source)
                and len({r for r, i in zip(regions, inliers.reshape(-1), strict=True) if i}) >= 3),
            'foreground_membership_qualified': False, 'runtime_authorized': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--declaration', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('new output required')
    raw = args.declaration.read_bytes()
    d = json.loads(raw)
    hashes = d['file_sha256']

    def verify():
        if any(hashlib.sha256(Path(p).read_bytes()).hexdigest() != h for p, h in hashes.items()):
            raise ValueError('frozen source/code dependency changed')

    verify()
    reports = {p: json.loads(Path(p).read_bytes()) for p in d['source_reports']}
    rows = []
    for pair in d['pairs']:
        images, bindings = [], []
        for case in pair:
            report, tick = reports[case['report']], case['source_pts_ticks']
            path = next(Path(p) for p in report['native_png_sha256']
                        if Path(p).stem == f'frame_{tick}')
            image = cv2.imread(str(path))
            if (image is None or hashlib.sha256(path.read_bytes()).hexdigest()
                    != report['native_png_sha256'][str(path)]):
                raise ValueError('native PNG binding mismatch')
            if hashlib.sha256(image.tobytes()).hexdigest() != case['source_pixel_sha256']:
                raise ValueError('native pixel binding mismatch')
            images.append(image)
            bindings.append({**case, 'native_png_sha256': report['native_png_sha256'][str(path)],
                             'source_pixel_sha256': hashlib.sha256(image.tobytes()).hexdigest()})
        rows.append({'source': bindings, 'comparison': compare_pose(*images, d['boxes'])})
    verify()
    if args.declaration.read_bytes() != raw:
        raise ValueError('declaration changed')
    result = {'scope': 'exposed pose correspondence; no source/world/animation qualification',
              'declaration_sha256': hashlib.sha256(raw).hexdigest(), 'rows': rows,
              'qualification_created': False, 'runtime_behavior_changed': False,
              'canonical_current': None, 'canonical_delta': None}
    args.output.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps([{'candidates': r['comparison']['candidate_count'],
                      'inliers': r['comparison']['inlier_count'],
                      'quorum': r['comparison']['descriptive_geometric_quorum']} for r in rows]))


if __name__ == '__main__':
    main()
