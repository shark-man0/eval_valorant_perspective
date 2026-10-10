"""Measure a frozen scene cohort through production native APIs, without qualification."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import time
from pathlib import Path

from valorant_ai_coach.hud.global_lifecycle import global_recognizer_fingerprint
from valorant_ai_coach.hud.native_scene_input import observe_native_scene_window
from valorant_ai_coach.hud.scene_source_binding import SceneSourceBinding
from valorant_ai_coach.video import VideoService


def verify_files(bindings):
    for path, expected in bindings.items():
        digest = hashlib.sha256()
        with Path(path).open('rb') as stream:
            for block in iter(lambda: stream.read(1024*1024), b''):
                digest.update(block)
        if digest.hexdigest() != expected:
            raise ValueError(f'frozen dependency changed: {path}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--declaration', type=Path, required=True)
    parser.add_argument('--output-directory', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output_directory.exists():
        raise ValueError('new cohort outputs required')
    declaration_bytes = args.declaration.read_bytes()
    declaration = json.loads(declaration_bytes)
    dependencies = declaration['file_sha256']
    runner = str(Path(__file__).relative_to(Path.cwd()))
    if dependencies.get(runner) != hashlib.sha256(Path(__file__).read_bytes()).hexdigest():
        raise ValueError('runner must be frozen before decode')
    verify_files(dependencies)
    if declaration['recognizer_fingerprint'] != global_recognizer_fingerprint():
        raise ValueError('production code must be frozen before decode')
    binding = SceneSourceBinding.load(Path(declaration['scene_profile']))
    if declaration['source_binding_fingerprint'] != binding.fingerprint():
        raise ValueError('source assets must be frozen before decode')
    args.output_directory.mkdir(parents=True)
    (args.output_directory / 'predecode_declaration.json').write_bytes(declaration_bytes)
    started = time.monotonic()
    excluded_ticks = set(declaration['excluded_source_pts_ticks'])
    excluded_pixels = set(declaration['excluded_native_pixel_sha256'])
    windows, image_bindings = [], {}
    for index, (start, end) in enumerate(declaration['windows_sec']):
        directory = args.output_directory / f'window-{index:03d}'
        directory.mkdir()
        with VideoService().native_window(
            Path(declaration['source_video']), start_sec=start, end_sec=end,
            source_video_sha256=declaration['source_video_sha256'],
        ) as frames:
            overlaps = sum(f.pts_ticks in excluded_ticks or f.pixel_sha256 in excluded_pixels
                           for f in frames)
            measurements = observe_native_scene_window(
                frames, binding, native_step_ticks=declaration['native_step_ticks'],
                deferred_initialization=declaration['deferred_initialization'],
            )
            for frame in frames:
                path = directory / f'frame_{frame.pts_ticks}.png'
                shutil.copyfile(frame.path, path)
                image_bindings[str(path)] = frame.encoded_sha256
            windows.append({'window_sec': [start, end], 'native_frames': len(frames),
                            'known_exposure_overlap_frames': overlaps,
                            'rows': measurements})
    verify_files(dependencies)
    verify_files(image_bindings)
    binding.verify()
    if (args.declaration.read_bytes() != declaration_bytes
            or global_recognizer_fingerprint() != declaration['recognizer_fingerprint']):
        raise ValueError('terminal declaration/code changed')
    result = {'scope': 'frozen native entrance; review pending, no qualification',
              'declaration_sha256': hashlib.sha256(declaration_bytes).hexdigest(),
              'source_video_sha256': declaration['source_video_sha256'],
              'windows': windows, 'native_png_sha256': image_bindings,
              'wall_clock_sec': time.monotonic()-started,
              'qualification_created': False, 'canonical_current': None,
              'canonical_delta': None}
    args.output.write_text(json.dumps(result, indent=2)+'\n')
    links = sum(bool(r['scene_measurement']['descriptive_scene_link'])
                for w in windows for r in w['rows'])
    print(json.dumps({'native_frames': sum(w['native_frames'] for w in windows),
                      'descriptive_links': links,
                      'known_overlap': sum(w['known_exposure_overlap_frames'] for w in windows),
                      'runtime_sec': result['wall_clock_sec']}))


if __name__ == '__main__':
    main()
