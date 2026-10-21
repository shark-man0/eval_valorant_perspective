"""Bounded DEVELOPMENT-only automatic observations and candidate runs, never GT.

Reuses VideoService, RealHudAnalyzer and the static Report header witness. There
is no evaluator, package builder, formal event release or human label import.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import tempfile
from collections import Counter
from fractions import Fraction
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from scripts.diagnostics.register_private_sources import write_private
from scripts.e2e.run_dataset_case import read_json, sha256_file
from scripts.temporal_gt.contract import require
from scripts.temporal_gt.review_session import append_exposure, load_plan, private_directory
from valorant_ai_coach.hud.analyzers import RealHudAnalyzer
from valorant_ai_coach.hud.report_header import ReportHeader, report_header_evidence
from valorant_ai_coach.video.service import VideoService


def candidate_runs(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Group consecutive *observations*, without counting physical Deaths.

    An unmatched or unavailable Report witness cannot attest Report absence.
    Reappearance may be a replay of the same Death, so it stays UNKNOWN.
    """
    runs: list[dict[str, Any]] = []
    active: dict[str, dict[str, Any]] = {}
    seen: dict[int, dict[str, Any]] = {}
    identity = None
    last = -1
    duplicates = 0
    for row in rows:
        tick = row["tick"]
        current = (row["source_sha256"], row["time_base"])
        require(type(tick) is int and tick >= 0 and Fraction(row["time_base"]) > 0, "source_pts")
        require(identity is None or current == identity, "mixed_source_or_timebase")
        identity = current
        if tick in seen:
            require(row == seen[tick], "conflicting_duplicate_pts")
            duplicates += 1
            continue
        require(tick > last, "ordered_source_pts")
        seen[tick] = row
        last = tick
        for field, kind in (("round_result", "round_end"), ("report_present", "self_death")):
            value = row[field]
            require(value is None or type(value) is bool, "tristate_observation")
            if value is not True:
                active.pop(kind, None)
                continue
            if kind not in active:
                previous = [r for r in runs if r["kind"] == kind]
                run = {
                    "candidate_id": f"{kind}_{len(previous) + 1:04d}",
                    "kind": kind,
                    "provisional_label": "ROUND_RESULT_DISPLAY_CANDIDATE"
                    if kind == "round_end" else "UNKNOWN",
                    "reason": "semantic_result_template_only_not_a_qualified_End_boundary"
                    if kind == "round_end" else "report_does_not_establish_self_identity_or_death",
                    "first_support_tick": tick,
                    "last_support_tick": tick,
                    "support_count": 0,
                    "possible_redisplay_of": previous[-1]["candidate_id"] if previous else None,
                    "physical_event_id": None,
                    "source_continuity": "UNVERIFIED",
                    "evidence": [],
                }
                runs.append(run)
                active[kind] = run
            run = active[kind]
            run["last_support_tick"] = tick
            run["support_count"] += 1
            run["evidence"].append({"tick": tick, "image_sha256": row["image_sha256"]})
    return {
        "kind": "automatic_candidates_not_gt",
        "candidates": runs,
        "candidate_counts": dict(Counter(r["kind"] for r in runs)),
        "unknown_candidates": sum(r["provisional_label"] == "UNKNOWN" for r in runs),
        "duplicate_input_rows_suppressed": duplicates,
        "persistent_support_rows_not_new_events": sum(r["support_count"] - 1 for r in runs),
        "formal_events": [],
        "precision": None, "recall": None,
        "qualification_complete": False, "approved_gt": False,
        "unmatched_or_unscanned_is_negative": False,
    }


def report_model(profile: Path) -> tuple[ReportHeader, tuple[int, ...]]:
    value = read_json(profile)
    assets = profile.parent / value["assets_file"]
    require(sha256_file(assets) == value["assets_sha256"], "report_assets_hash")
    spec = value["report_presence_header"]
    with np.load(assets, allow_pickle=False) as arrays:
        model = ReportHeader(
            arrays["report_presence_reference"], arrays["report_presence_mask"],
            arrays["report_presence_regions"], tuple(spec["input_shape"]),
            spec["reference_x"], spec["threshold"],
        )
    model.validate()
    roi = tuple(value["report_presence_search_roi"])
    require(len(roi) == 4 and all(type(v) is int for v in roi), "report_roi")
    require(0 <= roi[0] < roi[2] and 0 <= roi[1] < roi[3], "report_roi")
    require((roi[3] - roi[1], roi[2] - roi[0]) == model.input_shape, "report_geometry")
    return model, roi


def development_sources(session: Path) -> list[dict[str, Any]]:
    plan = load_plan(session)
    rows = read_json(Path(plan["batch"]) / "manifest.json")["records"]
    return sorted(
        (r for r in rows if r["status"] == "accepted" and r["split"] == "DEVELOPMENT"
         and r["exposure"] == "DEVELOPMENT"), key=lambda r: r["video_id"],
    )


def run(args: argparse.Namespace) -> None:
    require(math.isfinite(args.step_sec) and args.step_sec > 0, "positive_sampling_interval")
    require(type(args.max_frames) is int and 0 < args.max_frames <= 2000, "bounded_sample_count")
    rows = development_sources(args.session)
    require(bool(rows), "development_sources_required")
    private_directory(args.output)
    require(not any(args.output.iterdir()), "new_output_directory_required")
    analyzer = RealHudAnalyzer(args.layout, template_profile_path=args.templates)
    require(analyzer.template_profile is not None, "configured_template_profile_required")
    model, roi = report_model(args.report_profile)
    profile_hash = analyzer.fingerprint()
    report_hash = sha256_file(args.report_profile)
    report_spec = read_json(args.report_profile)
    report_assets = args.report_profile.parent / report_spec["assets_file"]
    plan = {
        "scope": "DEVELOPMENT automatic sparse observations, not GT or qualification",
        "source_ids": [r["video_id"] for r in rows],
        "source_sha256s": [r["source_sha256"] for r in rows],
        "step_sec": args.step_sec, "max_frames_per_source": args.max_frames,
        "profile_fingerprint": profile_hash, "report_profile_sha256": report_hash,
        "report_assets_sha256": report_spec["assets_sha256"],
        "script_sha256": sha256_file(Path(__file__)),
        "sample_images": "temporary JPEG at original resolution; not native lossless GT",
        "full_e2e": False, "qualification_complete": False,
    }
    write_private(args.output / "plan.json", plan)
    summaries: list[dict[str, Any]] = []
    for source in rows:
        out = args.output / source["video_id"]
        private_directory(out)
        append_exposure(
            args.session, "prediction", args.output / "plan.json",
            "Automatic DEVELOPMENT candidate analysis; predictions are not independent GT.",
            source_id=source["video_id"],
        )
        video = Path(source["managed_path"])
        require(sha256_file(video) == source["source_sha256"], "source_integrity")
        service = VideoService()
        metadata = service.probe(video)
        times = [i * args.step_sec for i in range(math.ceil(metadata.duration_sec / args.step_sec))]
        require(len(times) <= args.max_frames, "source_exceeds_sampling_budget")
        observations = []
        diagnostics: Counter[str] = Counter()
        for offset in range(0, len(times), 16):
            with tempfile.TemporaryDirectory(prefix="candidate-samples-", dir=out) as temp:
                frames = service.extract_frames(
                    video, times[offset:offset + 16], Path(temp), max_frames=16,
                    jpeg_quality=100, max_dimension=None, metadata=metadata,
                )
                require(len(frames) == len(times[offset:offset + 16]), "incomplete_decode")
                for frame in frames:
                    require(frame.source_pts_ticks is not None, "actual_source_pts_required")
                    measured = analyzer.observe_frames([frame], _build_events=False)
                    ui = measured.native_ui_measurements[0]
                    decoded = cv2.imread(str(frame.path))
                    if decoded is None:
                        raise ValueError("sample_image_decode")
                    image = np.asarray(decoded, dtype=np.uint8)
                    x1, y1, x2, y2 = roi
                    header = report_header_evidence(image[y1:y2, x1:x2], model)
                    for message in measured.diagnostics:
                        diagnostics[message] += 1
                    observations.append({
                        "tick": frame.source_pts_ticks, "time_base": frame.source_time_base,
                        "source_sha256": source["source_sha256"],
                        "image_sha256": sha256_file(frame.path),
                        "decoded_pixel_sha256": hashlib.sha256(image.tobytes()).hexdigest(),
                        "geometry_calibrated": measured.calibration.calibrated,
                        "round_result": True if ui["round_result_matched"] else None,
                        "round_result_confidence": ui["round_result_confidence"],
                        "phase_present": ui["phase_present"],
                        "report_present": header["present"], "report_score": header["score"],
                        "primary_state": measured.observations[0]["primary_state"],
                        "hud_values": measured.observations[0]["values"],
                        "ui": ui,
                    })
            print(json.dumps({"source_index": len(summaries) + 1,
                              "processed": len(observations), "planned": len(times)}), flush=True)
        require(sha256_file(video) == source["source_sha256"], "terminal_source_integrity")
        require(analyzer.fingerprint() == profile_hash, "terminal_profile_integrity")
        require(sha256_file(args.report_profile) == report_hash, "terminal_report_profile")
        require(
            sha256_file(report_assets) == plan["report_assets_sha256"], "terminal_report_assets"
        )
        result = candidate_runs(observations)
        result.update({
            "observations": observations, "source_sha256": source["source_sha256"],
            "time_base": observations[0]["time_base"], "sampling_step_sec": args.step_sec,
            "sample_count": len(observations), "diagnostics": dict(diagnostics),
            "uncalibrated_samples": sum(not r["geometry_calibrated"] for r in observations),
            "unobserved_intervals": "UNKNOWN; sparse samples cannot establish recall/continuity",
            "self_identity": "UNKNOWN; static Report header is not an identity reader",
            "terminal_source_integrity_verified": True,
        })
        write_private(out / "analysis.json", result)
        summaries.append({k: result[k] for k in (
            "candidate_counts", "unknown_candidates", "sample_count", "uncalibrated_samples",
            "persistent_support_rows_not_new_events",
        )})
    write_private(args.output / "summary.json", {
        "sources": summaries, "source_count": len(summaries), "approved_gt": False,
        "qualification_complete": False, "formal_events": [],
    })


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("session", "output", "layout", "templates", "report-profile"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--step-sec", type=float, default=5)
    parser.add_argument("--max-frames", type=int, default=2000)
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
