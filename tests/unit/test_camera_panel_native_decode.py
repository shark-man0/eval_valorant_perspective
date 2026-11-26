"""Camera panel samples are decoded with the acquisition's native FFmpeg decode."""

from __future__ import annotations

import hashlib
import io
import json
import shutil
import subprocess

import cv2
import numpy as np
import pytest

from valorant_ai_coach.temporal import camera_panel


@pytest.fixture
def native_video(tmp_path):
    ffmpeg, ffprobe = shutil.which("ffmpeg"), shutil.which("ffprobe")
    if ffmpeg is None or ffprobe is None:
        pytest.skip("native decode test needs FFmpeg and ffprobe")
    path = tmp_path / "native.mp4"
    subprocess.run([
        ffmpeg, "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
        "testsrc2=size=64x64:rate=60", "-frames:v", "600", "-fps_mode", "passthrough",
        "-c:v", "mpeg4", "-g", "30", "-threads", "1", "-video_track_timescale", "15360",
        str(path),
    ], check=True, capture_output=True)
    data = json.loads(subprocess.check_output([
        ffprobe, "-v", "error", "-select_streams", "v:0", "-show_frames",
        "-show_entries", "frame=best_effort_timestamp", "-of", "json", str(path),
    ]))
    ticks = [int(f["best_effort_timestamp"]) for f in data["frames"]]
    # Reference pixels exactly as the acquisition binds them: native PNG, then imdecode.
    batch = [ticks[30], ticks[150], ticks[420]]
    command = [str(path) if p == "{video}" else p
               for p in camera_panel.native_decode_command(ffmpeg, batch)]
    output = subprocess.run(command, check=True, capture_output=True).stdout
    frames = list(camera_panel.png_frames(io.BytesIO(output)))
    shas = [hashlib.sha256(cv2.imdecode(np.frombuffer(f, np.uint8), cv2.IMREAD_COLOR)
                           .tobytes()).hexdigest() for f in frames]
    assert len(shas) == 3
    return path, batch, shas


def _sample(tick, sha):
    return {"native_time_base": "1/15360", "native_pts_tick": tick,
            "native_pixel_sha256": sha, "sample_sha256": f"s{tick}"}


def test_identical_pixels_are_yielded_and_others_reported_missing(native_video):
    path, ticks, shas = native_video
    samples = [_sample(t, s) for t, s in zip(ticks, shas, strict=True)]
    samples.append(_sample(ticks[1], "0" * 64))  # same frame, different pixels
    samples.append(_sample(ticks[2] + 1, shas[2]))  # no frame at this PTS
    missing: list = []
    found = list(camera_panel.decode_samples(path, samples, missing))
    assert [s["native_pts_tick"] for s, _ in found] == ticks
    assert all(image.shape == (64, 64, 3) for _, image in found)
    assert sorted(s["native_pixel_sha256"][:1] + str(s["native_pts_tick"])
                  for s in missing) == sorted(["0" + str(ticks[1]), shas[2][:1]
                                               + str(ticks[2] + 1)])


def test_decode_command_matches_the_acquisition_native_audit_decode():
    command = camera_panel.native_decode_command("ffmpeg", [15360, 30720])
    assert command[command.index("-ss") + 1] == "1.0"
    assert "-copyts" in command and "-noaccurate_seek" in command
    vf = command[command.index("-vf") + 1]
    assert vf.startswith("trim=end_pts=30721,select=") and vf.endswith(",showinfo")
    assert command[command.index("-c:v") + 1] == "png"
