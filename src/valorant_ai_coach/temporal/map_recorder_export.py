"""Export experimental recorder paths from a private common timeline and native images."""

from __future__ import annotations

import argparse
import hashlib
from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from numpy.typing import NDArray

from .application import VERSION as APPLICATION_VERSION
from .evidence import digest, freeze_native_sample, is_sha, native_time
from .map_direct_recorder import (
    ADJACENT_PORTRAIT_REASON,
    DensePortraitSearch,
    DirectRecorderTracker,
    RecorderUUID,
    corroborate_direct_selection,
    measured_direct_view,
)
from .map_exact_alignment_cache import ExactAlignmentCache
from .map_path_quality import measure_path_quality
from .map_portrait_rim import Reference
from .map_recorder_knowledge import KnowledgeRecorderMap
from .map_recorder_path import (
    ReferenceZones,
    build_recorder_paths,
    join_recorder_seconds,
    measure_operable_coverage,
    project_recorder_witness,
)
from .map_recorder_selection import MapRecorderSelector
from .map_recording_alignment import NativeMapFlowAlignment, RecordingMapAlignment
from .map_recording_anchors import EVIDENCE as ANCHOR_ALIGNMENT
from .map_recording_anchors import RecordingMapAnchors
from .map_reference_support import atlas_distances_for, clearly_outside_atlas
from .public_map_pixels import CONTRAST_ALIGNMENT, PublicMapPixels
from .replay import SourcePolicy, file_sha, read_json, write_private


def _agent_references(catalog: Path) -> tuple[list[Reference], dict[str, str]]:
    references: list[Reference] = []
    hashes: dict[str, str] = {}
    root = catalog.parent.resolve()
    for agent in read_json(catalog).get("characters", []):
        relative = agent.get("minimap_portrait")
        if relative is None:
            continue
        path = (root / relative).resolve()
        if root not in path.parents or not path.is_file():
            raise ValueError("Readable minimap portrait within the catalog required")
        data = path.read_bytes()
        image = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_GRAYSCALE)
        if image is None:
            raise ValueError("Invalid minimap portrait")
        references.append((agent["name"], np.asarray(image, dtype=np.uint8)))
        hashes[agent["name"]] = hashlib.sha256(data).hexdigest()
    if len(hashes) != len(references):
        raise ValueError("Unique portrait Agent names required")
    return references, hashes


def _load_native_image(sample: dict[str, Any], path: Path) -> NDArray[np.uint8]:
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != sample["acquired_frame_sha256"]:
        raise ValueError("Exact native image bytes required")
    decoded = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if decoded is None:
        raise ValueError("Unreadable native image")
    return np.asarray(decoded, dtype=np.uint8)


def _pixels_match(image: NDArray[np.uint8], sample: dict[str, Any]) -> bool:
    if list(image.shape[:2][::-1]) != sample["frame_size_px"]:
        return False
    return hashlib.sha256(image.tobytes()).hexdigest() == str(sample["native_pixel_sha256"])


def _bind_recorder_uuid(
    knowledge: KnowledgeRecorderMap, native: dict[str, Any], observations: dict[str, Any],
    inputs: dict[str, tuple[dict[str, Any], Path]],
) -> RecorderUUID | None:
    candidates = []
    for key, frame in native.items():
        packet = inputs.get(key)
        rows = [observations[i] for i in frame["observation_ids"]]
        if packet and measured_direct_view(frame, rows):
            candidates.append(packet)
    votes = []
    if candidates:
        candidates.sort(key=lambda packet: native_time(packet[0]))
        count = min(len(candidates), 32)
        for index in range(count):
            sample, path = candidates[len(candidates)*index//count]
            image = _load_native_image(sample, path)
            uid = knowledge._hud_uuid(image) if _pixels_match(image, sample) else None
            if uid:
                votes.append((sample, uid))
    return RecorderUUID.bind(votes)


def export_recorder_paths(
    *, bundle_path: Path, frame_manifest: Path, policy_path: Path, catalog: Path,
    layout: Path, output: Path, zones_path: Path | None = None,
    recover_supported_portraits: bool = False, knowledge_asset_cache: Path | None = None,
    recover_knowledge_track: bool = False, recover_map_alignment: bool = False,
    direct_detector: str | None = None, corroborate_direct_with_legacy: bool = False,
    recover_native_flow: bool = False, recover_adjacent_portrait: bool = False,
    direct_tracker_factory: Callable[
        [RecorderUUID, KnowledgeRecorderMap], DirectRecorderTracker
    ] | None = None,
    comparison_evidence: bool = False,
    registration: str = "reference",
    training_evidence: bool = False,
    path_quality: bool = False,
    experimental_model_receipts: dict[str, str] | None = None,
    exact_alignment_cache: Path | None = None,
    screen_atlas_void: bool = False,
) -> dict[str, Any]:
    """Use existing current observations and preserve their native IDs and acquisition gaps."""
    bundle = read_json(bundle_path)
    if bundle.get("version") != APPLICATION_VERSION or bundle.get("formal_outputs") != 0:
        raise ValueError("Unqualified application timeline required")
    policy = SourcePolicy(read_json(policy_path))
    refs, asset_hashes = _agent_references(catalog)
    if direct_detector not in (None, "external", "augmented", "fast", "cascade", "guided"):
        raise ValueError("Known direct Map detector required")
    recording_anchors = registration in ("recording-anchors", "recording-anchors-contrast")
    if (registration not in ("reference", "exact") and not recording_anchors) or (
        registration != "reference" and direct_detector != "guided"
    ):
        raise ValueError("Exact Map registration requires guided development replay")
    if (recover_knowledge_track or direct_detector) and not knowledge_asset_cache:
        raise ValueError("Knowledge asset cache required for native UUID tracking")
    knowledge = (KnowledgeRecorderMap.load(
        knowledge_asset_cache, catalog, recover_track=recover_knowledge_track,
    ) if knowledge_asset_cache else None)
    projector = PublicMapPixels(catalog, layout,
                                verified_references=knowledge.map_references if knowledge else ())
    tracker = MapRecorderSelector(refs, recover_supported_portraits=recover_supported_portraits)
    zones = [
        ReferenceZones(z["map_id"], z["reference_sha256"], z["polygons"])
        for z in read_json(zones_path)["maps"]
    ] if zones_path else []
    receipt = read_json(frame_manifest)
    inputs = {}
    for row in receipt["frames"]:
        sample = freeze_native_sample(row["sample"])
        policy.admit(sample)
        key = sample["sample_sha256"]
        if key in inputs:
            raise ValueError("Repeated exact native image")
        inputs[key] = (sample, Path(row["path"]))
    native = bundle["native_frames"]
    if not inputs.keys() <= native.keys():
        raise ValueError("Image manifest contains a sample absent from the common timeline")
    if (corroborate_direct_with_legacy or recover_native_flow or recover_adjacent_portrait
            ) and direct_detector != "guided":
        raise ValueError("Optional direct Map recovery checks require guided search")
    if direct_tracker_factory is not None and (
        direct_detector != "guided" or recover_adjacent_portrait or corroborate_direct_with_legacy
    ):
        raise ValueError("Experimental tracker requires guided alignment without portrait recovery")
    if training_evidence and (direct_detector != "guided" or direct_tracker_factory is not None):
        raise ValueError("Weak training crops require a guided reference replay")
    if experimental_model_receipts is not None and (
        direct_tracker_factory is None
        or frozenset(experimental_model_receipts) not in ({"marker"}, {"marker", "portrait"})
        or not all(is_sha(sha) for sha in experimental_model_receipts.values())
    ):
        raise ValueError("Valid development model receipt hashes required")
    direct = None
    binding = None
    if direct_detector and knowledge is not None:
        binding = _bind_recorder_uuid(knowledge, native, bundle["observations"], inputs)
        if binding is not None and direct_tracker_factory is not None:
            direct = direct_tracker_factory(binding, knowledge)
        elif binding is not None:
            search = DensePortraitSearch(
                knowledge.minimap_portraits,
                augment=direct_detector in ("augmented", "fast", "guided"),
                fast_search=direct_detector in ("fast", "guided"),
            )
            fallback = DensePortraitSearch(
                knowledge.minimap_portraits, augment=direct_detector == "cascade",
                fast_search=direct_detector == "cascade", rim_guided=direct_detector == "guided",
            ) if direct_detector in ("cascade", "guided") else None
            direct = DirectRecorderTracker(search, binding, knowledge, fallback_search=fallback,
                                           compare_centers=direct_detector == "guided",
                                           recover_adjacent_portrait=recover_adjacent_portrait)
    exact = registration != "reference"
    if exact_alignment_cache is not None and (not exact or not direct_detector):
        raise ValueError("The alignment cache requires exact direct replay")
    exact_fits = ExactAlignmentCache(projector, exact_alignment_cache)
    alignment = (
        RecordingMapAlignment(projector, exact=exact) if direct_detector == "guided" else None
    )
    anchors = RecordingMapAnchors() if recording_anchors else None
    atlas_voids: dict[str, NDArray[np.float32] | None] = {}
    flow = NativeMapFlowAlignment() if recover_native_flow else None
    rows: list[dict[str, Any] | None] = []
    operable: set[str] = set()
    direct_stages: Counter[str] = Counter()
    direct_reasons: Counter[str] = Counter()
    portrait_rejections: Counter[str] = Counter()
    unresolved_portrait_samples: list[str] = []
    training_rows: list[dict[str, Any]] = []
    for frame in native.values():
        sample = freeze_native_sample(frame["sample"])
        policy.admit(sample)
        key = sample["sample_sha256"]
        packet = inputs.get(key)
        if packet is None:
            if flow is not None:
                flow.anchor = None
            tracker.reset()
            if knowledge is not None:
                knowledge.reset()
            if direct is not None:
                direct.previous = None
                direct.projected_portrait = None
            rows.append(None)
            continue
        image = _load_native_image(sample, packet[1])
        obs = [bundle["observations"][i] for i in frame["observation_ids"]]
        camera = measured_direct_view(frame, obs)
        if camera is not None and _pixels_match(image, sample):
            operable.add(key)
        else:
            camera = None
        if direct_detector:
            direct_stages["acquired"] += 1
            if camera is not None:
                direct_stages["current_recorder_view"] += 1
            if direct is None:
                direct_reasons["recording_agent_unbound"] += 1
                rows.append(None)
                continue
            height, width = image.shape[:2]
            roi = projector.layout.normalized_roi("minimap_normal").pixel_bounds(width, height)
            pool, result = direct._observe_measured(image, roi, sample, frame, camera)
            if corroborate_direct_with_legacy and knowledge is not None:
                old_pools = [r["map_candidates"] for r in obs if r["sample"] == sample
                             and r["raw"].get("schema") == "development_generic_map_pixels_v1"
                             and r["map_candidates"]]
                if len(old_pools) == 1:
                    legacy = tracker.observe(image, old_pools[0], sample, frame, observations=obs)
                    legacy = knowledge.observe(image, old_pools[0], sample, frame, obs, legacy)
                    result = corroborate_direct_selection(result, legacy, width / 1920)
                    if result["selection_reason"] == "direct_and_fitted_marker_conflict":
                        tracker.reset()
                        knowledge.reset()
                        direct.previous = None
                else:
                    tracker.reset()
                    knowledge.reset()
            direct_reasons[result["selection_reason"]] += 1
            if comparison_evidence and (
                result["selection_reason"] == "direct_portrait_or_rim_unresolved"
            ):
                unresolved_portrait_samples.append(key)
            if "portrait_rejection" in result:
                portrait_rejections[result["portrait_rejection"]] += 1
            if pool:
                direct_stages["dense_candidate"] += 1
            if result["support_count"]:
                direct_stages["unique_supported_portrait"] += 1
            if result["selection_status"] == "RESEARCH_SELECTED":
                direct_stages["research_selected"] += 1
        else:
            pools = [r for r in obs if r["sample"] == sample and r["map_candidates"]
                     and r["raw"].get("schema") == "development_generic_map_pixels_v1"]
            if len(pools) != 1:
                tracker.reset()
                if knowledge is not None:
                    knowledge.reset()
                rows.append(None)
                continue
            pool = pools[0]["map_candidates"]
            result = tracker.observe(image, pool, sample, frame, observations=obs)
            if knowledge is not None:
                result = knowledge.observe(image, pool, sample, frame, obs, result)
                if result["selection_reason"] == "recorder_selection_conflict":
                    tracker.reset()
        if result["support_count"] <= 0:
            if flow is not None:
                flow.anchor = None
            rows.append(None)
            continue
        if direct_detector:
            direct_stages["projection_attempted"] += 1
        raw = (exact_fits.inspect(image, sample) if exact else
               projector.inspect(image, recover_alignment=recover_map_alignment)["raw"])
        adjacent = result["selection_reason"] == ADJACENT_PORTRAIT_REASON
        if adjacent:
            if flow is not None:
                flow.anchor = None
            candidates = raw["map_name_candidates"]
            if (alignment is None or alignment.map_uuid is None or len(candidates) != 1
                    or candidates[0]["map_id"] != alignment.map_uuid):
                rows.append(None)
                continue
        elif alignment is not None:
            direct_raw = raw
            raw = alignment.inspect(image, sample, raw)
            if flow is not None:
                raw = flow.recover(
                    image, sample, result["track_anchor"], raw, result["support_center_frame_px"],
                    alignment.map_uuid,
                    carry=frame.get("continuity", {}).get("carry_allowed") is True,
                )
            if anchors is not None and result["selection_status"] == "RESEARCH_SELECTED":
                anchored = anchors.observe(
                    image, sample, direct_raw, alignment.map_uuid,
                    result["support_center_frame_px"],
                    recover=not raw["map_name_candidates"],
                )
                if anchored.get("alignment_recovery") == ANCHOR_ALIGNMENT:
                    raw = anchored
            if (registration == "recording-anchors-contrast" and not raw["map_name_candidates"]
                    and result["selection_status"] == "RESEARCH_SELECTED"):
                raw = projector.recover_contrast(
                    image, raw, alignment.map_uuid, tuple(result["support_center_frame_px"]),
                )
        projected = project_recorder_witness(
            image, sample, pool, result,
            raw,
            reference_sha256s=projector.bindings["asset_sha256s"],
        )
        outside_atlas = False
        if (screen_atlas_void or training_evidence) and projected is not None:
            map_id = projected["map_id"]
            if map_id not in atlas_voids:
                atlas_voids[map_id] = atlas_distances_for(
                    catalog, map_id, projected["reference_sha256"],
                    knowledge.map_references if knowledge is not None else (),
                )
            outside_atlas = clearly_outside_atlas(
                atlas_voids[map_id], projected["map_reference_px"],
            )
        if screen_atlas_void and outside_atlas:
            if direct is not None:
                direct.discard_projection()
            if flow is not None:
                flow.anchor = None
            direct_stages["outside_atlas"] += 1
            rows.append(None)
            continue
        if direct_detector and projected is not None:
            direct_stages["projection_available"] += 1
            if raw.get("alignment_recovery") == CONTRAST_ALIGNMENT:
                direct_stages["contrast_projection_available"] += 1
        if (
            training_evidence and not outside_atlas and projected is not None
            and projected["kind"] == "selected"
            and not adjacent and raw.get("alignment_recovery") != CONTRAST_ALIGNMENT
            and result["support_count"] >= 2
        ):
            training_rows.append({
                "sample": sample,
                "selection": {"support_center_frame_px": result["support_center_frame_px"]},
                "pool": pool,
                "observation_ids": frame["observation_ids"],
            })
        if adjacent and projected is not None:
            projected["selection_reason"] = ADJACENT_PORTRAIT_REASON
        if (direct is not None and projected is not None and not adjacent
                and raw.get("alignment_recovery") != CONTRAST_ALIGNMENT
                and result["selection_status"] == "RESEARCH_SELECTED"):
            direct.remember_projection(image)
        if (flow is not None and projected is not None and not adjacent
                and raw.get("alignment_recovery") not in (
                    "native_flow", ANCHOR_ALIGNMENT, CONTRAST_ALIGNMENT,
                )
                and result["selection_status"] == "RESEARCH_SELECTED"):
            flow.remember(image, sample, result["track_anchor"], raw)
        rows.append(projected)
    callouts = (KnowledgeRecorderMap.callouts(knowledge_asset_cache, catalog)
                if knowledge_asset_cache else [])
    paths = build_recorder_paths(rows, zones=zones, callouts=callouts)
    second_rows = join_recorder_seconds(paths, bundle)
    report = {
        **paths, "second_rows": second_rows,
        "operable_coverage": measure_operable_coverage(
            paths, bundle["seconds"], second_rows, operable,
        ),
        "timeline_sha256": file_sha(bundle_path), "frame_manifest_sha256": file_sha(frame_manifest),
        "portrait_assets_sha256": asset_hashes,
        "map_catalog_fingerprint": digest(projector.bindings),
        "zone_catalog_sha256": file_sha(zones_path) if zones_path else None,
        "native_track_recovery": recover_knowledge_track,
        "map_alignment_recovery": recover_map_alignment,
    }
    if knowledge is not None:
        report["game_knowledge"] = knowledge.provenance
    if exact:
        report["registration"] = registration
    if experimental_model_receipts is not None:
        report["experimental_model_receipts"] = experimental_model_receipts
    if path_quality:
        report["path_quality"] = measure_path_quality(
            paths, bundle["seconds"], second_rows, operable,
        )
    if training_evidence:
        report["training_evidence"] = {
            "schema": "map_cnn_reference_training_evidence_v1", "rows": training_rows,
        }
    if direct_detector:
        report["recording_map_uuid"] = alignment.map_uuid if alignment else None
        report["direct_detector"] = direct_detector
        if direct_tracker_factory is not None:
            report["experimental_direct_tracker"] = True
        if comparison_evidence:
            report["comparison_evidence"] = {
                "operable_sample_refs": sorted(operable),
                "unresolved_portrait_sample_refs": unresolved_portrait_samples,
            }
        report["direct_stage_counts"] = dict(direct_stages)
        report["portrait_rejection_counts"] = dict(portrait_rejections)
        report["direct_selection_reasons"] = dict(direct_reasons)
        report["recording_agent_uuid_binding"] = {
            "uuid": binding.uuid, "evidence_samples": list(binding.evidence_samples),
            "source_sha256": binding.source_sha256, "qualified": False,
        } if binding else None
    write_private(output, report)
    if exact_alignment_cache is not None:
        print(f"Exact Map alignment cache: {exact_fits.hits} hits, {exact_fits.misses} misses")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("bundle-path", "frame-manifest", "policy-path", "catalog", "layout", "output"):
        parser.add_argument(f"--{field}", required=True, type=Path)
    parser.add_argument("--zones-path", type=Path)
    parser.add_argument("--recover-supported-portraits", action="store_true")
    parser.add_argument("--knowledge-asset-cache", type=Path)
    parser.add_argument("--recover-knowledge-track", action="store_true")
    parser.add_argument("--recover-map-alignment", action="store_true")
    parser.add_argument("--recover-native-flow", action="store_true")
    parser.add_argument("--recover-adjacent-portrait", action="store_true")
    parser.add_argument("--corroborate-direct-with-legacy", action="store_true")
    parser.add_argument("--direct-detector",
                        choices=("external", "augmented", "fast", "cascade", "guided"))
    export_recorder_paths(**vars(parser.parse_args()))


if __name__ == "__main__":
    main()
