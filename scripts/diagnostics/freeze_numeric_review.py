"""Freeze explicitly supplied numeric source labels; never infer missing labels.

Run only after receiving the actual human response. A provenance reference is
a record of the declared source, not programmatic proof of human authorship.
This tool neither edits lifecycle GT nor authorizes a production recognizer.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import math
import re
from pathlib import Path

from scripts.e2e.run_dataset_case import sha256_file
from valorant_ai_coach.hud.calibrate_temporal import _check_output_privacy

FIELDS = ("round_timer", "ally_score", "enemy_score")


def parse_response(response: str, allowed: set[int]) -> dict[int, dict]:
    parsed = {}
    for row in csv.reader(io.StringIO(response)):
        if not row or not any(item.strip() for item in row):
            continue
        if len(row) != 4:
            raise ValueError(
                "four explicit CSV columns required; approval alone supplies no labels")
        match = re.fullmatch(r"(?:Frame\s*)?([1-9][0-9]*)", row[0].strip(), re.IGNORECASE)
        if match is None:
            raise ValueError("explicit reviewed Frame number required")
        number = int(match[1])
        if number not in allowed or number in parsed:
            raise ValueError("unknown or duplicate reviewed Frame")
        labels = {}
        for name, text in zip(FIELDS, row[1:], strict=True):
            value = text.strip()
            if not value:
                labels[name] = None
            elif value in {"unknown", "absent"}:
                labels[name] = {"kind": value}
            else:
                pattern = r"[0-9]{1,2}:[0-5][0-9]" if name == "round_timer" else r"[0-9]{1,2}"
                if re.fullmatch(pattern, value) is None:
                    raise ValueError("numeric label has invalid explicit format")
                labels[name] = {"kind": "value", "display": value}
        if not any(label is not None for label in labels.values()):
            raise ValueError("empty row does not constitute a reviewed label")
        parsed[number] = labels
    if not parsed:
        raise ValueError("no explicit human numeric labels supplied")
    return parsed


def verify_review_assets(review_dir: Path, review: dict) -> None:
    if (review.get("model_outputs_exposed") is not False
            or review.get("production_input") is not False):
        raise ValueError("blind evaluation-only numeric review required")
    numbers = [row["frame_number"] for row in review["frames"]]
    if (any(type(number) is not int or number < 1 for number in numbers)
            or len(numbers) != len(set(numbers)) or not numbers):
        raise ValueError("review frame inventory invalid")
    for row in review["frames"]:
        if (type(row["source_frame_pts"]) not in (int, float)
                or not math.isfinite(row["source_frame_pts"]) or row["source_frame_pts"] < 0
                or not isinstance(row["source_sha256"], str)
                or re.fullmatch(r"[0-9a-f]{64}", row["source_sha256"]) is None):
            raise ValueError("review source binding invalid")
        if set(row["roi_assets_sha256"]) != set(FIELDS):
            raise ValueError("review ROI inventory invalid")
        for name, expected in row["roi_assets_sha256"].items():
            if not isinstance(expected, str) or re.fullmatch(r"[0-9a-f]{64}", expected) is None:
                raise ValueError("review ROI hash invalid")
            path = review_dir / f'frame_{row["frame_number"]:02d}_{name}.png'
            if sha256_file(path) != expected:
                raise ValueError("human-reviewed ROI asset changed")


def freeze(review_dir: Path, response_path: Path, provenance_reference: str, output: Path) -> dict:
    _check_output_privacy(output.resolve())
    if output.exists():
        raise FileExistsError("freeze a new private revision; never overwrite labels")
    if not provenance_reference.strip():
        raise ValueError("actual human-response provenance reference required")
    receipt_path = review_dir / "review.json"
    receipt_hash, response_hash = sha256_file(receipt_path), sha256_file(response_path)
    review = json.loads(receipt_path.read_text(encoding="utf-8"))
    verify_review_assets(review_dir, review)
    response = response_path.read_text(encoding="utf-8")
    labels = parse_response(response, {row["frame_number"] for row in review["frames"]})
    rows = [{**row, "labels": labels.get(row["frame_number"])} for row in review["frames"]]
    result = {"kind": "explicit_numeric_source_review_not_lifecycle_gt",
              "review_receipt_sha256": receipt_hash, "response_sha256": response_hash,
              "provenance_reference": provenance_reference,
              "provenance_verification": "human_authorship_requires_external_trusted_record",
              "source_video_sha256": review["source_video_sha256"],
              "probe_summary_sha256": review["probe_summary_sha256"],
              "candidate_report_sha256": review["candidate_report_sha256"],
              "scope": "numeric_visibility_only", "production_input": False,
              "production_adoption_approved": False, "identity_approved": False,
              "event_timing_approved": False, "continuity_approved": False, "frames": rows}
    verify_review_assets(review_dir, review)
    if (sha256_file(receipt_path) != receipt_hash or sha256_file(response_path) != response_hash):
        raise ValueError("review/response changed during label freezing")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review-dir", type=Path, required=True)
    parser.add_argument("--human-response-file", type=Path, required=True)
    parser.add_argument("--provenance-reference", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = freeze(args.review_dir, args.human_response_file,
                    args.provenance_reference, args.output)
    print(f'Frozen {sum(row["labels"] is not None for row in result["frames"])} explicit '
          'source rows; no production or lifecycle approval')


if __name__ == "__main__":
    main()
