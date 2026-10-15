"""Prediction-free text review of fixed development held images, not event GT."""

from __future__ import annotations

import argparse
import html
import json
from fractions import Fraction
from pathlib import Path

import cv2

from scripts.diagnostics.prospective_numeric_probe import verify_partition
from scripts.e2e.run_dataset_case import sha256_file
from valorant_ai_coach.hud.calibrate_temporal import _check_output_privacy
from valorant_ai_coach.hud.layout import HudLayout


def indices(length: int, count: int) -> list[int]:
    if type(length) is not int or type(count) is not int or not 3 <= count <= length <= 256:
        raise ValueError("bounded distinct held inventory required")
    return [i * (length - 1) // (count - 1) for i in range(count)]


def prepare(report_path: Path, selection_path: Path, layout_path: Path,
            partition_path: Path, output: Path, *, count: int = 6) -> dict:
    _check_output_privacy(output.resolve())
    if output.exists():
        raise FileExistsError("new private blind review directory required")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if (report.get("kind") != "unlabeled_banner_discovery_not_qualification"
            or report.get("training_candidate_audit") is not True
            or report.get("held_predictions_measured") is not False
            or report.get("semantic_labels_assigned") is not False
            or report.get("production_adopted") is not False):
        raise ValueError("original training-only discovery receipt required")
    training, held = report["training_hashes"], report["held_hashes"]
    chosen = indices(len(held), count)
    if len(set(training + held)) != len(training + held):
        raise ValueError("training/held source overlap")
    bindings = {Path(p).resolve(): h for p, h in report["source_inputs_sha256"].items()}
    for path in (selection_path, layout_path):
        if bindings.get(path.resolve()) != sha256_file(path):
            raise ValueError("unchanged discovery selection/layout required")
    selection = json.loads(selection_path.read_text(encoding="utf-8"))
    partition = json.loads(partition_path.read_text(encoding="utf-8"))
    end = partition["development"]["end_sec_exclusive"]
    verify_partition(partition_path, report["source_sha256"], end)
    records = {row["sha256"]: row for row in selection["pool_records"]}
    paths = {}
    for path, digest in bindings.items():
        if path.parent.name == "pool_frames" and digest in held:
            if digest in paths:
                raise ValueError("ambiguous held source path")
            paths[digest] = path
    if set(paths) != set(held):
        raise ValueError("complete held source inventory required")
    for digest in held:
        row = records[digest]
        tick, base = row["source_pts_ticks"], Fraction(row["source_time_base"])
        if (row["source_video_sha256"] != report["source_sha256"]
                or type(tick) is not int or tick < 0 or base <= 0
                or float(tick * base) != row["source_frame_pts"]
                or not 0 <= float(tick * base) < end
                or sha256_file(paths[digest]) != digest):
            raise ValueError("source-bound development pixels/PTS required")
    inputs = {p.resolve(): sha256_file(p) for p in (
        report_path, selection_path, layout_path, partition_path, Path(__file__))}
    inputs.update({path: digest for digest, path in paths.items()})
    layout = HudLayout.load(layout_path)
    x1, y1, x2, y2 = layout.normalized_roi("round_end_banner").pixel_bounds(
        *layout.reference_resolution)
    output.mkdir(parents=True)
    cards, frames = [], []
    for number, index in enumerate(chosen, 1):
        digest, path = held[index], paths[held[index]]
        image = cv2.imread(str(path))
        if image is None or (image.shape[1], image.shape[0]) != layout.reference_resolution:
            raise ValueError("source dimensions mismatch")
        crop = output / f"frame_{number:02d}.png"
        if not cv2.imwrite(str(crop), image[y1:y2, x1:x2]):
            raise ValueError("cannot write blind broad ROI")
        frames.append({"frame_number": number, "held_index": index,
                       "source_image_sha256": digest, "roi_sha256": sha256_file(crop),
                       "label": None})
        cards.append(f'<h2>Frame {number}</h2><img src="{crop.name}">'
                     f'<p><a href="{html.escape(path.as_uri())}">元画像</a></p>')
    page = ('<!doctype html><meta charset="utf-8"><h1>固定画像の表示文字レビュー</h1>'
            '<p>番号と見える文字を回答してください。非表示はabsent、判読不能はunknown。'
            '予測・スコア・参照候補・時刻は非表示です。Round境界、本人視点、'
            '連続性、本番採用の承認は含みません。</p>' + ''.join(cards))
    (output / "index.html").write_text(page, encoding="utf-8")
    if any(sha256_file(path) != digest for path, digest in inputs.items()):
        raise ValueError("blind review source inputs changed")
    receipt = {"kind": "fixed_held_banner_text_review_not_lifecycle_gt",
               "source_video_sha256": report["source_sha256"],
               "selection_method": "uniform_indices_in_original_held_order",
               "selected_indices": chosen, "frames": frames,
               "inputs_sha256": {str(p): h for p, h in inputs.items()},
               "review_html_sha256": sha256_file(output / "index.html"),
               "model_outputs_exposed": False, "labels_assigned": False,
               "qualification_created": False, "production_adopted": False}
    (output / "review.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("report", "selection", "layout", "partition", "output"):
        parser.add_argument(f"--{name}", required=True, type=Path)
    parser.add_argument("--count", type=int, default=6)
    args = parser.parse_args()
    result = prepare(args.report, args.selection, args.layout, args.partition,
                     args.output, count=args.count)
    print(json.dumps({"frames": len(result["frames"]), "labels_assigned": False,
                      "qualification_created": False}))


if __name__ == "__main__":
    main()
