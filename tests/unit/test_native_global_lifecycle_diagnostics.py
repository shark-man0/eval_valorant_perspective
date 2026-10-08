from __future__ import annotations

import shutil
import subprocess
from fractions import Fraction

import pytest

from scripts.diagnostics.diagnose_native_global_lifecycle import (
    extract_window,
    native_pts_in_window,
    parse_source_pts,
    probe_json,
    verify_native_frames,
)


def showinfo(base="1/15360", frames=((0, 60201), (1, 60457))):
    return f"[showinfo] config in time_base: {base}, frame_rate: 60/1\n" + "\n".join(
        f"[showinfo] n: {n} pts: {tick} pts_time: {tick / 15360:.5f} checksum: dummy"
        for n, tick in frames
    )


def test_source_ticks_are_not_reconstructed_from_rounded_pts_time():
    assert parse_source_pts(showinfo(), Fraction(1, 15360)) == [60201, 60457]


@pytest.mark.parametrize('probed', [
    [1, 2, 3, 4], [3, 4, 5, 6], [1, 2, 4, 3, 6], [],
])
def test_truncated_tail_missing_prefix_or_reordered_probe_is_rejected(probed):
    with pytest.raises(ValueError, match='before and after'):
        native_pts_in_window(probed, Fraction(1, 10), .2, .5)


def test_varying_source_intervals_keep_all_interior_pts_without_fps_assumptions():
    assert native_pts_in_window([1, 2, 3, 5, 7], Fraction(1, 10), .2, .5) == [2, 3, 5]


@pytest.mark.parametrize("log", [
    "", showinfo("1/1000"), showinfo(frames=((0, 1), (2, 2))),
    showinfo(frames=((0, 2), (1, 1))), showinfo(frames=((0, 1), (1, 1))),
])
def test_missing_rebased_unordered_or_duplicate_source_pts_are_rejected(log):
    with pytest.raises(ValueError):
        parse_source_pts(log, Fraction(1, 15360))


@pytest.mark.parametrize("actual,expected,count", [
    ([10], [10], 1), ([10, 20], [10, 15, 20], 2),
    ([10, 20], [10, 20], 1), ([0, 10], [10, 20], 2),
])
def test_skipped_missing_or_rebased_decoded_frames_are_rejected(actual, expected, count):
    with pytest.raises(ValueError):
        verify_native_frames(actual, expected, count)


@pytest.mark.parametrize("gop", [1, 12])
def test_real_ffmpeg_window_keeps_nonzero_origin_and_every_native_pts(tmp_path, gop):
    ffmpeg, ffprobe = shutil.which("ffmpeg"), shutil.which("ffprobe")
    if ffmpeg is None or ffprobe is None:
        pytest.skip("native extraction contract requires local ffmpeg and ffprobe")
    video = tmp_path / "nonzero_origin.mp4"
    subprocess.run([
        ffmpeg, "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
        "testsrc2=size=64x64:rate=60", "-t", "1", "-vf", "setpts=PTS+0.137/TB",
        "-fps_mode", "passthrough", "-c:v", "mpeg4", "-g", str(gop),
        "-threads", "1", str(video),
    ], check=True)
    metadata = probe_json(ffprobe, video, [
        "-show_streams", "-show_entries", "stream=time_base,r_frame_rate",
    ])
    stream = metadata["streams"][0]
    time_base = Fraction(stream["time_base"])
    frames = probe_json(ffprobe, video, [
        "-show_frames", "-show_entries", "frame=best_effort_timestamp",
    ])["frames"]
    all_pts = [int(frame["best_effort_timestamp"]) for frame in frames]
    assert all_pts[0] > 0
    expected = [t for t in all_pts if .2 <= float(t * time_base) <= .5]
    paths, ticks = extract_window(
        ffmpeg, ffprobe, video, tmp_path / "window", .2, .5, time_base,
    )
    assert ticks == expected
    assert len(paths) == len(expected) >= 2
    assert all(path.stat().st_size > 0 for path in paths)
