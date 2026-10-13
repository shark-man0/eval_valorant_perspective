"""Source-only targeted replay through native processing; not canonical Full E2E.

No GT or pack is read. Each invocation creates fresh native services, and only
the declared continuous source window is passed into the processor. There is
no distant calibration prefix or injected continuity/phase/ownership evidence.
"""
from __future__ import annotations

import argparse
import json
import math
import time
from dataclasses import asdict
from pathlib import Path

from scripts.diagnostics.prepare_boundary_review import validate_review_pts
from scripts.e2e.frame_replay import decoder_fingerprints
from scripts.e2e.probe_cache import CachedVideoService
from scripts.e2e.run_dataset_case import git_identity, sha256_file
from tests.e2e.trace_adapter import to_e2e_trace
from valorant_ai_coach.bootstrap import build_services
from valorant_ai_coach.hud.calibrate_temporal import _check_output_privacy
from valorant_ai_coach.settings import AppSettings, SettingsStore


def window_schedule(start: float, end: float, duration: float, fps: float) -> list[float]:
    if not all(math.isfinite(x) for x in (start, end, duration, fps)):
        raise ValueError("finite window values required")
    if not 0 <= start < end < duration or fps <= 0:
        raise ValueError("window must be inside source; FPS must be positive")
    count = math.ceil((end - start) * fps) + 1
    if count > 600:
        raise ValueError("targeted window exceeds 600 frames")
    return sorted(set([start + i / fps for i in range(count) if start + i / fps <= end] + [end]))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--source-sha256", required=True)
    parser.add_argument("--hud-layout", type=Path, required=True)
    parser.add_argument("--start", type=float, required=True)
    parser.add_argument("--end", type=float, required=True)
    parser.add_argument("--fps", type=float, default=4)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    _check_output_privacy(output)
    if output.exists():
        parser.error("targeted output must be a new private directory")
    source_hash = sha256_file(args.video)
    if source_hash != args.source_sha256:
        raise ValueError("source SHA mismatch")
    output.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    raw = {
        "status": "starting", "source_sha256": source_hash,
        "git": git_identity(Path(__file__).resolve().parents[2]),
        "runtime_mode": {"input_scope": "continuous_window", "mode": "targeted",
                         "ground_truth_loaded": False, "visual_semantic_enabled": False,
                         "coach_mode": "mock", "full_sampler_used": False},
        "window": {"start_sec": args.start, "end_sec": args.end, "requested_fps": args.fps},
    }
    services = None
    profile_hash = None
    result = None
    trace_json = None
    stage = "service_initialization"
    raw["processing_completed"] = False
    try:
        settings = AppSettings(data_dir=output / "runtime_data", hud_mode="real", mock_ai=True,
                               hud_layout_path=str(args.hud_layout.resolve()),
                               visual_semantic_enabled=False)
        services = build_services(SettingsStore(output / "runner-settings.json"), settings=settings)
        processor = services.pipeline.hud_video_processor
        if processor is None:
            raise RuntimeError("native HUD processor unavailable")
        profile_hash = processor.analyzer.fingerprint()
        raw["hud_profile_fingerprint"] = profile_hash
        probe_fp, _ = decoder_fingerprints(services.video.ffprobe_path)
        video = CachedVideoService(
            services.video, Path("outputs/e2e_cache/probe"), source_hash, probe_fp,
        )
        stage = "source_probe"
        metadata = video.probe(args.video)
        schedule = window_schedule(args.start, args.end, metadata.duration_sec, args.fps)
        stage = "source_frame_extraction"
        frames = video.extract_frames(args.video, schedule, output / "frames", metadata=metadata,
                                      max_dimension=None)
        stage = "source_frame_validation"
        if len(frames) != len(schedule):
            raise ValueError("targeted source-frame extraction incomplete")
        validate_review_pts([frame.time_sec for frame in frames], metadata.duration_sec)
        if any(not args.start <= frame.time_sec <= args.end for frame in frames):
            raise ValueError("decoded targeted PTS outside declared source window")
        raw["source_frames"] = [{"pts_sec": frame.time_sec, "sha256": sha256_file(frame.path)}
                                for frame in frames]
        stage = "hud_processing"
        result = processor.process_frames(metadata, "source-window", frames,
                                           require_detected_rounds=False)
        raw.update(asdict(result), processing_completed=True, video_metadata=asdict(metadata))
        stage = "trace_export"
        trace_json = json.dumps(to_e2e_trace(result), indent=2, allow_nan=False) + "\n"
        raw["status"] = "complete"
    except Exception as exc:
        raw.update(status="error", error_type=type(exc).__name__, error=str(exc),
                   failure_stage=stage)
    finally:
        if services is not None:
            processor = services.pipeline.hud_video_processor
            if processor is not None:
                raw["hud_calibration_diagnostics"] = getattr(
                    processor.analyzer, "last_calibration_diagnostics", {},
                )
                if profile_hash is not None and processor.analyzer.fingerprint() != profile_hash:
                    raw.update(status="error", error_type="IntegrityError", error="profile changed",
                               failure_stage="profile_integrity")
        raw["source_hash_verified_after_processing"] = sha256_file(args.video) == source_hash
        if not raw["source_hash_verified_after_processing"]:
            raw.update(status="error", error_type="IntegrityError", error="source changed",
                       failure_stage="source_integrity")
        if raw["status"] == "complete" and trace_json is not None:
            try:
                (output / "e2e_trace.json").write_text(trace_json, encoding="utf-8")
            except Exception as exc:
                raw.update(status="error", error_type=type(exc).__name__, error=str(exc),
                           failure_stage="trace_export")
        raw["wall_clock_sec"] = time.perf_counter() - started
        (output / "raw_processing.json").write_text(
            json.dumps(raw, indent=2, default=str, allow_nan=False) + "\n", encoding="utf-8",
        )
    print(json.dumps({key: raw[key] for key in (
        "status", "window", "wall_clock_sec", "failure_stage", "processing_completed",
    ) if key in raw}))
    return 0 if raw["status"] == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
