"""Freeze an unseen development cohort before measuring a fixed numeric proposal.

Reads prior diagnostic sampling metadata only, never GT or Validation Packs.
No training, production adoption, temporal qualification or event generation.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import shutil
from collections import Counter
from pathlib import Path

import cv2
import numpy as np

from scripts.diagnostics import numeric_text_localization
from scripts.diagnostics.build_geometry_candidate import read_frames
from scripts.diagnostics.freeze_numeric_review import FIELDS
from scripts.diagnostics.prepare_numeric_review import prepare
from scripts.e2e.frame_replay import decoder_fingerprints
from scripts.e2e.probe_cache import CachedVideoService
from scripts.e2e.run_dataset_case import sha256_file
from scripts.e2e.run_metrics import code_fingerprint
from valorant_ai_coach.hud.analyzers import RealHudAnalyzer
from valorant_ai_coach.hud.calibrate_temporal import _check_output_privacy
from valorant_ai_coach.hud.templates import HudTemplateProfile, TesseractDigitsReader
from valorant_ai_coach.schema_validation import SchemaValidator
from valorant_ai_coach.video import FrameSample, VideoService


def verify_partition(path: Path, source_sha: str, end: float) -> None:
    partition = json.loads(path.read_text(encoding="utf-8"))
    if (partition.get("kind") != "development_holdout_partition_not_gt"
            or partition.get("source_video_sha256") != source_sha):
        raise ValueError("source-bound frozen non-GT partition required")
    development, holdout = partition["development"], partition["holdout"]
    values = [development["start_sec_inclusive"], development["end_sec_exclusive"],
              holdout["start_sec_inclusive"], holdout["end_sec_exclusive"], end]
    if (any(type(v) not in (int, float) or not math.isfinite(v) for v in values)
            or values[0] != 0 or not 0 < values[1] == values[2] < values[3]
            or end != values[1]):
        raise ValueError("development limit must equal frozen partition, never holdout")


def toolchain_fingerprints() -> dict:
    service = VideoService()
    probe, pixels = decoder_fingerprints(service.ffprobe_path)
    executable = shutil.which("tesseract")
    if executable is None:
        raise ValueError("prospective numeric qualification requires local Tesseract")
    return {"probe": probe, "decoded_pixels": pixels, "tesseract": sha256_file(Path(executable))}


def sampling_times(end: float, previous: list[float], *, phase: float = 16.75,
                   period: float = 30) -> list[float]:
    if (type(end) not in (int, float) or not math.isfinite(end) or end <= 0
            or any(type(t) not in (int, float) or not math.isfinite(t) or t < 0
                   for t in previous)):
        raise ValueError("finite development boundary/prior diagnostic PTS required")
    if (type(phase) not in (int, float) or type(period) not in (int, float)
            or not math.isfinite(phase) or not math.isfinite(period)
            or not 5 <= period <= 30 or not 0 <= phase < period):
        raise ValueError("bounded fixed phase/period required")
    # Fixed before image inspection; neither state nor OCR/GT chooses samples.
    times = [phase + period * i for i in range(math.ceil(end / period))
             if phase + period * i < end
             and all(abs(phase + period * i - old) >= 2 for old in previous)]
    if len(times) < 8:
        raise ValueError("insufficient untouched development points")
    return times


def select_low_contrast(images: list, records: list[dict], layout) -> tuple[list[int], dict]:
    """Candidate negatives only: rank raw ROI contrast before invoking any OCR.

    No absence/state assertion is inferred. Human source labels are still needed.
    Exact duplicate images are not chosen as separate review conditions.
    """
    selected, ranks = set(), {}
    for field in FIELDS:
        scores = []
        for index, image in enumerate(images):
            x1, y1, x2, y2 = layout.normalized_roi(field).pixel_bounds(
                image.shape[1], image.shape[0])
            gray = cv2.cvtColor(image[y1:y2, x1:x2], cv2.COLOR_BGR2GRAY)
            scores.append((float(np.std(gray)), index))
        unique, chosen = set(), []
        for contrast, index in sorted(scores):
            digest = records[index]["sha256"]
            if digest in unique:
                continue
            unique.add(digest)
            chosen.append({"pool_index": index, "contrast": contrast})
            selected.add(index)
            if len(chosen) == 6:
                break
        ranks[field] = chosen
    # If a duplicate was selected for a different ROI, still review it only once.
    seen, indices = set(), []
    for index in sorted(selected):
        if records[index]["sha256"] not in seen:
            indices.append(index)
            seen.add(records[index]["sha256"])
    return indices, {"method": "lowest_raw_roi_contrast_six_per_field",
                     "ranking": ranks, "selected_pool_indices": indices,
                     "absence_inferred": False, "ocr_used_for_selection": False}


def freeze_plan(video: Path, source_sha: str, trial: Path, histories: list[Path],
                end: float, output: Path, *, partition: Path, phase: float = 16.75,
                period: float = 30, low_contrast_candidates: bool = False,
                prior_numeric_probes: list[Path] | None = None) -> dict:
    _check_output_privacy(output.resolve())
    if output.exists():
        raise FileExistsError("freeze a new private prospective plan")
    verify_partition(partition, source_sha, end)
    previous, excluded_hashes = [], set()
    for path in histories:
        history = json.loads(path.read_text(encoding="utf-8"))
        if (history.get("source_sha256") != source_sha
                or history.get("candidate_assets_frozen_before_validation") is not True
                or history.get("production_adopted") is not False
                or history.get("identity_assets_generated") is not False):
            raise ValueError("only same-source unadopted geometry diagnostics permitted")
        for row in history["training_frames"] + history["validation_frames"]:
            previous.append(row["source_frame_pts"])
            excluded_hashes.add(row["sha256"])
    numeric_inputs = []
    for directory in prior_numeric_probes or []:
        report_path = directory / "candidate_report.json"
        summary_path = directory / "probe_summary.json"
        report = json.loads(report_path.read_text(encoding="utf-8"))
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        if (summary.get("kind") != "prospective_numeric_point_probe_not_lifecycle_e2e"
                or summary.get("source_sha256") != source_sha
                or summary.get("production_adopted") is not False
                or summary.get("candidate_report_sha256") != sha256_file(report_path)
                or report.get("source_sha256") != source_sha
                or report.get("training_performed") is not False):
            raise ValueError("only bound unadopted numeric sampling history permitted")
        for row in report["validation_frames"]:
            previous.append(row["source_frame_pts"])
            excluded_hashes.add(row["sha256"])
        numeric_inputs.extend((report_path, summary_path))
    times = sampling_times(end, previous, phase=phase, period=period)
    if sha256_file(video) != source_sha:
        raise ValueError("source video mismatch")
    layout, profile = trial / "hud_layout.json", trial / "hud_layout.templates.json"
    assets = HudTemplateProfile.load(profile)
    paths = [layout, profile, partition, *histories, *numeric_inputs, Path(__file__),
             Path(numeric_text_localization.__file__),
             *[assets.resolve_asset(str(p)) for p in assets.asset_paths]]
    result = {"kind": "prospective_numeric_point_plan_not_lifecycle_gt",
              "schema_version": 2, "partition_path": str(partition.resolve()),
              "source_sha256": source_sha, "source_path": str(video.resolve()),
              "trial_layout_path": str(layout.resolve()), "development_end_sec": end,
              "times": times, "period_sec": period, "phase_sec": phase,
              "review_selection": "low_contrast_candidates" if low_contrast_candidates else "all",
              "exclusion_radius_sec": 2, "excluded_source_hashes": sorted(excluded_hashes),
              "inputs_sha256": {str(p.resolve()): sha256_file(p) for p in paths},
              "runtime_code_fingerprint": code_fingerprint(Path(__file__).resolve().parents[2]),
              "toolchain_fingerprints": toolchain_fingerprints(),
              "production_adopted": False, "training_performed": False,
              "evaluation_holdout_used": False, "source_labels_available": False}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def measure(plan_path: Path, output: Path) -> dict:
    _check_output_privacy(output.resolve())
    if output.exists():
        raise FileExistsError("measure only once into a new private directory")
    plan_hash = sha256_file(plan_path)
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    if (plan.get("kind") != "prospective_numeric_point_plan_not_lifecycle_gt"
            or plan.get("schema_version") != 2):
        raise ValueError("frozen v2 partition-bound prospective plan required; do not rewrite v1")
    video, layout = Path(plan["source_path"]), Path(plan["trial_layout_path"])
    root = Path(__file__).resolve().parents[2]
    selection_hash = None

    def verify():
        verify_partition(Path(plan["partition_path"]), plan["source_sha256"],
                         plan["development_end_sec"])
        if (sha256_file(plan_path) != plan_hash
                or toolchain_fingerprints() != plan["toolchain_fingerprints"]
                or code_fingerprint(root) != plan["runtime_code_fingerprint"]
                or sha256_file(video) != plan["source_sha256"]
                or (selection_hash is not None and sha256_file(
                    output / "review_selection.json") != selection_hash)
                or any(sha256_file(Path(p)) != h for p, h in plan["inputs_sha256"].items())):
            raise ValueError("frozen source/code/profile inputs changed")

    verify()
    output.mkdir(parents=True)
    (output / "hud_layout.json").write_bytes(layout.read_bytes())
    service = VideoService()
    decoder, _ = decoder_fingerprints(service.ffprobe_path)
    cached = CachedVideoService(service, Path("outputs/e2e_cache/probe"),
                                plan["source_sha256"], decoder)
    metadata = cached.probe(video)
    if plan["development_end_sec"] > metadata.duration_sec:
        raise ValueError("development window outside source")
    select_candidates = plan.get("review_selection") == "low_contrast_candidates"
    directory = output / ("pool_frames" if select_candidates else "validation_frames")
    images, records = read_frames(cached, video, plan["times"], directory, metadata)
    if any(not 0 <= r["source_frame_pts"] < plan["development_end_sec"] for r in records):
        raise ValueError("decoded point escaped development partition")
    if select_candidates:
        from valorant_ai_coach.hud.layout import HudLayout
        indices, selection = select_low_contrast(images, records, HudLayout.load(layout))
        selection.update(plan_sha256=plan_hash, pool_records=records,
                         selection_frozen_before_numeric_measurement=True)
        (output / "review_selection.json").write_text(json.dumps(selection, indent=2) + "\n")
        selection_hash = sha256_file(output / "review_selection.json")
        pool_paths = sorted(directory.glob("*.jpg"))
        (output / "validation_frames").mkdir()
        for number, index in enumerate(indices):
            destination = output / "validation_frames" / f"frame_{number:05d}.jpg"
            shutil.copyfile(pool_paths[index], destination)
        images, records = [images[i] for i in indices], [records[i] for i in indices]
    # Frozen capture images may duplicate earlier images despite new PTS. Keep
    # the cohort (no outcome-driven replacement), and report overlap explicitly.
    report = {"source_sha256": plan["source_sha256"], "validation_frames": records,
              "plan_sha256": plan_hash, "training_performed": False}
    report_path = output / "candidate_report.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    scans = []
    analyzer = RealHudAnalyzer(layout, diagnostic_sink=scans.append)
    if analyzer.global_qualification is not None:
        raise ValueError("unqualified point probe must not inherit temporal qualification")
    paths = sorted((output / "validation_frames").glob("*.jpg"))
    frames = [FrameSample(row["source_frame_pts"], path)
              for row, path in zip(records, paths, strict=True)]
    measured = analyzer.observe_frames(frames, metadata, _build_events=False)
    if (measured.hud_events or len(measured.observations) != len(frames)
            or len(scans) != len(frames)
            or any(row["source_pts_sec"] != frame.time_sec
                   for row, frame in zip(scans, frames, strict=True))):
        raise ValueError("point-only coverage/events contract violated")
    validator = SchemaValidator()
    for row, frame in zip(measured.observations, frames, strict=True):
        validator.validate_hud_observation(row)
        if row["time_sec"] != frame.time_sec:
            raise ValueError("observation source PTS mismatch")
    localized = []
    reader = TesseractDigitsReader()
    for index, image in enumerate(images):
        for name in FIELDS:
            x1, y1, x2, y2 = analyzer.layout.normalized_roi(name).pixel_bounds(
                metadata.width, metadata.height)
            gray = cv2.cvtColor(image[y1:y2, x1:x2], cv2.COLOR_BGR2GRAY)
            bounds = numeric_text_localization.propose(gray, timer=name == "round_timer")
            row = {"sample_index": index, "region": name, "bounds_in_roi": bounds,
                   "source_image_sha256": records[index]["sha256"],
                   "runtime_geometry_valid": scans[index]["geometry_calibrated"],
                   "localization_qualified": False, "passed_to_analyzer": False,
                   "meets_ocr_floor_and_format": False}
            if bounds:
                a, b, c, d = bounds
                value = reader.read(image, gray[b:d, a:c])
                pattern = r"[0-9]{1,2}:[0-5][0-9]" if name == "round_timer" else r"[0-9]{1,2}"
                row.update(raw_ocr_text=value.value, ocr_confidence=value.confidence,
                           meets_ocr_floor_and_format=(value.value is not None
                           and value.confidence >= .90
                           and re.fullmatch(pattern, value.value) is not None))
            localized.append(row)
    raw_path = output / "observations.json"
    raw_path.write_text(json.dumps({"production_adopted": False,
        "observations": measured.observations, "hud_events": [],
        "producer_diagnostics": scans,
        "localized_numeric_diagnostics_not_analyzer_input": localized}, indent=2) + "\n")
    summary = {"kind": "prospective_numeric_point_probe_not_lifecycle_e2e",
               "source_sha256": plan["source_sha256"], "plan_sha256": plan_hash,
               "runtime_code_fingerprint": plan["runtime_code_fingerprint"],
               "candidate_report_sha256": sha256_file(report_path),
               "frames": len(records), "observations_sha256": sha256_file(raw_path),
               "pool_frame_count": len(plan["times"]),
               "source_selection_kind": plan.get("review_selection", "all"),
               "selection_sha256": selection_hash,
               "low_contrast_is_absence_proof": False,
               "production_adopted": False, "production_qualified": False,
               "previous_source_image_overlap_count": sum(
                   r["sha256"] in plan["excluded_source_hashes"] for r in records),
               "unique_image_count": len({r["sha256"] for r in records}),
               "state_counts": dict(Counter(r["primary_state"] for r in measured.observations)),
               "ocr_floor_and_format_counts_not_correctness": {name: sum(
                   r["region"] == name and r["meets_ocr_floor_and_format"] for r in localized)
                   for name in FIELDS}, "event_count": 0, "source_review_pending": True}
    verify()
    (output / "probe_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    prepare(output, output, output / "blind_review")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    freeze = sub.add_parser("freeze")
    freeze.add_argument("--video", type=Path, required=True)
    freeze.add_argument("--source-sha256", required=True)
    freeze.add_argument("--trial", type=Path, required=True)
    freeze.add_argument("--history", type=Path, action="append", required=True)
    freeze.add_argument("--development-end", type=float, required=True)
    freeze.add_argument("--partition", type=Path, required=True)
    freeze.add_argument("--sampling-phase", type=float, default=16.75)
    freeze.add_argument("--sampling-period", type=float, default=30)
    freeze.add_argument("--low-contrast-candidates", action="store_true")
    freeze.add_argument("--prior-numeric-probe", type=Path, action="append")
    freeze.add_argument("--output", type=Path, required=True)
    run = sub.add_parser("measure")
    run.add_argument("--plan", type=Path, required=True)
    run.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = (freeze_plan(args.video, args.source_sha256, args.trial, args.history,
                          args.development_end, args.output, partition=args.partition,
                          phase=args.sampling_phase, period=args.sampling_period,
                          low_contrast_candidates=args.low_contrast_candidates,
                          prior_numeric_probes=args.prior_numeric_probe)
              if args.command == "freeze"
              else measure(args.plan, args.output))
    print(json.dumps({k: v for k, v in result.items()
                      if k not in {"inputs_sha256", "source_path", "trial_layout_path"}}, indent=2))


if __name__ == "__main__":
    main()
