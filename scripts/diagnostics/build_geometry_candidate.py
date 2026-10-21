"""Build an isolated geometry-only candidate from unlabelled development frames.

Never installs a production profile, uses GT or emits lifecycle/identity events.
Validation is measured only after freezing training-derived assets. Unlabelled
source frames are not declared positive/negative geometry ground truth.
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from scripts.diagnostics.diagnose_geometry_edges import (
    edge_candidate,
    raw_scores,
    replay_geometry,
    summary,
)
from scripts.e2e.run_dataset_case import sha256_file
from valorant_ai_coach.hud.calibrate_temporal import ANCHORS, _check_output_privacy
from valorant_ai_coach.hud.layout import HudLayout
from valorant_ai_coach.hud.templates import HudTemplateProfile
from valorant_ai_coach.video import VideoMetadata, VideoService


def sampling_plan(end: float, previous: list[float]) -> dict[str, Any]:
    if (type(end) not in (int, float) or not math.isfinite(end) or end <= 0
            or any(type(t) not in (int, float) or not math.isfinite(t) or t < 0
                   for t in previous)):
        raise ValueError("finite development boundary/history required")
    roles = {}
    for role, offset in (("training", 3.25), ("validation", 13.25)):
        times = [offset + 20 * index for index in range(math.ceil(end / 20))
                 if offset + 20 * index < end]
        roles[role] = [t for t in times if all(abs(t - old) >= 2 for old in previous)]
        if len(roles[role]) < 8:
            raise ValueError("insufficient unseen development samples")
    return {"development_end_sec": end, "period_sec": 20, "exclusion_radius_sec": 2,
            "previous_geometry_pts": sorted(set(previous)), **roles}


def read_frames(service: VideoService, video: Path, times: list[float], directory: Path,
                metadata: VideoMetadata) -> tuple[list[np.ndarray], list[dict[str, Any]]]:
    frames = service.extract_frames(video, times, directory, metadata=metadata,
                                    max_frames=len(times), max_dimension=None)
    if len(frames) != len(times):
        raise ValueError("incomplete candidate extraction")
    images, records = [], []
    for frame, requested in zip(frames, times, strict=True):
        image = cv2.imread(str(frame.path))
        if (image is None or image.shape[:2] != (metadata.height, metadata.width)
                or not math.isfinite(frame.time_sec) or abs(frame.time_sec - requested)
                > 1 / metadata.fps + 1e-6):
            raise ValueError("native-resolution source PTS/dimensions mismatch")
        images.append(image)
        records.append({"requested_sec": requested, "source_frame_pts": frame.time_sec,
                        "sha256": sha256_file(frame.path)})
    if len({row["source_frame_pts"] for row in records}) != len(records):
        raise ValueError("duplicate source frame PTS")
    return images, records


def build(training: list[np.ndarray], layout: HudLayout, base: dict[str, Any], output: Path, *,
          template_strategy: str = "median") -> dict[str, Any]:
    if template_strategy not in {"median", "training_medoid"}:
        raise ValueError("unsupported diagnostic template strategy")
    specs: dict[str, Any] = {}
    diagnostics: dict[str, Any] = {}
    height, width = training[0].shape[:2]
    if layout.reference_resolution != (width, height):
        raise ValueError("candidate reference resolution mismatch")
    for name in ANCHORS:
        x1, y1, x2, y2 = layout.normalized_roi(name).pixel_bounds(width, height)
        crops = [image[y1:y2, x1:x2] for image in training]
        threshold = base.get("anchors", {}).get(name, {}).get("threshold", .90)
        if type(threshold) not in (float, int) or not math.isfinite(threshold) or not .90 <= (
                threshold) <= 1:
            raise ValueError("existing NCC threshold must remain >=0.90")
        candidate = edge_candidate(crops, template_strategy=template_strategy, threshold=threshold)
        if candidate is None:
            diagnostics[name] = {"status": "training_structure_insufficient"}
            continue
        template, mask, statistics = candidate
        specs[name] = {"template": f"{name}.template.png", "mask": f"{name}.mask.png",
                       "threshold": threshold}
        search = base.get("anchors", {}).get(name, {}).get("search_region")
        if search is not None:
            specs[name]["search_region"] = search
        for suffix, pixels in (("template", template), ("mask", mask)):
            ok, encoded = cv2.imencode(".png", pixels)
            if not ok:
                raise ValueError("cannot encode candidate asset")
            path = output / f"{name}.{suffix}.png"
            path.write_bytes(encoded.tobytes())
            statistics[f"{suffix}_sha256"] = sha256_file(path)
        scores = raw_scores(crops, template, mask)
        diagnostics[name] = {**statistics, "threshold": threshold,
                             "training_similarity": summary(scores),
                             "training_accept_count": sum(s >= threshold for s in scores)}
    (output / "hud_layout.templates.json").write_text(json.dumps({
        "schema_version": "1.0", "anchors": specs, "signals": {}, "readers": {},
    }, indent=2) + "\n", encoding="utf-8")
    return diagnostics


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("video", "layout", "approval", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--source-sha256", required=True)
    parser.add_argument("--template-strategy", choices=("median", "training_medoid"),
                        default="median")
    parser.add_argument("--development-end", type=float, required=True)
    parser.add_argument("--prior-diagnostics", type=Path, action="append", required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    _check_output_privacy(output)
    if output.exists():
        raise FileExistsError("use a new private candidate directory")
    approval = json.loads(args.approval.read_text(encoding="utf-8"))
    if (approval.get("candidate_profile_generation_authorized") is not True
            or approval.get("qualification_experiment_authorized") is not True
            or approval.get("production_adoption_authorized") is not False
            or approval.get("threshold_change_authorized") is not False
            or approval.get("identity_reuse_authorized") is not False):
        raise ValueError("scoped experimental candidate approval required")
    previous: list[float] = []
    inputs = [args.layout, args.layout.with_suffix(".templates.json"), args.approval,
              Path(__file__), Path(__file__).with_name("diagnose_geometry_edges.py"),
              *args.prior_diagnostics]
    hashes = {str(path): sha256_file(path) for path in inputs}
    for path in args.prior_diagnostics:
        history = json.loads(path.read_text(encoding="utf-8"))
        if (history.get("kind") != "geometry_edge_experiment_not_profile"
                or history["source_sha256"] != args.source_sha256):
            raise ValueError("only same-source geometry diagnostics may exclude samples")
        previous.extend(row["source_frame_pts"] for row in history["frames"])
    plan = sampling_plan(args.development_end, previous)
    if sha256_file(args.video) != args.source_sha256:
        raise ValueError("source SHA mismatch")
    service = VideoService()
    metadata = service.probe(args.video)
    if args.development_end > metadata.duration_sec:
        raise ValueError("development window outside source")
    layout = HudLayout.load(args.layout)
    base = json.loads(args.layout.with_suffix(".templates.json").read_text(encoding="utf-8"))
    output.mkdir(parents=True)
    (output / "plan.json").write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    training, training_records = read_frames(
        service, args.video, plan["training"], output / "training_frames", metadata)
    diagnostics = build(training, layout, base, output, template_strategy=args.template_strategy)
    shutil.copyfile(args.layout, output / "hud_layout.json")
    frozen = {p.name: sha256_file(p) for p in output.glob("*.png")}
    frozen.update({name: sha256_file(output / name)
                   for name in ("hud_layout.json", "hud_layout.templates.json", "plan.json")})
    # Assets/configuration are frozen before any validation image is extracted.
    (output / "candidate_fingerprint.json").write_text(
        json.dumps(frozen, indent=2) + "\n", encoding="utf-8")
    validation, validation_records = read_frames(
        service, args.video, plan["validation"], output / "validation_frames", metadata)
    if any(not 0 <= row["source_frame_pts"] < args.development_end
           for row in training_records + validation_records):
        raise ValueError("decoded frame escaped development window")
    profile = HudTemplateProfile.load(output / "hud_layout.templates.json")
    replay = replay_geometry(validation, layout, profile)
    # Known-invalid transforms of real source frames are challenge controls,
    # not labelled unmodified real-video negatives or complete qualification.
    invalid = {"large_shift_real_frame": np.roll(validation[0], metadata.width // 5, axis=1),
               "resolution_mismatch_real_frame": cv2.resize(validation[0], (
                   metadata.width // 2, metadata.height // 2)),
               "letterbox_real_frame": cv2.copyMakeBorder(validation[0][100:-100],
                                                           100, 100, 0, 0,
                                                           cv2.BORDER_CONSTANT)}
    controls = {name: replay_geometry([image], layout, profile) for name, image in invalid.items()}
    if (sha256_file(args.video) != args.source_sha256
            or any(sha256_file(Path(path)) != value for path, value in hashes.items())
            or any(sha256_file(output / name) != value for name, value in frozen.items())):
        raise ValueError("source/configuration/candidate changed during experiment")
    report = {"source_sha256": args.source_sha256, "input_sha256": hashes,
              "source_hash_verified_after_processing": True,
              "candidate_assets_frozen_before_validation": True,
              "training_frames": training_records, "validation_frames": validation_records,
              "anchors": diagnostics, "template_strategy": args.template_strategy,
              "validation_geometry_replay": replay,
              "real_source_transform_controls": controls,
              "independent_unmodified_geometry_labels": "not_reviewed",
              "real_video_negative_qualification": "not_completed",
              "identity_assets_generated": False, "production_adopted": False,
              "production_qualified": False,
              "status": "no_positive_geometry_evidence" if not replay[
                  "fresh_geometry_success_count"] else "pending_independent_geometry_review"}
    (output / "candidate_report.json").write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "training": len(training),
                      "validation": len(validation), "fresh_geometry_success": replay[
                          "fresh_geometry_success_count"], "production_adopted": False}))


if __name__ == "__main__":
    main()
