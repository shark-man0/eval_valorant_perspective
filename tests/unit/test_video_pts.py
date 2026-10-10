import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from valorant_ai_coach.video import VideoMetadata, VideoProbeError, VideoService


def test_pts_preserves_stream_offset_vfr_and_invalidates_cache(tmp_path, monkeypatch):
    path = tmp_path / "sample.mp4"
    path.write_bytes(b"sample")
    calls = []

    def probe(command, timeout, cancel):
        calls.append(command)
        return SimpleNamespace(returncode=0, stdout=json.dumps({"frames": [
            {"best_effort_timestamp_time": t} for t in ["0.036003", "0.05267", "0.10267"]
        ]}))

    monkeypatch.setattr("valorant_ai_coach.video.service._run_cancellable_process", probe)
    service = VideoService()
    assert service.presentation_times(path) == (0.036003, 0.05267, 0.10267)
    service.presentation_times(path)
    assert len(calls) == 1
    path.write_bytes(b"changed video")
    service.presentation_times(path)
    assert len(calls) == 2


@pytest.mark.parametrize("points", [[], ["nan"], ["-0.1"], ["1", "0"], ["1", "1"]])
def test_pts_rejects_invalid_timeline(tmp_path: Path, monkeypatch, points):
    path = tmp_path / "sample.mp4"
    path.write_bytes(b"sample")
    monkeypatch.setattr(
        "valorant_ai_coach.video.service._run_cancellable_process",
        lambda *_: SimpleNamespace(returncode=0, stdout=json.dumps({"frames": [
            {"best_effort_timestamp_time": t} for t in points
        ]})),
    )
    with pytest.raises(VideoProbeError):
        VideoService().presentation_times(path)


def test_extraction_uses_nearest_pts_and_decoded_image_index(tmp_path, monkeypatch):
    path = tmp_path / "sample.mp4"
    path.write_bytes(b"sample")
    captured_indices = []

    class Capture:
        index = 0

        def isOpened(self):
            return True

        def get(self, prop):
            return self.index if prop == 1 else 60

        def grab(self):
            self.index += 1
            return True

        def read(self):
            frame = self.index
            self.index += 1
            return True, frame

        def release(self):
            pass

    def write(path, frame, params):
        captured_indices.append(frame)
        Path(path).write_bytes(b"image")
        return True

    cv = SimpleNamespace(VideoCapture=lambda _: Capture(), CAP_PROP_POS_FRAMES=1,
                         CAP_PROP_FPS=2, IMWRITE_JPEG_QUALITY=3, imwrite=write)
    service = VideoService(cv2_module=cv)
    monkeypatch.setattr(service, "presentation_times", lambda *a, **kw: (.036, .053, .110))
    metadata = VideoMetadata(path, 1, 10, 10, 60, "h264", None, False, 6)
    samples = service.extract_frames(path, [0, .105], tmp_path / "out", metadata=metadata)
    assert [s.time_sec for s in samples] == [.036, .110]
    assert captured_indices == [0, 2]


def test_full_decode_has_separate_bounded_timeout_and_remains_cancellable(tmp_path, monkeypatch):
    from threading import Event

    path = tmp_path / "sample.mp4"
    path.write_bytes(b"sample")
    cancellation = Event()
    calls = []

    def probe(command, timeout, cancel):
        calls.append((timeout, cancel))
        return SimpleNamespace(returncode=0, stdout=json.dumps({"frames": [
            {"best_effort_timestamp_time": "0.036003"}
        ]}))

    monkeypatch.setattr("valorant_ai_coach.video.service._run_cancellable_process", probe)
    service = VideoService()
    assert service.timeout_sec == 45.0
    assert service.presentation_times(path, cancel_event=cancellation) == (0.036003,)
    assert calls == [(1800.0, cancellation)]
    VideoService(pts_timeout_sec=600.0).presentation_times(path, cancel_event=cancellation)
    assert calls[-1] == (600.0, cancellation)


def test_probe_keeps_integer_ticks_without_changing_public_pts(tmp_path, monkeypatch):
    import hashlib

    path = tmp_path / 'sample.mp4'
    path.write_bytes(b'unedited-source')
    monkeypatch.setattr(
        'valorant_ai_coach.video.service._run_cancellable_process',
        lambda *_: SimpleNamespace(returncode=0, stdout=json.dumps({
            'streams': [{'time_base': '1/15360'}],
            'frames': [{'best_effort_timestamp_time': '.036003',
                        'best_effort_timestamp': 553}],
        })),
    )
    service = VideoService()
    assert service.presentation_times(path) == (.036003,)
    assert service._tick_cache[1:] == (
        (553,), '1/15360', hashlib.sha256(path.read_bytes()).hexdigest(),
    )
