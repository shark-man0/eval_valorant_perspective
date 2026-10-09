"""Replay existing HUD roster observations on a bounded dense source window.

Selectors are offline only. No expected counts, states, events or Validation
Pack inputs are accepted. This never installs a profile or promotes UNKNOWN.
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
from pathlib import Path

from scripts.diagnostics.diagnose_round_lifecycle import (
    archived_frames,
    diagnostic_timer_comparison,
    sha256_file,
)
from scripts.diagnostics.score_numeric import load_score_candidate
from valorant_ai_coach.hud.analyzers import RealHudAnalyzer
from valorant_ai_coach.hud.calibrate_temporal import _check_output_privacy
from valorant_ai_coach.schema_validation import SchemaValidator


def roster_row(observation, feature):
    return {
        "pts_sec": observation["time_sec"], "primary_state": observation["primary_state"],
        "hud_confidence": observation["quality"]["hud_confidence"],
        "roster": {
            side: {"accepted_count": observation["values"].get(f"{side}_alive"),
                   # Generic ROI confidence and debounced/read value confidence
                   # share this legacy key. Do not mislabel it as value provenance.
                   "reported_roi_confidence": observation["quality"]["roi_confidence"].get(
                       f"{side}_roster", 0.0),
                   "slot_candidates": feature.signals.get(f"{side}_liveness_candidates", [])}
            for side in ("ally", "enemy")
        },
        "score": {side: observation["values"].get(f"score_{side}")
                  for side in ("ally", "enemy")},
        "timer": observation["values"].get("round_time_remaining_sec"),
        "state_flags": observation["state_flags"],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("video", "raw-processing", "prefix-root", "dense-root", "profile", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--window", nargs=2, type=float, required=True)
    parser.add_argument("--score-candidate", type=Path)
    parser.add_argument("--timer-comparison", choices=("production", "gaussian3x3_v1"),
                        default="production")
    args = parser.parse_args()
    _check_output_privacy(args.output.resolve())
    source_hash, raw_hash = map(sha256_file, (args.video, args.raw_processing))
    metadata = json.loads(args.raw_processing.with_name("run_metadata.json").read_bytes())
    if (metadata["metadata"]["source_sha256"] != source_hash
            or metadata["input_hashes"][args.raw_processing.name] != raw_hash):
        raise ValueError("source archive binding mismatch")
    raw = json.loads(args.raw_processing.read_bytes())
    start, end = args.window
    if not 0 <= start < end <= raw["video_metadata"]["duration_sec"] or end - start > 2:
        raise ValueError("dense diagnostic requires a source window of at most two seconds")
    # FFprobe may seek to an earlier keyframe. Select exact returned display PTS,
    # never infer native timestamps from FPS or rounded JPEG filenames.
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-read_intervals",
         f"{start}%{end}", "-show_frames", "-show_entries", "frame=best_effort_timestamp_time",
         "-of", "json", str(args.video)], capture_output=True, text=True, check=True, timeout=60,
    )
    times = [float(row["best_effort_timestamp_time"])
             for row in json.loads(result.stdout)["frames"]
             if start <= float(row["best_effort_timestamp_time"]) <= end]
    if (
        not times or len(times) > 240 or any(not math.isfinite(t) for t in times)
        or any(b <= a for a, b in zip(times, times[1:], strict=False))
    ):
        raise ValueError("bounded increasing native source PTS required")
    prefix = sorted({float(row["time_sec"]) for row in raw["observations"]})[:3]
    if len(prefix) != 3 or prefix[-1] >= start:
        raise ValueError("three genuine earlier calibration-prefix frames required")
    prefix_frames, prefix_hashes = archived_frames(prefix, args.prefix_root)
    frames, hashes = archived_frames(times, args.dense_root)
    evidence = []
    analyzer = RealHudAnalyzer(args.profile, diagnostic_sink=evidence.append)
    if analyzer.template_profile is None:
        raise ValueError("template profile required")
    fingerprint = analyzer.template_profile.fingerprint(args.profile)
    score_fingerprint = None
    if args.score_candidate:
        readers, score_fingerprint = load_score_candidate(args.score_candidate)
        analyzer.readers.update(readers)
    if args.timer_comparison != "production":
        spec = analyzer.template_profile.raw.get("readers", {}).get("round_timer", {})
        if spec.get("comparison_preprocessing") != args.timer_comparison:
            raise ValueError("timer comparison differs from frozen declaration")
        analyzer.readers["round_timer"] = diagnostic_timer_comparison(
            analyzer.readers["round_timer"]
        )
    analyzed = analyzer.observe_frames(prefix_frames + frames)
    rows = []
    for index, row in enumerate(analyzed.observations):
        SchemaValidator().validate_hud_observation(row)
        if index >= len(prefix_frames):
            rows.append({**roster_row(row, analyzed.feature_observations[index]),
                         "current_evidence": evidence[index]})
    if len(rows) != len(times):
        raise ValueError("not every native source frame was observed")
    if (analyzer.template_profile.fingerprint(args.profile) != fingerprint
            or sha256_file(args.video) != source_hash
            or sha256_file(args.raw_processing) != raw_hash
            or (args.score_candidate and load_score_candidate(args.score_candidate)[1]
                != score_fingerprint)
            or any(sha256_file(frame.path) != record["frame_sha256"]
                   for frame, record in zip(prefix_frames + frames, prefix_hashes + hashes,
                                            strict=True))):
        raise ValueError("diagnostic input changed")
    output = {
        "scope": __doc__, "source_video_sha256": source_hash,
        "raw_processing_sha256": raw_hash, "profile_fingerprint": fingerprint,
        "score_candidate_fingerprint": score_fingerprint, "timer_comparison": args.timer_comparison,
        "implementation_sha256": sha256_file(Path(__file__)),
        "geometry": analyzed.calibration_diagnostics, "source_frames": hashes,
        "calibration_prefix_frames": prefix_hashes, "rows": rows,
        "hud_events": list(analyzed.hud_events), "qualification_created": False,
        "production_reader_replay": args.score_candidate is None
        and args.timer_comparison == "production",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"frames": len(rows), "ally_known": sum(
        row["roster"]["ally"]["accepted_count"] is not None for row in rows),
        "enemy_known": sum(row["roster"]["enemy"]["accepted_count"] is not None for row in rows),
        "hud_events": len(analyzed.hud_events), "qualification_created": False}))


if __name__ == "__main__":
    main()
