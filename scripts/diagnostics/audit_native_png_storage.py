"""Fixed exposed-frame PNG codec benchmark, never recognition qualification."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import time
from pathlib import Path
from tempfile import TemporaryDirectory

import cv2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-report', type=Path, required=True)
    parser.add_argument('--indices', type=int, nargs='+', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--predictors', nargs='+',
                        choices=('none', 'sub', 'up', 'avg', 'paeth', 'mixed'))
    args = parser.parse_args()
    if args.output.exists() or len(set(args.indices)) != len(args.indices):
        raise ValueError('new output and distinct fixed source indices required')
    ffmpeg = shutil.which('ffmpeg')
    if ffmpeg is None:
        raise ValueError('FFmpeg required')
    raw = args.source_report.read_bytes()
    script_raw = Path(__file__).read_bytes()
    source = json.loads(raw)
    available = source['windows'][0]['rows']
    paths = {int(Path(p).stem.removeprefix('frame_')): Path(p)
             for p in source['native_png_sha256']}
    cases = []
    for index in args.indices:
        if not 0 <= index < len(available):
            raise ValueError('fixed source index out of range')
        row = available[index]
        path = paths[row['source_pts_ticks']]
        if hashlib.sha256(path.read_bytes()).hexdigest() != source['native_png_sha256'][str(path)]:
            raise ValueError('source PNG changed')
        image = cv2.imread(str(path))
        if (image is None or hashlib.sha256(image.tobytes()).hexdigest()
                != row['source_pixel_sha256']):
            raise ValueError('source pixels changed')
        cases.append({'source_index': index, 'path': str(path),
                      'source_pts_ticks': row['source_pts_ticks'],
                      'source_pixel_sha256': row['source_pixel_sha256'],
                      'source_png_sha256': source['native_png_sha256'][str(path)]})
    runs = []
    choices = ([(1, pred) for pred in args.predictors] if args.predictors else
               [(level, None) for level in (1, 6, 9)])
    choices = [*choices, *reversed(choices)]
    with TemporaryDirectory(prefix='native-png-storage-') as temporary:
        root = Path(temporary)
        staged = root/'input'
        staged.mkdir()
        for index, case in enumerate(cases, start=1):
            shutil.copyfile(case['path'], staged/f'frame_{index:06d}.png')
        # One serial encoder, fixed forward/reverse order; no parallelism.
        for index, (level, prediction) in enumerate(choices):
            output = root/f'run-{index}'
            output.mkdir()
            started = time.monotonic()
            subprocess.run([
                ffmpeg, '-hide_banner', '-loglevel', 'error', '-threads', '1',
                '-i', str(staged/'frame_%06d.png'), '-frames:v', str(len(cases)),
                '-fps_mode', 'passthrough', '-threads', '1', '-compression_level', str(level),
                *([] if prediction is None else ['-pred', prediction]),
                '-start_number', '1', str(output/'frame_%06d.png'),
            ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=180)
            encode_sec = time.monotonic()-started
            outputs = sorted(output.glob('frame_*.png'))
            if len(outputs) != len(cases):
                raise ValueError('codec frame coverage mismatch')
            sizes = []
            for case, path in zip(cases, outputs, strict=True):
                image = cv2.imread(str(path))
                if (image is None or hashlib.sha256(image.tobytes()).hexdigest()
                        != case['source_pixel_sha256']):
                    raise ValueError('lossless codec changed source pixels')
                sizes.append(path.stat().st_size)
            runs.append({'compression_level': level, 'prediction': prediction or 'none(default)',
                         'encode_wall_sec': encode_sec,
                         'png_bytes': sizes, 'total_bytes': sum(sizes),
                         'all_source_pixels_equal': True})
    if args.source_report.read_bytes() != raw or Path(__file__).read_bytes() != script_raw:
        raise ValueError('terminal benchmark bindings changed')
    for case in cases:
        if hashlib.sha256(Path(case['path']).read_bytes()).hexdigest() != case['source_png_sha256']:
            raise ValueError('terminal source changed')
    result = {'scope': 'exposed fixed codec cohort; not native PTS or recognition evaluation',
              'source_video_sha256': source['source_video_sha256'], 'cases': cases, 'runs': runs,
              'source_report_sha256': hashlib.sha256(raw).hexdigest(),
              'script_sha256': hashlib.sha256(script_raw).hexdigest(),
              'ffmpeg_version': subprocess.run([ffmpeg, '-version'], check=True,
                  capture_output=True, text=True).stdout.splitlines()[0],
              'qualification_created': False, 'production_behavior_changed': False,
              'canonical_current': None, 'canonical_delta': None}
    args.output.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps([{'level': r['compression_level'], 'prediction': r['prediction'],
                      'sec': r['encode_wall_sec'],
                      'bytes': r['total_bytes']} for r in runs]))


if __name__ == '__main__':
    main()
