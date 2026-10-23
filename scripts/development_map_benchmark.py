"""PRIVATE bounded DEVELOPMENT replay comparison and prediction-blind review packet.

No video decoding, uploads, model fitting or Production qualification. Split
attestations must be checked against the private intake before using this tool.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
from collections import Counter
from fractions import Fraction
from pathlib import Path
from typing import Any

import cv2

from valorant_ai_coach.video.geometry import normalized_roi_bounds
from valorant_ai_coach.visual.development_map import DevelopmentMapTimeline
from valorant_ai_coach.visual.development_path_viewer import write_candidate_path_html
from valorant_ai_coach.visual.development_position_review import (
    compare_position_review,
    fixed_review_indices,
    observation_fingerprint,
)
from valorant_ai_coach.visual.development_review_boundary import compare_review_boundaries
from valorant_ai_coach.visual.development_trajectory import analyze_candidate_path
from valorant_ai_coach.visual.development_view_review import compare_view_review


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _prepare_output(output: Path) -> None:
    if any((p/".git").exists() for p in [output.resolve(), *output.resolve().parents]):
        raise ValueError("Private output must be outside every Git checkout")
    if output.exists() and any(output.iterdir()):
        raise ValueError("Use a fresh private directory; frozen evidence must not be overwritten")
    output.mkdir(parents=True, exist_ok=True)


def build(manifest_path: Path, output: Path) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (manifest.get("source_split") != "DEVELOPMENT"
            or manifest.get("exposure") != "DEVELOPMENT"
            or manifest.get("qualification") != "development_only"):
        raise ValueError("Explicit DEVELOPMENT source/exposure declaration required")
    frames = manifest["observations"]
    if not isinstance(frames, list) or not 1 <= len(frames) <= 5000:
        raise ValueError("Bounded explicitly acquired observations required")
    time_base = Fraction(manifest["native_time_base"])
    if time_base <= 0:
        raise ValueError("Positive native time base required")
    for frame in frames:
        tick = frame["pts_tick"]
        if (not isinstance(tick, int) or isinstance(tick, bool) or tick < 0
                or not isinstance(frame["time_sec"], (int, float))
                or isinstance(frame["time_sec"], bool)
                or not math.isfinite(frame["time_sec"])
                or abs(frame["time_sec"]-float(tick*time_base)) > 1e-9
                or _sha(Path(frame["image_path"])) != frame["image_sha256"]):
            raise ValueError("Source tick/time or acquired image hash mismatch")
    _prepare_output(output)
    trials = {}
    profiles = {}
    # Review ordinals depend only on acquisition count, never successful predictions.
    review_indices = fixed_review_indices(len(frames))
    for name in ("baseline", "variant"):
        profile_path = Path(manifest[f"{name}_profile_path"])
        profiles[name] = _sha(profile_path)
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
        pipeline = DevelopmentMapTimeline(profile, inspect_reference_appearances=True)
        definition = pipeline.timeline.definition
        assert definition is not None and definition.reference_asset is not None
        bbox = definition.data["coordinate_system"]["reference_map_mask_bbox_within_roi_px"]
        reference_sha = _sha(definition.reference_asset)
        records: list[dict[str, Any]] = []
        previews: list[bytes | None] = []
        elapsed = 0.0
        for frame in frames:
            image_path = Path(frame["image_path"])
            image = cv2.imread(str(image_path))
            if image is None:
                raise ValueError("Acquired frame unavailable")
            started = time.perf_counter()
            record = pipeline.observe(
                image, frame["time_sec"], frame["frame_index"], view=frame["view"],
                evidence_kind=manifest["view_evidence_kind"], source_id=manifest["source_id"],
                acquisition_id=manifest["acquisition_id"],
                source_sha256=manifest.get("source_sha256"),
            )
            elapsed += time.perf_counter()-started
            if _sha(image_path) != frame["image_sha256"]:
                raise ValueError("Input changed during comparison")
            record["acquired_frame_sha256"] = frame["image_sha256"]
            record["acquired_frame_path"] = str(image_path.resolve())
            bounds = normalized_roi_bounds(profile["rois"]["minimap"],
                                           image.shape[1], image.shape[0])
            assert bounds is not None
            record["benchmark_geometry"] = {
                "roi_size_px": [bounds[2]-bounds[0], bounds[3]-bounds[1]],
                "reference_bbox": bbox, "reference_sha256": reference_sha,
            }
            records.append(record)
            h, w = image.shape[:2]
            ok, jpg = cv2.imencode(".jpg", cv2.resize(image, (min(960, w),
                                    round(h*min(1, 960/w)))))
            if not ok:
                raise ValueError("Source preview unavailable")
            previews.append(jpg.tobytes())
        definition = pipeline.timeline.definition
        assert definition is not None
        assert definition.reference_asset is not None
        bbox = definition.data["coordinate_system"]["reference_map_mask_bbox_within_roi_px"]
        trajectory = analyze_candidate_path(records, reference_size_px=(bbox[2]-bbox[0],
                                                                      bbox[3]-bbox[1]))
        write_candidate_path_html(
            output/f"{name}_path_PRIVATE.html", trajectory,
            reference_png=definition.reference_asset.read_bytes(), reference_bbox=tuple(bbox),
            zones=definition.data["zones"], source_frames_jpeg=previews)
        summaries = {
            "observations": len(records),
            "roi_candidates": sum(r["appearance"]["x_roi_norm"] is not None for r in records),
            "map_candidates": sum(r["map_position_norm"] is not None for r in records),
            "named_zones": sum(r["zone_resolution"]["zone_id"] is not None for r in records),
            "calibration_acceptances": sum(r["calibration"]["status"] == "ok" for r in records),
            "position_unknown_reasons": dict(Counter(r["appearance"]["reason"] for r in records)),
            "ownership_unknown_reasons": dict(Counter(reason for r in records
                for reason in r["ownership_evidence"]["reasons"])),
            "screen_contexts": dict(Counter(r["ownership_evidence"]["view_candidate"]
                                             for r in records)),
            "independent_context_blocks": sum(r["ownership_evidence"][
                "block_position_candidate"] for r in records),
            "processing_sec": elapsed,
            "auto_ownership_unknown": sum(r["ownership"]["identity"] == "UNKNOWN"
                                          for r in records),
            "formal_outputs": sum(r["formal_self_position_fact"] is not None for r in records)
                + sum("actor" in event or "type" in event
                      for r in records for event in r["development_events"]),
        }
        if (summaries["auto_ownership_unknown"] != len(records)
                or summaries["formal_outputs"] != 0):
            raise ValueError(
                "Unqualified replay must not assign ownership or emit Production output")
        trials[name] = {"records": records, "trajectory": trajectory, "summary": summaries}
        (output/f"{name}_observations_PRIVATE.json").write_text(json.dumps(
            trials[name], indent=2, allow_nan=False), encoding="utf-8")
        if name == "variant":
            packet = []
            for index in review_indices:
                frame, record = frames[index], records[index]
                review = {k: record[k] for k in ("source_id", "acquisition_id", "time_sec",
                                                "frame_index", "map_id", "geometry_version")}
                review.update(
                    status="pending", label_origin="source_image_review", not_used_for_fitting=True,
                    prediction_sha256=observation_fingerprint(record),
                    frame_sha256=frame["image_sha256"],
                    reference_sha256=_sha(definition.reference_asset),
                    role="UNKNOWN", center_roi_px=None, landmark_roi_px=None,
                    landmark_reference_px=None, source_tolerance_px=None,
                    reference_tolerance_px=None,
                    raw_image_path=frame["image_path"],
                )
                packet.append(review)
            (output/"review_packet_PRIVATE.json").write_text(json.dumps(
                {"selection": "first/middle/last acquisition ordinal before acceptance",
                 "prediction_positions_prefilled": False, "reviews": packet}, indent=2),
                encoding="utf-8")
    report = {"qualification": "development_only", "ownership": "UNKNOWN",
              "independent_qualification": False, "source_id": manifest["source_id"],
              "acquisition_id": manifest["acquisition_id"], "manifest_sha256": _sha(manifest_path),
              "profile_sha256": profiles,
              "benchmark_script_sha256": _sha(Path(__file__)),
              "summary": {k: v["summary"] for k, v in trials.items()},
              "implementation_sha256": {p.name: _sha(p) for p in Path(__file__).parents[1].joinpath(
                  "src/valorant_ai_coach/visual").glob("development_*.py")}}
    (output/"comparison_PRIVATE.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def apply_reviews(observations: Path, reviews_path: Path, output: Path) -> dict[str, Any]:
    """Attach a scoped response to saved predictions without rerunning recognition."""
    from valorant_ai_coach.visual.development_map import development_registry

    saved = json.loads(observations.read_text(encoding="utf-8"))
    records = saved["records"]
    if not 1 <= len(records) <= 5000:
        raise ValueError("Bounded saved observations required")
    responses = json.loads(reviews_path.read_text(encoding="utf-8"))
    reviews = responses.get("reviews", [])
    view_reviews = responses.get("view_reviews", [])
    if not isinstance(view_reviews, list) or len(view_reviews) > len(records):
        raise ValueError("View review count must be bounded by acquired observations")
    definition = development_registry(records[0]["map_id"]).load(records[0]["map_id"])
    if not isinstance(reviews, list) or len(reviews) > len(records):
        raise ValueError("Review count must be bounded by acquired observations")
    compared = []
    seen = set()
    for review in reviews:
        if review.get("status") == "pending":
            continue
        matches = [r for r in records if all(r.get(k) == review.get(k) for k in (
            "source_id", "acquisition_id", "time_sec", "frame_index", "map_id",
            "geometry_version"))]
        if len(matches) != 1 or review.get("prediction_sha256") in seen:
            raise ValueError("Review must identify a unique frozen observation")
        record = matches[0]
        seen.add(review["prediction_sha256"])
        geometry = record["benchmark_geometry"]
        if _sha(Path(record["acquired_frame_path"])) != record["acquired_frame_sha256"]:
            raise ValueError("Reviewed image changed after prediction freeze")
        kwargs = {"zones": definition.data["zones"]} if review.get(
            "include_boundary_comparison") is True else {}
        compare = compare_review_boundaries if kwargs else compare_position_review
        result = compare(
            record, review, frame_sha256=record["acquired_frame_sha256"],
            reference_sha256=geometry["reference_sha256"],
            roi_size_px=tuple(geometry["roi_size_px"]),
            reference_bbox=tuple(geometry["reference_bbox"]), **kwargs,
        )
        record["position_review"] = result
        compared.append(result)
    view_seen = set()
    for review in view_reviews:
        if review.get("status") == "pending":
            continue
        matches = [r for r in records if all(r.get(k) == review.get(k) for k in (
            "source_id", "acquisition_id", "time_sec", "frame_index", "map_id",
            "geometry_version"))]
        if len(matches) != 1 or review.get("prediction_sha256") in view_seen:
            raise ValueError("View review must identify a unique frozen observation")
        record = matches[0]
        view_seen.add(review["prediction_sha256"])
        if _sha(Path(record["acquired_frame_path"])) != record["acquired_frame_sha256"]:
            raise ValueError("Reviewed view image changed after prediction freeze")
        record["view_review"] = compare_view_review(
            record, review, frame_sha256=record["acquired_frame_sha256"])
    assert definition.reference_asset is not None
    bbox = records[0]["benchmark_geometry"]["reference_bbox"]
    if any(r["geometry_version"] != definition.geometry_version
           or r["map_id"] != definition.map_id
           or r["benchmark_geometry"]["reference_bbox"] != bbox
           or r["benchmark_geometry"]["reference_sha256"] != _sha(definition.reference_asset)
           for r in records):
        raise ValueError("Saved reference geometry changed or mixed")
    trajectory = analyze_candidate_path(
        records, reference_size_px=(bbox[2]-bbox[0], bbox[3]-bbox[1]))
    previews: list[bytes | None] = []
    for record in records:
        path = Path(record["acquired_frame_path"])
        if _sha(path) != record["acquired_frame_sha256"]:
            raise ValueError("Saved acquired image changed")
        image = cv2.imread(str(path))
        if image is None:
            raise ValueError("Saved acquired image unavailable")
        h, w = image.shape[:2]
        ok, data = cv2.imencode(".jpg", cv2.resize(image, (min(960, w), round(h*min(1, 960/w)))))
        if not ok:
            raise ValueError("Source preview unavailable")
        previews.append(data.tobytes())
    _prepare_output(output)
    result = {"qualification": "development_only", "ownership": "UNKNOWN",
              "comparisons": compared,
              "view_comparisons": [r["view_review"] for r in records if r.get("view_review")],
              "records": records, "trajectory": trajectory,
              "source_predictions_sha256": _sha(observations),
              "reviews_file_sha256": _sha(reviews_path),
              "qualification_or_error_bound_established": False}
    (output/"reviewed_observations_PRIVATE.json").write_text(json.dumps(
        result, indent=2, allow_nan=False), encoding="utf-8")
    write_candidate_path_html(output/"reviewed_path_PRIVATE.html", trajectory,
                              reference_png=definition.reference_asset.read_bytes(),
                              reference_bbox=tuple(bbox), zones=definition.data["zones"],
                              source_frames_jpeg=previews)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--manifest", type=Path)
    mode.add_argument("--observations", type=Path)
    parser.add_argument("--reviews", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    cv2.setNumThreads(1)
    if args.manifest is not None:
        build(args.manifest, args.output)
    elif args.reviews is not None:
        apply_reviews(args.observations, args.reviews, args.output)
    else:
        parser.error("--observations requires --reviews")
    print("Private development comparison/review packet ready; no ownership qualification.")


if __name__ == "__main__":
    main()
