"""Prepare a private score-number review using unchanged approved-start images.

Chronological annotation IDs are not score-derived game-round numbers. This
tool does not read pixels, infer scores, approve GT or consult recognizer output.
"""
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path

from scripts.e2e.run_dataset_case import sha256_file
from valorant_ai_coach.hud.calibrate_temporal import _check_output_privacy


def prepare(fragments_path: Path) -> dict:
    digest = sha256_file(fragments_path)
    data = json.loads(fragments_path.read_text(encoding="utf-8"))
    if (data.get("kind") != "private_v3_boundary_point_fragments_not_complete_pack"
            or data.get("production_input") is not False
            or data.get("formal_pack_completed") is not False):
        raise ValueError("private witnessed point fragments required")
    bindings = {row["evidence_path"]: row for row in data["evidence_bindings"]}
    if len(bindings) != len(data["evidence_bindings"]):
        raise ValueError("duplicate evidence binding")
    rows, seen = [], set()
    root = fragments_path.parent.resolve()
    for item in data["points"]:
        point = item["point"]
        if point["type"] != "round_start":
            continue
        rid = item["round_id"]
        if rid in seen:
            raise ValueError("duplicate Round start")
        seen.add(rid)
        evidence = []
        for name in point["evidence"]:
            bound = bindings[name]
            image = (root / name).resolve()
            if not image.is_relative_to(root) or sha256_file(image) != bound["sha256"]:
                raise ValueError("source asset integrity failed")
            evidence.append({"image_uri": image.as_uri(), "sha256": bound["sha256"],
                             "source_frame_pts": bound["source_frame_pts"]})
        if not evidence:
            raise ValueError("source score review needs visible evidence")
        rows.append({"annotation_round_id": rid, "evidence": evidence,
                     "score_left": None, "score_right": None,
                     "match_round_number_from_score": None,
                     "annotation_status": "awaiting_independent_score_review"})
    if not rows or sha256_file(fragments_path) != digest:
        raise ValueError("empty or mutated point fragments")
    rows.sort(key=lambda row: min(e["source_frame_pts"] for e in row["evidence"]))
    return {"kind": "private_score_number_review_not_gt", "production_input": False,
            "approved_ground_truth": False, "recognizer_outputs_consulted": False,
            "source_video_sha256": data["source_video_sha256"],
            "fragments_sha256": digest, "ledger_sha256": data["ledger_sha256"],
            "items": rows}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--point-fragments", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    _check_output_privacy(output)
    if output.exists():
        raise FileExistsError("use a new private output directory")
    report = prepare(args.point_fragments)
    cards = []
    for row in report["items"]:
        images = "".join(
            f'<a href="{html.escape(e["image_uri"], quote=True)}">'
            f'<img width="960" loading="lazy" src="{html.escape(e["image_uri"], quote=True)}">'
            f'<br>PTS {e["source_frame_pts"]}</a><br>' for e in row["evidence"])
        cards.append(f'<li><h2>{html.escape(row["annotation_round_id"])}</h2>{images}</li>')
    page = ('<!doctype html><meta charset="utf-8"><h1>上部スコアによるRound番号確認</h1>'
            '<p>未承認の確認ページです。annotation IDの末尾は時系列のラベルであり、'
            'ゲーム内Round番号の証明ではありません。</p>'
            '<p>ゲーム上部の左右スコアを確認し、合計+1をRound番号として確認してください。'
            '中央Trackerや観戦情報とは区別してください。読めない場合は保留します。'
            '開始時刻の再承認・連続性・本人視点・厳密なscore更新時刻の承認は求めません。</p>'
            '<ol>' + ''.join(cards) + '</ol>')
    output.mkdir(parents=True)
    (output / "review.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (output / "index.html").write_text(page, encoding="utf-8")
    print(f'Prepared {len(report["items"])} source score reviews; no score/GT inferred')


if __name__ == "__main__":
    main()
