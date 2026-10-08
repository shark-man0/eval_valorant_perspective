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
from types import SimpleNamespace

APP_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(APP_ROOT / "src"))
sys.path.insert(0, str(APP_ROOT))

from scripts.diagnostics.global_round_start_hypothesis import GlobalStartHypothesis  # noqa: E402
from valorant_ai_coach.events import EventSourceContract  # noqa: E402
from valorant_ai_coach.hud.analyzers import RealHudAnalyzer  # noqa: E402
from valorant_ai_coach.resources import resource_path  # noqa: E402
from valorant_ai_coach.rounds import RoundPackageBuilder, RoundPackageBuildError  # noqa: E402
from valorant_ai_coach.schema_validation import SchemaValidator  # noqa: E402
from valorant_ai_coach.video import FrameSample, VideoMetadata  # noqa: E402


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
    parser.add_argument(
        "--timer-reader-layout", type=Path,
        help="Diagnostic-only reuse of an existing timer reader; never profile adoption",
    )
    parser.add_argument("--window", required=True, action="append", nargs=2, type=float)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--package-diagnostics", action="store_true",
        help="Build native packages from replay outputs without injecting boundaries",
    )
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
    timer_reader_fingerprint = None
    for start, end in args.window:
        if not 0 <= start < end <= metadata["duration_sec"]:
            raise ValueError("window must be inside source duration")
        times = [t for t in native_times if start <= t <= end]
        if not times or any(b - a > 1.0 for a, b in zip(times, times[1:], strict=False)):
            raise ValueError("window must contain continuous native observations")
        context = sorted(set([t for t in prefix if t < start] + times))
        frames, hashes = archived_frames(context, args.frames_root)
        diagnostics: list[dict] = []
        lifecycle_diagnostics: list[dict] = []
        reader_override = {}
        timer_analyzer = None
        if args.timer_reader_layout:
            timer_analyzer = RealHudAnalyzer(args.timer_reader_layout)
            reader = timer_analyzer.readers.get("round_timer")
            if reader is None or timer_analyzer.template_profile is None:
                raise ValueError("existing configured timer reader required")
            reader_override["round_timer"] = reader
            reader_fingerprint = timer_analyzer.fingerprint()
            if (
                timer_reader_fingerprint is not None
                and reader_fingerprint != timer_reader_fingerprint
            ):
                raise ValueError("timer reader profile/assets changed between diagnostic windows")
            timer_reader_fingerprint = reader_fingerprint
        analyzer = RealHudAnalyzer(
            args.profile, readers=reader_override, diagnostic_sink=diagnostics.append,
            lifecycle_diagnostic_sink=lifecycle_diagnostics.append,
        )
        if timer_analyzer is not None and (
            analyzer.layout.normalized_roi("round_timer")
            != timer_analyzer.layout.normalized_roi("round_timer")
        ):
            raise ValueError("timer reader and replay layout ROI mismatch")
        if analyzer.template_profile is None:
            raise ValueError("complete template sidecar required")
        before = analyzer.template_profile.fingerprint(args.profile)
        window_started = time.perf_counter()
        result = analyzer.observe_frames(frames)
        elapsed = time.perf_counter() - window_started
        after = analyzer.template_profile.fingerprint(args.profile)
        if before != after:
            raise ValueError("profile/assets changed during diagnostic")
        if timer_analyzer is not None and timer_analyzer.fingerprint() != timer_reader_fingerprint:
            raise ValueError("timer reader profile/assets changed during diagnostic")
        fingerprints.add(before)
        indices = {i for i, t in enumerate(context) if start <= t <= end}
        observed = [row for row in result.observations if start <= row["time_sec"] <= end]
        if [row["time_sec"] for row in observed] != times:
            raise ValueError("native replay failed to preserve every requested PTS")
        inputs = [row for row in diagnostics if row["frame_index"] in indices]
        hypotheses = []
        if args.timer_reader_layout:
            hypothetical = GlobalStartHypothesis()
            for row, evidence in zip(observed, inputs, strict=True):
                signals = evidence["signals"]
                proposal = hypothetical.advance(
                    row, discontinuity=signals.get("content_jump") is True
                    or signals.get("discontinuity") is True,
                )
                if proposal is not None:
                    hypotheses.append(proposal)
        package_summary = None
        package_build_error = None
        trace_timer_displays = None
        if args.package_diagnostics:
            builder = RoundPackageBuilder(
                contract=EventSourceContract.load(
                    resource_path("config/event_source_contract_v1.json")
                ),
                validator=SchemaValidator(),
            )
            try:
                packages = builder.build(
                    match_id="continuous_diagnostic",
                    video_metadata=VideoMetadata(
                        args.video, metadata["duration_sec"], metadata["width"],
                        metadata["height"], metadata["fps"], metadata["video_codec"],
                        metadata["audio_codec"], metadata["has_audio"], metadata["file_size"],
                    ),
                    hud_observations=observed,
                    hud_events=[e for e in result.hud_events if start <= e["time_sec"] <= end],
                )
            except RoundPackageBuildError as exc:
                packages = ()
                package_build_error = str(exc)
            package_summary = [
                {
                    "round_no": package["round_no"],
                    "round_window": package["round_window"],
                    "timeline_completeness": package["observation_quality"][
                        "timeline_completeness"
                    ],
                    "snapshot_count": len(package["state_snapshots"]),
                    "event_counts": dict(Counter(e["type"] for e in package["events"])),
                    "boundary_events": [
                        e for e in package["events"]
                        if e["type"] in {"round_start", "round_end"}
                    ],
                    "source_timer_displays": [
                        {key: snapshot[key] for key in (
                            "time_sec", "round_time_remaining_sec",
                            "round_time_remaining_display",
                            "round_time_remaining_display_provenance",
                        )}
                        for snapshot in package["state_snapshots"]
                        if "round_time_remaining_display" in snapshot
                    ],
                }
                for package in packages
            ]
            from tests.e2e.trace_adapter import to_e2e_trace

            trace = to_e2e_trace(
                SimpleNamespace(round_packages=packages, observations=observed)
            )
            trace_timer_displays = [
                {key: snapshot[key] for key in (
                    "time_sec", "game_timer_display", "game_timer_display_provenance"
                )}
                for snapshot in trace["snapshots"]
                if "game_timer_display" in snapshot
            ]
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
                "state_flag_counts": dict(
                    Counter(flag for row in observed for flag in row["state_flags"])
                ),
                "identity_reasons": dict(Counter(row["identity"]["reason"] for row in inputs)),
                "input_counts": {
                    "buy_phase_template": sum(
                        row["signals"].get("buy_phase_template") is True for row in inputs
                    ),
                    "semantic_buy_phase_confirmed": sum(
                        row["signals"].get("semantic_buy_phase_confirmed") is True
                        for row in inputs
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
                "phase_evidence": [
                    {
                        "pts_sec": row["time_sec"],
                        "template_match": evidence["signals"].get("buy_phase_template"),
                        "template_confidence": evidence["signals"].get(
                            "buy_phase_template_confidence"
                        ),
                        "confirmed": evidence["signals"].get("semantic_buy_phase_confirmed")
                        is True,
                        "source_pts": evidence["signals"].get("semantic_buy_phase_source_pts"),
                        "phase_confidence": row["quality"]["roi_confidence"].get(
                            "center_phase_banner_semantic_text"
                        ),
                    }
                    for row, evidence in zip(observed, inputs, strict=True)
                ],
                "timer_display_evidence": [
                    {
                        "pts_sec": row["time_sec"],
                        "numeric_seconds": row["values"].get("round_time_remaining_sec"),
                        "display": row["values"].get("round_time_remaining_display"),
                        "provenance": row["values"].get(
                            "round_time_remaining_display_provenance"
                        ),
                        "accepted_value_confidence": row["quality"]["roi_confidence"].get(
                            "round_timer_value"
                        ),
                    }
                    for row in observed
                ],
                "geometry": result.calibration_diagnostics,
                "native_package_diagnostics": package_summary,
                "native_package_build_error": package_build_error,
                "trace_timer_displays": trace_timer_displays,
                "global_start_hypotheses": hypotheses,
                "lifecycle_diagnostics": [
                    row for row in lifecycle_diagnostics if start <= row["time_sec"] <= end
                ],
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
        "diagnostic_timer_reader_fingerprint": timer_reader_fingerprint,
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
                            "state_flag_counts",
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
