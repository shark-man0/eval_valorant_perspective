"""Bounded native recognizer replay; isolated points never imply event continuity."""

from __future__ import annotations

import hashlib
import json
import math
import os
from dataclasses import asdict
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from scripts.e2e.frame_cache import DecodedFrameCache
from scripts.e2e.probe_cache import CachedVideoService
from valorant_ai_coach.video import FrameSample


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


@lru_cache(maxsize=8)
def _cached_binary_hash(path: str, size: int, mtime_ns: int) -> str:
    # OpenCV's native module can be large; memoize by immutable install identity.
    return file_hash(Path(path))


def _opencv_native_hashes(cv2: Any) -> dict[str, str]:
    roots = [Path(root) for root in getattr(cv2, "__path__", ())]
    module_path = getattr(cv2, "__file__", None)
    if module_path:
        roots.append(Path(module_path).parent)
    binaries: set[Path] = set()
    for root in roots:
        if root.is_dir():
            binaries.update(root.glob("cv2*.so"))
            binaries.update(root.glob("cv2*.pyd"))
    result = {}
    for binary in sorted(binaries):
        resolved = binary.resolve()
        stat = resolved.stat()
        result[str(resolved)] = _cached_binary_hash(
            str(resolved), stat.st_size, stat.st_mtime_ns
        )
    if not result:
        raise RuntimeError("could not locate the loaded OpenCV native extension")
    return result


def decoded_pixel_sha256(image_path: Path) -> str:
    import cv2

    image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if image is None or getattr(image, "size", 0) == 0:
        raise ValueError(f"could not decode cached frame pixels: {image_path}")
    return hashlib.sha256(image.tobytes(order="C")).hexdigest()


def decoder_fingerprints(ffprobe: str) -> tuple[str, str]:
    import cv2

    from valorant_ai_coach.video import service

    policy = file_hash(Path(service.__file__))
    executable = Path(ffprobe)
    if not executable.is_file():
        import shutil

        executable = Path(shutil.which(ffprobe) or ffprobe)
    probe = hashlib.sha256((file_hash(executable) + policy).encode()).hexdigest()
    backend_preferences = {
        key: value for key, value in os.environ.items()
        if key == "OPENCV_VIDEOIO_PRIORITY_LIST" or key.startswith("OPENCV_VIDEOIO_PRIORITY_")
    }
    frame = hashlib.sha256(
        json.dumps(
            {
                "policy": policy,
                "jpeg_quality": 92,
                "max_dimension": None,
                "opencv_build": cv2.getBuildInformation(),
                "opencv_version": cv2.__version__,
                "opencv_native_extensions": _opencv_native_hashes(cv2),
                "video_backend_preferences": backend_preferences,
                "format": 1,
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()
    return probe, frame


def replay_points(
    *,
    processor: Any,
    metadata: Any,
    spec: dict[str, Any],
    output: Path,
    cache_dir: Path,
    video: Any,
) -> SimpleNamespace:
    """Use genuine calibration pixels and a fresh temporal context for each point.

    Prefix observations/events are discarded. Each queried point is independent:
    no state intervals, rounds, visual events or map trajectory are fabricated
    across the explicitly sparse input. Continuous interval replay is separate.
    """
    if spec.get("schema_version") != 1 or spec.get("input_scope") != "isolated_points":
        raise ValueError("unsupported bounded input scope")
    source_sha = file_hash(metadata.path)
    if source_sha != spec.get("source_sha256"):
        raise ValueError("bounded source SHA256 mismatch")
    prefix = spec.get("calibration_prefix", [])
    points = spec.get("pts_sec", [])
    for values in (prefix, points):
        if not isinstance(values, list) or not values:
            raise ValueError("bounded points and genuine calibration prefix are required")
        if any(
            isinstance(x, bool)
            or not isinstance(x, (int, float))
            or not math.isfinite(x)
            or not 0 <= x < metadata.duration_sec
            for x in values
        ):
            raise ValueError("bounded PTS must be finite and inside the recording")
        if values != sorted(set(values)):
            raise ValueError("bounded PTS must be sorted and unique")
    probe_fp, frame_fp = decoder_fingerprints(video.ffprobe_path)
    cached_video = CachedVideoService(video, cache_dir / "probe", source_sha, probe_fp)
    cache = DecodedFrameCache(cache_dir / "frames", source_sha, frame_fp)
    requested = sorted(set(prefix + points))
    frames: dict[float, FrameSample] = {}
    missing = []
    for pts in requested:
        hit = cache.get(pts)
        if hit is None:
            missing.append(pts)
        else:
            frames[pts] = hit
    if missing:
        extracted = cached_video.extract_frames(
            metadata.path,
            missing,
            output / "decoded_frames",
            metadata=metadata,
            max_frames=len(missing),
            jpeg_quality=92,
            max_dimension=None,
        )
        if len(extracted) != len(missing):
            raise ValueError("decoder did not return every requested exact PTS")
        for frame in extracted:
            if frame.time_sec not in missing:
                raise ValueError("decoder did not return the requested exact PTS")
            frames[frame.time_sec] = cache.put(frame)
    if set(frames) != set(requested):
        raise ValueError("one or more bounded frames could not be decoded")
    pixel_hashes = {
        str(pts): decoded_pixel_sha256(frames[pts].path) for pts in points
    }
    observations = []
    diagnostics: list[str] = []
    calibration_runs = []
    for pts in points:
        context_times = sorted(set([x for x in prefix if x <= pts] + [pts]))
        native = processor.analyzer.observe_frames(
            [frames[x] for x in context_times],
            video_metadata=metadata,
        )
        rows = [dict(row) for row in native.observations if abs(row["time_sec"] - pts) <= 1e-6]
        if len(rows) != 1:
            raise ValueError("native replay did not produce exactly one point observation")
        observations.extend(rows)
        diagnostics.extend(native.diagnostics)
        calibration_runs.append({"pts_sec": pts, "calibration": asdict(native.calibration)})
    return SimpleNamespace(
        observations=tuple(observations),
        sampled_frame_count=len(points),
        round_packages=(),
        hud_events=(),
        visual_events=(),
        visual_observations=(),
        visual_candidates=(),
        zone_resolutions=(),
        evidence_frames=(),
        diagnostics=tuple(dict.fromkeys(diagnostics)),
        calibration_diagnostics={"scope": "isolated_points", "runs": calibration_runs},
        replay_metadata={
            "input_scope": "isolated_points",
            "queried_frames": len(points),
            "unique_decoded_frames": len(requested),
            "recognizer_frame_visits": sum(
                len(set([x for x in prefix if x <= pts] + [pts])) for pts in points
            ),
            "frame_cache": asdict(cache.stats),
            "probe_cache": cached_video.stats,
            "preprocessing_fingerprint": frame_fp,
            "temporal_assertions_evaluated": False,
            "decoded_pixel_sha256": pixel_hashes,
        },
    )
