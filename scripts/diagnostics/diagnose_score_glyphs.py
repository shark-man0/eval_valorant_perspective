"""Inspect opt-in score readers on hash-bound native development frames.

No Validation Pack, expected score, timestamp or round ID is loaded. This is
not independent qualification and never installs a profile or emits events.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from collections import Counter
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from valorant_ai_coach.hud.global_lifecycle import global_recognizer_fingerprint  # noqa: E402
from valorant_ai_coach.hud.layout import HudLayout  # noqa: E402
from valorant_ai_coach.hud.templates import HudTemplateProfile  # noqa: E402


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def run(args):
    args.output_dir.mkdir(parents=True, exist_ok=False)
    source_hash = sha256(args.video)
    archive_hash = sha256(args.native_report)
    native = json.loads(args.native_report.read_text())
    if (
        source_hash != native['source_video_sha256']
        or native.get('native_pts_coverage_verified') is not True
    ):
        raise ValueError('complete native source report and matching video required')
    profile = HudTemplateProfile.load(args.score_profile)
    layout = HudLayout.load(args.layout)
    if any(profile.raw.get('readers', {}).get(name, {}).get('kind') != 'strict_score_glyphs'
           for name in ('ally_score', 'enemy_score')):
        raise ValueError('explicit strict score configurations required')
    readers = profile.build_readers()
    if profile.reader_diagnostics or not {'ally_score', 'enemy_score'} <= readers.keys():
        raise ValueError('valid explicit ally/enemy score readers required')
    profile_hash = profile.fingerprint(args.layout)
    code_hash = global_recognizer_fingerprint()
    script_hash = sha256(Path(__file__))
    freeze = {
        'scope': __doc__, 'source_video_sha256': source_hash,
        'native_report_sha256': archive_hash, 'score_profile_fingerprint': profile_hash,
        'recognizer_fingerprint': code_hash, 'diagnostic_script_sha256': script_hash,
        'roi_bounds_px': {name: layout.normalized_roi(name).pixel_bounds(1920, 1080)
                          for name in ('ally_score', 'enemy_score')},
        'geometry': 'assumed 1920x1080 reference; offline diagnostic only',
        'cohort': 'existing development source windows; not fresh holdout',
        'qualification_created': False, 'profile_adopted': False,
        'validation_pack_loaded': False, 'events_emitted': 0,
    }
    (args.output_dir / 'selection.json').write_text(json.dumps(freeze, indent=2) + '\n')
    started = time.perf_counter()
    results = []
    for window_index, window in enumerate(native['windows']):
        tiles = []
        for index, row in enumerate(window['rows'], start=1):
            path = args.frames_root / f'window-{window_index:03d}' / f'frame_{index:06d}.png'
            if sha256(path) != row['frame_sha256']:
                raise ValueError('source frame hash mismatch')
            image = cv2.imread(str(path))
            if image is None or image.shape != (1080, 1920, 3):
                raise ValueError('reference-size source image required')
            if hashlib.sha256(image.tobytes()).hexdigest() != row['source_pixel_sha256']:
                raise ValueError('decoded source pixel hash mismatch')
            values = {}
            tile = np.zeros((110, 240, 3), np.uint8)
            cv2.putText(
                tile, f"{index:02d} {row['pts_sec']:.6f}",
                (5, 16), 0, .4, (255, 255, 255), 1,
            )
            for side, name in enumerate(('ally_score', 'enemy_score')):
                x1, y1, x2, y2 = freeze['roi_bounds_px'][name]
                crop = image[y1:y2, x1:x2]
                value = readers[name].read(image, crop)
                values[name] = {'display': value.value, 'confidence': value.confidence,
                                'sources': value.sources}
                tile[25:100, side * 120:side * 120 + crop.shape[1]] = crop
            tiles.append(tile)
            results.append({'window_index': window_index,
                            'source_pts_ticks': row['source_pts_ticks'],
                            'time_base': row['time_base'], 'pts_sec': row['pts_sec'],
                            'frame_sha256': row['frame_sha256'], 'readings': values})
        while len(tiles) % 5:
            tiles.append(np.zeros_like(tiles[0]))
        sheet = np.vstack([np.hstack(tiles[i:i + 5]) for i in range(0, len(tiles), 5)])
        cv2.imwrite(str(args.output_dir / f'source-score-review-{window_index}.png'), sheet)
    if (source_hash != sha256(args.video) or archive_hash != sha256(args.native_report)
            or profile_hash != profile.fingerprint(args.layout)
            or code_hash != global_recognizer_fingerprint()
            or script_hash != sha256(Path(__file__))):
        raise ValueError('input/code/profile changed during diagnostic')
    summary = {}
    for name in ('ally_score', 'enemy_score'):
        readings = [row['readings'][name] for row in results]
        summary[name] = {'accepted': sum(row['display'] is not None for row in readings),
                         'unknown': sum(row['display'] is None for row in readings),
                         'reasons': dict(Counter(str(row['sources']) for row in readings))}
    return {**freeze, 'summary': summary, 'rows': results,
            'wall_clock_sec': time.perf_counter() - started,
            'manual_source_review_complete': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--video', type=Path, required=True)
    parser.add_argument('--native-report', type=Path, required=True)
    parser.add_argument('--frames-root', type=Path, required=True)
    parser.add_argument('--score-profile', type=Path, required=True)
    parser.add_argument('--layout', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    report = run(args)
    (args.output_dir / 'results.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'summary': report['summary'], 'wall_clock_sec': report['wall_clock_sec']}))


if __name__ == '__main__':
    main()
