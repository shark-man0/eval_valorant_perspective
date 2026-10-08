"""Replay every archived native PTS in explicit continuous diagnostic windows.

No labels, inferred boundaries, injected signals or recognizer-result cache are
used. This is an evidence diagnostic, not a substitute for canonical full E2E.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import time
from collections import Counter
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(APP_ROOT / "src"))

from valorant_ai_coach.hud.analyzers import RealHudAnalyzer  # noqa: E402
from valorant_ai_coach.video import FrameSample  # noqa: E402


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def archived_frames(
    times: list[float],
    frames_root: Path,
) -> tuple[list[FrameSample], list[dict[str, object]]]:
    """Resolve archived filename millisecond rounding, never a nearby raw PTS."""
    by_millisecond: dict[int, Path] = {}
    for path in sorted(frames_root.rglob("*.jpg")):
        try:
            timestamp = float(path.stem.rsplit("_", 1)[-1])
        except ValueError:
            continue
        if math.isfinite(timestamp):
            by_millisecond.setdefault(round(timestamp * 1000), path)
    samples = []
    hashes = []
    for timestamp in times:
        path = by_millisecond.get(round(timestamp * 1000))
        if path is None:
            raise ValueError(f"no archived image for native PTS {timestamp:.6f}")
        encoded_pts = float(path.stem.rsplit("_", 1)[-1])
        if abs(encoded_pts - timestamp) > 0.00051:
            raise ValueError(f"archived filename PTS differs from native PTS {timestamp:.6f}")
        samples.append(FrameSample(timestamp, path))
        hashes.append({"pts_sec": timestamp, "frame_sha256": sha256_file(path)})
    return samples, hashes


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", required=True, type=Path)
    parser.add_argument("--source-sha256", required=True)
    parser.add_argument("--raw-processing", required=True, type=Path)
    parser.add_argument("--frames-root", required=True, type=Path)
    parser.add_argument("--profile", required=True, type=Path)
    parser.add_argument("--window", required=True, action="append", nargs=2, type=float)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    started = time.perf_counter()
    source_sha = sha256_file(args.video)
    if source_sha != args.source_sha256:
        raise ValueError("source video SHA256 mismatch")
    raw_sha = sha256_file(args.raw_processing)
    run_metadata_path = args.raw_processing.parent / "run_metadata.json"
    run_metadata = json.loads(run_metadata_path.read_text(encoding="utf-8"))
    if (
        run_metadata["metadata"]["source_sha256"] != source_sha
        or run_metadata["input_hashes"][args.raw_processing.name] != raw_sha
    ):
        raise ValueError("archive terminal hashes or source association mismatch")
    raw = json.loads(args.raw_processing.read_text(encoding="utf-8"))
    if raw.get("status") != "complete":
        raise ValueError("completed native archive required")
    metadata = raw["video_metadata"]
    if Path(metadata["path"]).name != args.video.name:
        raise ValueError("archive source filename mismatch")
    native_times = sorted({float(row["time_sec"]) for row in raw["observations"]})
    if len(native_times) < 3 or any(not math.isfinite(t) for t in native_times):
        raise ValueError("three genuine finite calibration observations required")
    prefix = native_times[:3]
    summaries = []
    fingerprints = set()
    for start, end in args.window:
        if not 0 <= start < end <= metadata["duration_sec"]:
            raise ValueError("window must be inside source duration")
        times = [t for t in native_times if start <= t <= end]
        if not times or any(b - a > 1.0 for a, b in zip(times, times[1:], strict=False)):
            raise ValueError("window must contain continuous native observations")
        context = sorted(set([t for t in prefix if t < start] + times))
        frames, hashes = archived_frames(context, args.frames_root)
        diagnostics: list[dict] = []
        analyzer = RealHudAnalyzer(args.profile, diagnostic_sink=diagnostics.append)
        if analyzer.template_profile is None:
            raise ValueError("complete template sidecar required")
        before = analyzer.template_profile.fingerprint(args.profile)
        window_started = time.perf_counter()
        result = analyzer.observe_frames(frames)
        elapsed = time.perf_counter() - window_started
        after = analyzer.template_profile.fingerprint(args.profile)
        if before != after:
            raise ValueError("profile/assets changed during diagnostic")
        fingerprints.add(before)
        indices = {i for i, t in enumerate(context) if start <= t <= end}
        observed = [row for row in result.observations if start <= row["time_sec"] <= end]
        if [row["time_sec"] for row in observed] != times:
            raise ValueError("native replay failed to preserve every requested PTS")
        inputs = [row for row in diagnostics if row["frame_index"] in indices]
        summaries.append(
            {
                "window_sec": [start, end],
                "processed_frames": len(times),
                "calibration_prefix": [t for t in context if t < start],
                "wall_clock_sec": elapsed,
                "frames_per_sec": len(context) / elapsed,
                "maximum_sample_gap_sec": max(
                    (b - a for a, b in zip(times, times[1:], strict=False)), default=0
                ),
                "frames": hashes,
                "state_counts": dict(Counter(row["primary_state"] for row in observed)),
                "identity_reasons": dict(Counter(row["identity"]["reason"] for row in inputs)),
                "input_counts": {
                    "buy_phase_template": sum(
                        row["signals"].get("buy_phase_template") is True for row in inputs
                    ),
                    "round_end_template": sum(
                        row["signals"].get("round_end_template") is True for row in inputs
                    ),
                    "both_scores_known": sum(
                        type(row["values"]["score_ally"]) is int
                        and type(row["values"]["score_enemy"]) is int
                        for row in observed
                    ),
                    "numeric_timer_known": sum(
                        row["values"]["round_time_remaining_sec"] is not None for row in observed
                    ),
                },
                "hud_events": [e for e in result.hud_events if start <= e["time_sec"] <= end],
                "geometry": result.calibration_diagnostics,
            }
        )
    if (
        len(fingerprints) != 1
        or sha256_file(args.video) != source_sha
        or sha256_file(args.raw_processing) != raw_sha
    ):
        raise ValueError("input integrity changed during replay")
    output = {
        "status": "complete",
        "mode": "continuous_round_diagnostic",
        "scope": "every archived native PTS in explicit windows; no GT or signal injection",
        "source_video_sha256": source_sha,
        "raw_processing_sha256": raw_sha,
        "profile_fingerprint": next(iter(fingerprints)),
        "wall_clock_sec": time.perf_counter() - started,
        "windows": summaries,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "status": output["status"],
                "wall_clock_sec": output["wall_clock_sec"],
                "windows": [
                    {
                        k: w[k]
                        for k in (
                            "window_sec",
                            "processed_frames",
                            "state_counts",
                            "input_counts",
                            "hud_events",
                        )
                    }
                    for w in summaries
                ],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
