"""Blind private numeric source review; never display OCR or expected values."""
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path

import cv2

from scripts.e2e.run_dataset_case import sha256_file
from valorant_ai_coach.hud.calibrate_temporal import _check_output_privacy
from valorant_ai_coach.hud.layout import HudLayout


def prepare(candidate: Path, probe: Path, output: Path) -> dict:
    _check_output_privacy(output.resolve())
    if output.exists():
        raise FileExistsError("use a new private numeric review directory")
    report_path, summary_path = candidate / "candidate_report.json", probe / "probe_summary.json"
    summary_hash = sha256_file(summary_path)
    report_hash = sha256_file(report_path)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if (summary["candidate_report_sha256"] != report_hash
            or summary["source_sha256"] != report["source_sha256"]
            or summary["frames"] != len(report["validation_frames"])
            or sha256_file(probe / "hud_layout.json") != (
                sha256_file(candidate / "hud_layout.json"))):
        raise ValueError("numeric review inputs do not match frozen source probe")
    layout_path = probe / "hud_layout.json"
    layout_hash = sha256_file(layout_path)
    layout = HudLayout.load(layout_path)
    paths = sorted((candidate / "validation_frames").glob("*.jpg"))
    if len(paths) != len(report["validation_frames"]):
        raise ValueError("numeric review source inventory mismatch")
    output.mkdir(parents=True)
    cards, bindings = [], []
    for number, (path, source) in enumerate(
            zip(paths, report["validation_frames"], strict=True), 1):
        if sha256_file(path) != source["sha256"]:
            raise ValueError("numeric review source changed")
        image = cv2.imread(str(path))
        if image is None or (image.shape[1], image.shape[0]) != layout.reference_resolution:
            raise ValueError("numeric review dimensions mismatch")
        assets = {}
        for name in ("round_timer", "ally_score", "enemy_score"):
            # Broad configured ROI, NOT the model's proposed crop.
            x1, y1, x2, y2 = layout.normalized_roi(name).pixel_bounds(
                image.shape[1], image.shape[0])
            destination = output / f"frame_{number:02d}_{name}.png"
            if not cv2.imwrite(str(destination), image[y1:y2, x1:x2]):
                raise ValueError("cannot write private review crop")
            assets[name] = sha256_file(destination)
        cards.append(f'<section><h2>Frame {number}</h2><a href="'
                     f'{html.escape(path.resolve().as_uri())}">元画像</a><div>'
                     + ''.join(f'<figure><figcaption>{name}</figcaption>'
                               f'<img src="frame_{number:02d}_{name}.png" width="375"></figure>'
                               for name in assets) + '</div></section>')
        bindings.append({"frame_number": number, "source_sha256": source["sha256"],
                         "source_frame_pts": source["source_frame_pts"],
                         "roi_assets_sha256": assets, "labels": None})
    page = ('<!doctype html><meta charset="utf-8"><title>独立した数値レビュー</title>'
            '<style>section{border-top:1px solid #aaa;padding:1em}figure{display:inline-block;'
            'margin:.5em}img{image-rendering:auto}</style>'
            '<h1>Timer / Score の独立ソースレビュー</h1>'
            '<p>OCR結果・confidence・期待値・モデルの切り抜き位置は表示していません。'
            '設定された大きいROIと元画像だけを見てください。</p>'
            '<p>回答形式: Frame番号, Timer (m:ss), ally score, enemy score。'
            '読めない項目はunknown、数字が表示されていない項目はabsentにしてください。'
            'これは数字の視認確認だけです。本人視点・境界・連続性・本番採用は含みません。</p>'
            + ''.join(cards))
    (output / "index.html").write_text(page, encoding="utf-8")
    if (sha256_file(report_path) != report_hash or sha256_file(summary_path) != summary_hash
            or sha256_file(layout_path) != layout_hash
            or any(sha256_file(path) != source["sha256"] for path, source in
                   zip(paths, report["validation_frames"], strict=True))):
        raise ValueError("numeric review inputs changed during preparation")
    receipt = {"kind": "blind_global_numeric_review_not_lifecycle_gt",
               "candidate_report_sha256": report_hash, "probe_summary_sha256": summary_hash,
               "layout_sha256": layout_hash, "source_video_sha256": report["source_sha256"],
               "model_outputs_exposed": False, "approved": False, "production_input": False,
               "frames": bindings}
    (output / "review.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("candidate", "probe", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    result = prepare(args.candidate, args.probe, args.output)
    print(f'Prepared {len(result["frames"])} private source images; no numeric labels inferred')


if __name__ == "__main__":
    main()
