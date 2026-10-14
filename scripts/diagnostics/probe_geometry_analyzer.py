"""Private, point-only HUD Analyzer trial; never installs or qualifies a profile.

By default only geometry anchors change. Opt-in missing global digit readers
are unqualified proposals with minimum confidence .90; existing readers are
never replaced. Independent assets remain byte-identical. Reviewed geometry
labels are admission checks, not analyzer input.
No GT, temporal boundaries, AI, package generation or retained app settings.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import shutil
from collections import Counter
from copy import deepcopy
from pathlib import Path
from time import perf_counter

import cv2

from scripts.diagnostics import numeric_text_localization
from scripts.diagnostics.summarize_geometry_review import summarize
from scripts.e2e.run_dataset_case import sha256_file
from scripts.e2e.run_metrics import code_fingerprint
from valorant_ai_coach.hud.analyzers import RealHudAnalyzer
from valorant_ai_coach.hud.calibrate_temporal import _check_output_privacy
from valorant_ai_coach.hud.templates import HudTemplateProfile, TesseractDigitsReader
from valorant_ai_coach.schema_validation import SchemaValidator
from valorant_ai_coach.video import FrameSample, VideoService


def _absolute_assets(raw: dict, profile: HudTemplateProfile) -> dict:
    paths = {str(p): str(profile.resolve_asset(str(p)).resolve()) for p in profile.asset_paths}

    def replace(value):
        if isinstance(value, dict):
            return {key: replace(child) for key, child in value.items()}
        if isinstance(value, list):
            return [replace(child) for child in value]
        return paths.get(value, value) if isinstance(value, str) else value

    return replace(deepcopy(raw))


def add_global_digit_proposals(raw: dict) -> list[str]:
    """Add absent global readers only; no fallback, template training or overrides."""
    added = []
    for name in ("round_timer", "ally_score", "enemy_score"):
        if name not in raw["readers"]:
            raw["readers"][name] = {
                "kind": "digits", "minimum_confidence": .90,
                "format": "timer_mmss" if name == "round_timer" else "integer",
                "templates": {},
            }
            added.append(name)
    return added


def build_trial(base_layout: Path, candidate: Path, output: Path, *,
                global_digits: bool = False, retain_base_geometry: bool = False) -> dict:
    if type(global_digits) is not bool or type(retain_base_geometry) is not bool:
        raise ValueError("trial options must be explicitly boolean")
    _check_output_privacy(output.resolve())
    if output.exists():
        raise FileExistsError("use a new private diagnostic directory")
    frozen = json.loads((candidate / "candidate_fingerprint.json").read_text(encoding="utf-8"))
    for name, digest in frozen.items():
        path = (candidate / name).resolve()
        if not path.is_relative_to(candidate.resolve()) or sha256_file(path) != digest:
            raise ValueError("frozen geometry candidate changed or escaped")
    if sha256_file(base_layout) != sha256_file(candidate / "hud_layout.json"):
        raise ValueError("candidate and base layout must be identical")
    base = HudTemplateProfile.load(base_layout.with_suffix(".templates.json"))
    geometry = HudTemplateProfile.load(candidate / "hud_layout.templates.json")
    if (set(geometry.raw) != {"schema_version", "anchors", "signals", "readers"}
            or geometry.raw["signals"] or geometry.raw["readers"]
            or len(geometry.raw["anchors"]) < 3):
        raise ValueError("candidate must contain geometry only and at least three anchors")
    for name, spec in geometry.raw["anchors"].items():
        threshold = spec.get("threshold")
        floor = base.raw.get("anchors", {}).get(name, {}).get("threshold", .90)
        if (type(threshold) not in (int, float) or not math.isfinite(threshold)
                or not max(.90, floor) <= threshold <= 1):
            raise ValueError("geometry threshold must not be weakened")
        for key in ("template", "mask"):
            path = geometry.resolve_asset(spec[key]).resolve()
            if (not path.is_relative_to(candidate.resolve())
                    or path.relative_to(candidate.resolve()).as_posix() not in frozen):
                raise ValueError("geometry asset outside frozen inventory")
    nonanchor = {key: value for key, value in base.raw.items() if key != "anchors"}
    independent = HudTemplateProfile._find_asset_paths(nonanchor)
    independent_hashes = {str(p): sha256_file(base.resolve_asset(str(p))) for p in independent}
    geometry_hashes = {sha256_file(geometry.resolve_asset(str(p))) for p in geometry.asset_paths}
    if geometry_hashes & set(independent_hashes.values()):
        raise ValueError("geometry asset cannot be reused as independent signal/reader evidence")
    before = base.fingerprint(base_layout)
    mixed = _absolute_assets(base.raw, base)
    mixed["anchors"] = _absolute_assets(geometry.raw, geometry)["anchors"]
    retained = {}
    if retain_base_geometry:
        for name, spec in base.raw.get("anchors", {}).items():
            if name in mixed["anchors"]:
                continue
            threshold = spec.get("threshold", .90)
            if (name not in {"round_timer", "top_match_bar", "player_hp_armor", "abilities"}
                    or type(threshold) not in (int, float) or not math.isfinite(threshold)
                    or not .90 <= threshold <= 1 or not spec.get("template")
                    or not spec.get("mask")):
                raise ValueError("retained geometry requires named masked anchors and NCC >=.90")
            hashes = {str(p): sha256_file(base.resolve_asset(str(p)))
                      for p in HudTemplateProfile._find_asset_paths(spec)}
            if set(hashes.values()) & set(independent_hashes.values()):
                raise ValueError("retained geometry cannot be reused as independent evidence")
            retained[name] = {"threshold": threshold, "asset_hashes": hashes}
            mixed["anchors"][name] = _absolute_assets({"anchor": spec}, base)["anchor"]
    added = add_global_digit_proposals(mixed) if global_digits else []
    output.mkdir(parents=True)
    layout_path = output / "hud_layout.json"
    shutil.copyfile(base_layout, layout_path)
    profile_path = layout_path.with_suffix(".templates.json")
    profile_path.write_text(json.dumps(mixed, indent=2) + "\n", encoding="utf-8")
    trial = HudTemplateProfile.load(profile_path)
    if base.fingerprint(base_layout) != before:
        raise ValueError("base profile changed during trial preparation")
    receipt = {"kind": "geometry_only_private_trial_not_adoption",
               "base_profile_fingerprint": before,
               "trial_profile_fingerprint": trial.fingerprint(layout_path),
               "independent_assets_sha256": independent_hashes,
               "global_digit_proposals": added,
               "retained_base_geometry": retained,
               "retained_base_geometry_new_source_reviewed": False,
               "global_digit_readers_qualified": False,
               "global_qualification_inherited": False,
               "identity_assets_generated": False, "production_adopted": False}
    (output / "profile_binding.json").write_text(
        json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return receipt


def probe(video: Path, base_layout: Path, candidate: Path, review: Path,
          approval: Path, output: Path, *, global_digits: bool = False,
          diagnose_numeric_localization: bool = False,
          retain_base_geometry: bool = False) -> dict:
    # Fully bind the reviewed frozen artifacts before entering the analyzer.
    reviewed = summarize(candidate, review, approval)
    root = Path(__file__).resolve().parents[2]
    runtime_code = code_fingerprint(root)
    probe_code = sha256_file(Path(__file__))
    localization_code = sha256_file(Path(numeric_text_localization.__file__))
    report_path = candidate / "candidate_report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if sha256_file(video) != report["source_sha256"]:
        raise ValueError("source video SHA mismatch")
    binding = build_trial(base_layout, candidate, output, global_digits=global_digits,
                          retain_base_geometry=retain_base_geometry)
    sources = report["validation_frames"]
    paths = sorted((candidate / "validation_frames").glob("*.jpg"))
    frames = [FrameSample(row["source_frame_pts"], path)
              for row, path in zip(sources, paths, strict=True)]
    metadata = VideoService().probe(video)
    scans = []
    analyzer = RealHudAnalyzer(output / "hud_layout.json", diagnostic_sink=scans.append)
    if analyzer.template_profile is None or analyzer.global_qualification is not None:
        raise ValueError("trial must load its profile without inherited global qualification")
    start = perf_counter()
    measured = analyzer.observe_frames(frames, metadata, _build_events=False)
    wall = perf_counter() - start
    if (len(measured.observations) != len(frames)
            or any(row["time_sec"] != frame.time_sec
                   for row, frame in zip(measured.observations, frames, strict=True))):
        raise ValueError("point probe must preserve complete source timestamp coverage")
    if (len(scans) != len(frames)
            or any(row["source_pts_sec"] != frame.time_sec
                   for row, frame in zip(scans, frames, strict=True))):
        raise ValueError("point probe must preserve producer diagnostic coverage")
    validator = SchemaValidator()
    for row in measured.observations:
        validator.validate_hud_observation(row)
    if measured.hud_events:
        raise ValueError("point-only measurement unexpectedly generated events")
    localized = []
    if diagnose_numeric_localization:
        # These measurements never enter the Analyzer, observations or events.
        # Configuration ROI cropping here is explicitly unqualified, not a
        # bypass of production crop_roi's calibration contract.
        reader = TesseractDigitsReader()
        for index, frame in enumerate(frames):
            image = cv2.imread(str(frame.path))
            for name in ("round_timer", "ally_score", "enemy_score"):
                x1, y1, x2, y2 = analyzer.layout.normalized_roi(name).pixel_bounds(
                    image.shape[1], image.shape[0])
                gray = cv2.cvtColor(image[y1:y2, x1:x2], cv2.COLOR_BGR2GRAY)
                bounds = numeric_text_localization.propose(gray, timer=name == "round_timer")
                row = {"sample_index": index, "region": name, "bounds_in_roi": bounds,
                       "localization_qualified": False, "passed_to_analyzer": False,
                       "runtime_geometry_valid": scans[index]["geometry_calibrated"],
                       "source_image_sha256": sources[index]["sha256"],
                       "meets_ocr_floor_and_format": False}
                if bounds is not None:
                    left, top, right, bottom = bounds
                    result = reader.read(image, gray[top:bottom, left:right])
                    pattern = r"[0-9]{1,2}:[0-5][0-9]" if name == "round_timer" else r"[0-9]{1,2}"
                    row.update(raw_ocr_text=result.value, ocr_confidence=result.confidence,
                               sources=result.sources,
                               meets_ocr_floor_and_format=(
                                   result.value is not None and result.confidence >= .90
                                   and re.fullmatch(pattern, result.value) is not None))
                localized.append(row)
    trial = HudTemplateProfile.load(output / "hud_layout.templates.json")
    base = HudTemplateProfile.load(base_layout.with_suffix(".templates.json"))
    if (trial.fingerprint(output / "hud_layout.json") != binding["trial_profile_fingerprint"]
            or code_fingerprint(root) != runtime_code
            or sha256_file(Path(__file__)) != probe_code
            or sha256_file(Path(numeric_text_localization.__file__)) != localization_code
            or base.fingerprint(base_layout) != binding["base_profile_fingerprint"]
            or sha256_file(video) != report["source_sha256"]
            or sha256_file(report_path) != reviewed["candidate_report_sha256"]
            or sha256_file(review) != reviewed["review_receipt_sha256"]
            or sha256_file(approval) != reviewed["approval_sha256"]
            or sha256_file(candidate / "candidate_fingerprint.json") != (
                reviewed["candidate_fingerprint_sha256"])
            or any(sha256_file(path) != row["sha256"]
                   for path, row in zip(paths, sources, strict=True))):
        raise ValueError("trial inputs changed during measurement")
    raw = {"input_scope": "isolated_points", "production_adopted": False,
           "observations": measured.observations, "hud_events": [],
           "producer_diagnostics": scans,
           "localized_numeric_diagnostics_not_analyzer_input": localized,
           "calibration": measured.calibration_diagnostics,
           "diagnostics": measured.diagnostics}
    (output / "observations.json").write_text(
        json.dumps(raw, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    summary = {"kind": "geometry_analyzer_point_probe_not_lifecycle_e2e",
               "source_sha256": report["source_sha256"],
               "runtime_code_fingerprint": runtime_code, "probe_code_sha256": probe_code,
               "numeric_localization_code_sha256": localization_code,
               "candidate_report_sha256": reviewed["candidate_report_sha256"],
               "approval_sha256": reviewed["approval_sha256"],
               "frames": len(frames), "wall_sec": wall,
               "global_digit_proposals": binding["global_digit_proposals"],
               "global_digit_readers_qualified": False,
               "state_counts": dict(Counter(row["primary_state"] for row in measured.observations)),
               "calibration_counts": measured.calibration_diagnostics.get("counts", {}),
               "identity_reasons": measured.calibration_diagnostics.get("identity_reasons", {}),
               "numeric_presence": {key: sum(row["values"].get(key) is not None
                                            for row in measured.observations)
                                    for key in ("round_time_remaining_sec", "score_ally",
                                                "score_enemy", "hp", "ammo_current")},
               "raw_global_numeric_presence": {
                   key: sum(key in row["raw_accepted_reader_values"] for row in scans)
                   for key in ("round_timer", "ally_score", "enemy_score")},
               "localized_diagnostic_counts_not_qualified": {
                   name: {"proposed_crop_count": sum(row["bounds_in_roi"] is not None
                                                    for row in localized if row["region"] == name),
                          "ocr_floor_and_format_count": sum(row["meets_ocr_floor_and_format"]
                                                            for row in localized
                                                            if row["region"] == name)}
                   for name in ("round_timer", "ally_score", "enemy_score")
               } if diagnose_numeric_localization else None,
               "schema_valid_observation_count": len(measured.observations),
               "event_count": 0, "temporal_assertions_evaluated": False,
               "production_qualified": False, "production_adopted": False,
               "observations_sha256": sha256_file(output / "observations.json")}
    (output / "probe_summary.json").write_text(
        json.dumps(summary, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("video", "base-layout", "candidate", "review", "approval", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--global-digits", action="store_true",
                        help="Propose absent Timer/Score readers locally; not qualification")
    parser.add_argument("--diagnose-numeric-localization", action="store_true",
                        help="Measure unqualified component crops outside the Analyzer")
    parser.add_argument("--retain-base-geometry", action="store_true",
                        help="Retain missing masked base anchors at original NCC; unqualified")
    args = parser.parse_args()
    print(json.dumps(probe(args.video, args.base_layout, args.candidate, args.review,
                           args.approval, args.output,
                           global_digits=args.global_digits,
                           diagnose_numeric_localization=args.diagnose_numeric_localization,
                           retain_base_geometry=args.retain_base_geometry),
                     allow_nan=False))


if __name__ == "__main__":
    main()
