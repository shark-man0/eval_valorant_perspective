"""Private source-only inventory. Never runs recognition or creates an E2E manifest."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import jsonschema

from scripts.diagnostics.intake_recording import inspect_recording
from scripts.e2e.run_dataset_case import read_json, sha256_file, valid_id, validate_manifest
from valorant_ai_coach.hud.calibrate_temporal import _check_output_privacy

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "datasets/private_source_inventory.schema.json"
SPLITS = ("DEVELOPMENT", "QUALIFICATION_CANDIDATE", "FINAL_HOLDOUT_CANDIDATE")
EXPOSURES = ("DEVELOPMENT", "PROSPECTIVE_HELD_OUT", "UNKNOWN_EXPOSURE")
ALLOCATION_RULES = {
    "legacy-5-2-2": "source_sha256_lexical_5_2_2_before_content",
    "development-all": "source_sha256_lexical_development_all_before_content",
}
ALLOCATION_COUNTS = {"legacy-5-2-2": (5, 2, 2), "development-all": (9, 0, 0)}


def write_private(path: Path, value: dict[str, Any]) -> None:
    # Exclusive creation and restrictive permissions, independent of the caller's umask.
    with open(path, "x", encoding="utf-8", opener=lambda p, f: os.open(p, f, 0o600)) as stream:
        stream.write(json.dumps(value, indent=2, allow_nan=False) + "\n")


def validate_inventory(value: dict[str, Any]) -> None:
    jsonschema.validate(value, read_json(SCHEMA))
    mode = next(
        (name for name, rule in ALLOCATION_RULES.items()
         if value["allocation_rule"] == rule), None,
    )
    if mode is None:
        raise ValueError("UNKNOWN_ALLOCATION_RULE")
    counts = tuple(sum(row["split"] == split for row in value["records"]) for split in SPLITS)
    if counts != ALLOCATION_COUNTS[mode]:
        raise ValueError("ALLOCATION_COUNT_MISMATCH")
    if mode == "development-all":
        if value["declarations"]["unused_and_distinct"]:
            raise ValueError("UNSUPPORTED_UNUSED_CLAIM")
        for row in value["records"]:
            if row["exposure"] != "UNKNOWN_EXPOSURE" or (
                row.get("physical_match_verification") != "unverified"
            ):
                raise ValueError("DEVELOPMENT_EXPOSURE_OR_MATCH_UNVERIFIED_REQUIRED")
    ids: set[str] = set()
    hashes: set[str] = set()
    episodes: set[str] = set()
    for row in value["records"]:
        key = valid_id(row["video_id"]).casefold()
        if key in ids or row["source_sha256"] in hashes or row["physical_match_id"] in episodes:
            raise ValueError("DUPLICATE_ID_SOURCE_OR_MATCH")
        ids.add(key)
        hashes.add(row["source_sha256"])
        episodes.add(row["physical_match_id"])
        if row["split"] != SPLITS[0] and row["exposure"] == "DEVELOPMENT":
            raise ValueError("EXPOSED_EVALUATION_SOURCE")
        if row["exposure"] == "PROSPECTIVE_HELD_OUT" and (
            row["split"] == SPLITS[0] or not value["declarations"]["unused_and_distinct"]
        ):
            raise ValueError("UNSUPPORTED_UNUSED_CLAIM")


def public_summary(manifest: dict[str, Any]) -> dict[str, Any]:
    # Deliberately reconstruct from a whitelist: no free text, paths, IDs, source
    # hashes, timestamps, codec details, error text or detailed exposure journal.
    validate_inventory(manifest)
    rows = manifest["records"]
    return {
        "schema_version": 1,
        "kind": "anonymous_source_intake_summary",
        "allocation_mode": next(
            name for name, rule in ALLOCATION_RULES.items()
            if manifest["allocation_rule"] == rule
        ),
        "distinct_physical_matches_verified": False,
        "attempted": len(rows),
        "registered": sum(r["status"] == "accepted" for r in rows),
        "failed": sum(r["status"] == "rejected" for r in rows),
        "duplicates": 0,  # duplicates abort before a batch is enrolled
        "reserved_by_split": {s: sum(r["split"] == s for r in rows) for s in SPLITS},
        "accepted_by_split": {
            s: sum(r["split"] == s and r["status"] == "accepted" for r in rows) for s in SPLITS
        },
        "exposure_counts": {s: sum(r["exposure"] == s for r in rows) for s in EXPOSURES},
        "recognition_executed": False,
        "e2e_registered": False,
        "qualification_completed": False,
        "visual_continuity_verified": False,
        "human_annotation": "pending",
    }


def decode_source(video: Path, ffmpeg: str) -> None:
    # Null sink decodes video AND all audio, without raster files, recognition,
    # OCR, display, GT, or prediction. Any decode error quarantines this source.
    result = subprocess.run(
        [ffmpeg, "-nostdin", "-v", "error", "-xerror", "-err_detect", "explode",
         "-threads", "2", "-i", str(video), "-map", "0:v:0", "-map", "0:a?",
         "-fps_mode", "passthrough", "-f", "null", "-"],
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=21600, check=False,
    )
    if result.returncode or result.stderr:
        raise ValueError("DECODE_INTEGRITY_FAILED")


def prior_sources(registry: Path) -> tuple[set[str], set[str], list[dict[str, str]]]:
    ids: set[str] = set()
    hashes: set[str] = set()
    anchors = []
    for path in sorted((ROOT / "datasets/manifests").glob("*.json")):
        value = read_json(path)
        validate_manifest(value)
        ids.add(value["video_id"].casefold())
        hashes.add(value["sha256"])
        anchors.append({"path": str(path), "sha256": sha256_file(path)})
    # Include frozen reservations even if decoding failed or a run was interrupted.
    for path in sorted(registry.glob("*/allocation.json")):
        value = read_json(path)
        for row in value["records"]:
            ids.add(row["video_id"].casefold())
            hashes.add(row["source_sha256"])
        anchors.append({"path": str(path), "sha256": sha256_file(path)})
    return ids, hashes, anchors


def register(
    source_dir: Path, registry: Path, batch_id: str, *,
    unused_and_distinct: bool = False, unedited: bool = False,
    ffprobe: str = "ffprobe", ffmpeg: str = "ffmpeg",
    allocation_mode: str = "legacy-5-2-2",
) -> tuple[Path, dict[str, Any]]:
    batch_id = valid_id(batch_id)
    if allocation_mode not in ALLOCATION_RULES:
        raise ValueError("UNKNOWN_ALLOCATION_MODE")
    if allocation_mode == "development-all" and unused_and_distinct:
        raise ValueError("UNSUPPORTED_UNUSED_CLAIM")
    source_dir, registry = source_dir.resolve(), registry.resolve()
    _check_output_privacy(registry / batch_id)
    # Require an external registry, even if an in-repository path is gitignored.
    if registry.is_relative_to(ROOT) or source_dir.is_relative_to(registry) or any(
        (p / ".git").exists() for p in (registry, *registry.parents)
    ):
        raise ValueError("EXTERNAL_PRIVATE_STORAGE_REQUIRED")
    registry.mkdir(parents=True, exist_ok=True, mode=0o700)
    lock = registry / ".registration-lock"
    lock.mkdir(mode=0o700)  # cross-process exclusive; stale lock requires manual review
    try:
        batch = registry / batch_id
        if batch.exists() or any(
            p.name.casefold() == batch_id.casefold() for p in registry.iterdir()
        ):
            raise ValueError("BATCH_EXISTS")
        videos = sorted(
            p for p in source_dir.iterdir() if p.is_file() and not p.name.startswith(".")
        )
        if len(videos) != 9 or any(p.is_symlink() for p in videos):
            raise ValueError("EXACTLY_NINE_REGULAR_RECORDINGS_REQUIRED")
        ids, hashes, anchors = prior_sources(registry)
        records: list[dict[str, Any]] = []
        for video in videos:
            digest = sha256_file(video)
            if digest in hashes:
                raise ValueError("DUPLICATE_SOURCE")
            hashes.add(digest)
            records.append({"original_path": str(video), "source_sha256": digest})
        # Content-blind deterministic allocation, after identity checks and before
        # metadata/decode. No score, visual content or recognizer result selects it.
        records.sort(key=lambda row: row["source_sha256"])
        for index, row in enumerate(records):
            video_id = valid_id(f"{batch_id}_{index + 1:03d}")
            if video_id.casefold() in ids:
                raise ValueError("DUPLICATE_ID")
            split = SPLITS[
                0 if allocation_mode == "development-all" or index < 5
                else 1 if index < 7 else 2
            ]
            exposure = "UNKNOWN_EXPOSURE"
            if allocation_mode == "legacy-5-2-2" and unused_and_distinct:
                exposure = "DEVELOPMENT" if index < 5 else "PROSPECTIVE_HELD_OUT"
            row.update({
                "video_id": video_id, "physical_match_id": video_id,
                "split": split, "exposure": exposure,
                "status": "pending", "failure_rule": None,
                "managed_path": str(batch / "sources" / f"{video_id}.mp4"),
                "intake_path": str(batch / f"{video_id}.intake.json"),
            })
            if allocation_mode == "development-all":
                # Provisional identity: different encodes can be one physical match.
                row["physical_match_verification"] = "unverified"
        manifest: dict[str, Any] = {
            "schema_version": 1, "kind": "private_source_inventory_not_e2e",
            "created_at_utc": datetime.now(UTC).isoformat(), "batch_id": batch_id,
            "allocation_rule": ALLOCATION_RULES[allocation_mode],
            "declarations": {"unused_and_distinct": unused_and_distinct,
                             "unedited_full_match": unedited, "basis": "explicit_user_attestation"},
            "prior_inventory_anchors": anchors,
            "contract_anchors": [
                {"path": str(p.relative_to(ROOT)), "sha256": sha256_file(p)} for p in (
                    Path(__file__), SCHEMA, ROOT / "scripts/diagnostics/intake_recording.py",
                    ROOT / "schemas/round_end_temporal_dataset_v1.json",
                    ROOT / "docs/temporal_gt/annotation_contract_v1.md",
                    ROOT / "docs/temporal_gt/private_audit_anchors_20261020.json",
                )
            ],
            "backup": {"originals_retained": True, "managed_copy_hash_verified": True,
                       "separate_failure_domain_backup": "pending_operator_action"},
            "records": records,
        }
        batch.mkdir(mode=0o700)
        (batch / "sources").mkdir(mode=0o700)
        if allocation_mode == "development-all":
            # Freeze the initial exposure evidence before metadata or decoding;
            # this neither asserts prior non-use nor grants holdout status.
            journal = {
                "schema_version": 1,
                "kind": "private_development_all_exposure_initialization",
                "batch_id": batch_id,
                "prior_exposure_verified": False,
                "events": [
                    {
                        "video_id": row["video_id"], "sequence": index + 1,
                        "event": "development_reserved_before_source_inspection",
                        "split": "DEVELOPMENT", "exposure": "UNKNOWN_EXPOSURE",
                        "prior_use": "not_verified",
                    }
                    for index, row in enumerate(records)
                ],
            }
            write_private(batch / "exposure_history.json", journal)
            manifest["exposure_history_sha256"] = sha256_file(
                batch / "exposure_history.json"
            )
        validate_inventory(manifest)
        write_private(batch / "allocation.json", manifest)
        for row in records:
            try:
                original, managed = Path(row["original_path"]), Path(row["managed_path"])
                # Exclusive target; never move, chmod, transcode or replace originals.
                with original.open("rb") as src, managed.open("xb") as dst:
                    os.chmod(managed, 0o600)
                    shutil.copyfileobj(src, dst, length=8 * 1024 * 1024)
                if sha256_file(managed) != row["source_sha256"]:
                    raise ValueError("COPY_INTEGRITY_FAILED")
                os.chmod(managed, 0o400)
                report = inspect_recording(
                    managed, row["video_id"], ffprobe, user_confirmed_unedited=unedited,
                )
                if report["source_sha256"] != row["source_sha256"]:
                    raise ValueError("SOURCE_CHANGED")
                decode_source(managed, ffmpeg)
                if sha256_file(managed) != row["source_sha256"] or (
                    sha256_file(original) != row["source_sha256"]
                ):
                    raise ValueError("SOURCE_CHANGED")
                report["decode_integrity"] = "full_video_and_all_audio_null_sink_passed"
                report["decode_is_visual_or_semantic_review"] = False
                write_private(Path(row["intake_path"]), report)
                row["intake_sha256"] = sha256_file(Path(row["intake_path"]))
                row["status"] = "accepted"
            except (OSError, ValueError, KeyError, subprocess.SubprocessError):
                # Never include tool stderr / input paths in public errors. Keep
                # rejected reservations; do not backfill from another split.
                row["status"] = "rejected"
                row["failure_rule"] = "SOURCE_INTEGRITY_OR_METADATA_FAILED"
            write_private(batch / f'{row["video_id"]}.result.json', row)
            print(json.dumps({"completed": sum(r["status"] != "pending" for r in records),
                              "accepted": sum(r["status"] == "accepted" for r in records)}),
                  flush=True)
        validate_inventory(manifest)
        write_private(batch / "manifest.json", manifest)
        summary = public_summary(manifest)
        summary["allocation_sha256"] = sha256_file(batch / "allocation.json")
        summary["manifest_sha256"] = sha256_file(batch / "manifest.json")
        write_private(batch / "public_summary.json", summary)
        return batch, summary
    finally:
        lock.rmdir()


def verify(batch: Path, trusted_manifest: str, trusted_allocation: str) -> dict[str, Any]:
    if sha256_file(batch / "manifest.json") != trusted_manifest or (
        sha256_file(batch / "allocation.json") != trusted_allocation
    ):
        raise ValueError("TRUSTED_ANCHOR_MISMATCH")
    manifest, allocation = read_json(batch / "manifest.json"), read_json(batch / "allocation.json")
    validate_inventory(manifest)
    validate_inventory(allocation)
    if len(manifest["records"]) != len(allocation["records"]) or any(
        manifest[key] != allocation[key] for key in (
            "batch_id", "allocation_rule", "declarations", "prior_inventory_anchors",
            "contract_anchors", "backup",
        )
    ):
        raise ValueError("ALLOCATION_CHANGED")
    if manifest["allocation_rule"] == ALLOCATION_RULES["development-all"]:
        expected_hash = allocation["exposure_history_sha256"]
        if manifest["exposure_history_sha256"] != expected_hash or (
            sha256_file(batch / "exposure_history.json") != expected_hash
        ):
            raise ValueError("EXPOSURE_HISTORY_CHANGED")
        journal = read_json(batch / "exposure_history.json")
        if (
            journal.get("kind") != "private_development_all_exposure_initialization"
            or journal.get("batch_id") != allocation["batch_id"]
            or journal.get("prior_exposure_verified") is not False
            or journal.get("events") != [
                {
                    "video_id": row["video_id"], "sequence": index + 1,
                    "event": "development_reserved_before_source_inspection",
                    "split": "DEVELOPMENT", "exposure": "UNKNOWN_EXPOSURE",
                    "prior_use": "not_verified",
                }
                for index, row in enumerate(allocation["records"])
            ]
        ):
            raise ValueError("EXPOSURE_HISTORY_CHANGED")
    for row, frozen in zip(manifest["records"], allocation["records"], strict=True):
        if any(row[k] != v for k, v in frozen.items() if k not in {"status", "failure_rule"}):
            raise ValueError("ALLOCATION_CHANGED")
        if row["status"] != "accepted":
            continue
        if any(sha256_file(Path(row[k])) != row["source_sha256"]
               for k in ("original_path", "managed_path")):
            raise ValueError("SOURCE_INTEGRITY_FAILED")
        if sha256_file(Path(row["intake_path"])) != row["intake_sha256"]:
            raise ValueError("INTAKE_INTEGRITY_FAILED")
        intake = read_json(Path(row["intake_path"]))
        if intake["source_sha256"] != row["source_sha256"]:
            raise ValueError("INTAKE_SOURCE_MISMATCH")
    return public_summary(manifest)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    intake = sub.add_parser("register")
    intake.add_argument("--source-dir", type=Path, required=True)
    intake.add_argument("--registry", type=Path, required=True)
    intake.add_argument("--batch-id", required=True)
    intake.add_argument(
        "--allocation-mode", choices=tuple(ALLOCATION_RULES),
        default="legacy-5-2-2",
        help="Use development-all to allocate all nine recordings for development only",
    )
    intake.add_argument("--user-confirmed-unused-and-distinct", action="store_true")
    intake.add_argument("--user-confirmed-unedited", action="store_true")
    intake.add_argument("--ffprobe", default="ffprobe")
    intake.add_argument("--ffmpeg", default="ffmpeg")
    check = sub.add_parser("verify")
    check.add_argument("--batch", type=Path, required=True)
    check.add_argument("--trusted-manifest-sha256", required=True)
    check.add_argument("--trusted-allocation-sha256", required=True)
    args = parser.parse_args()
    try:
        if args.command == "register":
            _, summary = register(
                args.source_dir, args.registry, args.batch_id,
                unused_and_distinct=args.user_confirmed_unused_and_distinct,
                unedited=args.user_confirmed_unedited, ffprobe=args.ffprobe, ffmpeg=args.ffmpeg,
                allocation_mode=args.allocation_mode,
            )
        else:
            summary = verify(args.batch, args.trusted_manifest_sha256,
                             args.trusted_allocation_sha256)
        print(json.dumps(summary, indent=2))
        if summary["failed"]:
            raise SystemExit(2)
    except (OSError, ValueError, jsonschema.ValidationError, subprocess.SubprocessError):
        parser.exit(2, "PRIVATE_SOURCE_INTAKE_REJECTED\n")


if __name__ == "__main__":
    main()
