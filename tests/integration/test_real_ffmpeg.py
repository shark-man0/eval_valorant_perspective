from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest

from valorant_ai_coach.bootstrap import build_services
from valorant_ai_coach.clips import ClipService
from valorant_ai_coach.settings import AppSettings, SettingsStore
from valorant_ai_coach.video import VideoService


def test_real_ffmpeg_generates_bounded_playable_clip(tmp_path: Path) -> None:
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if ffmpeg is None or ffprobe is None:
        pytest.skip("ffmpeg/ffprobe are not installed on this host")

    source = tmp_path / "synthetic source.mp4"
    subprocess.run(
        [
            ffmpeg,
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "testsrc=size=160x90:rate=10",
            "-t",
            "2",
            "-pix_fmt",
            "yuv420p",
            "-y",
            str(source),
        ],
        check=True,
        capture_output=True,
        timeout=30,
    )
    video = VideoService(ffprobe)
    source_metadata = video.probe(source)
    artifact = ClipService(
        ffmpeg_path=ffmpeg,
        ffprobe_path=ffprobe,
        output_dir=tmp_path / "clips",
        video_service=video,
    ).create_clip(source, 0.4, 1.4, source_metadata.duration_sec, "real-clip")

    assert artifact.path.is_file() and artifact.path.stat().st_size > 0
    clip_metadata = video.probe(artifact.path)
    assert clip_metadata.duration_sec == pytest.approx(1.0, abs=0.25)
    assert (clip_metadata.width, clip_metadata.height) == (160, 90)


def test_real_multitrack_video_runs_coach_sqlite_and_shared_clip(tmp_path: Path) -> None:
    ffmpeg, ffprobe = shutil.which("ffmpeg"), shutil.which("ffprobe")
    if ffmpeg is None or ffprobe is None:
        pytest.skip("ffmpeg/ffprobe are not installed on this host")
    source = tmp_path / "three tracks.mp4"
    subprocess.run(
        [
            ffmpeg,
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "testsrc=size=160x90:rate=10",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:sample_rate=48000",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=660:sample_rate=48000",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=880:sample_rate=48000",
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-map",
            "2:a:0",
            "-map",
            "3:a:0",
            "-t",
            "36",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-metadata:s:a:0",
            "language=jpn",
            "-metadata:s:a:1",
            "language=eng",
            "-disposition:a:0",
            "0",
            "-disposition:a:1",
            "default",
            "-disposition:a:2",
            "0",
            "-y",
            str(source),
        ],
        check=True,
        capture_output=True,
        timeout=60,
    )
    store = SettingsStore(tmp_path / "settings.json")
    services = build_services(
        store,
        settings=AppSettings(
            data_dir=tmp_path / "data",
            ffmpeg_path=ffmpeg,
            ffprobe_path=ffprobe,
        ),
    )
    original = services.video.probe(source)
    assert len(original.audio_tracks) == 3
    assert original.audio_tracks[1].is_default
    result = services.pipeline.analyze_video(source, match_id="M-MULTITRACK")
    assert result.status == "completed"
    assert {item["label"] for item in result.rounds[0].output["evaluations"]} == {
        "good",
        "improve",
    }
    clips = services.repository.list_clips(result.match_id)
    assert len(clips) == 2
    assert len({item["file_path"] for item in clips}) == 1
    clip = services.video.probe(Path(clips[0]["file_path"]))
    assert len(clip.audio_tracks) == 3
    assert clip.audio_tracks[1].is_default
    assert [item.language for item in clip.audio_tracks[:2]] == ["jpn", "eng"]
    assert result.analysis_json.is_file()
    assert all(
        Path(item["path"]).is_file()
        for item in services.repository.list_round_packages(result.match_id)[0]["frames"]
    )
    # Use Qt's actual media backend to verify the ordinal audio-track API against
    # the clip's stream metadata (ffprobe indices are not Qt ordinals).
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QUrl
    from PySide6.QtMultimedia import QMediaPlayer, QVideoSink
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    player = QMediaPlayer()
    sink = QVideoSink()
    player.setVideoSink(sink)
    player.setSource(QUrl.fromLocalFile(str(Path(clips[0]["file_path"]))))
    deadline = time.monotonic() + 10
    while len(player.audioTracks()) < 3 and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.01)
    assert player.error() == QMediaPlayer.Error.NoError, player.errorString()
    assert len(player.audioTracks()) == 3
    player.setActiveAudioTrack(2)
    assert player.activeAudioTrack() == 2
    player.play()
    while sink.videoFrame().isValid() is False and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.01)
    assert sink.videoFrame().isValid()
    player.stop()
