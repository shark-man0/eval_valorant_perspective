"""Private blind geometry review: no model matches, scores or expected labels.

ROI guides come only from layout configuration. Human review is not automatic
qualification and must not be treated as player identity or lifecycle GT.
"""
from __future__ import annotations

import argparse
import html
import json
import math
import shutil
from pathlib import Path

import cv2

from scripts.diagnostics.prospective_numeric_probe import verify_partition
from scripts.e2e.run_dataset_case import sha256_file
from valorant_ai_coach.hud.calibrate_temporal import _check_output_privacy
from valorant_ai_coach.hud.layout import HudLayout


def prepare(candidate: Path, output: Path, *, source_pool: Path | None = None,
            partition: Path | None = None) -> dict:
    _check_output_privacy(output.resolve())
    if output.exists():
        raise FileExistsError("use a new private geometry review directory")
    fingerprint_path = candidate / "candidate_fingerprint.json"
    frozen = json.loads(fingerprint_path.read_text(encoding="utf-8"))
    for name, expected in frozen.items():
        path = (candidate / name).resolve()
        if not path.is_relative_to(candidate.resolve()) or sha256_file(path) != expected:
            raise ValueError("candidate changed or escaped")
    report_path = candidate / "candidate_report.json"
    report_hash = sha256_file(report_path)
    # Only source image bindings are consumed, not matching scores/decisions.
    candidate_report = json.loads(report_path.read_text(encoding="utf-8"))
    source_report = source_pool / "candidate_report.json" if source_pool else report_path
    source_hash = sha256_file(source_report)
    source_data = json.loads(source_report.read_text(encoding="utf-8"))
    sources = source_data["validation_frames"]
    paths = sorted(((source_pool or candidate) / "validation_frames").glob("*.jpg"))
    if len(paths) != len(sources):
        raise ValueError("source image inventory mismatch")
    partition_hash = None
    if source_pool is not None:
        if partition is None or not 1 <= len(sources) <= 64:
            raise ValueError("bounded external source inventory and partition required")
        partition_hash = sha256_file(partition)
        end = json.loads(partition.read_text(encoding="utf-8"))["development"]["end_sec_exclusive"]
        verify_partition(partition, candidate_report["source_sha256"], end)
        if source_data.get("source_sha256") != candidate_report["source_sha256"]:
            raise ValueError("same-source development review required")
        reserved = {row["sha256"] for key in ("training_frames", "validation_frames")
                    for row in candidate_report.get(key, [])}
        for source in sources:
            pts = source["source_frame_pts"]
            if (type(pts) not in (int, float) or not math.isfinite(pts) or not 0 <= pts < end
                    or source["sha256"] in reserved):
                raise ValueError("development sources disjoint from candidate images required")
    elif partition is not None:
        raise ValueError("partition option requires external source pool")
    raw = json.loads((candidate / "hud_layout.templates.json").read_text(encoding="utf-8"))
    names = list(raw["anchors"])
    layout = HudLayout.load(candidate / "hud_layout.json")
    output.mkdir(parents=True)
    cards, rows = [], []
    for index, (path, source) in enumerate(zip(paths, sources, strict=True), 1):
        if sha256_file(path) != source["sha256"]:
            raise ValueError("source review image changed")
        image = cv2.imread(str(path))
        if image is None or (image.shape[1], image.shape[0]) != layout.reference_resolution:
            raise ValueError("review geometry dimensions mismatch")
        for name in names:
            x1, y1, x2, y2 = layout.normalized_roi(name).pixel_bounds(
                image.shape[1], image.shape[0])
            cv2.rectangle(image, (x1, y1), (x2 - 1, y2 - 1), (255, 180, 0), 2)
            cv2.putText(image, name, (x1, max(18, y1 - 4)), cv2.FONT_HERSHEY_SIMPLEX,
                        .5, (255, 180, 0), 1)
        destination = output / f"guide_{index:02d}.jpg"
        if not cv2.imwrite(str(destination), image):
            raise ValueError("cannot render private guide")
        if source_pool is not None:
            # Do not expose the previous cohort's semantic directory name to
            # the blind reviewer (for example, "negative_candidates").
            neutral_source = output / f"source_{index:02d}.jpg"
            shutil.copyfile(path, neutral_source)
            if sha256_file(neutral_source) != source["sha256"]:
                raise ValueError("unmodified review source copy required")
            source_uri = neutral_source.name
        else:
            source_uri = html.escape(path.resolve().as_uri())
        cards.append(f'<section><h2>Frame {index}</h2><a href="{source_uri}">'
                     f'Unmodified source image</a><img src="{destination.name}" width="100%">'
                     '<p>Labels: not reviewed. ROI guides are configuration, '
                     'not detections.</p></section>')
        rows.append({"frame_number": index, "source_sha256": source["sha256"],
                     "source_frame_pts": source["source_frame_pts"],
                     "guide_sha256": sha256_file(destination), "labels": None})
    def asset_uri(name: str, key: str) -> str:
        path = (candidate / raw["anchors"][name][key]).resolve()
        if (not path.is_relative_to(candidate.resolve())
                or path.relative_to(candidate.resolve()).as_posix() not in frozen):
            raise ValueError("review asset escaped frozen candidate")
        return html.escape(path.as_uri())

    assets = ''.join(f'<section><h3>{html.escape(name)} training reference / mask</h3>'
                     f'<img src="{asset_uri(name, "template")}">'
                     f'<img src="{asset_uri(name, "mask")}">'
                     '</section>' for name in names)
    page = ('<!doctype html><meta charset="utf-8"><title>Blind geometry review</title>'
            '<h1>Private geometry-only source review</h1><p>Confirm visible fixed HUD shapes '
            'and configured ROI alignment. Mark absent or ambiguous structures as such. '
            'No match scores, predictions, expected state or automatic approval is shown. '
            'This is not player identity, event timing or whole-source continuity review.</p>'
            '<p>各Frameで、timer／HP・armor／abilitiesの固定UI形状がガイド位置に見えるかを'
            '確認してください。数字・可変アイコンの有無ではなく、先頭のreferenceとmaskが示す'
            '固定形状が対象です。visible／absent／misaligned／unknownで回答できます。'
            'メニュー・特殊視点という理由だけでabsentにはしないでください。'
            '未確認の画像は保留できます。</p>'
            + assets + ''.join(cards))
    (output / "index.html").write_text(page, encoding="utf-8")
    if (sha256_file(report_path) != report_hash or sha256_file(source_report) != source_hash
            or (partition is not None and sha256_file(partition) != partition_hash)
            or any(sha256_file(candidate / name) != expected for name, expected in frozen.items())
            or any(sha256_file(path) != source["sha256"]
                   for path, source in zip(paths, sources, strict=True))):
        raise ValueError("candidate/source changed during review preparation")
    receipt = {"kind": "blind_geometry_source_review_not_gt", "production_input": False,
               "approved_ground_truth": False, "model_scores_exposed": False,
               "candidate_report_sha256": report_hash,
               "source_inventory_sha256": source_hash,
               "partition_sha256": partition_hash,
               "external_source_pool": source_pool is not None,
               "scope": "fixed_geometry_visibility_and_alignment_only_not_identity_or_events",
               "candidate_fingerprint_sha256": sha256_file(fingerprint_path), "frames": rows}
    (output / "review.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-pool", type=Path,
                        help="Complete development image inventory, not predicted negatives")
    parser.add_argument("--partition", type=Path)
    args = parser.parse_args()
    receipt = prepare(args.candidate, args.output, source_pool=args.source_pool,
                      partition=args.partition)
    print(f'Prepared {len(receipt["frames"])} blind source images; no approval inferred')


if __name__ == "__main__":
    main()
