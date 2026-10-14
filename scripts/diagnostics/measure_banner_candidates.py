"""Measure every frozen unlabeled candidate on its development held images.

No candidate selection, semantic annotation, absence inference or adoption.
Neighbouring frames are not independent temporal qualification examples.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np

from scripts.e2e.run_dataset_case import sha256_file
from valorant_ai_coach.hud.calibrate_temporal import _check_output_privacy
from valorant_ai_coach.hud.layout import HudLayout
from valorant_ai_coach.hud.semantic_text import SemanticTextReference
from valorant_ai_coach.hud.weapon_identity import masked_score


def measure(report_path, pool, layout_path, output, role="round_end_banner"):
    _check_output_privacy(output.resolve())
    if output.exists():
        raise FileExistsError("new private measurement receipt required")
    report = json.loads(report_path.read_text())
    if (report.get("kind") != "unlabeled_banner_discovery_not_qualification"
            or report.get("training_candidate_audit") is not True
            or report.get("held_predictions_measured") is not False
            or report.get("semantic_labels_assigned") is not False
            or report.get("qualification_created") is not False
            or report.get("production_adopted") is not False):
        raise ValueError("frozen unlabeled training-only audit required")
    bindings = {str(Path(p).resolve()): h for p, h in report["source_inputs_sha256"].items()}
    if bindings.get(str(layout_path.resolve())) != sha256_file(layout_path):
        raise ValueError("layout must be the unchanged frozen discovery input")
    for path in (report_path, layout_path, Path(__file__),
                 Path(SemanticTextReference.score.__code__.co_filename),
                 Path(masked_score.__code__.co_filename)):
        resolved = str(path.resolve())
        digest = sha256_file(path)
        if resolved in bindings and bindings[resolved] != digest:
            raise ValueError("layout differs from frozen discovery input")
        bindings[resolved] = digest

    def verify():
        if any(sha256_file(Path(p)) != h for p, h in bindings.items()):
            raise ValueError("frozen discovery/source/assets changed")

    verify()
    training, held = report["training_hashes"], report["held_hashes"]
    if (min(len(training), len(held)) < 3 or max(len(training), len(held)) > 256
            or len(set(training + held)) != len(training + held)):
        raise ValueError("bounded distinct training/held source groups required")
    layout = HudLayout.load(layout_path)
    x1, y1, x2, y2 = layout.normalized_roi(role).pixel_bounds(*layout.reference_resolution)
    crops = {}
    for path in sorted((pool / "pool_frames").glob("*.jpg")):
        digest = sha256_file(path)
        if digest not in set(training + held):
            continue
        if bindings.get(str(path.resolve())) != digest or digest in crops:
            raise ValueError("source image must have unique frozen discovery binding")
        image = cv2.imread(str(path))
        if image is None or (image.shape[1], image.shape[0]) != layout.reference_resolution:
            raise ValueError("native source dimensions required")
        crops[digest] = cv2.cvtColor(image[y1:y2, x1:x2], cv2.COLOR_BGR2GRAY)
    if set(crops) != set(training + held):
        raise ValueError("complete frozen source pool required")
    rows = report["roles"][role]
    if not 1 <= len(rows) <= 16:
        raise ValueError("bounded preselected training candidates required")
    measurements = []
    for row in rows:
        if row["semantic_label"] is not None or row["held_scores"] is not None:
            raise ValueError("unlabeled candidate must be frozen before held scoring")
        assets = {}
        for suffix in ("reference", "mask", "groups"):
            name = f'{row["candidate_id"]}_{suffix}.png'
            if Path(name).name != name:
                raise ValueError("local candidate asset required")
            path = report_path.parent / name
            bindings[str(path.resolve())] = row["asset_hashes"][name]
            verify()
            assets[suffix] = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
        a, b, c, d = row["bounds_in_roi"]
        if (any(type(v) is not int for v in (a, b, c, d))
                or not 0 <= a < c <= x2 - x1 or not 0 <= b < d <= y2 - y1):
            raise ValueError("frozen bounds must be inside configured ROI")
        matcher = SemanticTextReference(assets["reference"], assets["mask"], assets["groups"],
            [(h, crops[h][b:d, a:c]) for h in training], report["threshold"])
        measured = [matcher.measure(crops[h][b:d, a:c]) for h in held]
        scores = [m["score"] for m in measured]
        measurements.append({"candidate_id": row["candidate_id"], "semantic_label": None,
            "held_accept_count": sum(s >= matcher.threshold for s in scores),
            "score_summary": {"min": min(scores), "median": float(np.median(scores)),
                              "max": max(scores)}, "held_measurements": measured})
    verify()
    result = {"kind": "frozen_banner_measurement_not_qualification",
        "source_sha256": report["source_sha256"], "role": role,
        "training_count": len(training), "held_hashes": held, "candidates": measurements,
        "source_inputs_sha256": bindings, "candidates_reselected": False,
        "semantic_labels_assigned": False, "independent_temporal_cohort": False,
        "events_generated": 0, "qualification_created": False, "production_adopted": False}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("report", "pool", "layout", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    result = measure(args.report, args.pool, args.layout, args.output)
    print(json.dumps({"held": len(result["held_hashes"]), "candidates": [
        {"candidate_id": r["candidate_id"], "accept_count": r["held_accept_count"]}
        for r in result["candidates"]], "production_adopted": False}))


if __name__ == "__main__":
    main()
