"""Export experimental recorder paths from a private common timeline and native images."""

from __future__ import annotations

import argparse
import hashlib
from collections import Counter
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from numpy.typing import NDArray

from .application import VERSION as APPLICATION_VERSION
from .evidence import digest, freeze_native_sample, native_time
from .map_direct_recorder import (
    DensePortraitSearch,
    DirectRecorderTracker,
    RecorderUUID,
    measured_direct_view,
)
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
from .public_map_pixels import PublicMapPixels
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
    direct_detector: str | None = None,
) -> dict[str, Any]:
    """Use existing current observations and preserve their native IDs and acquisition gaps."""
    bundle = read_json(bundle_path)
    if bundle.get("version") != APPLICATION_VERSION or bundle.get("formal_outputs") != 0:
        raise ValueError("Unqualified application timeline required")
    policy = SourcePolicy(read_json(policy_path))
    refs, asset_hashes = _agent_references(catalog)
    if direct_detector not in (None, "external", "augmented", "fast", "cascade"):
        raise ValueError("Known direct Map detector required")
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
    direct = None
    binding = None
    if direct_detector and knowledge is not None:
        binding = _bind_recorder_uuid(knowledge, native, bundle["observations"], inputs)
        if binding is not None:
            search = DensePortraitSearch(
                knowledge.minimap_portraits, augment=direct_detector in ("augmented", "fast"),
                fast_search=direct_detector == "fast",
            )
            fallback = DensePortraitSearch(
                knowledge.minimap_portraits, augment=True, fast_search=True,
            ) if direct_detector == "cascade" else None
            direct = DirectRecorderTracker(search, binding, knowledge, fallback_search=fallback)
    rows: list[dict[str, Any] | None] = []
    operable: set[str] = set()
    direct_stages: Counter[str] = Counter()
    direct_reasons: Counter[str] = Counter()
    for frame in native.values():
        sample = freeze_native_sample(frame["sample"])
        policy.admit(sample)
        key = sample["sample_sha256"]
        packet = inputs.get(key)
        if packet is None:
            tracker.reset()
            if knowledge is not None:
                knowledge.reset()
            if direct is not None:
                direct.previous = None
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
            direct_reasons[result["selection_reason"]] += 1
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
            rows.append(None)
            continue
        projected = project_recorder_witness(
            image, sample, pool, result,
            projector.inspect(image, recover_alignment=recover_map_alignment)["raw"],
            reference_sha256s=projector.bindings["asset_sha256s"],
        )
        if direct_detector:
            direct_stages["projection_attempted"] += 1
            if projected is not None:
                direct_stages["projection_available"] += 1
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
    if direct_detector:
        report["direct_detector"] = direct_detector
        report["direct_stage_counts"] = dict(direct_stages)
        report["direct_selection_reasons"] = dict(direct_reasons)
        report["recording_agent_uuid_binding"] = {
            "uuid": binding.uuid, "evidence_samples": list(binding.evidence_samples),
            "source_sha256": binding.source_sha256, "qualified": False,
        } if binding else None
    write_private(output, report)
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
    parser.add_argument("--direct-detector", choices=("external", "augmented", "fast", "cascade"))
    export_recorder_paths(**vars(parser.parse_args()))


if __name__ == "__main__":
    main()
