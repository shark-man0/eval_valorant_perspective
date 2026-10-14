"""Exercise unqualified numeric proposals through the real point Analyzer only.

No GT/labels, continuous lifecycle, qualification file, settings, or adoption.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from scripts.diagnostics import localized_digits_reader, numeric_text_localization
from scripts.e2e.run_dataset_case import sha256_file
from scripts.e2e.run_metrics import code_fingerprint
from valorant_ai_coach.hud.analyzers import RealHudAnalyzer
from valorant_ai_coach.hud.calibrate_temporal import _check_output_privacy
from valorant_ai_coach.hud.templates import HudTemplateProfile
from valorant_ai_coach.schema_validation import SchemaValidator
from valorant_ai_coach.video import FrameSample, VideoService


def probe(video: Path, layout: Path, cohort: Path, output: Path) -> dict:
    _check_output_privacy(output.resolve())
    if output.exists():
        raise FileExistsError("use a new private connection probe directory")
    summary_path, report_path = cohort / "probe_summary.json", cohort / "candidate_report.json"
    summary, report = (json.loads(path.read_text(encoding="utf-8"))
                       for path in (summary_path, report_path))
    profile_path = layout.with_suffix(".templates.json")
    if (summary.get("production_adopted") is not False
            or summary["candidate_report_sha256"] != sha256_file(report_path)
            or summary["observations_sha256"] != sha256_file(cohort / "observations.json")
            or summary["source_sha256"] != report["source_sha256"]
            or sha256_file(layout) != sha256_file(cohort / "hud_layout.json")
            or layout.with_name(layout.stem + ".global_qualification.json").exists()):
        raise ValueError("source-bound unadopted cohort without qualification required")
    profile = HudTemplateProfile.load(profile_path)
    paths = sorted((cohort / "validation_frames").glob("*.jpg"))
    records = report["validation_frames"]
    if (len(paths) != len(records) or len(records) != summary["frames"]
            or any(sha256_file(path) != row["sha256"]
                   for path, row in zip(paths, records, strict=True))):
        raise ValueError("cohort source image inventory changed")
    inputs = [layout, profile_path, summary_path, report_path, *paths,
              cohort / "observations.json", Path(__file__),
              Path(localized_digits_reader.__file__), Path(numeric_text_localization.__file__),
              *[profile.resolve_asset(str(p)) for p in profile.asset_paths]]
    hashes = {path: sha256_file(path) for path in inputs}
    root = Path(__file__).resolve().parents[2]
    code = code_fingerprint(root)
    if code != summary["runtime_code_fingerprint"] or sha256_file(video) != report["source_sha256"]:
        raise ValueError("runtime/source changed since frozen cohort")
    scans = []
    analyzer = RealHudAnalyzer(layout, readers=localized_digits_reader.build_readers(profile),
                              diagnostic_sink=scans.append)
    if analyzer.global_qualification is not None or analyzer._native_profile_readers:
        raise ValueError("injected diagnostic readers cannot enter qualified/native route")
    frames = [FrameSample(row["source_frame_pts"], path)
              for row, path in zip(records, paths, strict=True)]
    result = analyzer.observe_frames(frames, VideoService().probe(video), _build_events=False)
    if (result.hud_events or len(result.observations) != len(frames)
            or len(scans) != len(frames)):
        raise ValueError("point-only complete coverage without events required")
    validator = SchemaValidator()
    for row, scan, frame in zip(result.observations, scans, frames, strict=True):
        validator.validate_hud_observation(row)
        if row["time_sec"] != frame.time_sec or scan["source_pts_sec"] != frame.time_sec:
            raise ValueError("numeric connection probe changed source PTS")
        if row["values"]["player_specific_hud_valid"]:
            raise ValueError("numeric-only trial unexpectedly authorized player ownership")
    if (code_fingerprint(root) != code or sha256_file(video) != report["source_sha256"]
            or any(sha256_file(path) != h for path, h in hashes.items())):
        raise ValueError("frozen source/reader/assets changed during connection probe")
    output.mkdir(parents=True)
    raw = output / "observations.json"
    raw.write_text(json.dumps({"observations": result.observations,
        "producer_diagnostics": scans, "hud_events": [], "production_adopted": False},
        indent=2, allow_nan=False) + "\n", encoding="utf-8")
    counts = {}
    for region, field in (("round_timer", "round_time_remaining_sec"),
                          ("ally_score", "score_ally"), ("enemy_score", "score_enemy")):
        counts[region] = {"producer_accepted": sum(
            scan["raw_accepted_reader_values"].get(region) is not None for scan in scans),
            "normalized_observation_values": sum(row["values"].get(field) is not None
                                                  for row in result.observations)}
    receipt = {"kind": "diagnostic_numeric_reader_connection_not_lifecycle_e2e",
               "source_sha256": report["source_sha256"], "runtime_code_fingerprint": code,
               "cohort_summary_sha256": hashes[summary_path],
               "adapter_code_sha256": hashes[Path(localized_digits_reader.__file__)],
               "frames": len(frames), "numeric_counts": counts,
               "state_counts": dict(Counter(row["primary_state"] for row in result.observations)),
               "event_count": 0, "ownership_promotions": 0,
               "production_adopted": False, "production_qualified": False,
               "native_qualified_route": False, "observations_sha256": sha256_file(raw)}
    (output / "summary.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("video", "layout", "cohort", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(probe(args.video, args.layout, args.cohort, args.output), indent=2))


if __name__ == "__main__":
    main()
