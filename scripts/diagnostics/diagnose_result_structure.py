"""Training-only structural text feasibility; never an adopted result detector.

Uses the existing semantic-text matcher and unchanged 0.90 threshold. All
training images come from an explicit hash-bound native manifest. No holdout,
expected result, timestamp rule or Validation Pack is read.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np

from scripts.diagnostics.diagnose_result_text import load_method
from scripts.diagnostics.diagnose_round_lifecycle import sha256_file
from valorant_ai_coach.hud.calibrate_temporal import _check_output_privacy
from valorant_ai_coach.hud.layout import HudLayout, NormalizedRoi
from valorant_ai_coach.hud.semantic_text import SemanticTextReference
from valorant_ai_coach.hud.weapon_identity import masked_score


def glyph_candidate(crops: list[np.ndarray], hashes: list[str],
                    evaluation: list[np.ndarray] | None = None) -> dict:
    """Whole-box 3x3 tiles per connected glyph; no word repair or search."""
    if (len(crops) < 3 or len(crops) != len(hashes) or len(set(hashes)) != len(hashes)
            or any(c.ndim != 2 or c.dtype != np.uint8 or c.shape != crops[0].shape
                   for c in crops)):
        raise ValueError("distinct equally-sized source training required")
    reference = np.median(np.stack(crops), axis=0).astype(np.uint8)
    binary = (reference >= 210).astype(np.uint8) * 255
    count, _, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    boxes = sorted([tuple(int(v) for v in row[:4]) for row in stats[1:count]
                    if row[4] >= 32 and row[2] >= 3 and row[3] >= max(3, reference.shape[0] * .4)])
    report = {"method": "connected_glyph_binary210_wholebox_tiles3_v1",
              "threshold": .90, "glyph_boxes": boxes, "training_frame_hashes": hashes,
              "semantic_identity_verified": False, "qualification_created": False,
              "profile_adopted": False, "events_emitted": 0}
    if not 3 <= len(boxes) <= 16:
        return {**report, "status": "training_rejected", "reason": "glyph_count_unsupported"}

    def score(image):
        if image.shape != reference.shape:
            return 0.0
        sample = (image >= 210).astype(np.uint8) * 255
        scores = []
        for x, y, w, h in boxes:
            for ys in np.array_split(np.arange(y, y+h), 3):
                for xs in np.array_split(np.arange(x, x+w), 3):
                    ref = binary[np.ix_(ys, xs)]
                    current = sample[np.ix_(ys, xs)]
                    if ref.std() == 0:
                        # Include blank interior/background: extra strokes
                        # outside the foreground mask must not be ignored.
                        scores.append(float(np.mean(ref == current)))
                    else:
                        scores.append(masked_score(ref, current, np.full_like(ref, 255)))
        return min(scores)

    scores = [score(c) for c in crops]
    support = sum(s >= .90 for s in scores)
    return {**report, "training_scores": scores, "training_support": support,
            "status": "training_supported_not_qualified" if support >= 3 else "training_rejected",
            "evaluation_scores": [score(c) for c in (evaluation or [])] if support >= 3 else []}


def structural_candidate(crops: list[np.ndarray], hashes: list[str],
                         evaluation: list[np.ndarray] | None = None) -> dict:
    """Fixed four-group glyph-neighbourhood rule, with no parameter search."""
    if len(crops) < 3 or len(crops) != len(hashes):
        raise ValueError("at least three source crops required")
    if any(c.ndim != 2 or c.dtype != np.uint8 or c.shape != crops[0].shape for c in crops):
        raise ValueError("equal grayscale source dimensions required")
    reference = np.median(np.stack(crops), axis=0).astype(np.uint8)
    foreground = np.asarray(reference >= 210, dtype=np.uint8) * 255
    mask = cv2.dilate(foreground, np.ones((3, 3), np.uint8))
    regions = np.zeros_like(mask)
    for group, columns in enumerate(np.array_split(np.arange(mask.shape[1]), 4), 1):
        regions[:, columns] = np.where(mask[:, columns] > 0, group, 0)
    report = {
        "method": "median_gray_white210_dilate3_four_groups_v1",
        "threshold": .90, "training_frame_hashes": hashes,
        "dimensions": [reference.shape[1], reference.shape[0]],
        "mask_population": int(np.count_nonzero(mask)),
        "semantic_identity_verified": False,
        "qualification_created": False, "events_emitted": 0, "profile_adopted": False,
    }
    try:
        matcher = SemanticTextReference(reference, mask, regions,
                                        list(zip(hashes, crops, strict=True)), .90)
    except ValueError as error:
        return {**report, "status": "training_rejected", "reason": str(error)}
    scores = [matcher.score(crop) for crop in crops]
    return {**report, "status": "training_supported_not_qualified",
            "training_support": matcher.training_support, "training_scores": scores,
            "evaluation_scores": [matcher.score(crop) for crop in (evaluation or [])]}


def run(video: Path, native_run: Path, layout: Path, method: Path, output: Path,
        evaluation_runs: list[Path] | None = None, matcher: str = "four_groups") -> dict:
    _check_output_privacy(output.resolve())
    evaluation_runs = evaluation_runs or []
    source_root = Path(__file__).parents[2] / "src/valorant_ai_coach/hud"
    implementation_paths = [source_root / name for name in
                            ("semantic_text.py", "weapon_identity.py", "layout.py")]
    implementation_hashes = [sha256_file(p) for p in implementation_paths]
    inputs = [video, native_run / "results.json", layout, method, Path(__file__)]
    inputs.extend(p / "results.json" for p in evaluation_runs)
    input_hashes = [sha256_file(p) for p in inputs]
    manifest = json.loads(inputs[1].read_bytes())
    if (manifest.get("native_pts_coverage_verified") is not True
            or manifest.get("source_video_sha256") != input_hashes[0]):
        raise ValueError("verified source native manifest required")
    config = load_method(method)
    if config["version"] != "semantic_result_ocr_diagnostic_v1":
        raise ValueError("result text training crop required")
    selected_roi = HudLayout.load(layout).normalized_roi(config["roi"])
    populations = []
    for directory in [native_run, *evaluation_runs]:
        source = json.loads((directory / "results.json").read_bytes())
        if (source.get("native_pts_coverage_verified") is not True
                or source.get("source_video_sha256") != input_hashes[0]):
            raise ValueError("verified matching evaluation source required")
        crops, hashes, frame_paths, pts = [], [], [], []
        for index, window in enumerate(source["windows"]):
            for number, row in enumerate(window["rows"], 1):
                path = directory / f"window-{index:03d}" / f"frame_{number:06d}.png"
                if sha256_file(path) != row["frame_sha256"]:
                    raise ValueError("source image hash mismatch")
                image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
                if image is None:
                    raise ValueError("source image unreadable")
                a, b, c, d = selected_roi.pixel_bounds(image.shape[1], image.shape[0])
                roi = image[b:d, a:c]
                left, top, right, bottom = config["subregion_norm"]
                a, b, c, d = NormalizedRoi(left, top, right-left, bottom-top).pixel_bounds(
                    roi.shape[1], roi.shape[0])
                crops.append(roi[b:d, a:c])
                hashes.append(row["frame_sha256"])
                frame_paths.append(path)
                pts.append(row["pts_sec"])
        populations.append((crops, hashes, frame_paths, pts))
    crops, hashes, _, _ = populations[0]
    if any(set(hashes).intersection(population[1]) for population in populations[1:]):
        raise ValueError("training and evaluation source images overlap")
    evaluation = [crop for p in populations[1:] for crop in p[0]]
    if matcher not in {"four_groups", "glyph_tiles"}:
        raise ValueError("unsupported frozen structural matcher")
    report = (glyph_candidate if matcher == "glyph_tiles" else structural_candidate)(
        crops, hashes, evaluation)
    if evaluation and report["status"] == "training_rejected":
        report.pop("evaluation_scores", None)
    if "evaluation_scores" in report:
        scores = iter(report.pop("evaluation_scores"))
        report["evaluation_populations"] = [
            {"manifest_sha256": input_hashes[5 + index],
             "rows": [{"pts_sec": pts, "frame_sha256": frame_hash,
                       "score": next(scores)} for pts, frame_hash in zip(p[3], p[1], strict=True)]}
            for index, p in enumerate(populations[1:])
        ]
    if (input_hashes != [sha256_file(p) for p in inputs]
            or implementation_hashes != [sha256_file(p) for p in implementation_paths]
            or any(p[1] != [sha256_file(path) for path in p[2]] for p in populations)):
        raise ValueError("training inputs changed")
    report["input_hashes"] = input_hashes
    report["implementation_hashes"] = dict(zip(
        [p.name for p in implementation_paths], implementation_hashes, strict=True))
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(report, indent=2) + "\n")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("video", "native-run", "layout", "method", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--evaluation-run", type=Path, action="append", default=[])
    parser.add_argument("--matcher", choices=["four_groups", "glyph_tiles"], default="four_groups")
    args = parser.parse_args()
    report = run(args.video, args.native_run, args.layout, args.method, args.output,
                 args.evaluation_run, args.matcher)
    print(json.dumps({k: v for k, v in report.items() if k != "evaluation_populations"}))


if __name__ == "__main__":
    main()
