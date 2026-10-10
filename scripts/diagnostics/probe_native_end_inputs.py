"""Measure actual global end inputs on archived native frames; no events."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import time
from collections import Counter
from contextlib import ExitStack
from fractions import Fraction
from pathlib import Path

import cv2

from valorant_ai_coach.hud.analyzers import RealHudAnalyzer
from valorant_ai_coach.hud.global_lifecycle import global_recognizer_fingerprint
from valorant_ai_coach.hud.templates import HudTemplateProfile
from valorant_ai_coach.video import VideoService
from valorant_ai_coach.video.native import NativeSourceFrame


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def global_signal_setup(profile: HudTemplateProfile | None) -> dict:
    """Explain input availability separately from per-frame nonmatches."""
    result = {}
    for name in ('buy_phase_template', 'round_end_template'):
        spec = profile.raw.get('signals', {}).get(name) if profile else None
        loaded = bool(profile and name in profile._semantic_text)
        result[name] = {
            'configured': spec is not None,
            'semantic_matcher_loaded': loaded,
            'status': ('loaded' if loaded else 'not_configured' if spec is None
                       else 'semantic_matcher_unavailable'),
            'diagnostics': list(profile.reader_diagnostics) if profile else [],
        }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--video', type=Path, required=True)
    parser.add_argument('--layout', type=Path, required=True)
    parser.add_argument('--templates', type=Path,
                        help='Optional existing sidecar; diagnostic only, never adopted.')
    parser.add_argument('--archive-manifest', type=Path)
    parser.add_argument('--archive-directory', type=Path)
    parser.add_argument('--start', type=float)
    parser.add_argument('--end', type=float)
    parser.add_argument('--source-sha256')
    parser.add_argument('--native-step-ticks', type=int, default=256)
    parser.add_argument('--native-max-png-bytes', type=int, default=200_000_000,
                        help='Explicit bounded temporary native PNG storage; default200MB.')
    parser.add_argument('--save-source-directory', type=Path,
                        help='Optional new local review archive; unchanged encoded PNG bytes.')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('new output required')
    if args.save_source_directory is not None and args.save_source_directory.exists():
        raise ValueError('new source review directory required')
    archived = args.archive_manifest is not None
    if (archived and (args.archive_directory is None or args.start is not None
                      or args.end is not None or args.source_sha256 is not None)) or (
        not archived and (args.archive_directory is not None or args.start is None
                          or args.end is None or args.source_sha256 is None)
    ) or args.native_step_ticks <= 0 or args.native_max_png_bytes <= 0:
        raise ValueError('choose paired archive inputs or explicit fresh window and source hash')
    manifest_hash = digest(args.archive_manifest) if archived else None
    manifest = json.loads(args.archive_manifest.read_text()) if archived else None
    source_hash = manifest['source_video_sha256'] if archived else args.source_sha256
    frames = []
    for index, row in enumerate(manifest['source_frames'] if archived else (), 1):
        path = args.archive_directory / f'frame_{index:02d}.png'
        if digest(path) != row['frame_sha256']:
            raise ValueError('archived source image binding mismatch')
        image = cv2.imread(str(path))
        if image is None:
            raise ValueError('archived image unavailable')
        frame = NativeSourceFrame(
            path, row['source_pts_ticks'], Fraction(row['time_base']),
            'archived-end-diagnostic', source_hash, row['frame_sha256'],
            hashlib.sha256(image.tobytes()).hexdigest(), image.shape[1], image.shape[0],
        )
        if frame.time_sec != row['pts_sec'] or (
            frames and frame.pts_ticks - frames[-1].pts_ticks != args.native_step_ticks
        ):
            raise ValueError('archived native PTS/cadence mismatch')
        frames.append(frame)
    if archived and not frames:
        raise ValueError('archived source frames required')
    analyzer = RealHudAnalyzer(args.layout, template_profile_path=args.templates)
    profile = analyzer.fingerprint()
    code = global_recognizer_fingerprint()
    started = time.perf_counter()
    # Prefix is only geometric diagnostic context in the same analyzer call.
    # The large gap and separate source epoch never corroborate a boundary.
    with ExitStack() as stack:
        service = VideoService()
        if not archived:
            frames = stack.enter_context(service.native_window(
                args.video, start_sec=args.start, end_sec=args.end,
                source_video_sha256=source_hash, png_prediction='up',
                max_png_bytes=args.native_max_png_bytes,
            ))
        if not frames or any(
            frame.pts_ticks - previous.pts_ticks != args.native_step_ticks
            for previous, frame in zip(frames, frames[1:], strict=False)
        ):
            raise ValueError('nonempty exact native cadence required')
        prefix = stack.enter_context(service.native_window(
            args.video, start_sec=0, end_sec=.10, source_video_sha256=source_hash,
            png_prediction='up', max_png_bytes=20_000_000,
        ))
        saved = []
        if args.save_source_directory is not None:
            args.save_source_directory.mkdir(parents=True)
            for index, frame in enumerate(frames, 1):
                target = args.save_source_directory / f'frame_{index:02d}.png'
                shutil.copyfile(frame.path, target)
                if digest(target) != frame.encoded_sha256:
                    raise ValueError('review copy source binding mismatch')
                saved.append(target)
        measured = analyzer.observe_frames((*prefix, *frames), _build_events=False)
        offset = len(prefix)
        observations = measured.observations[offset:]
        ui = measured.native_ui_measurements[offset:]
        for frame in frames:
            frame.read_image()
        if any(digest(path) != frame.encoded_sha256
               for path, frame in zip(saved, frames, strict=False)):
            raise ValueError('review copy changed during analysis')
    if ((archived and digest(args.archive_manifest) != manifest_hash)
            or analyzer.fingerprint() != profile or global_recognizer_fingerprint() != code):
        raise ValueError('terminal diagnostic input changed')
    report = {
        'scope': ('Actual analyzer explicit end-window input diagnostic; '
                  'not continuous lifecycle, independent holdout or qualification.'),
        'source_video_sha256': source_hash, 'profile_fingerprint': profile,
        'template_profile_path': str(analyzer.template_profile_path),
        'global_signal_setup': global_signal_setup(analyzer.template_profile),
        'recognizer_fingerprint': code,
        'input_sha256': ({str(args.archive_manifest): manifest_hash} if archived else {}),
        'fresh_native_decode': not archived,
        'window_sec': [args.start, args.end] if not archived else None,
        'native_step_ticks': args.native_step_ticks,
        'native_max_png_bytes': args.native_max_png_bytes,
        'processed_prefix_frames': offset, 'processed_end_frames': len(frames),
        'prefix_gap_not_temporal_evidence': True,
        'rows': [{'pts_sec': frame.time_sec, 'source_pts_ticks': frame.pts_ticks,
                  'source_time_base': str(frame.time_base), 'source_epoch': frame.source_epoch,
                  'source_pixel_sha256': frame.pixel_sha256,
                  'frame_sha256': frame.encoded_sha256, 'observation': observation,
                  'native_ui_measurements': scan}
                 for frame, observation, scan in zip(frames, observations, ui, strict=True)],
        'state_counts': dict(Counter(o['primary_state'] for o in observations)),
        'timer_display_available': sum(o['values'].get('round_time_remaining_display')
                                       is not None for o in observations),
        'score_pair_available': sum(all(type(o['values'].get(k)) is int
                                        for k in ('score_ally', 'score_enemy'))
                                    for o in observations),
        'phase_scan_valid_frames': sum(s['phase_scan_valid'] for s in ui),
        'round_result_matched_frames': sum(s['round_result_matched'] for s in ui),
        'qualification_created': False, 'released_events': 0,
        'source_review_directory': (str(args.save_source_directory)
                                    if args.save_source_directory is not None else None),
        'review_before_predictions_claimed': False,
        'canonical_current': None, 'canonical_delta': None,
        'previous_comparable_run': None, 'runtime_delta': None,
        'wall_clock_sec': time.perf_counter() - started,
    }
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: report[k] for k in (
        'processed_end_frames', 'timer_display_available', 'score_pair_available',
        'round_result_matched_frames', 'wall_clock_sec',
    )}))


if __name__ == '__main__':
    main()
