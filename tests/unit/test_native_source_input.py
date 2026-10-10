import hashlib
import json
import shutil
import subprocess
from fractions import Fraction
from pathlib import Path

import pytest

from valorant_ai_coach.video import VideoProbeError, VideoService
from valorant_ai_coach.video.native import decoded_source_ticks


def make_video(tmp_path):
    ffmpeg, ffprobe = shutil.which('ffmpeg'), shutil.which('ffprobe')
    if ffmpeg is None or ffprobe is None:
        pytest.skip('verified native decoder needs FFmpeg and ffprobe')
    path = tmp_path / 'native.mp4'
    subprocess.run([
        ffmpeg, '-hide_banner', '-loglevel', 'error', '-f', 'lavfi', '-i',
        'testsrc2=size=64x64:rate=60', '-t', '1', '-vf',
        'select=not(eq(mod(n\\,3)\\,1)),setpts=PTS+0.137/TB',
        '-fps_mode', 'passthrough', '-c:v', 'mpeg4', '-g', '12', '-threads', '1',
        str(path),
    ], check=True)
    source_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    result = subprocess.run([
        ffprobe, '-v', 'error', '-select_streams', 'v:0', '-show_frames',
        '-show_streams', '-show_entries', 'frame=best_effort_timestamp:stream=time_base',
        '-of', 'json', str(path),
    ], check=True, capture_output=True, text=True)
    probed = json.loads(result.stdout)
    return path, source_hash, probed


@pytest.fixture
def video(tmp_path):
    return make_video(tmp_path)


def window(video, **kwargs):
    path, digest, _ = video
    return VideoService().native_window(
        path, start_sec=.2, end_sec=.5, source_video_sha256=digest, **kwargs,
    )


def test_lossless_input_preserves_every_variable_interval_and_nonzero_origin(video):
    _, source_hash, probed = video
    timebase = Fraction(probed['streams'][0]['time_base'])
    expected = [int(frame['best_effort_timestamp']) for frame in probed['frames']
                if .2 <= float(int(frame['best_effort_timestamp']) * timebase) <= .5]
    with window(video) as frames:
        assert [frame.pts_ticks for frame in frames] == expected
        assert len(set(b-a for a, b in zip(expected, expected[1:], strict=False))) > 1
        assert len({frame.source_epoch for frame in frames}) == 1
        for frame in frames:
            assert frame.source_video_sha256 == source_hash
            assert frame.time_sec == float(frame.pts_ticks * timebase)
            assert frame.read_image().shape == (64, 64, 3)
        paths = [frame.path for frame in frames]
    assert all(not path.exists() for path in paths)


def test_new_decode_window_owns_a_new_epoch(video):
    with window(video) as frames:
        first_epoch = frames[0].source_epoch
    with window(video) as frames:
        assert frames[0].source_epoch != first_epoch


def test_native_encoded_asset_mutation_is_rejected(video):
    with window(video) as frames:
        frames[0].path.write_bytes(frames[0].path.read_bytes() + b'changed')
        with pytest.raises(VideoProbeError, match='asset changed'):
            frames[0].read_image()


def test_native_source_change_during_consumption_is_rejected(video):
    path, _, _ = video
    with pytest.raises(VideoProbeError, match='during consumption'), window(video):
        path.write_bytes(path.read_bytes() + b'changed')


def test_source_hash_mismatch_rejects_before_probe_or_decode(video, monkeypatch):
    path, _, _ = video
    monkeypatch.setattr(subprocess, 'run', lambda *a, **k: pytest.fail('unexpected decoder'))
    with pytest.raises(VideoProbeError, match='SHA256 mismatch'), VideoService().native_window(
        path, start_sec=.2, end_sec=.5, source_video_sha256='0'*64,
    ):
        pytest.fail('unexpected consumer')


def test_truncated_probe_cannot_limit_decode_to_a_matching_prefix(video, monkeypatch):
    _, _, probed = video
    timebase = Fraction(probed['streams'][0]['time_base'])
    selected = [int(frame['best_effort_timestamp']) for frame in probed['frames']
                if .2 <= float(int(frame['best_effort_timestamp']) * timebase) <= .5]
    original = subprocess.run

    def truncated(command, **kwargs):
        result = original(command, **kwargs)
        if '-read_intervals' in command and '-show_frames' in command:
            data = json.loads(result.stdout)
            data['frames'] = [frame for frame in data['frames']
                              if int(frame['best_effort_timestamp']) != selected[-1]]
            return subprocess.CompletedProcess(command, 0, json.dumps(data), result.stderr)
        return result

    monkeypatch.setattr(subprocess, 'run', truncated)
    with pytest.raises(VideoProbeError, match='all native source PTS'), window(video):
        pytest.fail('a truncated probe must not reach the consumer')


@pytest.mark.parametrize('start,end', [(True, .5), (.5, .2), (-1, .5), (0, float('nan'))])
def test_invalid_window_is_rejected_before_source_access(tmp_path, start, end):
    from valorant_ai_coach.video.native import decode_native_window

    with pytest.raises(ValueError), decode_native_window(
        tmp_path/'missing.mp4', start_sec=start, end_sec=end,
        source_video_sha256='0'*64, ffmpeg='unused', ffprobe='unused',
    ):
        pytest.fail('unexpected consumer')


@pytest.mark.parametrize('log', [
    '', '[showinfo] config in time_base: 1/1000\nn: 0 pts: 256 pts_time: .017',
    '[showinfo] config in time_base: 1/15360\nn: 1 pts: 256 pts_time: .017',
    '[showinfo] config in time_base: 1/15360\nn: 0 pts: 256 pts_time: .017\n'
    'n: 1 pts: 256 pts_time: .017',
])
def test_decoder_log_rejects_missing_rebased_unordered_or_duplicate_pts(log):
    with pytest.raises(VideoProbeError):
        decoded_source_ticks(log, Fraction(1, 15360))


def test_decoder_ticks_never_use_rounded_pts_time():
    log = '[showinfo] config in time_base: 1/15360\nn: 0 pts: 59945 pts_time: 3.90\n'
    log += 'n: 1 pts: 60201 pts_time: 3.92'
    assert decoded_source_ticks(log, Fraction(1, 15360)) == (59945, 60201)


def test_qualification_code_fingerprint_includes_native_decoder(monkeypatch):
    from valorant_ai_coach.hud.global_lifecycle import global_recognizer_fingerprint

    before = global_recognizer_fingerprint()
    original = Path.read_bytes

    def changed(path):
        content = original(path)
        return content + b'\n# synthetic decoder mutation\n' if (
            path.name == 'native.py' and path.parent.name == 'video'
        ) else content

    monkeypatch.setattr(Path, 'read_bytes', changed)
    assert global_recognizer_fingerprint() != before


@pytest.mark.parametrize('start', [0, .2])
def test_explicit_eof_preserves_every_remaining_native_pts(video, start):
    path, digest, probed = video
    timebase = Fraction(probed['streams'][0]['time_base'])
    expected = [int(f['best_effort_timestamp']) for f in probed['frames']
                if float(int(f['best_effort_timestamp'])*timebase) >= start]
    with VideoService().native_window(
        path, start_sec=start, end_sec=None, source_video_sha256=digest,
    ) as frames:
        assert [f.pts_ticks for f in frames] == expected
        assert frames[-1].pts_ticks == int(probed['frames'][-1]['best_effort_timestamp'])
        assert len({f.source_epoch for f in frames}) == 1
        assert frames[0].time_sec > 0  # Preserve the source's nonzero origin.
        paths = [f.path for f in frames]
        assert all(f.read_image().shape == (64, 64, 3) for f in frames)
    assert all(not p.exists() for p in paths)


def test_physical_origin_supports_bounded_prefix_without_inventing_zero_frame(video):
    path, digest, probed = video
    timebase = Fraction(probed['streams'][0]['time_base'])
    expected = [int(f['best_effort_timestamp']) for f in probed['frames']
                if float(int(f['best_effort_timestamp'])*timebase) <= .5]
    with VideoService().native_window(
        path, start_sec=0, end_sec=.5, source_video_sha256=digest,
    ) as frames:
        assert [f.pts_ticks for f in frames] == expected
        assert frames[0].pts_ticks > 0


def test_eof_truncated_probe_tail_withholds_all_decoded_frames(video, monkeypatch):
    path, digest, _ = video
    original = subprocess.run

    def truncated(command, **kwargs):
        result = original(command, **kwargs)
        if '-show_frames' in command:
            data = json.loads(result.stdout)
            data['frames'] = data['frames'][:-1]
            return subprocess.CompletedProcess(command, 0, json.dumps(data), result.stderr)
        return result

    monkeypatch.setattr(subprocess, 'run', truncated)
    context = VideoService().native_window(
        path, start_sec=0, end_sec=None, source_video_sha256=digest,
    )
    with pytest.raises(VideoProbeError, match='all native source PTS'), context:
        pytest.fail('no truncated EOF prefix may reach a consumer')


def test_numeric_end_at_last_frame_still_requires_explicit_eof(video):
    path, digest, probed = video
    timebase = Fraction(probed['streams'][0]['time_base'])
    last = float(int(probed['frames'][-1]['best_effort_timestamp'])*timebase)
    with pytest.raises(VideoProbeError, match='both sides'), VideoService().native_window(
        path, start_sec=0, end_sec=last, source_video_sha256=digest,
    ):
        pytest.fail('a missing interior endpoint witness is not implicit EOF')


def test_negative_physical_source_origin_is_rejected_without_skipping_frames(video, monkeypatch):
    path, digest, _ = video
    original = subprocess.run

    def negative_origin(command, **kwargs):
        assert '-show_streams' in command or '-show_frames' in command
        result = original(command, **kwargs)
        if '-show_frames' in command:
            data = json.loads(result.stdout)
            data['frames'][0]['best_effort_timestamp'] = -1
            return subprocess.CompletedProcess(command, 0, json.dumps(data), result.stderr)
        return result

    monkeypatch.setattr(subprocess, 'run', negative_origin)
    context = VideoService().native_window(
        path, start_sec=0, end_sec=None, source_video_sha256=digest,
    )
    with pytest.raises(VideoProbeError, match='negative native source origin'), context:
        pytest.fail('negative source frames cannot be silently omitted')


def test_opt_in_png_prediction_preserves_native_pixels_pts_and_timebase(video):
    with window(video) as frames:
        baseline = [(f.pts_ticks, f.time_base, f.pixel_sha256, f.read_image()) for f in frames]
    with window(video, png_prediction='up') as frames:
        assert len(frames) == len(baseline)
        for frame, (tick, timebase, digest, image) in zip(frames, baseline, strict=True):
            assert frame.pts_ticks == tick and frame.time_base == timebase
            assert frame.pixel_sha256 == digest
            assert (frame.read_image() == image).all()


@pytest.mark.parametrize('prediction', ['', 'mixed', 'lossy', None])
def test_unknown_png_prediction_rejected_before_source_access(tmp_path, prediction):
    from valorant_ai_coach.video.native import decode_native_window

    with pytest.raises(ValueError, match='PNG prediction'), decode_native_window(
        tmp_path/'missing.mp4', start_sec=0, end_sec=None,
        source_video_sha256='0'*64, ffmpeg='unused', ffprobe='unused',
        png_prediction=prediction,
    ):
        pytest.fail('invalid codec setting must not access source')


def test_budgeted_pipe_preserves_complete_native_source_data(video):
    path, digest, _ = video
    with VideoService().native_window(
        path, start_sec=0, end_sec=None, source_video_sha256=digest, png_prediction='up',
    ) as frames:
        baseline = [(f.pts_ticks, f.pixel_sha256) for f in frames]
    with VideoService().native_window(
        path, start_sec=0, end_sec=None, source_video_sha256=digest,
        png_prediction='up', max_png_bytes=1000000,
    ) as frames:
        assert [(f.pts_ticks, f.pixel_sha256) for f in frames] == baseline
        assert len({f.source_epoch for f in frames}) == 1
        assert sum(f.path.stat().st_size for f in frames) <= 1000000
        paths = [f.path for f in frames]
        assert all(f.read_image().shape == (64, 64, 3) for f in frames)
    assert all(not p.exists() for p in paths)


def test_budget_overflow_never_yields_partial_frames_and_removes_files(video, monkeypatch):
    import valorant_ai_coach.video.native as native

    path, digest, _ = video
    original = native._write_png_pipe
    directory_seen = []

    def budgeted(stream, directory, max_bytes):
        directory_seen.append(directory)
        try:
            return original(stream, directory, max_bytes)
        finally:
            assert sum(p.stat().st_size for p in directory.glob('frame_*.png')) <= max_bytes

    monkeypatch.setattr(native, '_write_png_pipe', budgeted)
    with pytest.raises(VideoProbeError, match='budget exceeded'), VideoService().native_window(
        path, start_sec=0, end_sec=None, source_video_sha256=digest, max_png_bytes=50,
    ):
        pytest.fail('no partial decode may reach the consumer')
    assert len(directory_seen) == 1
    assert not directory_seen[0].exists()


@pytest.mark.parametrize('budget', [0, -1, True, 100.0])
def test_invalid_storage_budget_rejected_before_source_access(tmp_path, budget):
    from valorant_ai_coach.video.native import decode_native_window

    with pytest.raises(ValueError, match='storage budget'), decode_native_window(
        tmp_path/'missing.mp4', start_sec=0, end_sec=None,
        source_video_sha256='0'*64, ffmpeg='unused', ffprobe='unused', max_png_bytes=budget,
    ):
        pytest.fail('invalid budget must not access source')


def test_png_pipe_exact_budget_multiple_frames_and_truncation(tmp_path):
    from io import BytesIO

    import cv2
    import numpy as np

    from valorant_ai_coach.video.native import _write_png_pipe

    ok, encoded = cv2.imencode('.png', np.zeros((24, 32, 3), np.uint8))
    assert ok
    data = encoded.tobytes()
    directory = tmp_path/'exact'
    directory.mkdir()
    assert _write_png_pipe(BytesIO(data+data), directory, 2*len(data)) == 2
    assert sum(p.stat().st_size for p in directory.glob('frame_*.png')) == 2*len(data)
    directory = tmp_path/'truncated'
    directory.mkdir()
    with pytest.raises(VideoProbeError, match='truncated'):
        _write_png_pipe(BytesIO(data[:-1]), directory, 1000000)


def test_png_pipe_handles_fragmented_reads_and_rejects_invalid_signature(tmp_path):
    from io import BytesIO

    import cv2
    import numpy as np

    from valorant_ai_coach.video.native import _write_png_pipe

    class Fragmented(BytesIO):
        def read(self, size=-1):
            return super().read(min(size, 3))

    ok, encoded = cv2.imencode('.png', np.zeros((24, 32, 3), np.uint8))
    assert ok
    assert _write_png_pipe(Fragmented(encoded.tobytes()), tmp_path, 1000000) == 1
    with pytest.raises(VideoProbeError, match='signature mismatch'):
        _write_png_pipe(BytesIO(b'not-a-png'), tmp_path, 1000000)


def test_budgeted_encoder_timeout_terminates_once_and_closes_pipe(tmp_path, monkeypatch):
    import sys

    from valorant_ai_coach.video.native import _decode_budgeted_pngs

    started = []
    original = subprocess.Popen

    def tracked(*args, **kwargs):
        process = original(*args, **kwargs)
        started.append(process)
        return process

    monkeypatch.setattr(subprocess, 'Popen', tracked)
    with (tmp_path/'timeout.log').open('w') as log, pytest.raises(subprocess.TimeoutExpired):
        _decode_budgeted_pngs(
            [sys.executable, '-c', 'import time; time.sleep(60)'],
            tmp_path, log, 1000000, .1,
        )
    assert len(started) == 1
    assert started[0].returncode is not None
    assert started[0].stdout.closed


def test_budgeted_pipe_coverage_still_rejects_truncated_probe(video, monkeypatch):
    path, digest, _ = video
    original = subprocess.run

    def truncated(command, **kwargs):
        result = original(command, **kwargs)
        if '-show_frames' in command:
            data = json.loads(result.stdout)
            data['frames'] = data['frames'][:-1]
            return subprocess.CompletedProcess(command, 0, json.dumps(data), result.stderr)
        return result

    monkeypatch.setattr(subprocess, 'run', truncated)
    context = VideoService().native_window(
        path, start_sec=0, end_sec=None, source_video_sha256=digest, max_png_bytes=1000000,
    )
    with pytest.raises(VideoProbeError, match='all native source PTS'), context:
        pytest.fail('a matching truncated budgeted prefix is never accepted')
