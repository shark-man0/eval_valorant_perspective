"""Counterfactual source-frame anchor ablation, not unmodified real-video GT.

References/masks are frozen and never selected or altered using these controls.
A removed anchor must not match an unrelated neighbouring HUD/background line.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2

from scripts.diagnostics.diagnose_geometry_edges import replay_geometry
from scripts.e2e.run_dataset_case import sha256_file
from valorant_ai_coach.hud.calibrate_temporal import _check_output_privacy
from valorant_ai_coach.hud.layout import HudLayout
from valorant_ai_coach.hud.templates import HudTemplateProfile


def challenge(candidate: Path) -> dict:
    report = json.loads((candidate / "candidate_report.json").read_text(encoding="utf-8"))
    frozen = json.loads((candidate / "candidate_fingerprint.json").read_text(encoding="utf-8"))
    for name, digest in frozen.items():
        path = (candidate / name).resolve()
        if not path.is_relative_to(candidate.resolve()) or sha256_file(path) != digest:
            raise ValueError("candidate changed or escaped")
    layout = HudLayout.load(candidate / "hud_layout.json")
    profile = HudTemplateProfile.load(candidate / "hud_layout.templates.json")
    names = list(profile.raw["anchors"])
    frames = sorted((candidate / "validation_frames").glob("*.jpg"))
    if len(frames) != len(report["validation_frames"]):
        raise ValueError("validation image inventory mismatch")
    cases = []
    for index, (path, source) in enumerate(zip(frames, report["validation_frames"], strict=True)):
        if sha256_file(path) != source["sha256"]:
            raise ValueError("validation image changed")
        image = cv2.imread(str(path))
        if image is None or (image.shape[1], image.shape[0]) != layout.reference_resolution:
            raise ValueError("validation image dimensions mismatch")
        for removed in ([name] for name in names):
            altered = image.copy()
            for name in removed:
                x1, y1, x2, y2 = layout.normalized_roi(name).pixel_bounds(
                    image.shape[1], image.shape[0])
                altered[y1:y2, x1:x2] = 70
            row = replay_geometry([altered], layout, profile)["frames"][0]
            false_matches = sorted(set(removed) & set(row["accepted_anchors"]))
            cases.append({"validation_index": index, "removed_anchors": removed,
                          "accepted_anchors": row["accepted_anchors"],
                          "scores": row["scores"], "false_matches": false_matches,
                          "fresh_geometry_success": row["fresh_geometry_success"]})
    if any(sha256_file(candidate / name) != digest for name, digest in frozen.items()):
        raise ValueError("candidate changed during challenge")
    return {"kind": "geometry_source_ablation_challenge_not_real_gt",
            "candidate_report_sha256": sha256_file(candidate / "candidate_report.json"),
            "references_changed": False, "production_adopted": False,
            "case_count": len(cases),
            "false_match_cases": sum(bool(row["false_matches"]) for row in cases),
            "removed_anchor_false_match_counts": {
                name: sum(name in row["false_matches"] for row in cases) for name in names},
            "cases": cases}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    _check_output_privacy(args.output.resolve())
    if args.output.exists():
        raise FileExistsError("use a new private challenge receipt")
    result = challenge(args.candidate)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key != "cases"}))


if __name__ == "__main__":
    main()
