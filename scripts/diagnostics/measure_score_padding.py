"""Single frozen padding experiment on private source-bound review ROIs.

No labels, GT, profile training, per-frame winner selection or event release.
This exposed development comparison cannot qualify a production recognizer.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from pathlib import Path

import cv2

from scripts.diagnostics.numeric_text_localization import propose
from scripts.e2e.run_dataset_case import sha256_file
from valorant_ai_coach.hud.calibrate_temporal import _check_output_privacy
from valorant_ai_coach.hud.templates import TesseractDigitsReader

FIELDS = ("ally_score", "enemy_score")


def measure_crop(roi, reader) -> dict:
    """Keep both outputs; unchanged .90/format gate, never select a winner."""
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY) if roi.ndim == 3 else roi
    bounds = propose(gray, timer=False)
    result = {"localized": bounds is not None, "baseline": None, "padded": None}
    if bounds is None:
        return result
    left, top, right, bottom = bounds
    crop = gray[top:bottom, left:right]
    # Blank dark border preserves the current bright-text grayscale polarity.
    # Fixed before labels: half crop height on all sides, bounded to 64 pixels.
    border = min(64, max(1, crop.shape[0] // 2))
    padded = cv2.copyMakeBorder(crop, border, border, border, border,
                                cv2.BORDER_CONSTANT, value=0)
    for name, image in (("baseline", crop), ("padded", padded)):
        read = reader.read(image, image)
        accepted = (
            isinstance(read.value, str) and re.fullmatch(r"[0-9]{1,2}", read.value) is not None
            and type(read.confidence) in (int, float) and math.isfinite(read.confidence)
            and .90 <= read.confidence <= 1
        )
        result[name] = {"raw_value": read.value, "confidence": read.confidence,
                        "accepted": bool(accepted)}
    return result


def measure(review_path: Path, partition_path: Path, output: Path) -> dict:
    _check_output_privacy(output.resolve())
    if output.exists():
        raise FileExistsError("use a new private padding measurement")
    review = json.loads(review_path.read_text(encoding="utf-8"))
    partition = json.loads(partition_path.read_text(encoding="utf-8"))
    if (
        review.get("kind") != "blind_global_numeric_review_not_lifecycle_gt"
        or review.get("production_input") is not False
        or review.get("model_outputs_exposed") is not False
        or partition.get("kind") != "development_holdout_partition_not_gt"
        or partition.get("source_video_sha256") != review.get("source_video_sha256")
        or not 1 <= len(review.get("frames", [])) <= 128
    ):
        raise ValueError("bounded source-bound blind development review required")
    development = partition["development"]
    inputs = {review_path: sha256_file(review_path),
              partition_path: sha256_file(partition_path),
              Path(__file__): sha256_file(Path(__file__))}
    inventory = []
    seen = set()
    for row in review["frames"]:
        number, pts = row["frame_number"], row["source_frame_pts"]
        if (type(number) is not int or number <= 0 or number in seen
                or row.get("labels") is not None
                or type(pts) not in (int, float) or not math.isfinite(pts)
                or not development["start_sec_inclusive"] <= pts
                < development["end_sec_exclusive"]):
            raise ValueError("unlabelled distinct development frame inventory required")
        seen.add(number)
        for field in FIELDS:
            path = review_path.parent / f"frame_{number:02d}_{field}.png"
            digest = sha256_file(path)
            if digest != row["roi_assets_sha256"][field]:
                raise ValueError("source ROI hash mismatch")
            inputs[path] = digest
            inventory.append((number, field, path))
    # Match the current empty-template native score fallback exactly: grayscale,
    # PSM7 and digits/colon whitelist. Only padding differs between the arms.
    reader = TesseractDigitsReader()
    if reader.executable is None:
        raise ValueError("local Tesseract required")
    executable = Path(reader.executable)
    inputs[executable] = sha256_file(executable)
    # Bind the complete preprocessing/reader code before opening source ROIs.
    from scripts.diagnostics import numeric_text_localization
    from valorant_ai_coach.hud import templates
    for module in (numeric_text_localization, templates):
        path = Path(module.__file__)
        inputs[path] = sha256_file(path)
    rows = []
    for number, field, path in inventory:
        roi = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
        if roi is None or not roi.size or roi.shape[0] > 1024 or roi.shape[1] > 1024:
            raise ValueError("bounded readable ROI required")
        rows.append({"frame_number": number, "field": field,
                     "roi_sha256": inputs[path], **measure_crop(roi, reader)})
    if any(sha256_file(path) != digest for path, digest in inputs.items()):
        raise ValueError("measurement inputs changed")
    summary = {
        "scope": "exposed_development_padding_comparison_not_qualification",
        "source_video_sha256": review["source_video_sha256"],
        "review_sha256": inputs[review_path], "partition_sha256": inputs[partition_path],
        "code_sha256": inputs[Path(__file__)],
        "algorithm": "half_height_blank_border_max64_before_native_default_ocr",
        "confidence_floor": .90, "per_frame_winner_selection": False,
        "counts_not_correctness": {field: {
            name: sum(row["field"] == field and row[name] is not None
                      and row[name]["accepted"] for row in rows)
            for name in ("baseline", "padded")
        } for field in FIELDS},
        "training_performed": False, "production_adopted": False,
        "qualification_created": False, "events_released": 0,
    }
    report = {"summary": summary,
              "inputs_sha256": {str(path.resolve()): digest for path, digest in inputs.items()},
              "rows": rows}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return {**summary, "receipt_sha256": hashlib.sha256(output.read_bytes()).hexdigest()}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("review", "partition", "output"):
        parser.add_argument(f"--{name}", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(measure(args.review, args.partition, args.output)))


if __name__ == "__main__":
    main()
