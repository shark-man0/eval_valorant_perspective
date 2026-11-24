"""Recheck unfilled seconds of an exact development Map replay."""

from __future__ import annotations

import argparse
import math
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
from recording_portraits import RecordingPortraitBank, RecordingPortraitTracker
from runtime import DenseMarkerCNN, LearnedRecorderTracker, load_models

from valorant_ai_coach.temporal.evidence import digest, freeze_native_sample, is_sha, native_time
from valorant_ai_coach.temporal.map_direct_recorder import (
    DensePortraitSearch,
    DirectRecorderTracker,
    RecorderUUID,
    measured_direct_view,
)
from valorant_ai_coach.temporal.map_exact_alignment_cache import ExactAlignmentCache
from valorant_ai_coach.temporal.map_path_quality import measure_path_quality
from valorant_ai_coach.temporal.map_recorder_export import _load_native_image, _pixels_match
from valorant_ai_coach.temporal.map_recorder_knowledge import KnowledgeRecorderMap
from valorant_ai_coach.temporal.map_recorder_path import (
    ReferenceZones,
    build_recorder_paths,
    join_recorder_seconds,
    measure_operable_coverage,
    measured_native_edges,
    project_recorder_witness,
)
from valorant_ai_coach.temporal.map_recording_anchors import RecordingMapAnchors
from valorant_ai_coach.temporal.map_reference_support import (
    atlas_distances_for,
    clearly_outside_atlas,
)
from valorant_ai_coach.temporal.map_timeline_report import load_map_timeline
from valorant_ai_coach.temporal.public_map_pixels import CONTRAST_ALIGNMENT, PublicMapPixels
from valorant_ai_coach.temporal.replay import SourcePolicy, file_sha, read_json, write_private


def _points(report):
    return {p["sample"]["sample_sha256"]: p for segment in report["segments"] for p in segment}


def _load_companion(companion, source, timeline_path, timeline, *, manifest_sha, baseline):
    if companion is None and source is None:
        return {}, {}, 0
    if companion is None or source is None:
        raise ValueError("Companion report and its original replay must be supplied together")
    load_map_timeline(companion, timeline_path, timeline)
    load_map_timeline(source, timeline_path, timeline)
    report, parent = read_json(companion), read_json(source)
    if (report.get("reference_report_sha256") != file_sha(source)
            or parent.get("frame_manifest_sha256") != manifest_sha):
        raise ValueError("Companion report does not use the same native inputs")
    points = _points(report)
    incumbent = _points(parent)
    if any(points.get(key) != point for key, point in incumbent.items()):
        raise ValueError("Companion report must preserve every original observation")
    if parent["recording_agent_uuid_binding"] != baseline["recording_agent_uuid_binding"]:
        raise ValueError("Companion report belongs to a different recorder binding")
    if any(parent[key] != baseline[key]
           for key in ("map_catalog_fingerprint", "zone_catalog_sha256", "recording_map_uuid")):
        raise ValueError("Companion report uses different reference geometry")
    additions = {key: points[key] for key in points.keys() - incumbent.keys()}
    if any(point["kind"] != "selected" or point["support_count"] < 2
           for point in additions.values()):
        raise ValueError("Companion additions require at least two native observations")
    models = report.get("companion_candidate_model_receipts", {})
    if models == {} and additions:
        return {}, {}, len(additions)
    if models != {} and (not isinstance(models, dict) or set(models) != {"marker", "portrait"}
                   or not all(is_sha(value) for value in models.values())
                   or models["portrait"] != parent["experimental_model_receipts"]["portrait"]):
        raise ValueError("Companion model evidence does not match the reference replay")
    return additions, models, 0


def recover(
    *, bundle_path: Path, frame_manifest: Path, policy_path: Path, map_catalog: Path,
    layout: Path, asset_cache: Path, zones_path: Path, models_directory: Path, threshold: float,
    primary_report: Path, reference_report: Path, companion_report: Path | None = None,
    companion_baseline: Path | None = None,
    exact_alignment_cache: Path | None = None,
    strict_recovery_tracking: bool = False,
) -> dict[str, Any]:
    timeline = read_json(bundle_path)
    primary = read_json(primary_report)
    reference = read_json(reference_report)
    if primary.get("reference_report_sha256") != file_sha(reference_report):
        raise ValueError("Primary report must be composed with the provided reference replay")
    for report_path in (primary_report, reference_report):
        load_map_timeline(report_path, bundle_path, timeline)
    manifest_sha = file_sha(frame_manifest)
    if (reference["frame_manifest_sha256"] != manifest_sha
            or reference["zone_catalog_sha256"] != file_sha(zones_path)):
        raise ValueError("Matching Map frame and Zone receipts required")
    source = timeline["source"]["source_sha256"]
    policy = SourcePolicy(read_json(policy_path))
    if source not in policy.allowed or policy.allowed[source]["split"] != "DEVELOPMENT":
        raise ValueError("Catalog-admitted DEVELOPMENT recording required")
    binding = reference["recording_agent_uuid_binding"]
    map_id = reference["recording_map_uuid"]
    if binding is not None and (binding.get("qualified") is not False
                                or binding["source_sha256"] != source):
        raise ValueError("Unqualified recorder Agent binding required")
    if binding is None or map_id is None:
        if binding is None and primary["segments"]:
            raise ValueError("Unbound recorder cannot have measured Map segments")
        operable = set(reference["comparison_evidence"]["operable_sample_refs"])
        return {
            **primary, "primary_report_sha256": file_sha(primary_report), "recovery_counts": {},
            "recovery_status": "recorder_unbound" if binding is None else "map_unbound",
            "path_quality": measure_path_quality(primary, timeline["seconds"],
                                                 primary["second_rows"], operable),
        }
    knowledge = KnowledgeRecorderMap.load(asset_cache, map_catalog)
    identity = RecorderUUID(
        binding["source_sha256"], binding["uuid"], tuple(binding["evidence_samples"]),
    )
    target = knowledge._uuids.index(identity.uuid)
    classic = DirectRecorderTracker(
        DensePortraitSearch(knowledge.minimap_portraits, augment=True, fast_search=True),
        identity, knowledge, compare_centers=True,
        fallback_search=DensePortraitSearch(
            knowledge.minimap_portraits, augment=False, rim_guided=True,
        ),
    )
    receipt = file_sha(models_directory / "training_summary_PRIVATE.json")
    if not math.isfinite(threshold) or not 0 < threshold <= 1:
        raise ValueError("Validation-calibrated marker threshold required")
    weights = load_models(models_directory, knowledge, receipt_sha256=receipt)
    learned = LearnedRecorderTracker(
        DenseMarkerCNN(weights["marker"], threshold), identity, knowledge,
        portrait_model=weights["portrait"], refine_center=True,
    )
    bank = RecordingPortraitBank()
    rescue = RecordingPortraitTracker(bank, identity, knowledge)
    geometry = RecordingMapAnchors()
    projector = PublicMapPixels(map_catalog, layout, verified_references=knowledge.map_references)
    exact_fits = ExactAlignmentCache(projector, exact_alignment_cache)
    assets = projector.bindings["asset_sha256s"]
    void_distances = atlas_distances_for(
        map_catalog, map_id, assets[map_id], knowledge.map_references,
    )
    companion, companion_models, untracked_companion_count = _load_companion(
        companion_report, companion_baseline, bundle_path, timeline, manifest_sha=manifest_sha,
        baseline=reference,
    )
    zones = [ReferenceZones(r["map_id"], r["reference_sha256"], r["polygons"])
             for r in read_json(zones_path)["maps"]]
    callouts = KnowledgeRecorderMap.callouts(asset_cache, map_catalog)
    samples = {}
    for row in read_json(frame_manifest)["frames"]:
        sample = freeze_native_sample(row["sample"])
        key = sample["sample_sha256"]
        if key in samples or sample != timeline["native_frames"].get(key, {}).get("sample"):
            raise ValueError("Unique exact timeline sample required")
        policy.admit(sample)
        samples[key] = (sample, Path(row["path"]))
    known = _points(primary)
    rows = timeline["seconds"]
    operable = set(reference["comparison_evidence"]["operable_sample_refs"])
    if not operable <= samples.keys():
        raise ValueError("Missing native frames for current view evidence")
    vacancies = {
        key for row, attached in zip(rows, primary["second_rows"], strict=True)
        if not attached["recorder_map_observations"] and set(row["sample_refs"]) <= operable
        for key in row["sample_refs"]
    }
    native = timeline["native_frames"]
    observations = timeline["observations"]
    counts: Counter[str] = Counter()
    if untracked_companion_count:
        counts["companion_model_evidence_missing"] = untracked_companion_count
    portrait_reference_digest = digest(knowledge.provenance)
    recovered = {}
    recovery_evidence = {}
    seed_evidence = {}
    conflicting_samples = set()
    last_offer = None
    order = sorted(samples, key=lambda key: native_time(samples[key][0]))
    for key in order:
        sample, path = samples[key]
        at = native_time(sample)
        point = known.get(key)
        offer = (key in operable and point is not None and point["kind"] == "selected"
                 and not clearly_outside_atlas(void_distances, point["map_reference_px"])
                 and (last_offer is None or at - last_offer >= 8))
        if not offer and key not in vacancies:
            rescue.previous = None
            continue
        frame = native[key]
        current_observations = [observations[ref] for ref in frame["observation_ids"]]
        camera = measured_direct_view(frame, current_observations)
        if camera is None:
            rescue.previous = None
            continue
        image = _load_native_image(sample, path)
        if not _pixels_match(image, sample):
            raise ValueError("Exact native Map pixels required")
        bounds = projector.layout.normalized_roi("minimap_normal").pixel_bounds(
            image.shape[1], image.shape[0],
        )
        if offer:
            last_offer = at
            raw = exact_fits.inspect(image, sample)
            geometry.observe(image, sample, raw, map_id, (0., 0.), recover=False)
            for selector in (classic, learned):
                selector.previous = None
                pool, seed = selector._observe_measured(image, bounds, sample, frame, camera)
                if not seed["support_count"]:
                    continue
                center = tuple(seed["support_center_frame_px"])
                measured = project_recorder_witness(
                    image, sample, pool, seed, raw, reference_sha256s=assets,
                )
                if (measured is None or point is None or measured["map_id"] != point["map_id"]
                        or measured["reference_sha256"] != point["reference_sha256"]
                        or math.dist(measured["map_reference_px"], point["map_reference_px"]) > 3):
                    continue
                scores = knowledge._portrait_scores(image, center)
                if scores is not None and scores[target] >= .76 and (
                    scores[target] - np.delete(scores, target).max() >= .045
                ):
                    bank.visit(sample, bounds)
                    bank.remember(image, sample, center)
                    seed_evidence[key] = {
                        "method": "learned" if selector is learned else "public_reference",
                        "model_receipt_sha256": receipt if selector is learned else None,
                        "portrait_reference_sha256": portrait_reference_digest,
                    }
                    counts["exemplar_offers"] += 1
                    break
            rescue.previous = None
            continue
        pool, result = rescue._observe_measured(image, bounds, sample, frame, camera)
        counts[result["selection_reason"]] += 1
        if result["selection_status"] != "RESEARCH_SELECTED":
            continue
        classic.previous = None
        _, direct = classic._observe_measured(image, bounds, sample, frame, camera)
        center = result["support_center_frame_px"]
        conflicting_center = (
            direct["support_count"] and math.dist(direct["support_center_frame_px"], center) > 3
        )
        if conflicting_center or direct["selection_reason"] not in (
            "direct_portrait_or_rim_unresolved", "direct_portrait_needs_adjacent_observation",
        ):
            counts["reference_selector_veto"] += 1
            if strict_recovery_tracking:
                rescue.discard_projection()
            continue
        raw = exact_fits.inspect(image, sample)
        if not raw["map_name_candidates"]:
            raw = geometry.observe(image, sample, raw, map_id, tuple(center))
        if not raw["map_name_candidates"]:
            raw = projector.recover_contrast(image, raw, map_id, tuple(center))
        if not raw["map_name_candidates"] or raw["map_name_candidates"][0]["map_id"] != map_id:
            counts["registration_unavailable"] += 1
            if strict_recovery_tracking:
                rescue.discard_projection()
            continue
        measured = project_recorder_witness(
            image, sample, pool, result, raw, reference_sha256s=assets,
        )
        if measured is None:
            if strict_recovery_tracking:
                rescue.discard_projection()
            continue
        if clearly_outside_atlas(void_distances, measured["map_reference_px"]):
            counts["recovered_point_outside_atlas"] += 1
            if strict_recovery_tracking:
                rescue.discard_projection()
            continue
        alternate = companion.get(key)
        if (strict_recovery_tracking and alternate is not None
                and alternate["map_id"] == measured["map_id"]
                and alternate["reference_sha256"] == measured["reference_sha256"]
                and not clearly_outside_atlas(void_distances, alternate["map_reference_px"])
                and math.dist(alternate["map_reference_px"], measured["map_reference_px"]) > 3):
            conflicting_samples.add(key)
            counts["cross_detector_conflict"] += 1
            rescue.discard_projection()
            continue
        recovered[key] = measured
        recovery_evidence[key] = {
            "method": "recording_portraits", "current_view": camera,
            "portrait_anchors": {
                anchor: seed_evidence[anchor] for anchor in measured["portrait_anchor_sample_refs"]
            },
        }
        if raw.get("alignment_recovery") == CONTRAST_ALIGNMENT:
            counts["contrast_recovered"] += 1
    for key, point in companion.items():
        if key in known or key not in operable or key in conflicting_samples:
            continue
        if point["map_id"] != map_id or point["reference_sha256"] != assets[map_id]:
            continue
        if clearly_outside_atlas(void_distances, point["map_reference_px"]):
            counts["companion_point_outside_atlas"] += 1
            continue
        if key not in recovered:
            recovered[key] = point
            recovery_evidence[key] = {
                "method": "marker_companion", "heads": companion_models,
                "current_view": "reference_operability_evidence",
            }
            counts["companion_addition"] += 1
        elif math.dist(point["map_reference_px"], recovered[key]["map_reference_px"]) > 3:
            del recovered[key]
            counts["cross_detector_conflict"] += 1
    added = build_recorder_paths(
        (recovered.get(key) for key in order), zones=zones, callouts=callouts,
    )
    candidate_evidence = {
        key: {**recovery_evidence[key], "position_sha256": digest(point)}
        for key, point in _points(added).items()
    }
    path = {
        **added, "segments": sorted(
            primary["segments"] + added["segments"], key=lambda seg: native_time(seg[0]["sample"]),
        ),
        "corroborated_native_edges": primary.get("corroborated_native_edges", []),
    }
    if not measured_native_edges(primary) <= measured_native_edges(path):
        raise ValueError("Missing an existing measured trajectory edge")
    seconds = join_recorder_seconds(path, timeline)
    if exact_alignment_cache is not None:
        print(f"Exact Map alignment cache: {exact_fits.hits} hits, {exact_fits.misses} misses")
    return {
        **path, "timeline_sha256": file_sha(bundle_path), "frame_manifest_sha256": manifest_sha,
        "primary_report_sha256": file_sha(primary_report),
        "zone_catalog_sha256": file_sha(zones_path),
        "reference_report_sha256": file_sha(reference_report),
        "companion_report_sha256": file_sha(companion_report) if companion_report else None,
        "recovery_model_receipt_sha256": receipt,
        "recovery_candidate_evidence": candidate_evidence,
        "second_rows": seconds, "recovery_counts": dict(counts),
        "operable_coverage": measure_operable_coverage(path, rows, seconds, operable),
        "path_quality": measure_path_quality(path, rows, seconds, operable),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in (
        "bundle-path", "frame-manifest", "policy-path", "map-catalog", "layout", "asset-cache",
        "zones-path", "models-directory", "primary-report", "reference-report", "output",
    ):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--threshold", type=float, required=True)
    parser.add_argument("--companion-report", type=Path)
    parser.add_argument("--companion-baseline", type=Path)
    parser.add_argument("--exact-alignment-cache", type=Path)
    parser.add_argument("--strict-recovery-tracking", action="store_true")
    options = vars(parser.parse_args())
    output = options.pop("output")
    write_private(output, recover(**options))


if __name__ == "__main__":
    main()
