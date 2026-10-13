from __future__ import annotations

# The repository root is added below so script modules can be imported in pytest.
# ruff: noqa: E402, I001

import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.e2e.probe_cache import CachedVideoService
from valorant_ai_coach.video import AudioTrackMetadata, VideoMetadata


SOURCE_HASH = hashlib.sha256(b"video").hexdigest()
PROBE_FINGERPRINT = hashlib.sha256(b"ffprobe and timeline policy").hexdigest()


class FakeVideoService:
    def __init__(self, path: Path) -> None:
        self.path = path.resolve()
        self.probe_calls = 0
        self.pts_calls = 0
        self._pts_cache = None

    @staticmethod
    def _require_video(path: Path) -> Path:
        path = Path(path).resolve()
        if not path.is_file():
            raise FileNotFoundError(path)
        return path

    def probe(self, path: Path, *, cancel_event=None) -> VideoMetadata:
        self.probe_calls += 1
        return VideoMetadata(self._require_video(path), 12.5, 1920, 1080, 59.94,
                             "h264", "aac", True, 1234,
                             (AudioTrackMetadata(1, "aac", "en", "main", True),))

    def presentation_times(self, path: Path, *, cancel_event=None) -> tuple[float, ...]:
        self.pts_calls += 1
        return (0.0, 0.017, 0.034)

    def extract_frames(self, *args, **kwargs):
        return self._pts_cache[1] if self._pts_cache is not None else None


def test_probe_and_pts_survive_service_recreation_and_rebind_path(tmp_path: Path) -> None:
    video_path = tmp_path / "recording.mp4"
    video_path.write_bytes(b"video")
    cache_dir = tmp_path / "cache"
    first_backend = FakeVideoService(video_path)
    first = CachedVideoService(first_backend, cache_dir, SOURCE_HASH, PROBE_FINGERPRINT)

    original = first.probe(video_path)
    original_pts = first.presentation_times(video_path)
    assert original.path == video_path.resolve()
    assert original.audio_tracks == (AudioTrackMetadata(1, "aac", "en", "main", True),)
    assert original_pts == (0.0, 0.017, 0.034)

    second_backend = FakeVideoService(video_path)
    second = CachedVideoService(second_backend, cache_dir, SOURCE_HASH, PROBE_FINGERPRINT)
    assert second.probe(video_path) == original
    assert second.presentation_times(video_path) == original_pts
    assert second_backend.probe_calls == second_backend.pts_calls == 0
    assert second.stats == {"hits": 2, "misses": 0, "writes": 0}


def test_cached_pts_are_installed_before_extraction(tmp_path: Path) -> None:
    video_path = tmp_path / "recording.mp4"
    video_path.write_bytes(b"video")
    backend = FakeVideoService(video_path)
    service = CachedVideoService(backend, tmp_path / "cache", SOURCE_HASH, PROBE_FINGERPRINT)

    assert service.extract_frames(video_path, (0.01,), tmp_path / "frames") == (
        0.0, 0.017, 0.034
    )
    assert backend.pts_calls == 1
    assert backend._pts_cache[1] == (0.0, 0.017, 0.034)


def test_exact_source_ticks_survive_service_recreation(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from valorant_ai_coach.video import VideoService

    path = tmp_path / "recording.mp4"
    path.write_bytes(b"video")
    calls = []

    def probe(*args):
        calls.append(args)
        return SimpleNamespace(returncode=0, stdout=json.dumps({
            "streams": [{"time_base": "1/15360"}],
            "frames": [
                {"best_effort_timestamp_time": ".036003", "best_effort_timestamp": 553},
                {"best_effort_timestamp_time": ".052669", "best_effort_timestamp": 809},
            ],
        }))

    monkeypatch.setattr("valorant_ai_coach.video.service._run_cancellable_process", probe)
    backend = VideoService()
    cold = CachedVideoService(backend, tmp_path / "cache", SOURCE_HASH, PROBE_FINGERPRINT)
    expected = cold.presentation_times(path)
    assert backend._tick_cache is not None
    identity = backend._tick_cache
    recreated = VideoService()
    warm = CachedVideoService(recreated, tmp_path / "cache", SOURCE_HASH, PROBE_FINGERPRINT)
    assert warm.presentation_times(path) == expected
    assert recreated._tick_cache == identity
    assert len(calls) == 1


@pytest.mark.parametrize("fault", ["source", "count", "repeat", "boolean", "base", "pts"])
def test_corrupt_exact_identity_is_refreshed_not_relabelled_legacy(tmp_path, fault):
    path = tmp_path / "recording.mp4"
    path.write_bytes(b"video")
    backend = FakeVideoService(path)
    service = CachedVideoService(backend, tmp_path / "cache", SOURCE_HASH, PROBE_FINGERPRINT)
    payload = {"points": [0.0, .017, .034], "ticks": [0, 17, 34],
               "time_base": "1/1000", "source_sha256": SOURCE_HASH}
    if fault == "source":
        payload["source_sha256"] = "0" * 64
    elif fault == "count":
        payload["ticks"] = [0]
    elif fault == "repeat":
        payload["ticks"] = [0, 17, 17]
    elif fault == "boolean":
        payload["ticks"] = [False, 17, 34]
    elif fault == "base":
        payload["time_base"] = "0/1"
    else:
        payload["ticks"] = [0, 170, 340]
    service._save("pts", payload)
    assert service.presentation_times(path) == (0.0, .017, .034)
    assert backend.pts_calls == 1
    assert backend._tick_cache is None


def test_legacy_float_cache_cannot_inherit_another_source_identity(tmp_path):
    path = tmp_path / "recording.mp4"
    path.write_bytes(b"video")
    backend = FakeVideoService(path)
    backend._tick_cache = (("other", 5, 0), (0, 17, 34), "1/1000", SOURCE_HASH)
    service = CachedVideoService(backend, tmp_path / "cache", SOURCE_HASH, PROBE_FINGERPRINT)
    service._save("pts", [0.0, .017, .034])
    assert service.presentation_times(path) == (0.0, .017, .034)
    assert backend.pts_calls == 0
    assert backend._tick_cache is None


@pytest.mark.parametrize(
    "bad_pts",
    [[], [0.0, 0.0], [0.2, 0.1], [float("nan")], [float("inf")], [-0.1]],
)
def test_invalid_cached_pts_is_a_miss_then_replaced(tmp_path: Path, bad_pts: list[float]) -> None:
    video_path = tmp_path / "recording.mp4"
    video_path.write_bytes(b"video")
    service = CachedVideoService(FakeVideoService(video_path), tmp_path / "cache",
                                 SOURCE_HASH, PROBE_FINGERPRINT)
    cache_path = service._path("pts")
    payload = json.dumps(bad_pts, allow_nan=True, separators=(",", ":"))
    envelope = {"version": 1, "kind": "pts", "payload": bad_pts,
                "payload_sha256": hashlib.sha256(payload.encode()).hexdigest()}
    cache_path.write_text(json.dumps(envelope), encoding="utf-8")

    assert service.presentation_times(video_path) == (0.0, 0.017, 0.034)
    assert service.stats["misses"] == 1


def test_corrupt_envelope_and_different_fingerprint_are_misses(tmp_path: Path) -> None:
    video_path = tmp_path / "recording.mp4"
    video_path.write_bytes(b"video")
    cache_dir = tmp_path / "cache"
    first = CachedVideoService(FakeVideoService(video_path), cache_dir, SOURCE_HASH,
                               PROBE_FINGERPRINT)
    first.presentation_times(video_path)
    first._path("pts").write_text("{}", encoding="utf-8")
    backend = FakeVideoService(video_path)
    second_fingerprint = hashlib.sha256(b"other probe version").hexdigest()
    second = CachedVideoService(backend, cache_dir, SOURCE_HASH, second_fingerprint)

    assert second.presentation_times(video_path) == (0.0, 0.017, 0.034)
    assert backend.pts_calls == 1


@pytest.mark.parametrize("value", ["x" * 64, "a" * 63])
def test_invalid_fingerprints_are_rejected(tmp_path: Path, value: str) -> None:
    with pytest.raises(ValueError):
        CachedVideoService(FakeVideoService(tmp_path), tmp_path / "cache", SOURCE_HASH, value)
