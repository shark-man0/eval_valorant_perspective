"""Fixed diagnostic representation validation; never emits lifecycle events.

No Validation Pack, labels or expected clocks enter scoring. New source ticks
are reserved before decoding/prediction, excluding known saved exposures.
Exposure exclusion is conservative, not proof of exhaustive unseen data.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import time
from pathlib import Path

import cv2
import numpy as np

from scripts.diagnostics.inventory_native_exposure import collect_ticks
from valorant_ai_coach.hud.semantic_text import SemanticTextReference
from valorant_ai_coach.video.native import decode_native_window


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def timestamp_ticks(value):
    """Historical decimal coordinates used only for exposure exclusion."""
    found = set()
    if isinstance(value, dict):
        for key, child in value.items():
            if key in {'time_sec', 'pts_sec', 'source_pts_sec', 'timestamp_sec'}:
                for point in child if isinstance(child, list) else [child]:
                    if type(point) in (int, float) and np.isfinite(point):
                        tick = 553 + round((point * 15360 - 553) / 256) * 256
                        if abs(tick / 15360 - point) <= .00000051:
                            found.add(tick)
            found.update(timestamp_ticks(child))
    elif isinstance(value, list):
        for child in value:
            found.update(timestamp_ticks(child))
    return found


def run():
    start = time.perf_counter()
    reports = Path('e2e_reports/match_001')
    output = reports / 'result_persistent_feature_validation.json'
    reserve = reports / 'result_persistent_feature_reserved_cohort.json'
    directory = Path('outputs/recognition-investigation/result-persistent-feature-validation')
    if output.exists() or reserve.exists() or directory.exists():
        raise ValueError('new evidence paths required; do not overwrite a prior run')
    frozen_path = reports / 'result_persistent_minchannel_training.json'
    frozen = json.loads(frozen_path.read_text())
    feature_directory = Path(frozen['asset_directory'])
    for name, digest in frozen['asset_sha256'].items():
        if sha(feature_directory / name) != digest:
            raise ValueError('frozen feature asset changed')
    original_directory = (Path('outputs/hud_profiles/round-global-timer-glyph-20261008')
                          / 'result-late-diagnostic')
    training_path = (Path('outputs/recognition-investigation/result-support-inventory-20261008')
                     / 'reference-freeze.json')
    training = json.loads(training_path.read_text())
    inputs = {str(frozen_path): sha(frozen_path), str(training_path): sha(training_path),
              str(Path(__file__)): sha(Path(__file__))}

    def load_matcher(asset_directory):
        paths = [asset_directory / name for name in
                 ('reference.png', 'mask.png', 'regions.png',
                  'training-0.png', 'training-1.png', 'training-2.png')]
        for path in paths:
            inputs[str(path)] = sha(path)
        images = [cv2.imread(str(path), cv2.IMREAD_GRAYSCALE) for path in paths]
        support = list(zip(frozen['training_frame_sha256'], images[3:], strict=True))
        return SemanticTextReference(*images[:3], support, .90)

    previous, current = load_matcher(original_directory), load_matcher(feature_directory)
    old_reserve = json.loads((reports / 'frozen_result_late_native_cohort.json').read_text())
    exposure_paths = set(old_reserve['input_sha256']) | {str(p) for p in reports.glob('*.json')}
    exposed = set()
    for name in sorted(exposure_paths):
        path = Path(name)
        data = path.read_bytes()
        inputs[name] = hashlib.sha256(data).hexdigest()
        value = json.loads(data)
        exposed.update(collect_ticks(value))
        exposed.update(timestamp_ticks(value))
    ticks = [tick for tick in range(553, 2670000, 256) if 76.55 <= tick / 15360 <= 76.75]
    selected = sorted(set(ticks) - exposed)
    if len(selected) < 3:
        raise ValueError('insufficient new known-unexposed source ticks; no predictions made')
    source_hash = '71d58558559d6f578433ce9f234bf176f76fd5a86657dbfe3eba1e7d36136b06'
    reserve.write_text(json.dumps({
        'window_sec': [76.55, 76.75], 'cohort_ticks': ticks, 'selected_review_ticks': selected,
        'excluded_ticks': sorted(set(ticks) & exposed), 'time_base': '1/15360',
        'source_video_sha256': source_hash, 'input_sha256': inputs,
        'exhaustive_exposure_proven': False, 'same_episode_correlation': True,
        'predictions_made': False, 'qualification_created': False,
    }, indent=2) + '\n')
    directory.mkdir()
    rows = []

    def measure(image):
        crop = image[178:247, 842:1078]
        feature = (crop.min(axis=2) >= 200).astype(np.uint8) * 255
        return {'previous': previous.measure(crop), 'current': current.measure(feature)}

    video = Path('ValorantData/videos/Valorant_09-25-2026_0-37-29-379.mp4')
    with decode_native_window(video, start_sec=76.55, end_sec=76.75,
                              source_video_sha256=source_hash, ffmpeg=shutil.which('ffmpeg'),
                              ffprobe=shutil.which('ffprobe')) as frames:
        if [frame.pts_ticks for frame in frames] != ticks:
            raise ValueError('native coverage differs from frozen cohort')
        for index, frame in enumerate(frames, 1):
            image = frame.read_image()
            path = directory / f'frame_{index:02d}.png'
            shutil.copyfile(frame.path, path)
            rows.append({'source_pts_ticks': frame.pts_ticks, 'pts_sec': frame.time_sec,
                         'source_pixel_sha256': frame.pixel_sha256,
                         'frame_sha256': frame.encoded_sha256, 'path': str(path),
                         'reserved_for_review': frame.pts_ticks in selected, **measure(image)})
    negatives = []
    for item in training['negative']:
        path = Path(item['path'])
        image = cv2.imread(str(path))
        if (sha(path) != item['frame_sha256']
                or hashlib.sha256(image.tobytes()).hexdigest() != item['pixel_sha256']):
            raise ValueError('frozen negative source changed')
        negatives.append({**item, **measure(image)})
    if any(sha(path) != digest for path, digest in inputs.items()):
        raise ValueError('inputs changed during validation')
    output.write_text(json.dumps({
        'scope': 'Diagnostic frozen feature scores; no production adoption or reader qualification',
        'reservation_sha256': sha(reserve), 'processed_frames': len(rows), 'rows': rows,
        'existing_reviewed_negative_controls': negatives,
        'source_review_before_predictions': False, 'review_complete': False,
        'ncc_threshold': .90, 'wall_clock_sec': time.perf_counter() - start,
        'qualification_created': False, 'production_changed': False,
        'canonical_previous': {'PASS': 23, 'FAIL': 55, 'NE': 4},
        'canonical_current': None, 'canonical_delta': None,
    }, indent=2) + '\n')
    print(json.dumps({'processed': len(rows), 'reserved': len(selected),
                      'previous_accepts': sum(r['previous']['presence'] is True for r in rows),
                      'current_accepts': sum(r['current']['presence'] is True for r in rows),
                      'negative_accepts': sum(r['current']['presence'] is True
                                              for r in negatives)}))


if __name__ == '__main__':
    run()
