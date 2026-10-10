"""Run a frozen score-only native-window check, without labels or adoption."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import time
from pathlib import Path

import cv2

from scripts.diagnostics.score_enlarged_background import EnlargedBackgroundScoreReader
from valorant_ai_coach.hud.global_lifecycle import global_recognizer_fingerprint
from valorant_ai_coach.hud.templates import HudTemplateProfile, SubregionReader
from valorant_ai_coach.video import VideoService


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--archive', required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists() or args.archive.exists():
        raise ValueError('new output and archive required')
    plan_hash = digest(args.plan)
    plan = json.loads(args.plan.read_text())
    for path, expected in plan['input_sha256'].items():
        if digest(Path(path)) != expected:
            raise ValueError('frozen input mismatch')
    if global_recognizer_fingerprint() != plan['recognizer_fingerprint']:
        raise ValueError('frozen recognizer mismatch')
    readers = HudTemplateProfile.load(Path(plan['templates'])).build_readers()
    prototypes = {
        role: SubregionReader(EnlargedBackgroundScoreReader(
            reader.reader.templates, comparison_preprocessing='gaussian3x3_v1',
            foreground_preprocessing='white200_v1',
        ), reader.bounds) for role, reader in readers.items()
    }
    args.archive.mkdir(parents=True)
    rows = []
    started = time.perf_counter()
    with VideoService().native_window(
        Path(plan['video']), start_sec=plan['window_sec'][0],
        end_sec=plan['window_sec'][1], source_video_sha256=plan['source_video_sha256'],
        png_prediction='up', max_png_bytes=200_000_000,
    ) as frames:
        for index, frame in enumerate(frames, 1):
            if index > 1 and frame.pts_ticks - frames[index - 2].pts_ticks != 256:
                raise ValueError('native cadence mismatch')
            path = args.archive / f'frame_{index:02d}.png'
            shutil.copyfile(frame.path, path)
            image = cv2.imread(str(path))
            if (image is None or digest(path) != frame.encoded_sha256
                    or hashlib.sha256(image.tobytes()).hexdigest() != frame.pixel_sha256):
                raise ValueError('source image mismatch')
            readings = {}
            for role, bounds in plan['outer_roi_px'].items():
                x, y, right, bottom = bounds
                roi = image[y:bottom, x:right]
                readings[role] = {}
                for method, reader in [('baseline', readers[role]),
                                       ('prototype', prototypes[role])]:
                    result = reader.read(image, roi)
                    readings[role][method] = dict(
                        value=result.value, confidence=result.confidence, sources=result.sources,
                    )
            rows.append(dict(source_pts_ticks=frame.pts_ticks, pts_sec=frame.time_sec,
                             frame_sha256=digest(path),
                             source_pixel_sha256=hashlib.sha256(image.tobytes()).hexdigest(),
                             readings=readings))
    if not rows:
        raise ValueError('nonempty native input required')
    for path, expected in plan['input_sha256'].items():
        if digest(Path(path)) != expected:
            raise ValueError('terminal frozen input mismatch')
    if digest(args.plan) != plan_hash or global_recognizer_fingerprint() != plan[
        'recognizer_fingerprint'
    ]:
        raise ValueError('terminal plan/code mismatch')
    if digest(Path(plan['video'])) != plan['source_video_sha256']:
        raise ValueError('terminal video mismatch')
    report = dict(scope='Frozen score-only nominal ROI diagnostic; no geometry/lifecycle claim',
                  plan_sha256=plan_hash, rows=rows, wall_clock_sec=time.perf_counter()-started,
                  qualification_created=False, canonical_current=None, canonical_delta=None)
    args.output.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k: v for k, v in report.items() if k != 'rows'}))


if __name__ == '__main__':
    main()
