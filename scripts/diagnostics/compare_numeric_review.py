"""Compare a frozen diagnostic probe with explicit source labels, not lifecycle GT.

No Analyzer runs, threshold changes, production input or adoption. Output contains
only counts and content hashes; exact source labels and OCR remain local.
"""
from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter
from pathlib import Path

from scripts.diagnostics.freeze_numeric_review import FIELDS, parse_response, verify_review_assets
from scripts.e2e.run_dataset_case import sha256_file
from valorant_ai_coach.hud.calibrate_temporal import _check_output_privacy

OUTCOMES = ("correct_value", "wrong_value", "missing_visible_value",
            "correct_absent_rejection", "false_accept_absent", "unknown", "unreviewed")


def _number(value: str, field: str) -> int:
    pattern = r"[0-9]{1,2}:[0-5][0-9]" if field == "round_timer" else r"[0-9]{1,2}"
    if not isinstance(value, str) or re.fullmatch(pattern, value) is None:
        raise ValueError("accepted numeric value has invalid format")
    if field == "round_timer":
        minutes, seconds = map(int, value.split(":"))
        return minutes * 60 + seconds
    return int(value)


def classify(label: dict | None, row: dict, field: str) -> str:
    accepted = row["meets_ocr_floor_and_format"]
    if type(accepted) is not bool:
        raise ValueError("explicit diagnostic acceptance flag required")
    if accepted:
        confidence = row.get("ocr_confidence")
        if (type(confidence) not in (float, int) or not math.isfinite(confidence)
                or not .90 <= confidence <= 1 or row.get("bounds_in_roi") is None):
            raise ValueError("accepted result violates frozen OCR floor")
        actual = _number(row.get("raw_ocr_text"), field)
    if label is None:
        return "unreviewed"
    if label["kind"] == "unknown":
        return "unknown"
    if label["kind"] == "absent":
        return "false_accept_absent" if accepted else "correct_absent_rejection"
    if label["kind"] != "value":
        raise ValueError("unknown explicit label kind")
    expected = _number(label["display"], field)
    if not accepted:
        return "missing_visible_value"
    return "correct_value" if actual == expected else "wrong_value"


def compare(review_dir: Path, labels_path: Path, response_path: Path,
            probe_dir: Path, output: Path) -> dict:
    _check_output_privacy(output.resolve())
    if output.exists():
        raise FileExistsError("write a new comparison revision")
    receipt_path = review_dir / "review.json"
    summary_path = probe_dir / "probe_summary.json"
    raw_path = probe_dir / "observations.json"
    paths = (receipt_path, labels_path, response_path, summary_path, raw_path)
    before = {path: sha256_file(path) for path in paths}
    review, labels, summary, raw = (
        json.loads(path.read_text(encoding="utf-8"))
        for path in (receipt_path, labels_path, summary_path, raw_path))
    verify_review_assets(review_dir, review)
    if (labels.get("kind") != "explicit_numeric_source_review_not_lifecycle_gt"
            or labels.get("scope") != "numeric_visibility_only"
            or not labels.get("provenance_reference")
            or any(labels.get(flag) is not False for flag in (
                "production_input", "production_adoption_approved", "identity_approved",
                "event_timing_approved", "continuity_approved"))
            or labels["review_receipt_sha256"] != before[receipt_path]
            or labels["response_sha256"] != before[response_path]
            or review["probe_summary_sha256"] != before[summary_path]
            or summary["observations_sha256"] != before[raw_path]
            or raw.get("production_adopted") is not False
            or summary.get("production_adopted") is not False):
        raise ValueError("frozen evaluation binding mismatch")
    for key, probe_key in (("source_video_sha256", "source_sha256"),
                           ("candidate_report_sha256", "candidate_report_sha256")):
        if labels[key] != review[key] or labels[key] != summary[probe_key]:
            raise ValueError("source/candidate binding mismatch")
    if labels["probe_summary_sha256"] != before[summary_path]:
        raise ValueError("label/probe binding mismatch")
    explicit = parse_response(response_path.read_text(encoding="utf-8"),
                              {row["frame_number"] for row in review["frames"]})
    expected_frames = [{**row, "labels": explicit.get(row["frame_number"])}
                       for row in review["frames"]]
    if labels["frames"] != expected_frames or summary["frames"] != len(expected_frames):
        raise ValueError("labels do not match exact reviewed response/inventory")
    rows = {}
    for row in raw["localized_numeric_diagnostics_not_analyzer_input"]:
        index, field = row["sample_index"], row["region"]
        if (type(index) is not int or index < 0 or index >= len(expected_frames)
                or field not in FIELDS or (index, field) in rows
                or row.get("passed_to_analyzer") is not False
                or row.get("localization_qualified") is not False
                or row["source_image_sha256"] != expected_frames[index]["source_sha256"]):
            raise ValueError("diagnostic row/source inventory mismatch")
        rows[index, field] = row
    if len(rows) != len(expected_frames) * len(FIELDS):
        raise ValueError("missing diagnostic rows")
    counts = {field: Counter(dict.fromkeys(OUTCOMES, 0)) for field in FIELDS}
    unique = {field: Counter(dict.fromkeys(OUTCOMES, 0)) for field in FIELDS}
    missing_causes = {field: Counter({"no_crop_proposal": 0, "ocr_floor_or_format": 0})
                      for field in FIELDS}
    geometry_counts = {state: {field: Counter(dict.fromkeys(OUTCOMES, 0)) for field in FIELDS}
                       for state in ("valid", "invalid")}
    seen = {}
    for index, frame in enumerate(expected_frames):
        for field in FIELDS:
            label = frame["labels"].get(field) if frame["labels"] else None
            outcome = classify(label, rows[index, field], field)
            counts[field][outcome] += 1
            geometry_valid = rows[index, field].get("runtime_geometry_valid")
            if type(geometry_valid) is not bool:
                raise ValueError("explicit runtime geometry observation required")
            geometry_counts["valid" if geometry_valid else "invalid"][field][outcome] += 1
            if outcome == "missing_visible_value":
                reason = ("no_crop_proposal" if rows[index, field].get("bounds_in_roi") is None
                          else "ocr_floor_or_format")
                missing_causes[field][reason] += 1
            key = frame["source_sha256"], field
            evidence = label, outcome
            if key in seen and seen[key] != evidence:
                raise ValueError("duplicate image has inconsistent labels/results")
            if key not in seen:
                unique[field][outcome] += 1
                seen[key] = evidence
    result = {"kind": "exposed_development_numeric_comparison_not_lifecycle_e2e",
              "production_qualified": False, "production_adopted": False,
              "prospective_holdout": False, "temporal_assertions_evaluated": False,
              "frame_count": len(expected_frames),
              "unique_source_image_count": len({r["source_sha256"] for r in expected_frames}),
              "point_counts": {k: dict(v) for k, v in counts.items()},
              "unique_image_counts": {k: dict(v) for k, v in unique.items()},
              "missing_value_causes": {k: dict(v) for k, v in missing_causes.items()},
              "point_counts_by_runtime_geometry": {
                  state: {k: dict(v) for k, v in fields.items()}
                  for state, fields in geometry_counts.items()},
              "labels_sha256": before[labels_path], "response_sha256": before[response_path],
              "review_receipt_sha256": before[receipt_path],
              "probe_summary_sha256": before[summary_path],
              "observations_sha256": before[raw_path]}
    verify_review_assets(review_dir, review)
    if any(sha256_file(path) != digest for path, digest in before.items()):
        raise ValueError("comparison input changed")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review-dir", type=Path, required=True)
    parser.add_argument("--labels", type=Path, required=True)
    parser.add_argument("--human-response-file", type=Path, required=True)
    parser.add_argument("--probe-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(compare(args.review_dir, args.labels, args.human_response_file,
                             args.probe_dir, args.output), indent=2))


if __name__ == "__main__":
    main()
