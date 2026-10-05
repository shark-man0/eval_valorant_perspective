"""Create and validate deterministic manifests for fixed regression replay."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from collections.abc import Iterable
from fractions import Fraction
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
SET_KINDS = {"canonical_uniform", "frozen_production_coverage"}
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SET_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
_COMMIT = re.compile(r"^[0-9a-f]{7,64}$")


class ManifestError(ValueError):
    """Raised when manifest input is malformed or unsafe to publish."""


def _integer(value: Any, name: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ManifestError(f"{name} must be an integer >= {minimum}")
    return value


def _signed_integer(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ManifestError(f"{name} must be an integer")
    return value


def _sha(value: Any, name: str) -> str:
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise ManifestError(f"{name} must be a lowercase SHA-256 digest")
    return value


def normalize_time_base(value: Any) -> dict[str, int]:
    """Return a reduced positive rational time base from {num, den} or N/D."""
    if isinstance(value, str):
        try:
            left, right = value.split("/", 1)
            num, den = int(left), int(right)
        except (ValueError, TypeError) as exc:
            raise ManifestError("time_base must be a positive rational") from exc
    elif isinstance(value, dict) and set(value) == {"num", "den"}:
        num = _integer(value["num"], "time_base.num", minimum=1)
        den = _integer(value["den"], "time_base.den", minimum=1)
    else:
        raise ManifestError("time_base must be a rational string or {num, den}")
    if num <= 0 or den <= 0:
        raise ManifestError("time_base must be positive")
    rational = Fraction(num, den)
    return {"num": rational.numerator, "den": rational.denominator}


def _normalize_records(records: Iterable[dict[str, Any]]) -> list[dict[str, int | str]]:
    normalized: list[dict[str, int | str]] = []
    seen: set[tuple[int, int]] = set()
    previous: tuple[int, int] | None = None
    try:
        iterator = iter(records)
    except TypeError as exc:
        raise ManifestError("frames must be an iterable of locator records") from exc
    for offset, record in enumerate(iterator):
        if not isinstance(record, dict):
            raise ManifestError(f"locator {offset} must be an object")
        allowed = {"pts", "source_frame_index", "pixel_sha256"}
        extra = set(record) - allowed
        missing = {"pts", "source_frame_index"} - set(record)
        if extra:
            raise ManifestError(f"unknown locator fields: {', '.join(sorted(map(str, extra)))}")
        if missing:
            raise ManifestError("locator requires pts and source_frame_index")
        pts = _signed_integer(record["pts"], f"frames[{offset}].pts")
        source_index = _integer(
            record["source_frame_index"], f"frames[{offset}].source_frame_index"
        )
        locator = (pts, source_index)
        if locator in seen:
            raise ManifestError("duplicate locator")
        if previous is not None and (locator <= previous or source_index <= previous[1]):
            raise ManifestError("locators must be strictly ordered by PTS and source frame index")
        seen.add(locator)
        previous = locator
        item: dict[str, int | str] = {"pts": pts, "source_frame_index": source_index}
        if "pixel_sha256" in record:
            item["pixel_sha256"] = _sha(record["pixel_sha256"], "pixel_sha256")
        normalized.append(item)
    if not normalized:
        raise ManifestError("at least one locator is required")
    return normalized


def canonical_uniform_locators(
    native_locators: Iterable[dict[str, Any]],
    time_base: dict[str, int] | str,
    *,
    rate_hz: int = 6,
) -> list[dict[str, int | str]]:
    """Select nearest native PTS to each exact 1/rate target; ties go earlier."""
    records = _normalize_records(native_locators)
    base = normalize_time_base(time_base)
    if isinstance(rate_hz, bool) or not isinstance(rate_hz, int) or rate_hz <= 0:
        raise ManifestError("rate_hz must be a positive integer")
    tick_seconds = Fraction(base["num"], base["den"])
    times = [int(row["pts"]) * tick_seconds for row in records]
    duration = times[-1] - times[0]
    selected: dict[int, dict[str, int | str]] = {}
    step = Fraction(1, rate_hz)
    sample_number = 0
    while sample_number * step <= duration:
        target = times[0] + sample_number * step
        nearest = min(
            range(len(times)),
            key=lambda index: (abs(times[index] - target), times[index]),
        )
        selected[nearest] = records[nearest]
        sample_number += 1
    return [selected[index] for index in sorted(selected)]


def build_manifest(
    *,
    set_id: str,
    source_sha: str,
    stream_index: int,
    time_base: dict[str, int] | str,
    locators: Iterable[dict[str, Any]],
    setkind: str,
    provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not isinstance(set_id, str) or not _SET_ID.fullmatch(set_id):
        raise ManifestError("set_id must be lowercase-safe (letters, digits, _ or -)")
    _sha(source_sha, "sourceSHA")
    _integer(stream_index, "stream_index")
    if setkind not in SET_KINDS:
        raise ManifestError("unknown setkind")
    records = _normalize_records(locators)
    clean_provenance: dict[str, Any] = {}
    if setkind == "frozen_production_coverage":
        if not isinstance(provenance, dict) or set(provenance) != {
            "lineage_clean", "analyzer_commit", "run_hash"
        }:
            raise ManifestError(
                "coverage provenance requires lineage_clean, analyzer_commit, run_hash"
            )
        if provenance["lineage_clean"] is not True:
            raise ManifestError("coverage lineage must be clean")
        commit = provenance["analyzer_commit"]
        if not isinstance(commit, str) or not _COMMIT.fullmatch(commit):
            raise ManifestError("analyzer_commit must be a lowercase git commit id")
        clean_provenance = {
            "lineage_clean": True,
            "analyzer_commit": commit,
            "run_hash": _sha(provenance["run_hash"], "run_hash"),
        }
    elif provenance not in (None, {}):
        raise ManifestError("canonical_uniform provenance must be empty")
    return {
        "schema_version": SCHEMA_VERSION,
        "set_id": set_id,
        "setkind": setkind,
        "sourceSHA": source_sha,
        "stream_index": stream_index,
        "time_base": normalize_time_base(time_base),
        "frames": records,
        "provenance": clean_provenance,
    }


def validate_manifest(value: Any, *, expected_source_sha: str | None = None) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ManifestError("manifest must be an object")
    required = {
        "schema_version", "set_id", "setkind", "sourceSHA", "stream_index",
        "time_base", "frames", "provenance",
    }
    if set(value) != required:
        raise ManifestError("manifest has missing or unknown fields")
    if _integer(value["schema_version"], "schema_version", minimum=1) != SCHEMA_VERSION:
        raise ManifestError("unsupported schema version")
    if not isinstance(value["set_id"], str) or not _SET_ID.fullmatch(value["set_id"]):
        raise ManifestError("invalid set_id")
    source_sha = _sha(value["sourceSHA"], "sourceSHA")
    if expected_source_sha is not None and source_sha != _sha(
        expected_source_sha, "expected sourceSHA"
    ):
        raise ManifestError("sourceSHA mismatch")
    _integer(value["stream_index"], "stream_index")
    if normalize_time_base(value["time_base"]) != value["time_base"]:
        raise ManifestError("time_base must be reduced")
    if value["setkind"] not in SET_KINDS:
        raise ManifestError("unknown setkind")
    frames = _normalize_records(value["frames"])
    if frames != value["frames"]:
        raise ManifestError("frames must use canonical field ordering and values")
    provenance = value["provenance"]
    if value["setkind"] == "frozen_production_coverage":
        if not isinstance(provenance, dict) or set(provenance) != {
            "lineage_clean", "analyzer_commit", "run_hash"
        }:
            raise ManifestError("invalid coverage provenance")
        if provenance["lineage_clean"] is not True:
            raise ManifestError("coverage lineage must be clean")
        build_manifest(
            set_id=value["set_id"], source_sha=source_sha,
            stream_index=value["stream_index"], time_base=value["time_base"],
            locators=frames, setkind=value["setkind"], provenance=provenance,
        )
    elif provenance != {}:
        raise ManifestError("canonical_uniform provenance must be empty")
    return value


def serialize_manifest(manifest: dict[str, Any]) -> bytes:
    validate_manifest(manifest)
    encoded = json.dumps(manifest, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return (encoded + "\n").encode()


def manifest_hash(manifest: dict[str, Any]) -> str:
    return hashlib.sha256(serialize_manifest(manifest)).hexdigest()


def write_manifest_immutable(path: Path, manifest: dict[str, Any]) -> str:
    """Create once, never overwrite an existing manifest."""
    path = Path(path)
    data = serialize_manifest(manifest)
    try:
        with path.open("xb") as stream:
            stream.write(data)
    except FileExistsError as exc:
        raise ManifestError("manifest output already exists") from exc
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def ffprobe_native_locators(
    video: Path, ffprobe: str = "ffprobe"
) -> tuple[str, int, list[dict[str, int]]]:
    """Read exact decoded-display PTS and stream time_base; ordinal is ffprobe frame order."""
    command = [
        ffprobe, "-v", "error", "-select_streams", "v:0", "-show_streams", "-show_frames",
        "-show_entries", "stream=index,time_base:frame=best_effort_timestamp",
        "-of", "json", str(video),
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False, timeout=600)
        if result.returncode:
            raise ManifestError("ffprobe failed")
        payload = json.loads(result.stdout)
        stream = payload["streams"][0]
        records = [
            {"pts": int(frame["best_effort_timestamp"]), "source_frame_index": index}
            for index, frame in enumerate(payload["frames"])
        ]
        _normalize_records(records)
        return str(stream["time_base"]), int(stream["index"]), records
    except (
        OSError, subprocess.SubprocessError, ValueError, KeyError, TypeError, IndexError
    ) as exc:
        if isinstance(exc, ManifestError):
            raise
        raise ManifestError("could not read exact ffprobe native frame locators") from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "video", type=Path, help="source video used only to derive metadata and SHA-256"
    )
    parser.add_argument("--set-id", required=True)
    parser.add_argument("--setkind", choices=sorted(SET_KINDS), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--ffprobe", default="ffprobe")
    parser.add_argument("--coverage-locators", type=Path,
                        help="private JSON list of all frozen production locators")
    parser.add_argument("--analyzer-commit")
    parser.add_argument("--run-hash")
    parser.add_argument("--lineage-clean", action="store_true")
    args = parser.parse_args(argv)
    try:
        time_base, stream_index, native = ffprobe_native_locators(args.video, args.ffprobe)
        if args.setkind == "canonical_uniform":
            if args.coverage_locators:
                raise ManifestError("canonical selection cannot receive coverage input")
            locators = canonical_uniform_locators(native, time_base)
        else:
            if args.coverage_locators is None:
                raise ManifestError("coverage requires the full frozen production locator list")
            locators = _normalize_records(
                json.loads(args.coverage_locators.read_text(encoding="utf-8"))
            )
            native_pairs = {(row["pts"], row["source_frame_index"]) for row in native}
            if any((row["pts"], row["source_frame_index"]) not in native_pairs for row in locators):
                raise ManifestError("coverage locator not in native source")
        provenance = None
        if args.setkind == "frozen_production_coverage":
            provenance = {
                "lineage_clean": args.lineage_clean,
                "analyzer_commit": args.analyzer_commit,
                "run_hash": args.run_hash,
            }
        manifest = build_manifest(
            set_id=args.set_id,
            source_sha=sha256_file(args.video),
            stream_index=stream_index,
            time_base=time_base,
            locators=locators,
            setkind=args.setkind,
            provenance=provenance,
        )
        digest = write_manifest_immutable(args.output, manifest)
    except (ManifestError, OSError) as exc:
        print(f"fixed-replay-manifest: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"manifest_sha256": digest, "frame_count": len(manifest["frames"])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
