import hashlib
import shutil
import subprocess

import numpy as np
import pytest

from valorant_ai_coach.video import VideoService
from valorant_ai_coach.video.native_replay import decode_native_replay
from valorant_ai_coach.video.service import VideoProbeError


@pytest.fixture
def source(tmp_path):
    ffmpeg, ffprobe = shutil.which('ffmpeg'), shutil.which('ffprobe')
    if not ffmpeg or not ffprobe:
        pytest.skip('FFmpeg/ffprobe required for native decoder contract test')
    path = tmp_path / 'source.mkv'
    subprocess.run([ffmpeg, '-v', 'error', '-f', 'lavfi', '-i',
                    'testsrc=size=64x48:rate=3', '-t', '2', '-c:v', 'ffv1', str(path)],
                   check=True, capture_output=True, timeout=30)
    return path, {'ffmpeg': ffmpeg, 'ffprobe': ffprobe,
                  'source_video_sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def test_replay_matches_png_pixels_pts_and_supports_repeated_passes(source):
    path, options = source
    with VideoService().native_window(
        path, start_sec=0, end_sec=None, source_video_sha256=options['source_video_sha256'],
        max_png_bytes=1_000_000,
    ) as pngs:
        expected = [(p.pts_ticks, p.time_base, p.pixel_sha256) for p in pngs]
    with decode_native_replay(path, **options, max_buffer_bytes=64 * 48 * 3 * 3) as frames:
        assert [(f.pts_ticks, f.time_base, f.pixel_sha256) for f in frames] == expected
        assert len({f.source_epoch for f in frames}) == 1
        for order in (range(len(frames)), range(len(frames)), [2, 0, 5, 1]):
            for index in order:
                image = frames[index].read_image()
                assert hashlib.sha256(image.tobytes()).hexdigest() == frames[index].pixel_sha256
                assert len(frames[index].owner.cache) <= 1
        # Exposed arrays are copies, never mutable aliases of trusted cache data.
        image = frames[1].read_image()
        image[:] = 0
        assert np.any(frames[1].read_image())
    with pytest.raises(VideoProbeError, match='after context exit'):
        frames[0].read_image()


def test_replay_rejects_source_change_at_terminal_even_with_cached_frame(source):
    path, options = source
    with (
        pytest.raises(VideoProbeError, match='source changed'),
        decode_native_replay(path, **options) as frames,
    ):
        frames[0].read_image()
        path.write_bytes(path.read_bytes() + b'changed')


def test_replay_rejects_changed_pixels_and_clears_cache(source):
    path, options = source
    with (
        pytest.raises(VideoProbeError, match='pixels changed'),
        decode_native_replay(path, **options) as frames,
    ):
        frames[0].owner.hashes[0] = '0' * 64
        frames[0].read_image()
    assert frames[0].owner.closed
    assert not frames[0].owner.cache


def test_replay_requires_full_pts_verification_before_exposing_handles(source, monkeypatch):
    import valorant_ai_coach.video.native_replay as module

    path, options = source
    parse = module.decoded_source_ticks
    monkeypatch.setattr(module, 'decoded_source_ticks', lambda text, base: parse(text, base)[:-1])
    with (
        pytest.raises(VideoProbeError, match='PTS coverage changed'),
        decode_native_replay(path, **options),
    ):
        pytest.fail('unverified source handles exposed')


def test_replay_rejects_invalid_budget_and_timeout(source):
    path, options = source
    with (
        pytest.raises(ValueError, match='three raw frames'),
        decode_native_replay(path, **options, max_buffer_bytes=10),
    ):
        pytest.fail('invalid budget accepted')
    with (
        pytest.raises(ValueError, match='timeout'),
        decode_native_replay(path, **options, timeout_sec=float('nan')),
    ):
        pytest.fail('invalid timeout accepted')


def test_replay_probe_uses_single_decoder_thread(source, monkeypatch):
    path, options = source
    original = subprocess.run
    commands = []

    def tracked(command, **kwargs):
        commands.append(command)
        return original(command, **kwargs)

    monkeypatch.setattr(subprocess, 'run', tracked)
    with decode_native_replay(path, **options) as frames:
        assert len(frames) == 6
    probe = next(c for c in commands if '-show_frames' in c)
    assert probe[probe.index('-threads') + 1] == '1'
