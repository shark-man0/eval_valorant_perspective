"""Freeze sparse human absence labels and test a fixed diagnostic reader.

Source review is evaluation-only. Expected labels never enter the reader.
No production profile, native geometry bypass or qualification is created.
"""
from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path

import cv2

from scripts.diagnostics import localized_digits_reader, numeric_text_localization
from scripts.diagnostics.prospective_numeric_probe import toolchain_fingerprints
from scripts.e2e.run_dataset_case import sha256_file
from scripts.e2e.run_metrics import code_fingerprint
from valorant_ai_coach.hud.calibrate_temporal import _check_output_privacy
from valorant_ai_coach.hud.layout import HudLayout
from valorant_ai_coach.hud.templates import HudTemplateProfile

FIELDS = ("ally_score", "enemy_score")


def parse_response(text: str, allowed: set[int]) -> dict:
    if text.strip() == "該当なし":
        return {}
    roles = {"両方非表示": FIELDS, "味方のみ非表示": ("ally_score",),
             "敵のみ非表示": ("enemy_score",)}
    labels = {}
    for line in text.strip().splitlines():
        match = re.fullmatch(r"\s*(両方非表示|味方のみ非表示|敵のみ非表示|unknown)\s*[:：]\s*"
                             r"([1-9][0-9]*(?:\s*[,、，]\s*[1-9][0-9]*)*)\s*", line)
        if match is None:
            raise ValueError("explicit source-reviewed absence IDs required")
        for token in re.split(r"[,、，]", match[2]):
            number = int(token.strip())
            if number not in allowed or number in labels:
                raise ValueError("unknown, duplicate or conflicting source Frame")
            labels[number] = ({field: {"kind": "unknown"} for field in FIELDS}
                              if match[1] == "unknown" else {
                                  field: {"kind": "absent"} if field in roles[match[1]] else None
                                  for field in FIELDS})
    if not labels:
        raise ValueError("no explicit source absence labels supplied")
    return labels


def verify_assets(directory: Path, review: dict) -> None:
    if (review.get("kind") != "blind_remaining_pool_score_presence_review_not_lifecycle_gt"
            or review.get("model_outputs_exposed") is not False
            or review.get("labels_inferred") is not False
            or review.get("production_input") is not False):
        raise ValueError("blind evaluation-only presence review required")
    numbers = [row["frame_number"] for row in review["frames"]]
    if (not numbers or len(set(numbers)) != len(numbers)
            or any(type(n) is not int or n < 1 for n in numbers)):
        raise ValueError("source Frame inventory invalid")
    for row in review["frames"]:
        if (set(row["roi_assets_sha256"]) != set(FIELDS)
                or not re.fullmatch(r"[0-9a-f]{64}", row["source_image_sha256"])
                or type(row["source_frame_pts"]) not in (int, float)
                or not math.isfinite(row["source_frame_pts"]) or row["source_frame_pts"] < 0):
            raise ValueError("source binding invalid")
        for field, digest in row["roi_assets_sha256"].items():
            if sha256_file(directory / f'frame_{row["frame_number"]:02d}_{field}.png') != digest:
                raise ValueError("reviewed score ROI changed")


def freeze(directory: Path, response: Path, provenance: str, output: Path) -> dict:
    _check_output_privacy(output.resolve())
    if output.exists():
        raise FileExistsError("freeze a new immutable private label revision")
    if not provenance.strip():
        raise ValueError("trusted human-response provenance required")
    path = directory / "review.json"
    before, response_hash = sha256_file(path), sha256_file(response)
    review = json.loads(path.read_text(encoding="utf-8"))
    verify_assets(directory, review)
    explicit = parse_response(response.read_text(encoding="utf-8"),
                              {row["frame_number"] for row in review["frames"]})
    result = {"kind": "sparse_source_score_absence_review_not_lifecycle_gt",
              "review_sha256": before, "response_sha256": response_hash,
              "provenance_reference": provenance, "scope": "score_absence_only",
              "provenance_verification": "human_authorship_requires_external_trusted_record",
              "explicit_no_absent_matches": (
                  response.read_text(encoding="utf-8").strip() == "該当なし"),
              "source_video_sha256": review["source_video_sha256"],
              "frames": [{**row, "labels": explicit.get(row["frame_number"])}
                         for row in review["frames"]],
              "production_input": False, "production_adoption_approved": False,
              "identity_approved": False, "event_timing_approved": False,
              "continuity_approved": False}
    verify_assets(directory, review)
    if sha256_file(path) != before or sha256_file(response) != response_hash:
        raise ValueError("review/response changed while freezing")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def measure(directory: Path, labels: Path, response: Path, pool: Path,
            layout_path: Path, reader_receipt: Path, output: Path) -> dict:
    _check_output_privacy(output.resolve())
    if output.exists():
        raise FileExistsError("use a new private fixed-reader control run")
    review_path = directory / "review.json"
    review, frozen, selection, summary, reader = (
        json.loads(p.read_text(encoding="utf-8")) for p in (review_path, labels,
            pool / "review_selection.json", pool / "probe_summary.json", reader_receipt))
    verify_assets(directory, review)
    explicit = parse_response(response.read_text(encoding="utf-8"),
                              {r["frame_number"] for r in review["frames"]})
    expected = [{**row, "labels": explicit.get(row["frame_number"])}
                for row in review["frames"]]
    if (frozen.get("kind") != "sparse_source_score_absence_review_not_lifecycle_gt"
            or frozen["review_sha256"] != sha256_file(review_path)
            or frozen["response_sha256"] != sha256_file(response) or frozen["frames"] != expected
            or frozen.get("scope") != "score_absence_only" or not frozen.get("provenance_reference")
            or any(frozen.get(k) is not False for k in ("production_input",
                "production_adoption_approved", "identity_approved", "event_timing_approved",
                "continuity_approved"))
            or frozen["source_video_sha256"] != review["source_video_sha256"]
            or summary["source_sha256"] != review["source_video_sha256"]
            or review["parent_probe_summary_sha256"] != sha256_file(pool / "probe_summary.json")
            or review["source_pool_selection_sha256"] != sha256_file(pool / "review_selection.json")
            or review["layout_sha256"] != sha256_file(layout_path)
            or reader["adapter_code_sha256"] != sha256_file(Path(localized_digits_reader.__file__))
            or reader.get("production_qualified") is not False):
        raise ValueError("fixed model or source review binding changed")
    paths = sorted((pool / "pool_frames").glob("*.jpg"))
    if len(paths) != len(selection["pool_records"]):
        raise ValueError("source pool inventory incomplete")
    selected = [r for r in expected if r["labels"] is not None
                and any(label is not None and label["kind"] == "absent"
                        for label in r["labels"].values())]
    if not selected:
        raise ValueError("no explicitly reviewed controls")
    for row in selected:
        index = row["pool_index"]
        record = selection["pool_records"][index]
        if (record["sha256"] != row["source_image_sha256"]
                or record["source_frame_pts"] != row["source_frame_pts"]
                or sha256_file(paths[index]) != record["sha256"]):
            raise ValueError("reviewed source pixels/PTS changed")
    profile_path = layout_path.with_suffix(".templates.json")
    profile = HudTemplateProfile.load(profile_path)
    plan_path = pool.parent / "plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    model_paths = [layout_path, profile_path, Path(numeric_text_localization.__file__),
                   *[profile.resolve_asset(str(p)) for p in profile.asset_paths]]
    if (summary.get("plan_sha256") != sha256_file(plan_path)
            or any(plan["inputs_sha256"].get(str(p.resolve())) != sha256_file(p)
                   for p in model_paths)
            or toolchain_fingerprints() != plan["toolchain_fingerprints"]):
        raise ValueError("model/profile/toolchain changed since fixed source pool")
    bound = [review_path, labels, response, reader_receipt, layout_path, profile_path,
             plan_path, pool / "review_selection.json", pool / "probe_summary.json", Path(__file__),
             Path(localized_digits_reader.__file__), Path(numeric_text_localization.__file__),
             *[paths[r["pool_index"]] for r in selected],
             *[profile.resolve_asset(str(p)) for p in profile.asset_paths]]
    hashes = {p: sha256_file(p) for p in bound}
    code = code_fingerprint(Path(__file__).resolve().parents[2])
    tools = toolchain_fingerprints()
    if code != reader["runtime_code_fingerprint"]:
        raise ValueError("runtime reader changed since pre-review measurement")
    model = localized_digits_reader.build_readers(profile)
    layout = HudLayout.load(layout_path)
    measurements = []
    for row in selected:
        image = cv2.imread(str(paths[row["pool_index"]]))
        if image is None or (image.shape[1], image.shape[0]) != layout.reference_resolution:
            raise ValueError("control source dimensions invalid")
        for field in FIELDS:
            if row["labels"][field] is None or row["labels"][field]["kind"] != "absent":
                continue
            a, b, c, d = layout.normalized_roi(field).pixel_bounds(image.shape[1], image.shape[0])
            # Only actual image pixels enter the model, never labels/Frame IDs.
            result = model[field].read(image, image[b:d, a:c])
            measurements.append({"frame_number": row["frame_number"], "field": field,
                "source_image_sha256": row["source_image_sha256"],
                "value": result.value, "confidence": result.confidence,
                "sources": result.sources, "false_positive": result.value is not None})
    verify_assets(directory, review)
    if (any(sha256_file(p) != h for p, h in hashes.items())
            or code_fingerprint(Path(__file__).resolve().parents[2]) != code
            or toolchain_fingerprints() != tools):
        raise ValueError("controls/model/inputs changed during measurement")
    output.mkdir(parents=True)
    raw = output / "measurements.json"
    raw.write_text(json.dumps(measurements, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    receipt = {"kind": "fixed_reader_score_absence_controls_not_lifecycle_e2e",
               "review_sha256": hashes[review_path], "labels_sha256": hashes[labels],
               "reader_receipt_sha256": hashes[reader_receipt],
               "toolchain_fingerprints": tools, "runtime_code_fingerprint": code,
               "counts": {field: {"reviewed": sum(r["field"] == field for r in measurements),
                   "false_positive": sum(r["field"] == field and r["false_positive"]
                                         for r in measurements)} for field in FIELDS},
               "measurements_sha256": sha256_file(raw), "outside_analyzer": True,
               "native_geometry_bypass": False, "production_qualified": False,
               "production_adopted": False}
    (output / "summary.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    common = ("review-dir", "human-response-file", "output")
    freeze_args, run = sub.add_parser("freeze"), sub.add_parser("measure")
    for child in (freeze_args, run):
        for name in common:
            child.add_argument("--" + name, type=Path, required=True)
    freeze_args.add_argument("--provenance-reference", required=True)
    for name in ("labels", "pool", "layout", "reader-receipt"):
        run.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    result = (freeze(args.review_dir, args.human_response_file, args.provenance_reference,
                     args.output) if args.command == "freeze" else measure(
                     args.review_dir, args.labels, args.human_response_file, args.pool,
                     args.layout, args.reader_receipt, args.output))
    if args.command == "freeze":
        print(f'Frozen {sum(r["labels"] is not None for r in result["frames"])} explicit rows')
    else:
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
