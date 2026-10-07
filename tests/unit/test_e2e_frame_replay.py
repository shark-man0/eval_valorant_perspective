from __future__ import annotations

# The repository root is added below so script modules can be imported in pytest.
# ruff: noqa: E402, I001

import hashlib
import sys
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest
import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.e2e import frame_replay
from valorant_ai_coach.video import FrameSample, VideoMetadata


@dataclass(frozen=True)
class FakeCalibration:
    profile: str


class FakeAnalyzer:
    def __init__(self) -> None:
        self.calls: list[tuple[tuple[float, ...], VideoMetadata, tuple[str, ...]]] = []

    def observe_frames(self, frames, *, video_metadata):
        times = tuple(frame.time_sec for frame in frames)
        # This strict signature verifies replay does not forward expected labels.
        self.calls.append((times, video_metadata, ()))
        observations = tuple({"time_sec": t, "observed": True} for t in times)
        return SimpleNamespace(
            observations=observations,
            diagnostics=(f"native:{times[-1]}",),
            calibration=FakeCalibration(f"profile-at-{times[-1]}"),
        )


class FakeVideo:
    def __init__(self, *, shifted_pts: bool = False, invalid_jpeg: bool = False) -> None:
        self.ffprobe_path = "unused-ffprobe"
        # Prevent wrapper extraction from doing a full PTS scan in this fake.
        self._capture_factory = object()
        self.shifted_pts = shifted_pts
        self.invalid_jpeg = invalid_jpeg
        self.decode_calls: list[tuple[float, ...]] = []

    def extract_frames(
        self, path, timestamps_sec, output_dir, *, metadata, max_frames,
        jpeg_quality, max_dimension,
    ):
        requested = tuple(timestamps_sec)
        self.decode_calls.append(requested)
        output_dir.mkdir(parents=True, exist_ok=True)
        result = []
        for index, pts in enumerate(requested):
            actual = pts + (0.0000001 if self.shifted_pts else 0.0)
            image = output_dir / f"frame-{index}.jpg"
            if self.invalid_jpeg:
                image.write_bytes(b"not an image")
            else:
                pixels = np.full((8, 8, 3), int(round(actual * 10)) % 256, dtype=np.uint8)
                assert cv2.imwrite(str(image), pixels)
            result.append(FrameSample(actual, image))
        return result


def _fixture(tmp_path: Path, *, shifted_pts: bool = False, invalid_jpeg: bool = False):
    source = tmp_path / "match.mp4"
    source.write_bytes(b"test video bytes")
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    metadata = VideoMetadata(source.resolve(), 20.0, 1920, 1080, 60.0,
                             "h264", None, False, source.stat().st_size)
    spec = {
        "schema_version": 1,
        "input_scope": "isolated_points",
        "source_sha256": source_hash,
        "calibration_prefix": [0.05, 0.1],
        "pts_sec": [0.25, 4.5, 8.0],
    }
    video = FakeVideo(shifted_pts=shifted_pts, invalid_jpeg=invalid_jpeg)
    analyzer = FakeAnalyzer()
    processor = SimpleNamespace(analyzer=analyzer)
    return source, metadata, spec, video, analyzer, processor


def _fingerprints(monkeypatch) -> tuple[str, str]:
    probe = hashlib.sha256(b"probe fingerprint").hexdigest()
    frame = hashlib.sha256(b"frame fingerprint").hexdigest()
    monkeypatch.setattr(frame_replay, "decoder_fingerprints", lambda _path: (probe, frame))
    return probe, frame


def test_replay_uses_only_genuine_prefix_and_resets_analyzer_context(
    tmp_path: Path, monkeypatch,
) -> None:
    _fingerprints(monkeypatch)
    _source, metadata, spec, video, analyzer, processor = _fixture(tmp_path)

    result = frame_replay.replay_points(
        processor=processor,
        metadata=metadata,
        spec=spec,
        output=tmp_path / "output",
        cache_dir=tmp_path / "cache",
        video=video,
    )

    assert [call[0] for call in analyzer.calls] == [
        (0.05, 0.1, 0.25),
        (0.05, 0.1, 4.5),
        (0.05, 0.1, 8.0),
    ]
    assert all(call[1] is metadata and call[2] == () for call in analyzer.calls)
    assert [row["time_sec"] for row in result.observations] == [0.25, 4.5, 8.0]
    assert [run["calibration"]["profile"] for run in result.calibration_diagnostics["runs"]] == [
        "profile-at-0.25", "profile-at-4.5", "profile-at-8.0",
    ]
    assert result.round_packages == result.hud_events == result.visual_events == ()
    assert result.visual_observations == result.visual_candidates == ()
    assert result.zone_resolutions == result.evidence_frames == ()
    assert result.replay_metadata["temporal_assertions_evaluated"] is False
    assert set(result.replay_metadata["decoded_pixel_sha256"]) == {"0.25", "4.5", "8.0"}
    assert all(
        len(value) == 64
        for value in result.replay_metadata["decoded_pixel_sha256"].values()
    )


def test_warm_cache_skips_decode_but_repeats_native_analysis(tmp_path: Path, monkeypatch) -> None:
    _fingerprints(monkeypatch)
    _source, metadata, spec, first_video, _analyzer, processor = _fixture(tmp_path)
    cache_dir = tmp_path / "cache"
    first = frame_replay.replay_points(
        processor=processor, metadata=metadata, spec=spec, output=tmp_path / "out-1",
        cache_dir=cache_dir, video=first_video,
    )
    first_visits = len(processor.analyzer.calls)
    warm_video = FakeVideo()
    second = frame_replay.replay_points(
        processor=processor, metadata=metadata, spec=spec, output=tmp_path / "out-2",
        cache_dir=cache_dir, video=warm_video,
    )

    assert len(first_video.decode_calls) == 1
    assert warm_video.decode_calls == []
    assert len(processor.analyzer.calls) == first_visits * 2
    assert second.observations == first.observations
    assert second.replay_metadata["frame_cache"]["hits"] == 5
    assert second.replay_metadata["decoded_pixel_sha256"] == first.replay_metadata[
        "decoded_pixel_sha256"
    ]


def test_nonexact_decoded_pts_fail_closed(tmp_path: Path, monkeypatch) -> None:
    _fingerprints(monkeypatch)
    _source, metadata, spec, video, analyzer, processor = _fixture(tmp_path, shifted_pts=True)

    with pytest.raises(ValueError, match="exact PTS"):
        frame_replay.replay_points(
            processor=processor,
            metadata=metadata,
            spec=spec,
            output=tmp_path / "output",
            cache_dir=tmp_path / "cache",
            video=video,
        )
    assert analyzer.calls == []


def test_source_hash_is_verified_before_decode_or_analysis(tmp_path: Path, monkeypatch) -> None:
    _fingerprints(monkeypatch)
    _source, metadata, spec, video, analyzer, processor = _fixture(tmp_path)
    spec["source_sha256"] = "0" * 64

    with pytest.raises(ValueError, match="source SHA256"):
        frame_replay.replay_points(
            processor=processor,
            metadata=metadata,
            spec=spec,
            output=tmp_path / "output",
            cache_dir=tmp_path / "cache",
            video=video,
        )
    assert video.decode_calls == []
    assert analyzer.calls == []


def test_invalid_cached_jpeg_fails_pixel_witness_generation(tmp_path: Path, monkeypatch) -> None:
    _fingerprints(monkeypatch)
    _source, metadata, spec, video, analyzer, processor = _fixture(
        tmp_path, invalid_jpeg=True
    )

    with pytest.raises(ValueError, match="could not decode cached frame pixels"):
        frame_replay.replay_points(
            processor=processor,
            metadata=metadata,
            spec=spec,
            output=tmp_path / "output",
            cache_dir=tmp_path / "cache",
            video=video,
        )
    assert analyzer.calls == []


def test_spec_requires_strictly_ordered_real_pts(tmp_path: Path, monkeypatch) -> None:
    _fingerprints(monkeypatch)
    _source, metadata, spec, video, analyzer, processor = _fixture(tmp_path)
    spec["pts_sec"] = [0.25, 0.25]

    with pytest.raises(ValueError, match="sorted and unique"):
        frame_replay.replay_points(
            processor=processor,
            metadata=metadata,
            spec=spec,
            output=tmp_path / "output",
            cache_dir=tmp_path / "cache",
            video=video,
        )
    assert video.decode_calls == []
    assert analyzer.calls == []
