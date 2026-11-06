"""Frozen transfer experiments; no recognition, state rules or qualification added.

New comparison sources are explicitly attested, content-blindly enrolled and
rejected if already reserved anywhere in the supplied private registries.
Source identity is used only for admission, provenance and physical grouping.
"""

from __future__ import annotations

import argparse
import csv
import importlib
import importlib.metadata
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time
from collections import Counter, defaultdict
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from fractions import Fraction
from pathlib import Path
from typing import Any, cast

from .application import VERSION as APPLICATION_VERSION
from .application import export_application
from .evidence import digest, is_sha, native_time, source_scope
from .replay import SourcePolicy, file_sha, peak_rss_mib, read_json, write_private

ROOT = Path(__file__).resolve().parents[3]
PROTOCOL = "development_frozen_timeline_protocol_v1"
ENROLLMENT = "development_timeline_comparison_sources_v1"


def _git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=repo, text=True, encoding="utf-8").strip()


def _private(path: Path) -> Path:
    path = path.expanduser().resolve()
    if any((p / ".git").exists() for p in (path, *path.parents)):
        raise ValueError("Private experiment must be outside Git")
    return path


def _observer(name: str, config: Path) -> Any:
    module, attribute = name.split(":", 1)
    return getattr(importlib.import_module(module), attribute)(config)


def freeze_protocol(
    *,
    config: Path,
    observer: str,
    output: Path,
    runtime_files: list[Path],
    max_refinement_windows: int = 40,
    report_view_bridge: bool = True,
    repository: Path = ROOT,
) -> dict[str, Any]:
    if _git(repository, "status", "--porcelain"):
        raise ValueError("Commit the runtime before freezing the experiment")
    if max_refinement_windows < 0:
        raise ValueError("Nonnegative refinement budget required")
    reader = _observer(observer, config)
    if not is_sha(reader.fingerprint) or not isinstance(reader.bindings, dict):
        raise ValueError("Existing fingerprint-bound observer required")
    files = list(Path(__file__).parent.glob("*.py")) + runtime_files
    files.append(Path(__file__).parent.parent / "rules/development_timeline.py")
    if any(p.suffix != ".py" or not p.is_file() for p in files):
        raise ValueError("Existing Python runtime files required")
    binaries = {
        name: Path(value).resolve()
        for name in ("ffmpeg", "ffprobe")
        if (value := shutil.which(name)) is not None
    }
    if len(binaries) != 2:
        raise ValueError("Native decoder/probe required")
    result = {
        "version": PROTOCOL,
        "created_at_utc": datetime.now(UTC).isoformat(),
        "repository": str(repository.resolve()),
        "code_commit": _git(repository, "rev-parse", "HEAD"),
        "reader_config": str(config.resolve()),
        "reader_config_sha256": file_sha(config),
        "observer": observer,
        "observer_fingerprint": reader.fingerprint,
        "observer_bindings": reader.bindings,
        "runtime_sha256s": {str(p.resolve()): file_sha(p) for p in files},
        "binary_sha256s": {str(p): file_sha(p) for p in binaries.values()},
        "binary_paths": {name: str(path) for name, path in binaries.items()},
        "python": {
            "executable": str(Path(sys.executable).resolve()),
            "version": sys.version,
            "executable_sha256": file_sha(Path(sys.executable)),
        },
        "dependency_versions": {
            name: importlib.metadata.version(name)
            for name in ("numpy", "opencv-python", "shapely", "jsonschema")
        },
        "settings": {
            "coarse_seconds": "1",
            "dense_seconds": "1/5",
            "max_refinement_windows": max_refinement_windows,
            "refinement_selection_policy": "chronological",
            "report_view_bridge": report_view_bridge,
        },
        "human_labels_or_initial_states": False,
        "source_conditioned_recognition": False,
        "formal_outputs": 0,
    }
    write_private(output, result)
    return result


def verify_protocol(path: Path) -> dict[str, Any]:
    plan = read_json(path)
    if plan["version"] != PROTOCOL or plan["formal_outputs"] != 0:
        raise ValueError("Frozen development protocol required")
    repo = Path(plan["repository"])
    if _git(repo, "rev-parse", "HEAD") != plan["code_commit"] or _git(
        repo, "status", "--porcelain"
    ):
        raise ValueError("Frozen code commit or clean checkout changed")
    if any(
        str(Path(shutil.which(name) or "").resolve()) != path
        for name, path in plan["binary_paths"].items()
    ):
        raise ValueError("Active native decoder/probe path changed")
    if (
        plan["python"]["executable"] != str(Path(sys.executable).resolve())
        or plan["python"]["version"] != sys.version
        or plan["python"]["executable_sha256"] != file_sha(Path(sys.executable))
        or any(
            importlib.metadata.version(name) != version
            for name, version in plan["dependency_versions"].items()
        )
    ):
        raise ValueError("Frozen interpreter or feature dependency versions changed")
    for key in ("runtime_sha256s", "binary_sha256s"):
        if any(file_sha(Path(p)) != sha for p, sha in plan[key].items()):
            raise ValueError("Frozen runtime or binary changed")
    config = Path(plan["reader_config"])
    if file_sha(config) != plan["reader_config_sha256"]:
        raise ValueError("Frozen configuration changed")
    reader = _observer(plan["observer"], config)
    if (
        reader.fingerprint != plan["observer_fingerprint"]
        or reader.bindings != plan["observer_bindings"]
    ):
        raise ValueError("Frozen models/features/thresholds/bindings changed")
    return cast(dict[str, Any], plan)


def prior_catalog(registries: list[Path]) -> dict[str, Any]:
    ids, matches, hashes, paths = set(), set(), set(), set()
    anchors = {}
    files = list((ROOT / "datasets/manifests").glob("*.json"))
    for registry in registries:
        files.extend(registry.glob("*/allocation.json"))
    for path in sorted(set(files)):
        data = read_json(path)
        anchors[str(path.resolve())] = file_sha(path)
        rows = data.get("records", [data])
        for row in rows:
            identifier = row.get("video_id")
            if identifier:
                ids.add(identifier.casefold())
            if row.get("physical_match_id"):
                matches.add(row["physical_match_id"].casefold())
            sha = row.get("source_sha256", row.get("sha256"))
            if is_sha(sha):
                hashes.add(sha)
            for key in ("original_path", "managed_path"):
                if row.get(key):
                    paths.add(str(Path(row[key]).resolve()))
    return {"ids": ids, "matches": matches, "hashes": hashes, "paths": paths, "anchors": anchors}


def _inspect(video: Path, identifier: str) -> dict[str, Any]:
    module = importlib.import_module("scripts.diagnostics.intake_recording")
    return cast(
        dict[str, Any], module.inspect_recording(video, identifier, user_confirmed_unedited=True)
    )


def _decode(video: Path) -> None:
    module = importlib.import_module("scripts.diagnostics.register_private_sources")
    module.decode_source(video, shutil.which("ffmpeg") or "ffmpeg")


@contextmanager
def _exclusive(path: Path) -> Iterator[None]:
    """Cross-platform exclusive directory lock; a crash requires explicit recovery."""
    path.mkdir(mode=0o700)
    try:
        yield
    finally:
        path.rmdir()


def enroll_sources(
    *,
    declaration: Path,
    protocol: Path,
    registry: Path,
    batch_id: str,
    prior_registries: list[Path],
) -> dict[str, Any]:
    """Register any positive number; do not edit the old nine-source contract."""
    registry = _private(registry)
    registry.mkdir(parents=True, exist_ok=True, mode=0o700)
    with _exclusive(registry / ".timeline_enrollment.lock"):
        return _enroll_sources(
            declaration=declaration,
            protocol=protocol,
            registry=registry,
            batch_id=batch_id,
            prior_registries=[*prior_registries, registry],
        )


def _enroll_sources(
    *,
    declaration: Path,
    protocol: Path,
    registry: Path,
    batch_id: str,
    prior_registries: list[Path],
) -> dict[str, Any]:
    verify_protocol(protocol)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", batch_id):
        raise ValueError("Safe batch identifier required")
    request = read_json(declaration)
    if (
        set(request) != {"purpose", "content_kind", "declarations", "records"}
        or request["purpose"] != "frozen_timeline_comparison"
        or request["content_kind"] not in {"VALORANT_FULL_MATCH", "SYNTHETIC_TEST"}
        or request["declarations"]
        != {
            "permission": True,
            "unused_for_development": True,
            "distinct_physical_matches": True,
            "unedited_full_matches": True,
        }
        or not isinstance(request["records"], list)
        or not request["records"]
        or not all(value is True for value in request["declarations"].values())
    ):
        raise ValueError("Explicit permission, unused/distinct/unedited attestation required")
    prior = prior_catalog(prior_registries)
    seen_ids, seen_matches = set(prior["ids"]), set(prior["matches"])
    for row in request["records"]:
        if set(row) != {"path", "source_id", "physical_match_id"}:
            raise ValueError("Source metadata only; no labels or initial states")
        identifier, physical = row["source_id"], row["physical_match_id"]
        if not all(
            isinstance(v, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", v)
            for v in (identifier, physical)
        ):
            raise ValueError("Safe Source and physical-match identifiers required")
        if identifier.casefold() in seen_ids or physical.casefold() in seen_matches:
            raise ValueError("Duplicate or previously reserved Source/physical match")
        seen_ids.add(identifier.casefold())
        seen_matches.add(physical.casefold())
    batch = _private(registry / batch_id)
    if batch.exists():
        raise ValueError("Batch already exists; never overwrite reservations")
    batch.mkdir(parents=True, mode=0o700)
    write_private(batch / "request_PRIVATE.json", request)
    records = []
    for row in request["records"]:
        source = Path(row["path"]).expanduser()
        record = {
            "video_id": row["source_id"],
            "physical_match_id": row["physical_match_id"],
            "original_path": str(source.resolve()),
            "split": "DEVELOPMENT",
            "exposure": "DEVELOPMENT",
            "initial_unused_basis": "explicit_user_attestation",
            "source_sha256": None,
            "status": "pending",
            "failure_rule": None,
            "managed_path": str(batch / "sources" / (row["source_id"] + source.suffix)),
            "intake_path": str(batch / (row["source_id"] + ".intake.json")),
        }
        # Known reservations are rejected before media reads, even when the
        # declaration incorrectly says unused. Unknown exposure is never cleared.
        if str(source.resolve()) in prior["paths"] or source.is_symlink() or not source.is_file():
            record.update(status="rejected", failure_rule="PRIOR_PATH_OR_INVALID_SOURCE")
        else:
            try:
                record["source_sha256"] = file_sha(source)
            except OSError as exc:
                record.update(
                    status="rejected",
                    failure_rule="SOURCE_UNREADABLE",
                    error_type=type(exc).__name__,
                )
        records.append(record)
    counts = Counter(r["source_sha256"] for r in records if r["source_sha256"] is not None)
    for row in records:
        sha = row["source_sha256"]
        if sha is not None and (sha in prior["hashes"] or counts[sha] > 1):
            row.update(status="rejected", failure_rule="PRIOR_OR_DUPLICATE_SOURCE_BYTES")
    allocation = {
        "version": ENROLLMENT,
        "purpose": request["purpose"],
        "content_kind": request["content_kind"],
        "declarations": request["declarations"],
        "protocol_sha256": file_sha(protocol),
        "prior_anchors": prior["anchors"],
        "records": records,
    }
    write_private(batch / "allocation.json", allocation)
    (batch / "sources").mkdir(mode=0o700)
    for row in records:
        if row["status"] == "rejected":
            continue
        try:
            original, managed = Path(row["original_path"]), Path(row["managed_path"])
            with original.open("rb") as src, managed.open("xb") as dst:
                os.chmod(managed, 0o600)
                shutil.copyfileobj(src, dst, length=1024 * 1024)
            if file_sha(managed) != row["source_sha256"]:
                raise ValueError("Copy digest mismatch")
            report = _inspect(managed, row["video_id"])
            _decode(managed)
            if (
                report["source_sha256"] != row["source_sha256"]
                or file_sha(original) != row["source_sha256"]
                or file_sha(managed) != row["source_sha256"]
            ):
                raise ValueError("Recording changed during intake")
            report["decode_integrity"] = "full_video_and_audio_null_sink_passed"
            report["decode_is_recognition_or_GT"] = False
            write_private(Path(row["intake_path"]), report)
            os.chmod(managed, 0o400)
            row.update(status="accepted", intake_sha256=file_sha(Path(row["intake_path"])))
        except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
            row.update(
                status="rejected",
                failure_rule="SOURCE_INTEGRITY_OR_METADATA_FAILED",
                error_type=type(exc).__name__,
                failure_detail=str(exc),
            )
    manifest = {**allocation, "records": records}
    write_private(batch / "manifest.json", manifest)
    accepted = [r["source_sha256"] for r in records if r["status"] == "accepted"]
    if accepted:
        write_private(
            batch / "policy_PRIVATE.json",
            {
                "manifest": str(batch / "manifest.json"),
                "allocation": str(batch / "allocation.json"),
                "manifest_sha256": file_sha(batch / "manifest.json"),
                "allocation_sha256": file_sha(batch / "allocation.json"),
                "allowed_source_sha256s": accepted,
            },
        )
    return manifest


def inspect_bundle(bundle: dict[str, Any]) -> dict[str, Any]:
    """Structure, actual candidate coverage and stable-field signature, not accuracy."""
    if (
        bundle.get("version") != APPLICATION_VERSION
        or bundle.get("formal_outputs") != 0
        or bundle.get("qualification") != "development_only"
    ):
        raise ValueError("Development application timeline required")
    duration = Fraction(bundle["recording"]["duration_seconds"])
    rows = bundle["seconds"]
    expected = list(range(math.ceil(duration)))
    if [r["timestamp"] for r in rows] != expected or duration <= 0:
        raise ValueError("Missing, duplicate or backward recording seconds")
    observations, frames = bundle["observations"], bundle["native_frames"]
    origin = Fraction(bundle["recording"]["native_origin_seconds"])
    assigned = []
    for index, row in enumerate(rows):
        if row["end_timestamp"] != float(min(Fraction(index + 1), duration)):
            raise ValueError("Incorrect partial or complete second endpoint")
        if (
            not set(row["evidence_refs"]) <= observations.keys()
            or not set(row["sample_refs"]) <= frames.keys()
        ):
            raise ValueError("Unresolvable original evidence")
        if Fraction(row["native_start_seconds"]) != origin + index:
            raise ValueError("Recording/native origin mismatch")
        for ref in row["sample_refs"]:
            if (
                not index
                <= native_time(frames[ref]["sample"]) - origin
                < min(Fraction(index + 1), duration)
            ):
                raise ValueError("Native sample assigned to wrong second")
        if not set(row["event_candidates"]) <= bundle["events"].keys():
            raise ValueError("Unresolvable candidate event")
        assigned.extend(row["sample_refs"])
        if row["map_observations"]["continuous_path"] is not None:
            raise ValueError("No qualified continuous path contract in this development schema")
    if len(assigned) != len(set(assigned)) or set(assigned) != frames.keys():
        raise ValueError("Native sample lost or duplicated in recording grid")
    for event in bundle["events"].values():
        if event["qualified"] is not False or event["internal_event_time"] is not None:
            raise ValueError("Candidate promoted to an event or exact event time")
        if not set(event["evidence_refs"]) <= observations.keys():
            raise ValueError("Unresolvable event evidence")
    scopes: dict[tuple[Any, ...], list[Fraction]] = defaultdict(list)
    for frame in frames.values():
        sample = frame["sample"]
        if sample["source_sha256"] != bundle["source"]["source_sha256"]:
            raise ValueError("Mixed recording Source")
        scopes[source_scope(sample)].append(native_time(sample))
    if any(times != sorted(set(times)) for times in scopes.values()):
        raise ValueError("Native PTS duplicate/backward within an acquisition")
    domains = {
        d: dict(Counter(r[d]["value"] for r in rows))
        for d in ("round_state", "life_state", "camera_state")
    }
    hud = {
        field: sum(bool(row["hud_observations"].get(field, {}).get("candidates")) for row in rows)
        for field in sorted({key for row in rows for key in row["hud_observations"]})
    }
    mapping = {
        name: sum(bool(r["map_observations"][name]) for r in rows)
        for name in (
            "map_name_candidates",
            "position_candidates",
            "zone_candidates",
            "current_self_position_candidates",
        )
    }
    information = (
        any(hud.values())
        or any(mapping.values())
        or any(value != "UNKNOWN" for domain in domains.values() for value in domain)
        or bool(bundle["events"])
    )
    stable = [
        {
            "timestamp": r["timestamp"],
            "states": {
                d: {k: r[d][k] for k in ("value", "hypotheses", "uncertainty")} for d in domains
            },
            "hud_values": {
                k: [c["value"] for c in v["candidates"]] for k, v in r["hud_observations"].items()
            },
        }
        for r in rows
    ]
    return {
        "processing": "COMPLETE_WITH_INFORMATION" if information else "COMPLETE_UNINFORMATIVE",
        "structural_pass": True,
        "real_observation_or_estimate_present": information,
        "duration_seconds": str(duration),
        "one_second_rows": len(rows),
        "missing_seconds": 0,
        "observed_seconds": sum(r["observation_present"] for r in rows),
        "unobserved_seconds": sum(not r["observation_present"] for r in rows),
        "inference_only_seconds": sum(
            not r["observation_present"] and any(r[d]["value"] != "UNKNOWN" for d in domains)
            for r in rows
        ),
        "domain_seconds": domains,
        "domain_status_seconds": {d: dict(Counter(r[d]["status"] for r in rows)) for d in domains},
        "hypothesis_seconds": {d: sum(bool(r[d]["hypotheses"]) for r in rows) for d in domains},
        "round_number_candidate_seconds": sum(bool(r["round_number"]["candidates"]) for r in rows),
        "hud_candidate_seconds": hud,
        "map_candidate_seconds": mapping,
        "event_candidates": dict(Counter(e["kind"] for e in bundle["events"].values())),
        "stable_view_signature": digest(stable),
        "signature_scope": "Selected states/HUD fields only; not whole-byte equality across epochs",
        "accuracy": None,
        "human_labels_read": False,
        "formal_outputs": 0,
        "field_limits": bundle["field_limits"],
        "viewer_and_seek_verification": "NOT_VERIFIED_BY_STRUCTURE_CHECK",
    }


def check_output(output: Path) -> dict[str, Any]:
    receipt = read_json(output / "completion_PRIVATE.json")
    if any(file_sha(output / name) != sha for name, sha in receipt["output_sha256s"].items()):
        raise ValueError("Application output digest mismatch")
    bundle = read_json(output / "timeline_PRIVATE.json")
    result = inspect_bundle(bundle)
    # Evidence-rich Map cells can exceed the stdlib's 128 KiB default.
    # Bound individual fields without silently truncating their evidence.
    previous_limit = csv.field_size_limit()
    try:
        csv.field_size_limit(max(previous_limit, 64 * 1024**2))
        with (output / "timeline_1s_PRIVATE.csv").open(encoding="utf-8", newline="") as stream:
            csv_rows = list(csv.DictReader(stream))
    finally:
        csv.field_size_limit(previous_limit)
    if len(csv_rows) != len(bundle["seconds"]):
        raise ValueError("CSV row count mismatch")
    for actual, expected in zip(csv_rows, bundle["seconds"], strict=True):
        for key, value in expected.items():
            if isinstance(value, (dict, list)):
                if json.loads(actual[key]) != value:
                    raise ValueError("CSV candidate/evidence content mismatch")
            # csv encodes None as an empty cell, without inventing a value.
            elif actual[key] != str(value) and (value is not None or actual[key] != ""):
                raise ValueError("CSV scalar mismatch")
    evaluation = read_json(output / "evaluation_PRIVATE.json")
    if (
        evaluation["seconds_consumed"] != result["one_second_rows"]
        or not evaluation["existing_scope_resolver_consumed"]
        or evaluation["formal_outputs"] != 0
        or evaluation["deterministic_engine_decision"] is not None
    ):
        raise ValueError("Downstream evaluation/review handoff mismatch")
    return {
        **result,
        "JSON_CSV_content_equal": True,
        "evaluation_handoff": True,
        "artifact_sha256s": receipt["output_sha256s"],
    }


def _append(path: Path, event: dict[str, Any]) -> None:
    with os.fdopen(
        os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600), "a", encoding="utf-8"
    ) as stream:
        stream.write(json.dumps(event, ensure_ascii=False, allow_nan=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def _decoded_progress(output: Path) -> list[dict[str, Any]]:
    progress = []
    for path in sorted((output / "acquisition").glob("*_decode.log")):
        last = None
        with path.open(encoding="utf-8", errors="replace") as stream:
            for line in stream:
                match = re.search(r"\bn:\s*\d+\s+pts:\s*(-?\d+)\s+pts_time:(\S+)", line)
                if match:
                    last = {"pts_tick": int(match[1]), "pts_time_text": match[2]}
        progress.append(
            {
                "pass": path.stem,
                "last_logged_decoded_frame": last,
                "log_sha256": file_sha(path),
                "scope": "Decoder progress only; not last recognized frame or event time",
            }
        )
    return progress


def run_one(protocol: Path, policy: Path, source_id: str, output: Path) -> dict[str, Any]:
    """Worker is a fresh process per match, for meaningful peak-RSS boundaries."""
    from .match import run_match

    plan = verify_protocol(protocol)
    started = time.perf_counter()
    module, name = plan["observer"].split(":", 1)
    factory = getattr(importlib.import_module(module), name)
    acquisition = output / "acquisition"
    run_match(
        policy_path=policy,
        source_id=source_id,
        reader_config=Path(plan["reader_config"]),
        output=acquisition,
        observer_factory=factory,
        **{
            **plan["settings"],
            "coarse_seconds": Fraction(plan["settings"]["coarse_seconds"]),
            "dense_seconds": Fraction(plan["settings"]["dense_seconds"]),
        },
    )
    export_application(
        timeline_path=acquisition / "timeline_PRIVATE.json",
        receipt_path=acquisition / "completion_PRIVATE.json",
        policy_path=policy,
        output=output / "application",
    )
    result = check_output(output / "application")
    verify_protocol(protocol)
    result["performance"] = {
        "elapsed_seconds": time.perf_counter() - started,
        "python_peak_RSS_MiB": peak_rss_mib(),
        "excludes_children": True,
    }
    write_private(output / "result_PRIVATE.json", result)
    return result


def run_enrollment(protocol: Path, batch: Path, output: Path) -> dict[str, Any]:
    batch = _private(batch)
    with _exclusive(batch / ".recognition.lock"):
        return _run_enrollment(protocol, batch, output)


def _run_enrollment(protocol: Path, batch: Path, output: Path) -> dict[str, Any]:
    verify_protocol(protocol)
    manifest = read_json(batch / "manifest.json")
    if manifest["version"] != ENROLLMENT or manifest["protocol_sha256"] != file_sha(protocol):
        raise ValueError("Enrollment belongs to a different frozen experiment")
    accepted = [r for r in manifest["records"] if r["status"] == "accepted"]
    if accepted:
        policy = SourcePolicy(read_json(batch / "policy_PRIVATE.json"))
        if set(policy.allowed) != {r["source_sha256"] for r in accepted}:
            raise ValueError("Enrollment/Source allowlist mismatch")
    output = _private(output)
    if output.exists():
        raise ValueError("New comparison output directory required")
    output.mkdir(parents=True, mode=0o700)
    journal = batch / "exposure_journal_PRIVATE.jsonl"
    history = (
        []
        if not journal.exists()
        else [json.loads(line) for line in journal.read_text(encoding="utf-8").splitlines()]
    )
    results = []
    for row in manifest["records"]:
        sid = row["video_id"]
        if row["status"] != "accepted":
            results.append(
                {
                    "source_id": sid,
                    "processing": "REGISTRATION_REJECTED",
                    "failure_rule": row["failure_rule"],
                    "first_attempt": False,
                }
            )
            continue
        first = not any(e["source_id"] == sid for e in history)
        event = {
            "source_id": sid,
            "physical_match_id": row["physical_match_id"],
            "protocol_sha256": file_sha(protocol),
            "kind": "recognition_attempt_started",
            "first_attempt": first,
            "output": str(output / sid),
            "recorded_at_utc": datetime.now(UTC).isoformat(),
        }
        _append(journal, event)
        history.append(event)
        log = output / (sid + "_PRIVATE.log")
        conditions = {}
        try:
            intake_path = Path(row["intake_path"])
            if file_sha(intake_path) != row["intake_sha256"]:
                raise ValueError("Registered intake metadata changed")
            intake = read_json(intake_path)
            conditions = {
                k: intake[k]
                for k in (
                    "width",
                    "height",
                    "fps",
                    "video_codec",
                    "duration_sec",
                    "native_time_base",
                )
            }
            with log.open("xb") as stream:
                os.chmod(log, 0o600)
                process = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "valorant_ai_coach.temporal.validation",
                        "_worker",
                        "--protocol",
                        str(protocol),
                        "--batch",
                        str(batch),
                        "--source-id",
                        sid,
                        "--output",
                        str(output / sid),
                    ],
                    stdout=stream,
                    stderr=subprocess.STDOUT,
                    check=False,
                )
            if process.returncode != 0:
                raise RuntimeError(f"Worker exited with return code {process.returncode}")
            result = read_json(output / sid / "result_PRIVATE.json")
        except (OSError, ValueError, KeyError, RuntimeError) as exc:
            result = {
                "processing": "FAILED",
                "error_type": type(exc).__name__,
                "failure_detail": str(exc),
                "last_observed_native_PTS": None,
                "decoder_progress": _decoded_progress(output / sid),
                "stop_position_scope": "Not guessed from elapsed time or progress counts",
                "failure_log_sha256": file_sha(log) if log.exists() else None,
            }
        result["recording_conditions"] = conditions
        result["source_sha256"] = row["source_sha256"]
        result.update(
            source_id=sid,
            physical_match_id=row["physical_match_id"],
            first_attempt=first,
            exposure="DEVELOPMENT",
            independence="user_attested_unused_before_first_attempt"
            if first
            else "REPEATED_EXPOSED_COMPARISON",
        )
        results.append(result)
        _append(
            journal,
            {**event, "kind": "recognition_attempt_finished", "processing": result["processing"]},
        )
    report = {
        "protocol_sha256": file_sha(protocol),
        "manifest_sha256": file_sha(batch / "manifest.json"),
        "content_kind": manifest["content_kind"],
        "results": results,
        "real_first_attempt_matches": sum(r.get("first_attempt", False) for r in results)
        if manifest["content_kind"] == "VALORANT_FULL_MATCH"
        else 0,
        "successful_informative_first_matches": sum(
            r.get("first_attempt", False) and r["processing"] == "COMPLETE_WITH_INFORMATION"
            for r in results
        )
        if manifest["content_kind"] == "VALORANT_FULL_MATCH"
        else 0,
        "accuracy": None,
        "formal_outputs": 0,
    }
    write_private(output / "comparison_PRIVATE.json", report)
    with (output / "matches_PRIVATE.csv").open("x", encoding="utf-8", newline="") as stream:
        os.chmod(output / "matches_PRIVATE.csv", 0o600)
        fields = sorted({key for r in results for key in r})
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in results:
            writer.writerow(
                {
                    k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v
                    for k, v in row.items()
                }
            )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    freeze = sub.add_parser("freeze")
    for name in ("reader-config", "output"):
        freeze.add_argument("--" + name, type=Path, required=True)
    freeze.add_argument(
        "--observer", default="valorant_ai_coach.temporal.match_observer:ProfileHudObserver"
    )
    freeze.add_argument("--runtime-file", type=Path, action="append", default=[])
    freeze.add_argument("--max-refinement-windows", type=int, default=40)
    freeze.add_argument("--no-report-view-bridge", action="store_true")
    enroll = sub.add_parser("enroll")
    for name in ("declaration", "protocol", "registry"):
        enroll.add_argument("--" + name, type=Path, required=True)
    enroll.add_argument("--batch-id", required=True)
    enroll.add_argument("--prior-registry", type=Path, action="append", required=True)
    run = sub.add_parser("run")
    worker = sub.add_parser("_worker")
    for command in (run, worker):
        for name in ("protocol", "batch", "output"):
            command.add_argument("--" + name, type=Path, required=True)
    worker.add_argument("--source-id", required=True)
    validate = sub.add_parser("check")
    validate.add_argument("--application", type=Path, required=True)
    validate.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "freeze":
        result = freeze_protocol(
            config=args.reader_config,
            observer=args.observer,
            output=args.output,
            runtime_files=args.runtime_file,
            max_refinement_windows=args.max_refinement_windows,
            report_view_bridge=not args.no_report_view_bridge,
        )
    elif args.command == "enroll":
        result = enroll_sources(
            declaration=args.declaration,
            protocol=args.protocol,
            registry=args.registry,
            batch_id=args.batch_id,
            prior_registries=args.prior_registry,
        )
    elif args.command == "run":
        result = run_enrollment(args.protocol, args.batch, args.output)
    elif args.command == "_worker":
        result = run_one(
            args.protocol, args.batch / "policy_PRIVATE.json", args.source_id, args.output
        )
    else:
        result = check_output(args.application)
        write_private(args.output, result)
    print(json.dumps({"command": args.command, "formal_outputs": result.get("formal_outputs", 0)}))


if __name__ == "__main__":
    main()
