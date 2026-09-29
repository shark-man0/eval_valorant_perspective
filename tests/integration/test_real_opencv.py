from __future__ import annotations

from pathlib import Path

import pytest

cv2 = pytest.importorskip("cv2")
numpy = pytest.importorskip("numpy")

from valorant_ai_coach.video import VideoMetadata, VideoService  # noqa: E402


def test_real_opencv_extracts_planned_frames(tmp_path: Path) -> None:
    video_path = tmp_path / "fixture.avi"
    writer = cv2.VideoWriter(
        str(video_path),
        cv2.VideoWriter_fourcc(*"MJPG"),
        10.0,
        (64, 48),
    )
    if not writer.isOpened():
        pytest.skip("このOpenCV buildではMJPG VideoWriterを利用できません")
    try:
        for index in range(12):
            frame = numpy.full((48, 64, 3), index * 15, dtype=numpy.uint8)
            writer.write(frame)
    finally:
        writer.release()

    metadata = VideoMetadata(
        path=video_path.resolve(),
        duration_sec=1.2,
        width=64,
        height=48,
        fps=10.0,
        video_codec="mjpeg",
        audio_codec=None,
        has_audio=False,
        file_size=video_path.stat().st_size,
    )
    service = VideoService(cv2_module=cv2)
    service.probe = lambda _path, **_kwargs: metadata  # type: ignore[method-assign]

    frames = service.extract_frames(video_path, [0.0, 0.5, 1.0], tmp_path / "frames")

    assert len(frames) == 3
    assert all(frame.path.is_file() and frame.path.stat().st_size > 0 for frame in frames)
    assert [frame.time_sec for frame in frames] == pytest.approx([0.0, 0.5, 1.0], abs=0.11)
