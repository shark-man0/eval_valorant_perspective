"""Export source-frame identities and historical splits, never labels or images."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from fractions import Fraction
from pathlib import Path
from typing import Any

SOURCES = {
    "supplemental_010246": {
        "sha256": "06919642d69f68895ac123b505bfd7d3643dd28d903585008fcdc2b7f1b7e3fd",
        "filename": "Valorant_10-08-2026_1-2-46-283.mp4",
        "time_base": "1/15360",
        "roots": ["work/new-source-review", "work/new-source-development"],
    },
    "supplemental_001927": {
        "sha256": "f5a3d2e78f183ffbcdb066ddd21574c2d38846d73b067204145ebaee7cd59c69",
        "filename": "Valorant_10-08-2026_0-19-27-350.mp4",
        "time_base": "1/15360",
        "roots": ["work/independent-source-001927"],
    },
}
MANIFESTS = {"source-manifest.json", "source-frames.json", "training-source-grid.json"}
HASH = re.compile(r"^[0-9a-f]{64}$")
EPOCH = re.compile(r"^[0-9a-f]{32}$")


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def frame_records(value: Any, source: dict[str, Any]):
    """Only exact integer source ticks paired with a physical pixel hash qualify."""
    if isinstance(value, list):
        for child in value:
            yield from frame_records(child, source)
    elif isinstance(value, dict):
        pixel = value.get("pixel_sha256", value.get("source_pixel_sha256"))
        tick = value.get("pts_ticks", value.get("source_pts_ticks", value.get("tick")))
        if pixel is not None and tick is not None:
            if type(tick) is not int or tick < 0 or not HASH.fullmatch(str(pixel)):
                raise ValueError("invalid physical frame identity")
            sha = value.get("source_video_sha256", value.get("source_sha256", source["sha256"]))
            base = str(value.get("time_base", value.get("source_time_base", source["time_base"])))
            if sha != source["sha256"] or Fraction(base) != Fraction(source["time_base"]):
                raise ValueError("source identity/timebase mismatch")
            row = {"pts_ticks": tick, "time_base": base, "pixel_sha256": pixel}
            for old, new in [
                ("source_epoch", "source_epoch"),
                ("encoded_sha256", "encoded_sha256"),
            ]:
                if old in value:
                    item = value[old]
                    if (
                        not isinstance(item, str)
                        or (old == "encoded_sha256" and not HASH.fullmatch(item))
                        or (old == "source_epoch" and not EPOCH.fullmatch(item))
                    ):
                        raise ValueError("invalid frame provenance")
                    row[new] = item
            row["source_identity_inherited"] = (
                "source_video_sha256" not in value and "source_sha256" not in value
            )
            row["time_base_inherited"] = (
                "time_base" not in value and "source_time_base" not in value
            )
            yield row
        for child in value.values():
            if isinstance(child, (dict, list)):
                yield from frame_records(child, source)


def purpose(path: Path) -> str:
    text = path.as_posix()
    if "geometry" in text:
        return "geometry_check"
    if "discovery" in text or "refinement" in text:
        return "source_discovery"
    if "native-cases" in text or "held" in text or "next-End" in text:
        return "historical_evaluation"
    if "training" in text or "development-timing" in text:
        return "development"
    return "saved_source_manifest"


def export(repo: Path, output: Path) -> dict[str, Any]:
    if output.exists():
        raise ValueError("output must not exist; preserve earlier inventory snapshots")
    artifacts = []
    frames: dict[str, dict[str, Any]] = {}
    plans = []
    requests = []
    methods = []
    snapshots: dict[Path, str] = {}
    for source_id, source in SOURCES.items():
        candidates = set()
        for root in source["roots"]:
            for path in (repo / root).rglob("*.json"):
                rel = path.relative_to(repo)
                if (
                    path.name in MANIFESTS
                    or path.name == "split-plan.json"
                    or path.name.endswith("freeze.json")
                    or (path.name == "result.json" and "geometry-preflight" in str(rel))
                    or (path.name == "selection.json" and "discovery" in str(rel))
                ):
                    candidates.add(path)
        for path in sorted(candidates):
            raw = path.read_bytes()
            snapshots[path] = digest(raw)
            data = json.loads(raw)
            rel = path.relative_to(repo)
            aid = digest(str(rel).encode())[:20]
            artifact = {
                "id": aid,
                "record_file": rel.as_posix(),
                "sha256": digest(raw),
                "source_id": source_id,
                "purpose": purpose(rel),
                "frame_records": 0,
            }
            artifacts.append(artifact)
            if path.name.endswith("freeze.json") and isinstance(data, dict):
                method = {
                    "artifact_id": aid,
                    "source_id": source_id,
                    "status": "historical_method_snapshot_not_current_admission",
                }
                for key in [
                    "code_fingerprint",
                    "recognizer_fingerprint",
                    "profile_fingerprint",
                    "parent_profile_fingerprint",
                    "method_commit",
                    "code",
                    "profile",
                    "candidate_profile",
                    "baseline_profile",
                ]:
                    if (
                        key in data
                        and isinstance(data[key], str)
                        and re.fullmatch(r"[0-9a-f]{40,64}", data[key])
                    ):
                        method[key] = data[key]
                methods.append(method)
            if path.name == "split-plan.json":
                # Historical plan only; do not export misleading current viewed flags.
                plan = {
                    "artifact_id": aid,
                    "source_id": source_id,
                    "status": "historical_plan_not_current_exposure_certification",
                }
                for key in [
                    "partitions",
                    "pools",
                    "excluded_previously_viewed_sec",
                    "geometry_preflight_times_sec",
                    "initial_evaluation_source_discovery_times_sec",
                    "recorded_at_utc",
                    "code_fingerprint",
                    "initial_profile_fingerprint",
                ]:
                    if key in data:
                        plan[key] = data[key]
                plans.append(plan)
            if path.name == "selection.json" and isinstance(data, dict):
                times = data.get("times_sec")
                if isinstance(times, list) and all(type(t) in (int, float) for t in times):
                    requests.append(
                        {
                            "artifact_id": aid,
                            "source_id": source_id,
                            "requested_times_sec": times,
                            "actual_decoded_pts_or_visual_view_not_proven_by_request": True,
                        }
                    )
            if path.name.endswith("freeze.json"):
                continue  # Preserve method identity without exporting review/GT sidecars.
            for record in frame_records(data, source):
                artifact["frame_records"] += 1
                key_fields = {
                    k: record.get(k)
                    for k in [
                        "pts_ticks",
                        "time_base",
                        "pixel_sha256",
                        "source_epoch",
                        "encoded_sha256",
                    ]
                }
                key = digest(json.dumps([source_id, key_fields], sort_keys=True).encode())
                if key not in frames:
                    frames[key] = {
                        "id": key,
                        "source_id": source_id,
                        **record,
                        "artifact_ids": [],
                        "purposes": [],
                        "visual_review_status": "not_inferred_from_manifest",
                        "new_blind_holdout_status": "not_certified",
                    }
                row = frames[key]
                if aid not in row["artifact_ids"]:
                    row["artifact_ids"].append(aid)
                if artifact["purpose"] not in row["purposes"]:
                    row["purposes"].append(artifact["purpose"])
    if any(digest(path.read_bytes()) != sha for path, sha in snapshots.items()):
        raise ValueError("input changed during export")
    output.mkdir(parents=True)
    registry = {
        sid: {k: v for k, v in source.items() if k != "roots"} for sid, source in SOURCES.items()
    }
    docs = {
        "sources.json": registry,
        "artifact_index.json": artifacts,
        "historical_split_plans.json": plans,
        "discovery_requests.json": requests,
        "method_snapshots.json": methods,
    }
    for name, value in docs.items():
        (output / name).write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    ordered = sorted(frames.values(), key=lambda x: (x["source_id"], x["pts_ticks"], x["id"]))
    (output / "frames.jsonl").write_text(
        "".join(json.dumps(x, sort_keys=True) + "\n" for x in ordered), encoding="utf-8"
    )
    summary = {
        "schema_version": 1,
        "scope": "Known saved source identities, not exhaustive visual exposure",
        "source_records": len(ordered),
        "input_artifacts": len(artifacts),
        "unique_source_pts": len(
            {(x["source_id"], x["pts_ticks"], str(Fraction(x["time_base"]))) for x in ordered}
        ),
        "source_counts": {sid: sum(x["source_id"] == sid for x in ordered) for sid in SOURCES},
        "exhaustive_exposure_proven": False,
        "unlisted_frames_certified_unviewed": False,
        "independent_holdout_certified": False,
        "exact_first_view_times_available": False,
        "source_images_labels_profiles_included": False,
        "match_002_image_exposure_assessed": False,
        "files_sha256": {p.name: digest(p.read_bytes()) for p in sorted(output.iterdir())},
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(export(args.repo_root.resolve(), args.output_dir), indent=2))


if __name__ == "__main__":
    main()
