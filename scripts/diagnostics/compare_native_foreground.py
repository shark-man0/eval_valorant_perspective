"""Compare exposed foreground poses with every native frame of a control window.

Reference crops are manually chosen offline image inputs, never a recognizer
profile or ownership evidence. Similarity is descriptive and cannot prove a
normal animation or exclude a scene-preserving content jump.
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
from valorant_ai_coach.video import VideoService


def pose_patches(image, boxes):
    if image.dtype != np.uint8 or image.ndim != 3 or image.shape[2] != 3:
        raise ValueError('native uint8 BGR image required')
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    patches = []
    for box in boxes:
        if (
            len(box) != 4 or any(type(v) is not int for v in box)
            or not 0 <= box[0] < box[2] <= image.shape[1]
            or not 480 <= box[1] < box[3] <= image.shape[0]
        ):
            raise ValueError('explicit native foreground crops below timer/phase required')
        x1, y1, x2, y2 = box
        patches.append(gray[y1:y2, x1:x2].copy())
    if len(patches) < 3:
        raise ValueError('multiple distinct source crop comparisons required')
    if len(set(tuple(box) for box in boxes)) != len(boxes):
        raise ValueError('distinct foreground crops required')
    return tuple(patches)


def compare_pose(reference, current):
    if len(reference) != len(current) or not reference:
        raise ValueError('matching crop sets required')
    if any(a.shape != b.shape for a, b in zip(reference, current, strict=True)):
        raise ValueError('matching native crop shapes required')
    scores = [_ncc(a, b) for a, b in zip(reference, current, strict=True)]
    return {'crop_ncc': scores, 'minimum_ncc': (
        min(scores) if all(score is not None for score in scores) else None
    ), 'runtime_authorized': False, 'normal_animation_proven': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('video', 'reference_directory', 'reference_source_report', 'output_directory',
                 'output_report'):
        parser.add_argument('--' + name.replace('_', '-'), type=Path, required=True)
    parser.add_argument('--source-sha256', required=True)
    parser.add_argument('--window', type=float, nargs=2, required=True)
    parser.add_argument('--reference-frames', type=int, nargs=2, required=True)
    parser.add_argument('--native-step-ticks', type=int, required=True)
    parser.add_argument('--roi', type=int, nargs=4, action='append', required=True)
    args = parser.parse_args()
    if args.output_report.exists() or args.output_directory.exists():
        raise ValueError('new output paths required')
    started = time.monotonic()
    report_bytes = args.reference_source_report.read_bytes()
    source = json.loads(report_bytes)
    if source['source_video_sha256'] != args.source_sha256:
        raise ValueError('reference and control source video differ')
    dependencies = [Path(__file__), Path('src/valorant_ai_coach/hud/scene_domains.py'),
                    Path('src/valorant_ai_coach/video/native.py'),
                    Path('src/valorant_ai_coach/video/service.py')]
    hashes = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in dependencies}
    references = []
    reference_bindings = {}
    for index in args.reference_frames:
        path = args.reference_directory / f'frame_{index:06d}.png'
        expected = source['windows'][0]['rows'][index-1]
        image = cv2.imread(str(path))
        if (
            hashlib.sha256(path.read_bytes()).hexdigest() != expected['frame_sha256']
            or image is None
            or hashlib.sha256(image.tobytes()).hexdigest() != expected['source_pixel_sha256']
        ):
            raise ValueError('reference native pixels changed')
        reference_bindings[str(path)] = expected['frame_sha256']
        references.append(pose_patches(image, args.roi))
    args.output_directory.mkdir(parents=True)
    selection = {
        'scope': 'offline exposed source/control comparison; not qualification',
        'source_video_sha256': args.source_sha256, 'window_sec': args.window,
        'reference_frame_numbers': args.reference_frames, 'native_roi_bounds': args.roi,
        'code_sha256': hashes, 'reference_png_sha256': reference_bindings,
        'reference_source_report_sha256': hashlib.sha256(report_bytes).hexdigest(),
    }
    (args.output_directory / 'predecode_selection.json').write_text(
        json.dumps(selection, indent=2) + '\n'
    )
    rows = []
    panels = []
    with VideoService().native_window(
        args.video, start_sec=args.window[0], end_sec=args.window[1],
        source_video_sha256=args.source_sha256,
    ) as frames:
        previous_patches = None
        previous_tick = None
        for frame in frames:
            if (
                previous_tick is not None
                and frame.pts_ticks-previous_tick != args.native_step_ticks
            ):
                raise ValueError('complete native cadence required')
            image = frame.read_image()
            patches = pose_patches(image, args.roi)
            scores = [compare_pose(ref, patches) for ref in references]
            pair = None
            if previous_patches is not None:
                prior = compare_pose(references[0], previous_patches)
                after = scores[1]
                pair = {'previous_source_pts_ticks': previous_tick,
                        'before_crop_ncc': prior['crop_ncc'], 'after_crop_ncc': after['crop_ncc'],
                        'minimum_ncc': (min(prior['minimum_ncc'], after['minimum_ncc'])
                                        if prior['minimum_ncc'] is not None
                                        and after['minimum_ncc'] is not None else None)}
            rows.append({'source_pts_ticks': frame.pts_ticks, 'source_pts_sec': frame.time_sec,
                         'time_base': str(frame.time_base), 'source_epoch': frame.source_epoch,
                         'encoded_sha256': frame.encoded_sha256,
                         'source_pixel_sha256': frame.pixel_sha256,
                         'reference_pose_comparisons': scores, 'reference_pair_comparison': pair})
            panel = cv2.resize(image[480:1080], (384, 120), interpolation=cv2.INTER_AREA)
            cv2.putText(panel, f'{frame.pts_ticks} / {frame.time_base}', (4, 16),
                        cv2.FONT_HERSHEY_SIMPLEX, .4, (255, 255, 255), 1)
            panels.append(panel)
            previous_patches, previous_tick = patches, frame.pts_ticks
    sheets = {}
    for offset in range(0, len(panels), 30):
        batch = panels[offset:offset+30]
        canvas = np.zeros((720, 1920, 3), np.uint8)
        for index, panel in enumerate(batch):
            y, x = (index//5)*120, (index%5)*384
            canvas[y:y+120, x:x+384] = panel
        path = args.output_directory / f'foreground_{offset//30:02d}.png'
        if not cv2.imwrite(str(path), canvas):
            raise ValueError('foreground review sheet write failed')
        sheets[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
    if args.reference_source_report.read_bytes() != report_bytes or any(
        hashlib.sha256(Path(p).read_bytes()).hexdigest() != h
        for p, h in {**hashes, **reference_bindings}.items()
    ):
        raise ValueError('terminal comparison bindings changed')
    result = {**selection, 'rows': rows, 'review_sheet_sha256': sheets,
              'wall_clock_sec': time.monotonic()-started,
              'native_frames': len(rows), 'qualification_created': False,
              'runtime_authorized': False, 'canonical_current': None, 'canonical_delta': None}
    args.output_report.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({'frames': len(rows), 'wall_clock_sec': result['wall_clock_sec'],
                      'report': str(args.output_report)}))


if __name__ == '__main__':
    main()
