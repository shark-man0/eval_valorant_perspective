"""Validate lossless cache on all saved native frames; no lifecycle qualification."""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from fractions import Fraction
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.diagnostics.pixel_archive_prototype import KEY_INTERVAL, NativePixelArchive
from valorant_ai_coach.hud.global_lifecycle import global_recognizer_fingerprint
from valorant_ai_coach.video import VideoService
from valorant_ai_coach.video.native import NativeSourceFrame, _sha256


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--video', type=Path, required=True)
    parser.add_argument('--source-report', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--max-bytes', type=int, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('new output required')
    started = time.monotonic()
    raw = args.source_report.read_bytes()
    script = Path(__file__).read_bytes()
    fingerprint = global_recognizer_fingerprint()
    source = json.loads(raw)
    if _sha256(args.video) != source['source_video_sha256']:
        raise ValueError('source video mismatch')
    metadata = VideoService().probe(args.video)
    paths = {int(Path(p).stem.removeprefix('frame_')): Path(p)
             for p in source['native_png_sha256']}
    source_frames = [NativeSourceFrame(
        paths[row['source_pts_ticks']], row['source_pts_ticks'], Fraction(row['source_time_base']),
        row['source_epoch'], row['source_video_sha256'],
        source['native_png_sha256'][str(paths[row['source_pts_ticks']])],
        row['source_pixel_sha256'], metadata.width, metadata.height,
    ) for row in source['windows'][0]['rows']]
    with TemporaryDirectory(prefix='native-archive-validation-') as temporary:
        archive = NativePixelArchive(Path(temporary)/'pixels.bin', max_bytes=args.max_bytes)
        try:
            encode_started = time.monotonic()
            for frame in source_frames:
                archive.append(frame)
            frames = archive.seal()
            encode_sec = time.monotonic()-encode_started
            read_started = time.monotonic()
            for _ in range(2):
                for original, frame in zip(source_frames, frames, strict=True):
                    if (frame.pts_ticks != original.pts_ticks
                            or frame.time_base != original.time_base
                            or frame.source_epoch != original.source_epoch
                            or hashlib.sha256(frame.read_image().tobytes()).hexdigest()
                            != original.pixel_sha256):
                        raise ValueError('source pixel/PTS/epoch mismatch')
            read_sec = time.monotonic()-read_started
            archive.verify()
            size = archive.size_bytes
        finally:
            archive.close()
    if (_sha256(args.video) != source['source_video_sha256']
            or args.source_report.read_bytes() != raw
            or Path(__file__).read_bytes() != script
            or global_recognizer_fingerprint() != fingerprint):
        raise ValueError('terminal inputs changed')
    for frame in source_frames:
        if _sha256(frame.path) != frame.encoded_sha256:
            raise ValueError('terminal source PNG changed')
    original_size = sum(frame.path.stat().st_size for frame in source_frames)
    result = {
        'scope': 'exposed saved pixel-cache diagnostic; no video decode or qualification',
        'source_video_sha256': source['source_video_sha256'],
        'source_report_sha256': hashlib.sha256(raw).hexdigest(),
        'script_sha256': hashlib.sha256(script).hexdigest(), 'recognizer_fingerprint': fingerprint,
        'processed_frames': len(frames), 'key_interval': KEY_INTERVAL,
        'original_png_bytes': original_size, 'archive_bytes': size,
        'storage_delta_bytes': size-original_size,
        'storage_delta_percent': 100*(size/original_size-1),
        'encode_wall_sec': encode_sec, 'two_read_passes_wall_sec': read_sec,
        'wall_clock_sec': time.monotonic()-started, 'read_passes': 2,
        'pixel_mismatches': 0, 'pts_mismatches': 0, 'temporary_cache_removed': True,
        'decoder_archive_connection_implemented': False, 'recognizer_executed': False,
        'qualification_created': False, 'canonical_current': None, 'canonical_delta': None,
    }
    args.output.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
