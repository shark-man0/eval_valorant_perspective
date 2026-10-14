"""Unlabeled development-only banner candidates; no semantic/event adoption.

Training pixels select candidates. Held pixels measure the frozen candidates
but never select them. A repeated shape is not automatically a purchase/result
label, and no qualification or configured signal is written.
"""
from __future__ import annotations

import argparse
import html
import json
import math
import re
from pathlib import Path

import cv2
import numpy as np

from scripts.diagnostics.prospective_numeric_probe import verify_partition
from scripts.e2e.run_dataset_case import sha256_file
from valorant_ai_coach.hud.calibrate_temporal import _check_output_privacy
from valorant_ai_coach.hud.layout import HudLayout
from valorant_ai_coach.hud.semantic_text import SemanticTextReference


def text_rows(gray):
    if gray.dtype != np.uint8 or gray.ndim != 2 or min(gray.shape) < 20:
        raise ValueError("native gray banner ROI required")
    _, _, stats, _ = cv2.connectedComponentsWithStats((gray >= 210).astype(np.uint8), 8)
    glyphs = [tuple(int(v) for v in row[:4]) for row in stats[1:]
              if 20 <= row[3] <= 90 and .10 <= row[2] / row[3] <= 2.5 and row[4] >= 12]
    boxes = set()
    for _, y, _, h in glyphs:
        group = [b for b in glyphs if abs(b[3] - h) <= .25 * h
                 and abs(b[1] + b[3] / 2 - y - h / 2) <= .20 * h]
        if len(group) < 4:
            continue
        left, right = min(b[0] for b in group), max(b[0] + b[2] for b in group)
        if right - left < 120:
            continue
        boxes.add((max(0, left - 3), max(0, min(b[1] for b in group) - 3),
                   min(gray.shape[1], right + 3),
                   min(gray.shape[0], max(b[1] + b[3] for b in group) + 3)))
    return sorted(boxes)


def propose(crops, hashes):
    """Existing >=.90 grouped NCC, all candidate selection training-only."""
    proposals = []
    for crop in crops:
        for box in text_rows(crop):
            x1, y1, x2, y2 = box
            reference = crop[y1:y2, x1:x2]
            mask = cv2.dilate((reference >= 210).astype(np.uint8) * 255,
                              np.ones((3, 3), np.uint8))
            groups = np.zeros_like(mask)
            for group, columns in enumerate(np.array_split(np.arange(mask.shape[1]), 3), 1):
                groups[:, columns] = np.where(mask[:, columns] > 0, group, 0)
            training = [(h, c[y1:y2, x1:x2]) for h, c in zip(hashes, crops, strict=True)]
            try:
                matcher = SemanticTextReference(reference, mask, groups, training, .90)
            except ValueError:
                continue
            support = tuple(i for i, (_, c) in enumerate(training) if matcher.score(c) >= .90)
            proposals.append((box, reference.copy(), mask, groups, matcher, support))
    # Group equivalent training support sets; no held score participates.
    unique = {}
    for proposal in proposals:
        key = proposal[-1]
        if key not in unique:
            unique[key] = proposal
    return sorted(unique.values(), key=lambda p: (-len(p[-1]), p[0]))[:4]


def discover(pool: Path, layout_path: Path, partition_path: Path, output: Path,
             reserved: set[str]) -> dict:
    _check_output_privacy(output.resolve())
    if output.exists():
        raise FileExistsError("new private discovery directory required")
    selection_path = pool / "review_selection.json"
    selection = json.loads(selection_path.read_text(encoding="utf-8"))
    parent_path = pool / "candidate_report.json"
    parent = json.loads(parent_path.read_text(encoding="utf-8"))
    partition = json.loads(partition_path.read_text(encoding="utf-8"))
    end = partition["development"]["end_sec_exclusive"]
    verify_partition(partition_path, parent["source_sha256"], end)
    paths = sorted((pool / "pool_frames").glob("*.jpg"))
    records = selection["pool_records"]
    selected = selection["selected_pool_indices"]
    if (not isinstance(selected, list)
            or any(type(i) is not int or not 0 <= i < len(records) for i in selected)
            or len(set(selected)) != len(selected)
            or any(re.fullmatch(r"[0-9a-f]{64}", h) is None for h in reserved)):
        raise ValueError("explicit valid reserved source inventory required")
    if len(paths) != len(records) or not paths:
        raise ValueError("complete frozen image inventory required")
    inputs = [selection_path, parent_path, layout_path, partition_path, Path(__file__), *paths]
    bindings = {p: sha256_file(p) for p in inputs}
    layout = HudLayout.load(layout_path)
    frames, seen = [], set()
    excluded = set(selected)
    for index, (path, row) in enumerate(zip(paths, records, strict=True)):
        pts = row["source_frame_pts"]
        if (type(pts) not in (int, float) or not math.isfinite(pts) or not 0 <= pts < end
                or sha256_file(path) != row["sha256"]):
            raise ValueError("source hash or development partition mismatch")
        image = cv2.imread(str(path))
        if image is None or (image.shape[1], image.shape[0]) != layout.reference_resolution:
            raise ValueError("configured source resolution required")
        if index in excluded or row["sha256"] in reserved | seen:
            continue
        seen.add(row["sha256"])
        frames.append((index, path, row, image))
    training, held = frames[::2], frames[1::2]
    if min(len(training), len(held)) < 3:
        raise ValueError("distinct training and held source groups required")
    output.mkdir(parents=True)
    report = {"kind": "unlabeled_banner_discovery_not_qualification",
              "source_sha256": parent["source_sha256"], "threshold": .90,
              "training_count": len(training), "held_count": len(held),
              "training_hashes": [r[2]["sha256"] for r in training],
              "held_hashes": [r[2]["sha256"] for r in held],
              "reserved_source_hashes": sorted(reserved),
              "excluded_pool_indices": selected,
              "training_selected_before_held_measurement": True,
              "held_scope": "fixed development images, not final evaluation holdout",
              "source_inputs_sha256": {str(p): h for p, h in bindings.items()},
              "roles": {}, "semantic_labels_assigned": False,
              "independent_semantic_reviewed": False, "review_frames": [],
              "qualification_created": False, "production_adopted": False}
    cards = []
    for role in ("center_phase_banner", "round_end_banner"):
        bounds = layout.normalized_roi(role).pixel_bounds(*layout.reference_resolution)
        x1, y1, x2, y2 = bounds
        crops = [cv2.cvtColor(r[3][y1:y2, x1:x2], cv2.COLOR_BGR2GRAY) for r in training]
        candidates = propose(crops, report["training_hashes"])
        rows = []
        for number, (box, reference, mask, groups, matcher, support) in enumerate(candidates, 1):
            name = f"{role}_{number}"
            assets = {}
            for suffix, image in (("reference", reference), ("mask", mask), ("groups", groups)):
                path = output / f"{name}_{suffix}.png"
                if not cv2.imwrite(str(path), image):
                    raise ValueError("candidate image write failed")
                assets[path.name] = sha256_file(path)
            a, b, c, d = box
            reference_index = next(i for i, crop in enumerate(crops)
                                   if np.array_equal(reference, crop[b:d, a:c]))
            scores = [matcher.score(cv2.cvtColor(r[3][y1:y2, x1:x2],
                         cv2.COLOR_BGR2GRAY)[b:d, a:c]) for r in held]
            rows.append({"candidate_id": name, "bounds_in_roi": box,
                         "asset_hashes": assets, "training_support_indices": support,
                         "reference_training_index": reference_index,
                         "reference_source_hash": report["training_hashes"][reference_index],
                         "held_scores": scores, "held_accept_count": sum(s >= .90 for s in scores),
                         "semantic_label": None})
            source_uri = html.escape(training[reference_index][1].resolve().as_uri())
            cards.append(f'<h2>{html.escape(name)}</h2><img src="{name}_reference.png">'
                         f'<img src="{name}_mask.png"><p>意味付けは未確定です。</p>'
                         f'<a href="{source_uri}">'
                         'reference元画像</a>')
        report["roles"][role] = rows
    # Broad crops, not detector boxes or scores, for the fixed held source group.
    cards.append('<h1>固定held画像：画面上の表示内容を確認</h1>')
    for number, (pool_index, path, source, image) in enumerate(held, 1):
        review_row = {"frame_id": number, "pool_index": pool_index,
                      "source_hash": source["sha256"], "roi_assets": {}}
        cards.append(f'<h2>Frame {number}</h2>'
                     f'<a href="{html.escape(path.resolve().as_uri())}">元画像</a>')
        for role in report["roles"]:
            x1, y1, x2, y2 = layout.normalized_roi(role).pixel_bounds(*layout.reference_resolution)
            name = f"held_{number}_{role}.png"
            if not cv2.imwrite(str(output / name), image[y1:y2, x1:x2]):
                raise ValueError("review crop write failed")
            review_row["roi_assets"][name] = sha256_file(output / name)
            cards.append(f'<img src="{name}">')
        report["review_frames"].append(review_row)
    if any(sha256_file(p) != h for p, h in bindings.items()):
        raise ValueError("frozen inputs changed during discovery")
    (output / "index.html").write_text('<!doctype html><meta charset="utf-8">'
        '<h1>未ラベルUI形状候補（GT・イベント・本番採用ではありません）</h1>' + ''.join(cards),
        encoding="utf-8")
    report["review_html_sha256"] = sha256_file(output / "index.html")
    (output / "candidate_report.json").write_text(json.dumps(report, indent=2) + "\n",
                                                    encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("pool", "layout", "partition", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--reserved-source-hash", action="append", default=[])
    args = parser.parse_args()
    result = discover(args.pool, args.layout, args.partition, args.output,
                      set(args.reserved_source_hash))
    print(json.dumps({"training": result["training_count"], "held": result["held_count"],
                      "candidates": {k: len(v) for k, v in result["roles"].items()},
                      "production_adopted": False}))


if __name__ == "__main__":
    main()
