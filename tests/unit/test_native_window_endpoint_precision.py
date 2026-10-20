"""Real decoder regressions for inclusive windows on exact source PTS."""
import hashlib
import json
import shutil
import subprocess
from fractions import Fraction

import pytest

from valorant_ai_coach.video import VideoService


@pytest.fixture
def decimal_endpoint_video(tmp_path):
    ffmpeg, ffprobe = shutil.which('ffmpeg'), shutil.which('ffprobe')
    if ffmpeg is None or ffprobe is None:
        pytest.skip('native endpoint integration needs FFmpeg and ffprobe')
    path = tmp_path/'endpoint.mp4'
    subprocess.run([
        ffmpeg, '-hide_banner', '-loglevel', 'error', '-f', 'lavfi', '-i',
        'testsrc2=size=64x64:rate=60', '-frames:v', '120', '-vf',
        'setpts=PTS+220/TB', '-fps_mode', 'passthrough', '-c:v', 'mpeg4',
        '-g', '12', '-threads', '1', '-video_track_timescale', '15360', str(path),
    ], check=True, capture_output=True)
    data = json.loads(subprocess.check_output([
        ffprobe, '-v', 'error', '-select_streams', 'v:0', '-show_frames',
        '-show_streams', '-show_entries', 'frame=best_effort_timestamp:stream=time_base',
        '-of', 'json', str(path),
    ]))
    timebase = Fraction(data['streams'][0]['time_base'])
    ticks = tuple(int(f['best_effort_timestamp']) for f in data['frames'])
    assert len(ticks) == 120 and ticks[0]*timebase == 220
    return path, hashlib.sha256(path.read_bytes()).hexdigest(), ticks, timebase


@pytest.mark.parametrize('start,end', [
    (220.8, 221.6),
    (220.800001, 221.599999),
    (220.799999, 221.600001),
    (220.8, None),
])
def test_decimal_bounds_preserve_exact_inclusive_source_frames(decimal_endpoint_video, start, end):
    path, digest, ticks, timebase = decimal_endpoint_video
    expected = tuple(t for t in ticks if Fraction(str(start)) <= t*timebase
                     and (end is None or t*timebase <= Fraction(str(end))))
    with VideoService().native_window(
        path, start_sec=start, end_sec=end, source_video_sha256=digest,
    ) as frames:
        assert tuple(frame.pts_ticks for frame in frames) == expected
        assert all(frame.time_base == timebase for frame in frames)
        assert frames[0].read_image().shape == (64, 64, 3)
        assert frames[-1].read_image().shape == (64, 64, 3)
        if start == 220.8:
            assert frames[0].pts_ticks == 3391488
        if end == 221.6:
            assert frames[-1].pts_ticks == 3403776 and len(frames) == 49
