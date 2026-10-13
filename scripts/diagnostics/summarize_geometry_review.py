"""Bind private human geometry labels to frozen candidate measurements.

No fitting, new matcher threshold, identity decision or adoption occurs here.
Edge scores are descriptive only; raw NCC acceptance remains unchanged.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np

from scripts.diagnostics.diagnose_geometry_edges import raw_scores, replay_geometry, summary
from scripts.diagnostics.geometry_edge_similarity import measure
from scripts.e2e.run_dataset_case import sha256_file
from valorant_ai_coach.hud.calibrate_temporal import _check_output_privacy
from valorant_ai_coach.hud.layout import HudLayout
from valorant_ai_coach.hud.templates import HudTemplateProfile


def summarize(candidate: Path, review: Path, approval: Path) -> dict:
    fingerprint = candidate / "candidate_fingerprint.json"
    frozen = json.loads(fingerprint.read_text(encoding="utf-8"))
    if not {"hud_layout.json", "hud_layout.templates.json"} <= frozen.keys():
        raise ValueError("candidate inventory missing required inputs")

    def check_frozen() -> None:
        for name, digest in frozen.items():
            path = (candidate / name).resolve()
            if not path.is_relative_to(candidate.resolve()) or sha256_file(path) != digest:
                raise ValueError("frozen candidate changed or escaped")

    check_frozen()
    hashes = {"review_receipt_sha256": sha256_file(review),
              "candidate_report_sha256": sha256_file(candidate / "candidate_report.json"),
              "candidate_fingerprint_sha256": sha256_file(fingerprint)}
    approved = json.loads(approval.read_text(encoding="utf-8"))
    approval_hash = sha256_file(approval)
    if any(approved.get(key) != value for key, value in hashes.items()):
        raise ValueError("human approval fingerprint mismatch")
    receipt = json.loads(review.read_text(encoding="utf-8"))
    if (receipt.get("production_input") is not False
            or receipt.get("model_scores_exposed") is not False
            or any(receipt.get(key) != hashes[key] for key in (
                "candidate_report_sha256", "candidate_fingerprint_sha256"))):
        raise ValueError("independent blind review required")
    report = json.loads((candidate / "candidate_report.json").read_text(encoding="utf-8"))
    sources = report["validation_frames"]
    frames = receipt["frames"]
    scope = approved["scope"]
    if (scope.get("mask_fixed_ui_not_digits_or_variable_icons") is not True
            or scope.get("all_reviewed_frames_fixed_ui_visible_at_guides") is not True
            or scope.get("frame_numbers") != list(range(1, len(sources) + 1))
            or len(frames) != len(sources) or not sources):
        raise ValueError("explicit complete geometry-only review required")
    layout = HudLayout.load(candidate / "hud_layout.json")
    profile = HudTemplateProfile.load(candidate / "hud_layout.templates.json")
    if (set(scope["anchors"]) != set(profile.raw["anchors"])
            or len(scope["anchors"]) != len(profile.raw["anchors"])):
        raise ValueError("review anchor scope mismatch")
    paths = sorted((candidate / "validation_frames").glob("*.jpg"))
    if len(paths) != len(sources):
        raise ValueError("source inventory mismatch")
    images = []
    for number, (path, source, frame) in enumerate(zip(paths, sources, frames, strict=True), 1):
        if (frame["frame_number"] != number or frame["source_sha256"] != source["sha256"]
                or frame["source_frame_pts"] != source["source_frame_pts"]
                or sha256_file(path) != source["sha256"]):
            raise ValueError("review source binding changed")
        image = cv2.imread(str(path))
        if image is None or (image.shape[1], image.shape[0]) != layout.reference_resolution:
            raise ValueError("source dimensions mismatch")
        images.append(image)
    replay = replay_geometry(images, layout, profile)
    anchors = {}
    for name, spec in profile.raw["anchors"].items():
        for key in ("template", "mask"):
            asset = profile.resolve_asset(spec[key]).resolve()
            if (not asset.is_relative_to(candidate.resolve())
                    or asset.relative_to(candidate.resolve()).as_posix() not in frozen):
                raise ValueError("anchor asset outside frozen inventory")
        template = profile.load_template(name, spec["template"], spec["threshold"]).image
        mask = cv2.imread(str(profile.resolve_asset(spec["mask"])), cv2.IMREAD_GRAYSCALE)
        if mask is None or mask.shape != template.shape or not mask.any():
            raise ValueError("invalid frozen geometry mask")
        x1, y1, x2, y2 = layout.normalized_roi(name).pixel_bounds(*layout.reference_resolution)
        crops = [image[y1:y2, x1:x2] for image in images]
        aligned = raw_scores(crops, template, mask)
        edges = [measure(template, cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY), mask)
                 for crop in crops]
        scores = [row["scores"][name] for row in replay["frames"] if name in row["scores"]]
        anchors[name] = {
            "threshold": spec["threshold"],
            "human_visible_aligned_count": len(images),
            "runtime_accept_count": sum(name in row["accepted_anchors"]
                                        for row in replay["frames"]),
            "runtime_similarity": summary(scores) if scores else None,
            "runtime_score_unavailable_count": len(images) - len(scores),
            "configured_position_similarity": summary(aligned),
            "edge_similarity_diagnostic_only": summary(
                [row["score"] for row in edges if row["score"] is not None]
            ) if any(row["score"] is not None for row in edges) else None,
            "edge_acceptance_threshold": None,
            "mask_population": int(np.count_nonzero(mask)),
        }
    check_frozen()
    if (sha256_file(review) != hashes["review_receipt_sha256"]
            or sha256_file(approval) != approval_hash
            or any(sha256_file(path) != source["sha256"]
                   for path, source in zip(paths, sources, strict=True))):
        raise ValueError("review/source changed during measurement")
    return {"kind": "reviewed_geometry_measurements_not_adoption", **hashes,
            "approval_sha256": approval_hash, "sample_count": len(images),
            "unique_source_image_count": len({row["sha256"] for row in sources}),
            "fresh_geometry_success_count": replay["fresh_geometry_success_count"],
            "anchors": anchors, "production_adopted": False,
            "production_qualified": False, "player_identity_qualified": False,
            "real_video_negative_qualification": "incomplete",
            "validation_used_for_fitting": False}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("candidate", "review", "approval", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    _check_output_privacy(args.output.resolve())
    if args.output.exists():
        raise FileExistsError("use a new private diagnostic receipt")
    result = summarize(args.candidate, args.review, args.approval)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps(result, allow_nan=False))


if __name__ == "__main__":
    main()
