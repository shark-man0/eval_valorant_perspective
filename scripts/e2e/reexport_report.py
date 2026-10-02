"""Recover shared reports using saved files only; no analyzer/evaluator execution."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from scripts.e2e.report_context import INPUT_FILES
from scripts.e2e.run_dataset_case import (
    APP_ROOT,
    CaseError,
    pack_identity,
    read_json,
    sha256_file,
    valid_id,
    validate_manifest,
)
from scripts.e2e.share_report import export_report, sanitize_run_metadata


def reexport(args, *, root=APP_ROOT):
    video_id = valid_id(args.video_id)
    run_dir = Path(args.run_dir).expanduser().resolve()
    raw, trace, evaluation = [read_json(run_dir / name) for name in INPUT_FILES]
    if raw.get("status") != "complete":
        raise CaseError("RECOVERY_ANALYZER_INCOMPLETE")
    if not isinstance(evaluation.get("pass"), bool) or not isinstance(
        evaluation.get("schema_valid"), bool
    ):
        raise CaseError("RECOVERY_EVALUATION_INVALID")
    pack = Path(args.validation_pack).expanduser().resolve()
    manifest, pack_hash, assertions_hash = pack_identity(pack)
    counts = evaluation.get("trace_counts")
    if isinstance(counts, dict) and any(
        count != len(trace.get(key, [])) for key, count in counts.items()
    ):
        raise CaseError("RECOVERY_TRACE_COUNTS_MISMATCH")
    assertions = read_json(pack / "tests/generated/e2e_assertions_v3.json")
    saved = run_dir / "run_metadata.json"
    recorded_layout_hash = None
    if saved.is_file():
        context = read_json(saved)
        recorded_layout_hash = context.get("hud_layout_sha256")
        if context.get("schema_version") != 1:
            raise CaseError("RECOVERY_METADATA_INVALID")
        if not isinstance(context.get("metadata"), dict) or not isinstance(
            context.get("input_hashes"), dict
        ):
            raise CaseError("RECOVERY_METADATA_INVALID")
        metadata = sanitize_run_metadata(context.get("metadata", {}))
        if metadata.get("video_id") != video_id:
            raise CaseError("RECOVERY_VIDEO_ID_MISMATCH")
        if (
            metadata.get("source_sha256") is not None
            and metadata["source_sha256"] != manifest["source_sha256"]
        ):
            raise CaseError("RECOVERY_SOURCE_MISMATCH")
        if (
            metadata.get("validation_pack_sha256") != pack_hash
            or context.get("assertions_sha256") != assertions_hash
        ):
            raise CaseError("RECOVERY_PACK_MISMATCH")
        hashes = context.get("input_hashes", {})
        if any(hashes.get(name) != sha256_file(run_dir / name) for name in INPUT_FILES):
            raise CaseError("RECOVERY_INPUT_INTEGRITY_MISMATCH")
    else:
        # Legacy runs cannot recover historical commit/dirty/time/settings hashes.
        # Do not read current git state or infer timestamps from directory names.
        dataset = read_json(root / "datasets/manifests" / f"{video_id}.json")
        validate_manifest(dataset, root)
        if (
            dataset["validation_pack_sha256"] != pack_hash
            or dataset["assertions_sha256"] != assertions_hash
            or dataset["sha256"] != manifest["source_sha256"]
        ):
            raise CaseError("RECOVERY_PACK_MISMATCH")
        source = raw.get("source_video")
        source_hash = (
            sha256_file(Path(source))
            if isinstance(source, str) and Path(source).is_file()
            else None
        )
        if source_hash is not None and source_hash != dataset["sha256"]:
            raise CaseError("RECOVERY_SOURCE_MISMATCH")
        settings_path = run_dir / "runner-settings.json"
        settings = read_json(settings_path) if settings_path.is_file() else {}
        metadata = sanitize_run_metadata(
            {
                "video_id": video_id,
                "source_sha256": source_hash,
                "validation_pack": manifest["name"],
                "validation_pack_sha256": pack_hash,
                "manual_map_id": settings.get("manual_map_id"),
                "error_code": read_json(run_dir / "error_code.json").get("error_code")
                if (run_dir / "error_code.json").is_file()
                else None,
            }
        )
        print(
            "Legacy recovery: historical commit/dirty/time/settings fingerprint are unknown.",
            file=sys.stderr,
        )
    if args.manual_map_id and args.manual_map_id != metadata.get("manual_map_id"):
        raise CaseError("RECOVERY_MANUAL_MAP_UNVERIFIED")
    # Only a previously recorded hash can verify a present-day layout. Never
    # manufacture a historical settings fingerprint from the supplied file.
    if args.hud_layout and (
        recorded_layout_hash is None or sha256_file(Path(args.hud_layout)) != recorded_layout_hash
    ):
        raise CaseError("RECOVERY_LAYOUT_UNVERIFIED")
    output = Path(args.output_dir) if args.output_dir else root / "e2e_reports" / video_id
    path = export_report(
        raw=raw,
        trace=trace,
        evaluation=evaluation,
        assertions=assertions,
        metadata=metadata,
        output_dir=output,
    )
    print(f"Re-exported shared report: {path.name}")
    return 0  # Export success, not an assertion that the saved E2E passed.


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run-dir", required=True)
    p.add_argument("--video-id", required=True)
    p.add_argument("--validation-pack", required=True)
    p.add_argument("--hud-layout")
    p.add_argument("--manual-map-id")
    p.add_argument("--output-dir")
    return p


def main():
    try:
        return reexport(parser().parse_args())
    except CaseError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except Exception:
        print(
            "RECOVERY_FAILED: inputs missing, unverifiable, or changed; no analysis was run.",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
