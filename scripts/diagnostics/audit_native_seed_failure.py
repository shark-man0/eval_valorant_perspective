"""Replay an existing native scene episode with observational model sinks only."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import cv2

from valorant_ai_coach.hud.scene_episode import ObservedSceneEpisode
from valorant_ai_coach.hud.scene_references import WorldDomainBootstrap
from valorant_ai_coach.hud.scene_source_binding import SceneSourceBinding


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-report', type=Path, required=True)
    parser.add_argument('--scene-profile', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('new output required')
    source_bytes = args.source_report.read_bytes()
    source = json.loads(source_bytes)
    binding = SceneSourceBinding.load(args.scene_profile)
    hashes = {str(path): hashlib.sha256(path.read_bytes()).hexdigest()
              for path in [Path(__file__), *Path('src/valorant_ai_coach/hud').glob('*.py')]}
    rows = source['windows'][0]['rows']
    seeds = [i for i, r in enumerate(rows)
             if r['scene_measurement']['reason'] == 'image_supported_observed_seed']
    if len(seeds) != 1:
        raise ValueError('one recorded observed seed required')
    selected = rows[seeds[0]:]
    paths = {int(Path(p).stem.removeprefix('frame_')): Path(p)
             for p in source['native_png_sha256']}
    episode = ObservedSceneEpisode(lambda: WorldDomainBootstrap(args.scene_profile),
                                   native_step_ticks=256, deferred_initialization=True)
    diagnostics = []
    for row in selected:
        path = paths[row['source_pts_ticks']]
        image = cv2.imread(str(path))
        if (image is None or image.shape != (1080, 1920, 3)
                or hashlib.sha256(path.read_bytes()).hexdigest()
                != source['native_png_sha256'][str(path)]
                or hashlib.sha256(image.tobytes()).hexdigest() != row['source_pixel_sha256']
                or row['source_time_base'] != '1/15360'):
            raise ValueError('native source integrity mismatch')
        models, regions = [], []
        if episode.chain is not None:
            original_advance = episode.chain.advance

            def measured_advance(current, *, _advance=original_advance,
                                 _models=models, _regions=regions, **kwargs):
                return _advance(current, model_sink=_models, region_sink=_regions, **kwargs)

            episode.chain.advance = measured_advance
        result = episode.observe(image, row['source_pts_ticks'], source_epoch=row['source_epoch'])
        if episode.chain is not None and models:
            episode.chain.advance = original_advance
        if result != row['scene_measurement']:
            raise ValueError('observational replay changed original scene output')
        diagnostics.append({'source_pts_ticks': row['source_pts_ticks'],
                            'source_pts_sec': row['source_pts_sec'],
                            'reason': result['reason'], 'seed_model': models,
                            'region_counts': regions})
        if episode.terminated:
            break
    binding.verify()
    if (args.source_report.read_bytes() != source_bytes
            or any(hashlib.sha256(Path(p).read_bytes()).hexdigest() != h
                   for p, h in {**hashes, **source['native_png_sha256']}.items())):
        raise ValueError('terminal replay inputs changed')
    final_model = diagnostics[-1]['seed_model']
    model = final_model[0] if final_model else {}
    inliers = model.get('original_inliers') or []
    result = {'scope': 'observational existing-episode replay; no qualification or policy change',
              'source_report_sha256': hashlib.sha256(source_bytes).hexdigest(),
              'code_sha256': hashes, 'rows': diagnostics,
              'seed_pts_sec': selected[0]['source_pts_sec'],
              'stop_pts_sec': diagnostics[-1]['source_pts_sec'],
              'replayed_outputs_exact': True, 'stop_reason': diagnostics[-1]['reason'],
              'stop_candidates': len(inliers), 'stop_inliers': sum(inliers),
              'required_inlier_ratio': .90, 'qualification_created': False,
              'canonical_current': None, 'canonical_delta': None}
    args.output.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({k: result[k] for k in ('seed_pts_sec', 'stop_pts_sec', 'stop_reason',
                                           'stop_candidates', 'stop_inliers')}))


if __name__ == '__main__':
    main()
