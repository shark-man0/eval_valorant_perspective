"""Private diagnostic experiment; never exports a loadable HUD profile or events.

Geometry-only edge masks use training pixels. Holdout is scored once with
unchanged raw masked pixel NCC, not a new runtime edge matcher. This script
does not run an Analyzer or read GT/Validation Packs. Runtime anchor/inlier
replay remains diagnostic evidence, not player identity or production qualification.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import cv2
import numpy as np

from scripts.diagnostics import geometry_edge_similarity
from scripts.diagnostics.prepare_boundary_review import validate_review_pts
from scripts.e2e.frame_replay import decoder_fingerprints
from scripts.e2e.probe_cache import CachedVideoService
from scripts.e2e.run_dataset_case import git_identity, sha256_file
from valorant_ai_coach.hud.analyzers import _detect_letterbox
from valorant_ai_coach.hud.calibrate_temporal import (
    ANCHORS,
    _check_output_privacy,
    _validated_candidate,
    sampling_times,
)
from valorant_ai_coach.hud.layout import HudLayout
from valorant_ai_coach.hud.templates import HudTemplateProfile
from valorant_ai_coach.video import VideoService


def summary(values: list[float]) -> dict:
    return {"min": min(values), "median": float(np.median(values)), "max": max(values)}


def edge_candidate(images: list[np.ndarray]) -> tuple[np.ndarray, np.ndarray, dict] | None:
    """Frozen experimental proposal; no holdout pixels or state labels accepted."""
    if len(images) < 8 or any(image.shape != images[0].shape for image in images):
        return None
    gray = [cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) for image in images]
    edges = np.stack([cv2.Canny(image, 60, 150) > 0 for image in gray])
    hits = edges.sum(axis=0)
    real = np.zeros(hits.shape, np.float32)
    imaginary = np.zeros_like(real)
    for image, edge in zip(gray, edges, strict=True):
        gx = cv2.Sobel(image, cv2.CV_32F, 1, 0)
        gy = cv2.Sobel(image, cv2.CV_32F, 0, 1)
        denominator = np.maximum(gx * gx + gy * gy, 1e-6)
        # Unsigned orientation: contrast polarity may reverse, position must not.
        real += edge * (gx * gx - gy * gy) / denominator
        imaginary += edge * (2 * gx * gy) / denominator
    orientation = np.sqrt(real * real + imaginary * imaginary) / np.maximum(hits, 1)
    persistence = hits / len(images)
    core = (persistence >= .65) & (orientation >= .90)
    # Sobel reflection at crop boundaries fabricates axis-aligned orientations.
    # Exclude derivative border plus the one-pixel dilation neighborhood.
    core[:2, :] = core[-2:, :] = False
    core[:, :2] = core[:, -2:] = False
    # Include both sides of an edge for informative raw-pixel NCC contrast.
    mask = cv2.dilate(core.astype(np.uint8), np.ones((3, 3), np.uint8)) * 255
    template = np.median(np.stack(gray), axis=0).astype(np.uint8)
    values = template[mask > 0]
    if values.size < 64 or float(values.std()) < 1:
        return None
    diagnostics = {
        "edge_count": int(np.count_nonzero(hits)),
        "persistent_edge_count": int(np.count_nonzero(persistence >= .65)),
        "stable_edge_ratio": float(np.count_nonzero(core) / max(np.count_nonzero(hits), 1)),
        "orientation_consistent_edge_count": int(np.count_nonzero(core)),
        "orientation_consistency": summary(orientation[core].tolist()),
        "mask_population": int(values.size),
        "mask_ratio": float(values.size / mask.size),
        "selected_contrast_std": float(values.std()),
    }
    return template, mask, diagnostics


def raw_scores(images: list[np.ndarray], template: np.ndarray, mask: np.ndarray) -> list[float]:
    result = []
    for image in images:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        value = float(cv2.matchTemplate(gray, template, cv2.TM_CCOEFF_NORMED, mask=mask)[0, 0])
        result.append(max(0.0, min(1.0, value)) if math.isfinite(value) else 0.0)
    return result


def training_medoid(
    training: list[np.ndarray], mask: np.ndarray, threshold: float,
) -> tuple[np.ndarray, dict]:
    """Select one observed reference using training-only, non-self raw NCC.

    No score threshold or mask is adjusted. Ties use cross-frame median then
    earliest training index; holdout pixels cannot select a reference.
    """
    rows, templates = [], []
    for index, image in enumerate(training):
        template = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        scores = raw_scores(training[:index] + training[index + 1:], template, mask)
        rows.append({"training_index": index,
                     "nonself_accept_count": sum(score >= threshold for score in scores),
                     "nonself_similarity": summary(scores)})
        templates.append(template)
    selected = max(range(len(rows)), key=lambda index: (
        rows[index]["nonself_accept_count"],
        rows[index]["nonself_similarity"]["median"], -index,
    ))
    return templates[selected], {"selected_training_index": selected,
                                 "selection_scores_exclude_self": True,
                                 "training_reference_candidates": rows}


def compare(images: list[np.ndarray], threshold: float, *,
            template_strategy: str = "median",
            edge_similarity_diagnostic: bool = False) -> tuple[dict, tuple | None]:
    if template_strategy not in {"median", "training_medoid"}:
        raise ValueError("unsupported diagnostic template strategy")
    baseline = {}
    _validated_candidate(images, baseline, threshold)
    training, holdout = images[::2], images[1::2]
    candidate = edge_candidate(training)
    result = {"current_mask": baseline, "production_qualified": False, "threshold": threshold,
              "template_strategy": template_strategy}
    if candidate is None:
        result["experiment"] = {"status": "training_structure_insufficient"}
        return result, None
    template, mask, statistics = candidate
    if template_strategy == "training_medoid":
        template, selection = training_medoid(training, mask, threshold)
        statistics.update(selection)
        statistics["median_template_contrast_std"] = statistics["selected_contrast_std"]
        statistics["selected_contrast_std"] = float(template[mask > 0].std())
    train_scores = raw_scores(training, template, mask)
    test_scores = raw_scores(holdout, template, mask)
    train_support = sum(score >= threshold for score in train_scores)
    test_support = sum(score >= threshold for score in test_scores)
    supported = train_support >= 3 and test_support >= 3 and (
        test_support >= .80 * train_support * len(holdout) / len(training)
    )
    # Synthetic stress only; not an independent real-video negative qualification.
    negatives = [np.full_like(holdout[0], 70), np.roll(holdout[0], 12, axis=1)]
    if edge_similarity_diagnostic:
        def measurements(frames: list[np.ndarray]) -> list[dict]:
            return [geometry_edge_similarity.measure(
                template, cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), mask) for frame in frames]
        result["edge_similarity_diagnostic"] = {
            "metric": "bidirectional_soft_edge_orientation_coverage_v1",
            "acceptance_threshold": None, "production_qualified": False,
            "used_for_reference_selection": False,
            "training": measurements(training), "development_validation": measurements(holdout),
            "synthetic_flat_shift": measurements(negatives),
        }
    result["experiment"] = {
        **statistics, "status": "raw_ncc_supported" if supported else "raw_ncc_rejected",
        "training_similarity": summary(train_scores), "holdout_similarity": summary(test_scores),
        "training_accept_count": train_support, "holdout_accept_count": test_support,
        "synthetic_flat_shift_scores": raw_scores(negatives, template, mask),
        "real_negative_qualification": "not_performed",
        "geometric_inlier_qualification": "not_performed",
    }
    return result, (template, mask)


def replay_geometry(images: list[np.ndarray], layout: HudLayout,
                    profile: HudTemplateProfile) -> dict:
    """Exercise unchanged runtime matching; no identity, events or retained geometry.

    Crop handling mirrors runtime's matching-resolution metadata policy. It is
    not independent proof that the recorded game image was never cropped.
    Every frame needs fresh anchor evidence; no temporal retention is applied.
    """
    rows = []
    for index, image in enumerate(images):
        height, width = image.shape[:2]
        anchors, scores, _ = profile.detect_anchors(image, layout)
        calibration = layout.validate_calibration(
            width, height, detected_anchors=anchors,
            letterboxed=_detect_letterbox(image),
            crop_applied=False if layout.reference_resolution == (width, height) else None,
        )
        rows.append({
            "sample_index": index, "accepted_anchors": sorted(anchors),
            "scores": scores, "fresh_geometry_success": calibration.calibrated,
            "reasons": list(calibration.reasons),
            "median_position_error_norm": calibration.median_position_error_norm,
            "median_size_relative_error": calibration.median_size_relative_error,
        })
    return {
        "frames": rows, "sample_count": len(rows),
        "fresh_geometry_success_count": sum(row["fresh_geometry_success"] for row in rows),
        "matcher": "unchanged_runtime_masked_pixel_ncc",
        "temporal_geometry_retention": False, "production_qualified": False,
        "independent_capture_crop_qualification": "not_performed",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--source-sha256", required=True)
    parser.add_argument("--layout", type=Path, required=True)
    parser.add_argument("--sampling-window", type=float, nargs=2, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--template-strategy", choices=("median", "training_medoid"),
                        default="median")
    parser.add_argument("--edge-similarity-diagnostic", action="store_true")
    parser.add_argument("--cache-dir", type=Path, default=Path("outputs/e2e_cache/probe"))
    args = parser.parse_args()
    output = args.output.resolve()
    _check_output_privacy(output)
    if output.exists():
        raise FileExistsError("diagnostic output must be a new ignored directory")
    root = Path(__file__).resolve().parents[2]
    provenance = git_identity(root)
    inputs = {
        "experiment_code": Path(__file__),
        "baseline_code": root / "src/valorant_ai_coach/hud/calibrate_temporal.py",
        "layout": args.layout,
        "template_config": args.layout.with_suffix(".templates.json"),
    }
    if args.edge_similarity_diagnostic:
        inputs["edge_metric_code"] = Path(geometry_edge_similarity.__file__)
    input_hashes = {name: sha256_file(path) for name, path in inputs.items()}
    before = sha256_file(args.video)
    if before != args.source_sha256:
        raise ValueError("source hash mismatch")
    layout = HudLayout.load(args.layout)
    profile = HudTemplateProfile.load(args.layout.with_suffix(".templates.json"))
    service = VideoService()
    fp, _ = decoder_fingerprints(service.ffprobe_path)
    video = CachedVideoService(service, args.cache_dir, before, fp)
    metadata = video.probe(args.video)
    times, bounds = sampling_times(metadata.duration_sec, 32, tuple(args.sampling_window))
    output.mkdir(parents=True)
    frames = video.extract_frames(args.video, times, output / "frames", metadata=metadata,
                                  max_frames=32, max_dimension=None)
    if len(frames) != 32:
        raise ValueError("incomplete diagnostic sampling")
    validate_review_pts([frame.time_sec for frame in frames], metadata.duration_sec)
    if any(not bounds[0] <= frame.time_sec < bounds[1] for frame in frames):
        raise ValueError("actual frame outside development sampling window")
    images = [cv2.imdecode(np.frombuffer(frame.path.read_bytes(), np.uint8), cv2.IMREAD_COLOR)
              for frame in frames]
    if any(image is None or image.shape[:2] != (metadata.height, metadata.width)
           for image in images) or layout.reference_resolution != (metadata.width, metadata.height):
        raise ValueError("diagnostic geometry input resolution mismatch")
    anchors = {}
    replay_specs = {}
    for name in ANCHORS:
        x1, y1, x2, y2 = layout.normalized_roi(name).pixel_bounds(metadata.width, metadata.height)
        spec = profile.raw.get("anchors", {}).get(name, {})
        threshold = float(spec.get("threshold", .90))
        if not math.isfinite(threshold) or not 0 <= threshold <= 1:
            raise ValueError("invalid existing anchor threshold")
        row, candidate = compare([image[y1:y2, x1:x2] for image in images], max(.90, threshold),
                                 template_strategy=args.template_strategy,
                                 edge_similarity_diagnostic=args.edge_similarity_diagnostic)
        if candidate is not None:
            for suffix, pixels in zip(("template", "mask"), candidate, strict=True):
                path = output / f"{name}.{suffix}.png"
                ok, encoded = cv2.imencode(".png", pixels)
                if not ok:
                    raise ValueError("cannot encode diagnostic asset")
                path.write_bytes(encoded.tobytes())
                row[f"{suffix}_sha256"] = sha256_file(path)
            replay_specs[name] = {
                "template": f"{name}.template.png", "mask": f"{name}.mask.png",
                "threshold": max(.90, threshold), "search_region": spec.get("search_region"),
            }
        anchors[name] = row
    # In-memory experiment only: deliberately never write a runtime profile JSON.
    replay_profile = HudTemplateProfile(output / "not_exported.templates.json", {
        "schema_version": "1.0", "anchors": replay_specs, "signals": {}, "readers": {},
    })
    geometry_replay = replay_geometry(images, layout, replay_profile)
    negative_inputs = {
        "flat_frame": np.full_like(images[1], 70),
        "large_horizontal_wrap_shift": np.roll(images[1], metadata.width // 5, axis=1),
    }
    negative_replay = {
        name: replay_geometry([image], layout, replay_profile)
        for name, image in negative_inputs.items()
    }
    if sha256_file(args.video) != before:
        raise ValueError("source changed during diagnostic experiment")
    if any(sha256_file(path) != input_hashes[name] for name, path in inputs.items()):
        raise ValueError("experiment code or configuration changed during processing")
    report = {
        "kind": "geometry_edge_experiment_not_profile", "source_sha256": before,
        "sampling_window_sec": list(bounds), "source_hash_verified_after_processing": True,
        "sample_count": 32, "training_indices": list(range(0, 32, 2)),
        "holdout_indices": list(range(1, 32, 2)), "production_qualified": False,
        "identity_assets_generated": False, "anchors": anchors,
        "runtime_geometry_replay": geometry_replay,
        "synthetic_geometry_negative_controls": negative_replay,
        "git_identity": provenance, "input_sha256": input_hashes,
        "input_hashes_verified_after_processing": True,
        "experiment_policy": {
            "canny_thresholds": [60, 150], "edge_persistence_min": .65,
            "orientation_resultant_min": .90, "crop_border_excluded_px": 2,
            "mask_dilation_px": 3, "minimum_mask_population": 64,
            "minimum_training_frames": 8, "minimum_contrast_std": 1,
            "matcher": "unchanged_raw_masked_pixel_ncc", "minimum_ncc": .90,
            "minimum_training_support": 3, "minimum_holdout_support": 3,
            "holdout_expected_support_ratio": .80,
            "template_strategy": args.template_strategy,
            "template_selection_uses_holdout": False,
            "development_validation_reuse_is_not_independent_qualification": True,
            "edge_similarity_diagnostic_enabled": args.edge_similarity_diagnostic,
            "edge_similarity_acceptance_threshold": None,
        },
        "frames": [{"source_frame_pts": frame.time_sec, "sha256": sha256_file(frame.path)}
                   for frame in frames],
    }
    (output / "diagnostics.json").write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": "diagnostic_complete", "production_qualified": False}))


if __name__ == "__main__":
    main()
