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
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import cv2
import numpy as np

APP_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(APP_ROOT / "src"))
sys.path.insert(0, str(APP_ROOT))

from scripts.diagnostics.score_numeric import load_score_candidate  # noqa: E402
from tests.e2e.trace_adapter import to_e2e_trace  # noqa: E402
from valorant_ai_coach.events import EventSourceContract  # noqa: E402
from valorant_ai_coach.hud.analyzers import RealHudAnalyzer  # noqa: E402
from valorant_ai_coach.hud.calibrate_temporal import _check_output_privacy  # noqa: E402
from valorant_ai_coach.hud.templates import SubregionReader  # noqa: E402
from valorant_ai_coach.hud.timer_glyphs import StrictTimerGlyphReader  # noqa: E402
from valorant_ai_coach.resources import resource_path  # noqa: E402
from valorant_ai_coach.rounds import RoundPackageBuilder  # noqa: E402
from valorant_ai_coach.schema_validation import SchemaValidator  # noqa: E402
from valorant_ai_coach.video import FrameSample, VideoMetadata  # noqa: E402


class AuditedReader:
    """Record configured reader attempts without changing the returned result."""

    def __init__(self, role: str, reader: Any, pending: list[dict[str, Any]]) -> None:
        self.role = role
        self.reader = reader
        self.pending = pending

    def read(self, image: Any, roi: Any) -> Any:
        result = self.reader.read(image, roi)
        self.pending.append({
            "role": self.role, "value": deepcopy(result.value),
            "confidence": result.confidence, "sources": list(result.sources),
            "cross_checked": result.cross_checked,
        })
        return result


class FixedGaussianTimerComparison(StrictTimerGlyphReader):
    """Diagnostic-only frozen comparison representation, not profile adoption.

    Keep all production segmentation/format/threshold/margin gates. Apply one
    fixed Gaussian3x3 sigma0 to both normalized glyph and binary reference.
    No blur is applied to the source frame, ROI, colon or component geometry.
    """

    def __init__(self, original: StrictTimerGlyphReader) -> None:
        super().__init__(original.templates)
        self.templates = {
            digit: tuple(cv2.GaussianBlur(ref, (3, 3), 0) for ref in refs)
            for digit, refs in self.templates.items()
        }

    @classmethod
    def _normalize_known_white(cls, image: np.ndarray) -> np.ndarray:
        return cv2.GaussianBlur(super()._normalize_known_white(image), (3, 3), 0)


def diagnostic_timer_comparison(reader: Any) -> Any:
    if isinstance(reader, SubregionReader):
        return SubregionReader(diagnostic_timer_comparison(reader.reader), reader.bounds)
    if isinstance(reader, StrictTimerGlyphReader):
        return FixedGaussianTimerComparison(reader)
    raise ValueError("Gaussian comparison requires a configured strict timer glyph reader")


def package_trace_diagnostic(
    observations: list[dict[str, Any]],
    hud_events: list[dict[str, Any]],
    metadata: VideoMetadata,
) -> dict[str, Any]:
    """Exercise the native builder and exact adapter without evaluator labels.

    Prefix frames establish calibration only: callers must pass the measured
    window, not disconnected prefix observations. Incomplete windows retain
    the production builder's semantics, not an invented diagnostic end event.
    """
    builder = RoundPackageBuilder(
        contract=EventSourceContract.load(resource_path("config/event_source_contract_v1.json")),
        validator=SchemaValidator(),
    )
    packages = builder.build(
        match_id="continuous-diagnostic",
        video_metadata=metadata,
        hud_observations=observations,
        hud_events=hud_events,
        require_detected_rounds=False,
    )
    trace = to_e2e_trace(
        SimpleNamespace(round_packages=packages, observations=observations, visual_observations=())
    )
    windows = builder._round_windows(observations, builder._unique_boundaries(hud_events),
                                     metadata.duration_sec)
    return {
        "scope": "bounded native window; not a canonical full evaluation",
        "package_count": len(packages),
        "windows": [
            {
                "round_no": package["round_no"],
                "start_sec": window.start_sec,
                "end_sec": window.end_sec,
                "complete": window.complete,
                "include_end": window.include_end,
                "start_event_sec": window.start_event_sec,
                "end_event_sec": window.end_event_sec,
                "observation_pts_sec": [
                    float(row["time_sec"]) for row in observations
                    if window.contains(float(row["time_sec"]))
                ],
                "snapshot_pts_sec": [row["time_sec"] for row in package["state_snapshots"]],
                "boundary_events": [
                    row for row in package["events"]
                    if row["type"] in {"round_start", "round_end"}
                ],
            }
            for package, window in zip(packages, windows, strict=True)
        ],
        "unassigned_observation_pts_sec": [
            float(row["time_sec"]) for row in observations
            if not any(window.contains(float(row["time_sec"])) for window in windows)
        ],
        "trace_counts": {key: len(rows) for key, rows in trace.items()},
        "trace_boundary_events": [
            row for row in trace["events"] if row["type"] in {"round_start", "round_end"}
        ],
        "trace_snapshot_association": [
            {"time_sec": row["time_sec"], "round_id": row["round_id"]}
            for row in trace["snapshots"]
        ],
    }


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
    parser.add_argument(
        "--timer-comparison", choices=("production", "gaussian3x3_v1"), default="production",
        help="Opt-in diagnostic comparison only; never changes the saved profile or defaults",
    )
    parser.add_argument(
        "--score-candidate", type=Path,
        help="Frozen diagnostic-only score sidecar; does not install production readers",
    )
    args = parser.parse_args()
    _check_output_privacy(args.output.resolve())
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
    video_metadata = VideoMetadata(
        args.video, metadata["duration_sec"], metadata["width"], metadata["height"],
        metadata["fps"], metadata.get("video_codec", "unknown"),
        metadata.get("audio_codec"), metadata.get("has_audio", False),
        metadata.get("file_size", args.video.stat().st_size),
    )
    if Path(metadata["path"]).name != args.video.name:
        raise ValueError("archive source filename mismatch")
    native_times = sorted({float(row["time_sec"]) for row in raw["observations"]})
    if len(native_times) < 3 or any(not math.isfinite(t) for t in native_times):
        raise ValueError("three genuine finite calibration observations required")
    prefix = native_times[:3]
    summaries = []
    fingerprints = set()
    score_fingerprints = set()
    for start, end in args.window:
        if not 0 <= start < end <= metadata["duration_sec"]:
            raise ValueError("window must be inside source duration")
        times = [t for t in native_times if start <= t <= end]
        if not times or any(b - a > 1.0 for a, b in zip(times, times[1:], strict=False)):
            raise ValueError("window must contain continuous native observations")
        context = sorted(set([t for t in prefix if t < start] + times))
        frames, hashes = archived_frames(context, args.frames_root)
        diagnostics: list[dict] = []
        pending_reads: list[dict[str, Any]] = []

        def record_diagnostics(
            row: dict[str, Any],
            diagnostics: list[dict] = diagnostics,
            pending_reads: list[dict[str, Any]] = pending_reads,
        ) -> None:
            # The native sink is called after readers for the current frame.
            # Bind attempts there, not by assuming every frame invokes OCR.
            diagnostics.append({**row, "numeric_reader_attempts": list(pending_reads)})
            pending_reads.clear()

        analyzer = RealHudAnalyzer(args.profile, diagnostic_sink=record_diagnostics)
        if analyzer.template_profile is None:
            raise ValueError("complete template sidecar required")
        before = analyzer.template_profile.fingerprint(args.profile)
        if args.score_candidate:
            score_readers, score_fingerprint = load_score_candidate(args.score_candidate)
            score_fingerprints.add(score_fingerprint)
            analyzer.readers.update(score_readers)
        reader_classes = {role: type(reader).__name__ for role, reader in analyzer.readers.items()}
        if args.timer_comparison != "production":
            spec = analyzer.template_profile.raw.get("readers", {}).get("round_timer", {})
            if spec.get("comparison_preprocessing") != args.timer_comparison:
                raise ValueError("diagnostic comparison must match the frozen profile declaration")
            analyzer.readers["round_timer"] = diagnostic_timer_comparison(
                analyzer.readers.get("round_timer")
            )
        for role in ("round_timer", "ally_score", "enemy_score"):
            if role in analyzer.readers:
                analyzer.readers[role] = AuditedReader(role, analyzer.readers[role], pending_reads)
        window_started = time.perf_counter()
        result = analyzer.observe_frames(frames)
        elapsed = time.perf_counter() - window_started
        after = analyzer.template_profile.fingerprint(args.profile)
        if before != after:
            raise ValueError("profile/assets changed during diagnostic")
        if args.score_candidate:
            _, after_score = load_score_candidate(args.score_candidate)
            if after_score != score_fingerprint:
                raise ValueError("score candidate changed during diagnostic")
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
                "reader_configuration": {
                    role: {
                        "configured": role in analyzer.readers,
                        "reader_class": (
                            reader_classes[role]
                            if role in analyzer.readers else None
                        ),
                        "ocr_fallback_enabled": role in analyzer.ocr_fallback_rois,
                    }
                    for role in ("round_timer", "ally_score", "enemy_score")
                },
                "shared_value_provenance": [
                    {"pts_sec": row["time_sec"], "primary_state": row["primary_state"],
                     "hud_confidence": row["quality"]["hud_confidence"],
                     "values": {
                         key: {"value": row["values"].get(key),
                               "value_confidence": row["quality"]["roi_confidence"].get(
                                   confidence_key, 0.0)}
                         for key, confidence_key in (
                             ("round_time_remaining_sec", "round_timer_value"),
                             ("score_ally", "score_ally_value"),
                             ("score_enemy", "score_enemy_value"),
                         )
                     }} for row in observed
                ],
                "numeric_reader_attempts": [
                    {"pts_sec": context[row["frame_index"]], **attempt}
                    for row in inputs for attempt in row["numeric_reader_attempts"]
                ],
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
                "geometry": result.calibration_diagnostics,
                "package_trace": package_trace_diagnostic(
                    observed,
                    [e for e in result.hud_events if start <= e["time_sec"] <= end],
                    video_metadata,
                ),
            }
        )
    if (
        len(fingerprints) != 1
        or (args.score_candidate is not None and len(score_fingerprints) != 1)
        or sha256_file(args.video) != source_sha
        or sha256_file(args.raw_processing) != raw_sha
    ):
        raise ValueError("input integrity changed during replay")
    output = {
        "status": "complete",
        "mode": "continuous_round_diagnostic",
        "timer_comparison": args.timer_comparison,
        "production_reader_replay": (
            args.timer_comparison == "production" and args.score_candidate is None
        ),
        "score_candidate_fingerprint": next(iter(score_fingerprints), None),
        "score_diagnostic_implementation_sha256": sha256_file(
            APP_ROOT / "scripts/diagnostics/score_numeric.py"
        ) if args.score_candidate else None,
        "diagnostic_implementation_sha256": sha256_file(Path(__file__)),
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
