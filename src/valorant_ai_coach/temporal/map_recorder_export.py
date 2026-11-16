"""Export experimental recorder paths from a private common timeline and native images."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from .application import VERSION as APPLICATION_VERSION
from .evidence import digest, freeze_native_sample
from .map_portrait_rim import Reference
from .map_recorder_path import (
    ReferenceZones,
    build_recorder_paths,
    join_recorder_seconds,
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


def export_recorder_paths(
    *, bundle_path: Path, frame_manifest: Path, policy_path: Path, catalog: Path,
    layout: Path, output: Path, zones_path: Path | None = None,
    recover_supported_portraits: bool = False,
) -> dict[str, Any]:
    """Use existing current observations and preserve their native IDs and acquisition gaps."""
    bundle = read_json(bundle_path)
    if bundle.get("version") != APPLICATION_VERSION or bundle.get("formal_outputs") != 0:
        raise ValueError("Unqualified application timeline required")
    policy = SourcePolicy(read_json(policy_path))
    refs, asset_hashes = _agent_references(catalog)
    projector = PublicMapPixels(catalog, layout)
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
    rows: list[dict[str, Any] | None] = []
    for frame in native.values():
        sample = freeze_native_sample(frame["sample"])
        policy.admit(sample)
        key = sample["sample_sha256"]
        packet = inputs.get(key)
        if packet is None:
            tracker.reset()
            rows.append(None)
            continue
        path = packet[1]
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != sample["acquired_frame_sha256"]:
            raise ValueError("Exact native image bytes required")
        decoded = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
        if decoded is None:
            raise ValueError("Unreadable native image")
        obs = [bundle["observations"][i] for i in frame["observation_ids"]]
        pools = [r for r in obs if r["sample"] == sample and r["map_candidates"]
                 and r["raw"].get("schema") == "development_generic_map_pixels_v1"]
        if len(pools) != 1:
            tracker.reset()
            rows.append(None)
            continue
        pool = pools[0]["map_candidates"]
        image = np.asarray(decoded, dtype=np.uint8)
        result = tracker.observe(image, pool, sample, frame, observations=obs)
        if result["support_count"] <= 0:
            rows.append(None)
            continue
        rows.append(project_recorder_witness(
            image, sample, pool, result, projector.inspect(image)["raw"],
            reference_sha256s=projector.bindings["asset_sha256s"],
        ))
    paths = build_recorder_paths(rows, zones=zones)
    report = {
        **paths, "second_rows": join_recorder_seconds(paths, bundle),
        "timeline_sha256": file_sha(bundle_path), "frame_manifest_sha256": file_sha(frame_manifest),
        "portrait_assets_sha256": asset_hashes,
        "map_catalog_fingerprint": digest(projector.bindings),
        "zone_catalog_sha256": file_sha(zones_path) if zones_path else None,
    }
    write_private(output, report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("bundle-path", "frame-manifest", "policy-path", "catalog", "layout", "output"):
        parser.add_argument(f"--{field}", required=True, type=Path)
    parser.add_argument("--zones-path", type=Path)
    parser.add_argument("--recover-supported-portraits", action="store_true")
    export_recorder_paths(**vars(parser.parse_args()))


if __name__ == "__main__":
    main()
