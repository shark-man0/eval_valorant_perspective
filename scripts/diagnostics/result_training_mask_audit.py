"""Training-only result-mask audit; no heldout inputs or production assets written."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np

from valorant_ai_coach.hud.weapon_identity import masked_score


def persistent_white_feature(training_bgr, regions):
    """Training-derived foreground/contrast support; validation remains required."""
    if (len(training_bgr) < 3 or any(
        image.dtype != np.uint8 or image.shape != (*regions.shape, 3)
        for image in training_bgr
    )):
        raise ValueError('three aligned original BGR training crops required')
    features = [(image.min(axis=2) >= 200).astype(np.uint8) * 255
                for image in training_bgr]
    stack = np.stack(features)
    stable = np.all(stack == stack[0], axis=0)
    supported_regions = np.where(stable, regions, 0).astype(np.uint8)
    return features[0], (supported_regions > 0).astype(np.uint8) * 255, supported_regions, features


def audit(reference, regions, training):
    if (len(training) < 3 or reference.ndim != 2
            or any(image.shape != reference.shape for image in training)
            or regions.shape != reference.shape):
        raise ValueError('three aligned training crops and matching support regions required')
    stack = np.stack(training)
    bright = np.all(stack >= 200, axis=0)
    dark = np.all(stack <= 180, axis=0)
    stable = stack.max(axis=0).astype(int) - stack.min(axis=0).astype(int) <= 20
    edge_reference = cv2.Canny(reference, 12, 24)
    edge_training = [cv2.Canny(image, 12, 24) for image in training]
    groups = []
    for group in sorted(int(i) for i in np.unique(regions) if i):
        selected = regions == group
        mask = selected.astype(np.uint8) * 255
        trimmed = selected & stable & (bright | dark)
        trim_mask = trimmed.astype(np.uint8) * 255
        groups.append({
            'group': group, 'mask_population': int(selected.sum()),
            'persistent_bright_population': int((selected & bright).sum()),
            'other_contrast_neighborhood_population': int((selected & ~bright).sum()),
            'training_pixel_std_percentiles': np.percentile(
                stack.astype(float).std(axis=0)[selected], [25, 50, 75, 90, 99],
            ).tolist(),
            'original_training_scores': [masked_score(reference, image, mask)
                                         for image in training],
            'stable_trim_population': int(trimmed.sum()),
            'stable_trim_dark_support': int((trimmed & dark).sum()),
            'stable_trim_reference_std': float(reference[trimmed].std())
            if trimmed.any() else 0.0,
            'stable_trim_training_scores': [masked_score(reference, image, trim_mask)
                                            for image in training],
            'fixed_canny_training_scores': [masked_score(edge_reference, image, mask)
                                           for image in edge_training],
        })
    return {'groups': groups, 'minimum_training_support': 3, 'ncc_threshold': .90,
            'stable_trim_hypothesis': 'range<=20, all bright>=200 or all dark<=180',
            'edge_hypothesis': 'Canny12/24 with unchanged original groups and NCC0.90',
            'production_changed': False, 'qualification_created': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--asset-directory', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('new output required')
    paths = [args.asset_directory / name for name in (
        'reference.png', 'regions.png', 'training-0.png', 'training-1.png', 'training-2.png',
    )]
    originals = {str(p): p.read_bytes() for p in paths}
    images = [cv2.imread(str(p), cv2.IMREAD_GRAYSCALE) for p in paths]
    if any(image is None for image in images):
        raise ValueError('training assets unavailable')
    result = audit(images[0], images[1], images[2:])
    if any(Path(p).read_bytes() != raw for p, raw in originals.items()):
        raise ValueError('training assets changed')
    result['input_sha256'] = {p: hashlib.sha256(raw).hexdigest()
                              for p, raw in originals.items()}
    result['diagnostic_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    args.output.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({'minimum_scores': {
        key: min(min(g[key]) for g in result['groups']) for key in (
            'original_training_scores', 'stable_trim_training_scores',
            'fixed_canny_training_scores',
        )}}))


if __name__ == '__main__':
    main()
