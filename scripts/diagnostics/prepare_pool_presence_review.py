"""Blind score-presence gallery of the unreviewed frozen source pool.

No decoding, OCR, Analyzer, GT, reference generation or qualification. Omitted
human answers remain unreviewed; nothing in this tool declares numeric absence.
"""
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path

import cv2

from scripts.e2e.run_dataset_case import sha256_file
from valorant_ai_coach.hud.calibrate_temporal import _check_output_privacy
from valorant_ai_coach.hud.layout import HudLayout


def prepare(probe: Path, output: Path) -> dict:
    _check_output_privacy(output.resolve())
    if output.exists():
        raise FileExistsError("use a new private source-presence review directory")
    summary_path = probe / "probe_summary.json"
    selection_path = probe / "review_selection.json"
    layout_path = probe / "hud_layout.json"
    report_path = probe / "candidate_report.json"
    summary, selection, report = (json.loads(p.read_text(encoding="utf-8"))
                                  for p in (summary_path, selection_path, report_path))
    if (summary.get("kind") != "prospective_numeric_point_probe_not_lifecycle_e2e"
            or summary.get("production_adopted") is not False
            or summary.get("selection_sha256") != sha256_file(selection_path)
            or summary["candidate_report_sha256"] != sha256_file(report_path)
            or summary["source_sha256"] != report["source_sha256"]
            or selection.get("selection_frozen_before_numeric_measurement") is not True):
        raise ValueError("unchanged frozen source pool required")
    records = selection["pool_records"]
    paths = sorted((probe / "pool_frames").glob("*.jpg"))
    if len(paths) != len(records) or len(records) != summary["pool_frame_count"]:
        raise ValueError("complete source pool inventory required")
    bindings = {p: sha256_file(p) for p in [summary_path, selection_path, layout_path,
                                          report_path, *paths]}
    if any(bindings[p] != row["sha256"] for p, row in zip(paths, records, strict=True)):
        raise ValueError("source pool images changed")
    # Exclude the whole already-reviewed subset, irrespective of its labels.
    # Never read labels or filter by numeric predictions/acceptance/confidence.
    seen = {row["sha256"] for row in report["validation_frames"]}
    remaining = []
    for index, row in enumerate(records):
        if row["sha256"] not in seen:
            remaining.append(index)
            seen.add(row["sha256"])
    if not remaining:
        raise ValueError("no distinct unreviewed source images")
    layout = HudLayout.load(layout_path)
    output.mkdir(parents=True)
    cards, rows = [], []
    for number, index in enumerate(remaining, 1):
        image = cv2.imread(str(paths[index]))
        if image is None or (image.shape[1], image.shape[0]) != layout.reference_resolution:
            raise ValueError("source presence review dimensions mismatch")
        assets = {}
        for field in ("ally_score", "enemy_score"):
            a, b, c, d = layout.normalized_roi(field).pixel_bounds(image.shape[1], image.shape[0])
            asset = output / f"frame_{number:02d}_{field}.png"
            if not cv2.imwrite(str(asset), image[b:d, a:c]):
                raise ValueError("cannot save local source ROI")
            assets[field] = sha256_file(asset)
        cards.append(f'<section><h2>Frame {number}</h2><a href="'
                     f'{html.escape(paths[index].resolve().as_uri())}">元画像を確認</a>'
                     + ''.join(f'<figure><figcaption>{field}</figcaption>'
                               f'<img src="frame_{number:02d}_{field}.png" width="160">'
                               '</figure>' for field in assets) + '</section>')
        rows.append({"frame_number": number, "pool_index": index,
                     "source_image_sha256": records[index]["sha256"],
                     "source_frame_pts": records[index]["source_frame_pts"],
                     "roi_assets_sha256": assets, "labels": None})
    page = ('<!doctype html><meta charset="utf-8"><title>スコア表示の独立確認</title>'
            '<style>main{display:grid;grid-template-columns:repeat(auto-fit,minmax(360px,1fr))}'
            'section{border:1px solid #aaa;margin:6px;padding:8px}h2{font-size:18px}'
            'figure{display:inline-block;margin:5px}img{image-rendering:auto}</style>'
            '<h1>スコアが非表示のFrameだけを確認</h1>'
            '<p>OCR結果・confidence・予測・期待stateは表示していません。'
            '数字の書き起こしは不要です。非表示ならFrame番号と味方／敵／両方を回答してください。'
            '読めないだけならunknown、疑わしい場合は元画像を確認してください。'
            '非表示がなければ「該当なし」と回答できます。</p>'
            '<p>この一覧のFrame番号は独立しています。回答されなかったFrameを表示／非表示と'
            '自動判定しません。本人視点・境界・連続性・本番採用は含みません。</p><main>'
            + ''.join(cards) + '</main>')
    (output / "index.html").write_text(page, encoding="utf-8")
    if any(sha256_file(p) != h for p, h in bindings.items()):
        raise ValueError("frozen source pool changed during review preparation")
    receipt = {"kind": "blind_remaining_pool_score_presence_review_not_lifecycle_gt",
               "source_video_sha256": summary["source_sha256"],
               "parent_probe_summary_sha256": bindings[summary_path],
               "source_pool_selection_sha256": bindings[selection_path],
               "layout_sha256": bindings[layout_path], "frames": rows,
               "model_outputs_exposed": False, "labels_inferred": False,
               "approved": False, "production_input": False}
    (output / "review.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--probe", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(f'Prepared {len(prepare(args.probe, args.output)["frames"])} source-only presence cards')


if __name__ == "__main__":
    main()
