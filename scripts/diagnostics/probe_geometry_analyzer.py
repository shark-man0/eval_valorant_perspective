"""Private, point-only HUD Analyzer trial; never installs or qualifies a profile.

Only geometry anchors change. Existing independent signal/reader assets remain
byte-identical. Reviewed geometry labels are admission checks, not analyzer input.
No GT, temporal boundaries, AI, package generation or retained app settings.
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
from collections import Counter
from copy import deepcopy
from pathlib import Path
from time import perf_counter

from scripts.diagnostics.summarize_geometry_review import summarize
from scripts.e2e.run_dataset_case import sha256_file
from scripts.e2e.run_metrics import code_fingerprint
from valorant_ai_coach.hud.analyzers import RealHudAnalyzer
from valorant_ai_coach.hud.calibrate_temporal import _check_output_privacy
from valorant_ai_coach.hud.templates import HudTemplateProfile
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


def build_trial(base_layout: Path, candidate: Path, output: Path) -> dict:
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
               "global_qualification_inherited": False,
               "identity_assets_generated": False, "production_adopted": False}
    (output / "profile_binding.json").write_text(
        json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return receipt


def probe(video: Path, base_layout: Path, candidate: Path, review: Path,
          approval: Path, output: Path) -> dict:
    # Fully bind the reviewed frozen artifacts before entering the analyzer.
    reviewed = summarize(candidate, review, approval)
    root = Path(__file__).resolve().parents[2]
    runtime_code = code_fingerprint(root)
    probe_code = sha256_file(Path(__file__))
    report_path = candidate / "candidate_report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if sha256_file(video) != report["source_sha256"]:
        raise ValueError("source video SHA mismatch")
    binding = build_trial(base_layout, candidate, output)
    sources = report["validation_frames"]
    paths = sorted((candidate / "validation_frames").glob("*.jpg"))
    frames = [FrameSample(row["source_frame_pts"], path)
              for row, path in zip(sources, paths, strict=True)]
    metadata = VideoService().probe(video)
    analyzer = RealHudAnalyzer(output / "hud_layout.json")
    if analyzer.template_profile is None or analyzer.global_qualification is not None:
        raise ValueError("trial must load its profile without inherited global qualification")
    start = perf_counter()
    measured = analyzer.observe_frames(frames, metadata, _build_events=False)
    wall = perf_counter() - start
    if (len(measured.observations) != len(frames)
            or any(row["time_sec"] != frame.time_sec
                   for row, frame in zip(measured.observations, frames, strict=True))):
        raise ValueError("point probe must preserve complete source timestamp coverage")
    validator = SchemaValidator()
    for row in measured.observations:
        validator.validate_hud_observation(row)
    if measured.hud_events:
        raise ValueError("point-only measurement unexpectedly generated events")
    trial = HudTemplateProfile.load(output / "hud_layout.templates.json")
    base = HudTemplateProfile.load(base_layout.with_suffix(".templates.json"))
    if (trial.fingerprint(output / "hud_layout.json") != binding["trial_profile_fingerprint"]
            or code_fingerprint(root) != runtime_code
            or sha256_file(Path(__file__)) != probe_code
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
           "calibration": measured.calibration_diagnostics,
           "diagnostics": measured.diagnostics}
    (output / "observations.json").write_text(
        json.dumps(raw, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    summary = {"kind": "geometry_analyzer_point_probe_not_lifecycle_e2e",
               "source_sha256": report["source_sha256"],
               "runtime_code_fingerprint": runtime_code, "probe_code_sha256": probe_code,
               "candidate_report_sha256": reviewed["candidate_report_sha256"],
               "approval_sha256": reviewed["approval_sha256"],
               "frames": len(frames), "wall_sec": wall,
               "state_counts": dict(Counter(row["primary_state"] for row in measured.observations)),
               "calibration_counts": measured.calibration_diagnostics.get("counts", {}),
               "identity_reasons": measured.calibration_diagnostics.get("identity_reasons", {}),
               "numeric_presence": {key: sum(row["values"].get(key) is not None
                                            for row in measured.observations)
                                    for key in ("round_time_remaining_sec", "score_ally",
                                                "score_enemy", "hp", "ammo_current")},
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
    args = parser.parse_args()
    print(json.dumps(probe(args.video, args.base_layout, args.candidate, args.review,
                           args.approval, args.output), allow_nan=False))


if __name__ == "__main__":
    main()
