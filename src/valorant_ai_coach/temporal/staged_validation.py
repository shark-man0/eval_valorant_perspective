"""Content-blind six-source reservation and one-source DEVELOPMENT first use.

The reservation never probes, hashes, copies, decodes or recognizes media. A
caller supplies independently measured metadata and a before/after source hash.
Only the first DEVELOPMENT source gets an existing SourcePolicy admission file.
This is a development workflow, not qualification or a new state engine.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from fractions import Fraction
from pathlib import Path
from typing import Any

from .evidence import is_sha
from .replay import SourcePolicy, file_sha, read_json, write_private
from .validation import _append, _exclusive, _private, prior_catalog, verify_protocol

VERSION = "development_staged_six_metadata_v1"
SEED = "staged-six-20261108-v1"
DECLARATIONS = {
    "permission",
    "unused_for_development",
    "distinct_physical_matches",
    "distinct_from_prior_physical_matches",
    "unedited_full_matches",
    "hash_verified_before_after_probe",
    "probe_format_stream_only",
}
FIELDS = {
    "path",
    "filename",
    "source_id",
    "size_bytes",
    "source_sha256",
    "duration_sec",
    "width",
    "height",
    "fps",
    "native_time_base",
    "video_codec",
    "physical_match_id",
}
RUN_FLAGS = {
    "coarse_seconds",
    "dense_seconds",
    "max_refinement_windows",
    "refinement_selection_policy",
    "refinement_padding_seconds",
    "report_view_bridge",
    "buy_clock_expiry",
    "provisional_map_roles",
    "active_clock_bridge",
    "return_display_tail",
    "buy_clock_tail",
    "retain_frames",
    "audit_sample_plan",
}
BOOLEAN_FLAGS = {
    "report_view_bridge",
    "buy_clock_expiry",
    "provisional_map_roles",
    "active_clock_bridge",
    "return_display_tail",
    "buy_clock_tail",
    "retain_frames",
}
FROZEN_FLAGS = RUN_FLAGS - {"retain_frames", "audit_sample_plan"}
RATIONAL_FLAGS = {"coarse_seconds", "dense_seconds", "refinement_padding_seconds"}


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _safe_name(value: Any) -> bool:
    return isinstance(value, str) and bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", value))


def _settings(value: dict[str, Any], protocol: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != RUN_FLAGS:
        raise ValueError("Every run_match sampling and feature flag must be frozen")
    if any(type(value[key]) is not bool for key in BOOLEAN_FLAGS):
        raise ValueError("Feature flags must be explicit booleans")
    if value["retain_frames"] or value["audit_sample_plan"] is not None:
        raise ValueError("No frame retention or source-conditioned audit plan on first use")
    try:
        coarse = Fraction(value["coarse_seconds"])
        dense = Fraction(value["dense_seconds"])
        padding = Fraction(value["refinement_padding_seconds"])
    except (TypeError, ValueError, ZeroDivisionError) as exc:
        raise ValueError("Exact rational sampling settings required") from exc
    if not 0 < dense < coarse <= 2 or not 0 <= padding <= 10:
        raise ValueError("Invalid observation cadence or padding")
    if type(value["max_refinement_windows"]) is not int or value["max_refinement_windows"] < 0:
        raise ValueError("Invalid refinement budget")
    if value["refinement_selection_policy"] not in {"chronological", "balanced"}:
        raise ValueError("Unknown refinement selection policy")
    frozen = protocol["settings"]
    if not isinstance(frozen, dict) or set(frozen) != FROZEN_FLAGS:
        raise ValueError("Frozen protocol must bind every runtime sampling and feature flag")
    for key in FROZEN_FLAGS:
        if key in RATIONAL_FLAGS:
            same = Fraction(value[key]) == Fraction(frozen[key])
        elif key in BOOLEAN_FLAGS:
            same = type(frozen[key]) is bool and value[key] is frozen[key]
        elif key == "max_refinement_windows":
            same = type(frozen[key]) is int and value[key] == frozen[key]
        else:
            same = value[key] == frozen[key]
        if not same:
            raise ValueError("Run settings disagree with frozen observer protocol")
    return {
        **value,
        "coarse_seconds": str(coarse),
        "dense_seconds": str(dense),
        "refinement_padding_seconds": str(padding),
    }


def _validate_metadata(record: dict[str, Any], prior: dict[str, Any]) -> None:
    if not isinstance(record, dict) or set(record) != FIELDS:
        raise ValueError("Only format/stream metadata and source identity are accepted")
    path = Path(record["path"])
    if (
        not path.is_absolute()
        or path.name != record["filename"]
        or not path.is_file()
        or path.is_symlink()
    ):
        raise ValueError("Existing regular source path and matching filename required")
    if str(path.resolve()) in prior["paths"]:
        raise ValueError("Source path already reserved")
    if not is_sha(record["source_sha256"]) or record["source_sha256"] in prior["hashes"]:
        raise ValueError("Invalid or previously reserved source hash")
    physical = record["physical_match_id"]
    if not _safe_name(physical) or physical.casefold() in prior["matches"]:
        raise ValueError("Invalid or previously reserved physical match")
    if type(record["size_bytes"]) is not int or record["size_bytes"] <= 0:
        raise ValueError("Positive source size required")
    if path.stat().st_size != record["size_bytes"]:
        raise ValueError("Source size changed since metadata probe")
    if any(type(record[k]) is not int or record[k] <= 0 for k in ("width", "height")):
        raise ValueError("Positive video dimensions required")
    try:
        duration, fps, base = (
            Fraction(record[k]) for k in ("duration_sec", "fps", "native_time_base")
        )
    except (TypeError, ValueError, ZeroDivisionError) as exc:
        raise ValueError("Exact positive duration, FPS and time base required") from exc
    if (
        min(duration, fps, base) <= 0
        or not isinstance(record["video_codec"], str)
        or not record["video_codec"]
    ):
        raise ValueError("Valid format/stream metadata required")


def register_six(
    *,
    declaration: Path,
    protocol: Path,
    registry: Path,
    batch_id: str,
    prior_registries: list[Path],
) -> dict[str, Any]:
    """Reserve six reported Sources without reading a single media byte."""
    registry = _private(registry)
    if not _safe_name(batch_id):
        raise ValueError("Safe batch identifier required")
    plan = verify_protocol(protocol)
    request = read_json(declaration)
    if (
        set(request) != {"version", "seed", "content_kind", "declarations", "records", "run_flags"}
        or request["version"] != VERSION
        or request["seed"] != SEED
        or request["content_kind"] != "VALORANT_FULL_MATCH"
        or not isinstance(request["declarations"], dict)
        or set(request["declarations"]) != DECLARATIONS
        or any(value is not True for value in request["declarations"].values())
        or not isinstance(request["records"], list)
        or len(request["records"]) != 6
    ):
        raise ValueError("Six authorized, unused, distinct full-match metadata records required")
    settings = _settings(request["run_flags"], plan)
    registry.mkdir(parents=True, exist_ok=True, mode=0o700)
    with _exclusive(registry / ".staged_six.lock"):
        batch = _private(registry / batch_id)
        if batch.exists():
            raise ValueError("Batch already reserved; no overwrite")
        prior = prior_catalog([*prior_registries, registry])
        records = sorted(request["records"], key=lambda row: row["filename"])
        identifiers = [row["source_id"] for row in records]
        if (
            any(
                not _safe_name(sid) or not sid.endswith(f"_{i:03d}")
                for i, sid in enumerate(identifiers, start=1)
            )
            or len({sid.casefold() for sid in identifiers}) != 6
            or any(sid.casefold() in prior["ids"] for sid in identifiers)
        ):
            raise ValueError("Unique Source IDs must follow filename order 001..006")
        filenames = [r["filename"].casefold() for r in records]
        hashes = [r["source_sha256"] for r in records]
        physicals = [r["physical_match_id"].casefold() for r in records]
        paths = [str(Path(r["path"]).resolve()) for r in records]
        if any(len(set(values)) != 6 for values in (filenames, hashes, physicals, paths)):
            raise ValueError("All six filenames, hashes, paths and physical matches must differ")
        for row in records:
            _validate_metadata(row, prior)
        ranked = sorted(
            hashes,
            key=lambda sha: (hashlib.sha256(f"{SEED}{sha}".encode("ascii")).hexdigest(), sha),
        )
        split = {
            sha: ("DEVELOPMENT" if i < 2 else "QUALIFICATION" if i < 4 else "FINAL_HOLDOUT")
            for i, sha in enumerate(ranked)
        }
        first = next(sha for sha in ranked if split[sha] == "DEVELOPMENT")
        reserved = [
            {
                **row,
                "video_id": row["source_id"],
                "split": split[row["source_sha256"]],
                "exposure": "UNEXPOSED_AT_REGISTRATION",
                "status": "reserved",
                "original_path": str(Path(row["path"]).resolve()),
            }
            for i, row in enumerate(records, start=1)
        ]
        allocation = {
            "version": VERSION,
            "seed": SEED,
            "content_kind": "VALORANT_FULL_MATCH",
            "declarations": request["declarations"],
            "records": reserved,
            "first_development_source_id": next(
                r["video_id"] for r in reserved if r["source_sha256"] == first
            ),
            "future_five_order": [
                next(r["video_id"] for r in reserved if r["source_sha256"] == sha)
                for sha in ranked
                if sha != first
            ],
            "protocol": str(protocol.resolve()),
            "protocol_sha256": file_sha(protocol),
            "run_flags": settings,
            "prior_anchors": prior["anchors"],
            "metadata_only": True,
            "media_bytes_read_by_registration": 0,
            "formal_outputs": 0,
            "qualification": "NOT_EVALUATED",
            "created_at_utc": _now(),
        }
        batch.mkdir(mode=0o700)
        write_private(batch / "allocation.json", allocation)
        return allocation


def _load_batch(batch: Path) -> dict[str, Any]:
    batch = _private(batch)
    allocation: dict[str, Any] = read_json(batch / "allocation.json")
    if allocation.get("version") != VERSION or len(allocation["records"]) != 6:
        raise ValueError("Staged six-source allocation required")
    protocol = Path(allocation["protocol"])
    if file_sha(protocol) != allocation["protocol_sha256"]:
        raise ValueError("Frozen protocol changed")
    _settings(allocation["run_flags"], verify_protocol(protocol))
    return allocation


def _verify_active_runtime(protocol: dict[str, Any]) -> None:
    """The currently imported temporal tree must match the old frozen runtime."""
    current = Path(__file__).parent
    frozen = protocol.get("runtime_sha256s", {})
    temporal = {
        Path(path).name: sha for path, sha in frozen.items() if Path(path).parent.name == "temporal"
    }
    if not temporal or "match.py" not in temporal or "replay.py" not in temporal:
        raise ValueError("Frozen temporal runtime hashes required")
    if any(
        not (current / name).is_file() or file_sha(current / name) != sha
        for name, sha in temporal.items()
    ):
        raise ValueError("Active temporal runtime differs from frozen old recognizer")


def activate_first_development(batch: Path) -> Path:
    """Create a single-source policy; five future Sources remain protected."""
    batch = _private(batch)
    with _exclusive(batch / ".activation.lock"):
        allocation = _load_batch(batch)
        activation = batch / "first_development"
        if activation.exists():
            raise ValueError("First activation already exists")
        first_id = allocation["first_development_source_id"]
        records = []
        for row in allocation["records"]:
            current = row["video_id"] == first_id
            records.append(
                {
                    **row,
                    "status": "accepted" if current else "protected",
                    "exposure": "DEVELOPMENT" if current else "UNEXPOSED_AT_REGISTRATION",
                    "managed_path": row["original_path"],
                }
            )
        allowed = [r["source_sha256"] for r in records if r["video_id"] == first_id]
        protected = [r["source_sha256"] for r in records if r["video_id"] != first_id]
        activation.mkdir(mode=0o700)
        manifest = {
            "version": VERSION,
            "allocation_sha256": file_sha(batch / "allocation.json"),
            "records": records,
            "formal_outputs": 0,
            "qualification": "development_only",
        }
        write_private(activation / "manifest.json", manifest)
        policy_path = activation / "policy_PRIVATE.json"
        write_private(
            policy_path,
            {
                "manifest": str(activation / "manifest.json"),
                "allocation": str(batch / "allocation.json"),
                "manifest_sha256": file_sha(activation / "manifest.json"),
                "allocation_sha256": file_sha(batch / "allocation.json"),
                "allowed_source_sha256s": allowed,
                "protected_source_sha256s": protected,
            },
        )
        SourcePolicy(read_json(policy_path))
        _append(
            batch / "attempts_PRIVATE.jsonl",
            {
                "kind": "first_development_activated",
                "source_id": first_id,
                "policy_sha256": file_sha(policy_path),
                "at_utc": _now(),
            },
        )
        return policy_path


def confirm_pilot(
    *, batch: Path, pilot_receipt_sha256: str, pilot_check: Path, review: dict[str, Any]
) -> Path:
    """Record a separate human/operator go/no-go after examining the pilot."""
    batch, pilot_check = _private(batch), _private(pilot_check)
    required = {
        "input_integrity_checked",
        "candidate_output_checked",
        "pilot_timeline_checked",
        "proceed_to_full",
    }
    if (
        not is_sha(pilot_receipt_sha256)
        or not isinstance(review, dict)
        or set(review) != required
        or any(v is not True for v in review.values())
    ):
        raise ValueError("Explicit positive pilot inspection required")
    with _exclusive(batch / ".first_use.lock"):
        allocation = _load_batch(batch)
        receipt = batch / "first_pilot_prediction_receipt_PRIVATE.json"
        if not receipt.exists() or file_sha(receipt) != pilot_receipt_sha256:
            raise ValueError("Exact preserved pilot receipt required")
        value = read_json(receipt)
        if (
            file_sha(Path(value["timeline_path"])) != value["timeline_sha256"]
            or file_sha(Path(value["completion_path"])) != value["completion_sha256"]
        ):
            raise ValueError("Pilot prediction or completion changed")
        checked = read_json(pilot_check)
        expected_source_sha = next(
            r["source_sha256"] for r in allocation["records"] if r["video_id"] == value["source_id"]
        )
        if (
            checked.get("source_id") != value["source_id"]
            or checked.get("source_sha256") != expected_source_sha
            or checked.get("first_pilot_receipt_sha256") != pilot_receipt_sha256
            or checked.get("acquisition_receipt_sha256") != value["completion_sha256"]
        ):
            raise ValueError("Pilot check must bind the same Source and preserved prediction")
        if (
            checked.get("processing") != "COMPLETE_WITH_INFORMATION"
            or checked.get("structural_pass") is not True
            or checked.get("JSON_CSV_content_equal") is not True
            or checked.get("evaluation_handoff") is not True
            or checked.get("formal_outputs") != 0
        ):
            raise ValueError("Informative, structurally checked pilot handoff required")
        destination = batch / "pilot_review_PRIVATE.json"
        write_private(
            destination,
            {
                "version": VERSION,
                "pilot_receipt_sha256": pilot_receipt_sha256,
                "pilot_check": str(pilot_check),
                "pilot_check_sha256": file_sha(pilot_check),
                "review": review,
                "at_utc": _now(),
                "scope": "structural go/no-go; no accuracy or qualification",
            },
        )
        _append(
            batch / "attempts_PRIVATE.jsonl",
            {
                "kind": "pilot_reviewed_for_full",
                "pilot_receipt_sha256": pilot_receipt_sha256,
                "review_sha256": file_sha(destination),
                "at_utc": _now(),
            },
        )
        return destination


def run_first(
    *, batch: Path, source_id: str, output: Path, phase: str, pilot_seconds: int = 120
) -> dict[str, Any]:
    """Run the frozen old recognizer once per phase, preserving first predictions.

    `phase=full` requires a completed pilot and its immutable prediction receipt.
    The caller must not use the policy directly to bypass this sequence.
    """
    from .match import run_match

    batch, output = _private(batch), _private(output)
    if (
        phase not in {"pilot", "full"}
        or type(pilot_seconds) is not int
        or not 0 < pilot_seconds <= 180
    ):
        raise ValueError("Bounded pilot or gated full phase required")
    with _exclusive(batch / ".first_use.lock"):
        allocation = _load_batch(batch)
        if source_id != allocation["first_development_source_id"]:
            raise ValueError("Only the first DEVELOPMENT Source may be used")
        policy_path = batch / "first_development/policy_PRIVATE.json"
        policy = SourcePolicy(read_json(policy_path))
        if {r["video_id"] for r in policy.allowed.values()} != {source_id}:
            raise ValueError("Single-source activation changed")
        if output.exists():
            raise ValueError("New private output required; never overwrite prediction")
        receipt_path = batch / f"first_{phase}_prediction_receipt_PRIVATE.json"
        if receipt_path.exists():
            raise ValueError("First prediction already preserved; no repeated first-use claim")
        if phase == "full":
            pilot = batch / "first_pilot_prediction_receipt_PRIVATE.json"
            if not pilot.exists():
                raise ValueError("Successful pilot and preserved first prediction required")
            pilot_receipt = read_json(pilot)
            review_path = batch / "pilot_review_PRIVATE.json"
            if not review_path.exists() or read_json(review_path)[
                "pilot_receipt_sha256"
            ] != file_sha(pilot):
                raise ValueError("Explicit successful pilot review required before full")
            pilot_review = read_json(review_path)
            if file_sha(Path(pilot_review["pilot_check"])) != pilot_review["pilot_check_sha256"]:
                raise ValueError("Pilot structural check changed")
            if (
                file_sha(Path(pilot_receipt["timeline_path"])) != pilot_receipt["timeline_sha256"]
                or file_sha(Path(pilot_receipt["completion_path"]))
                != pilot_receipt["completion_sha256"]
            ):
                raise ValueError("Pilot prediction changed")
        journal = batch / "attempts_PRIVATE.jsonl"
        if journal.exists() and any(
            e.get("kind") == "recognition_attempt_started" and e.get("phase") == phase
            for e in (json.loads(line) for line in journal.read_text(encoding="utf-8").splitlines())
        ):
            raise ValueError("Phase already attempted; preserve first-use failure")
        protocol_path = Path(allocation["protocol"])
        frozen = verify_protocol(protocol_path)
        _verify_active_runtime(frozen)
        settings = _settings(allocation["run_flags"], frozen)
        attempt = {
            "kind": "recognition_attempt_started",
            "source_id": source_id,
            "source_sha256": next(
                r["source_sha256"] for r in allocation["records"] if r["video_id"] == source_id
            ),
            "phase": phase,
            "output": str(output),
            "protocol_sha256": allocation["protocol_sha256"],
            "run_flags_sha256": hashlib.sha256(
                json.dumps(settings, sort_keys=True).encode("ascii")
            ).hexdigest(),
            "at_utc": _now(),
        }
        _append(journal, attempt)
        module, name = frozen["observer"].split(":", 1)
        # Observer import is resolved by the existing frozen-protocol verifier.
        import importlib

        factory = getattr(importlib.import_module(module), name)
        try:
            result = run_match(
                policy_path=policy_path,
                source_id=source_id,
                reader_config=Path(frozen["reader_config"]),
                output=output,
                observer_factory=factory,
                coarse_seconds=Fraction(settings["coarse_seconds"]),
                dense_seconds=Fraction(settings["dense_seconds"]),
                max_refinement_windows=settings["max_refinement_windows"],
                refinement_selection_policy=settings["refinement_selection_policy"],
                refinement_padding_seconds=Fraction(settings["refinement_padding_seconds"]),
                report_view_bridge=settings["report_view_bridge"],
                buy_clock_expiry=settings["buy_clock_expiry"],
                provisional_map_roles=settings["provisional_map_roles"],
                active_clock_bridge=settings["active_clock_bridge"],
                return_display_tail=settings["return_display_tail"],
                buy_clock_tail=settings["buy_clock_tail"],
                retain_frames=False,
                audit_sample_plan=None,
                stop_after=pilot_seconds if phase == "pilot" else None,
            )
            verify_protocol(protocol_path)
            timeline = output / "timeline_PRIVATE.json"
            receipt = {
                "kind": "first_prediction_preserved",
                "phase": phase,
                "source_id": source_id,
                "timeline_path": str(timeline),
                "timeline_sha256": file_sha(timeline),
                "completion_path": str(output / "completion_PRIVATE.json"),
                "completion_sha256": file_sha(output / "completion_PRIVATE.json"),
                "protocol_sha256": allocation["protocol_sha256"],
                "run_flags": settings,
                "at_utc": _now(),
                "formal_outputs": 0,
                "accuracy": None,
            }
            write_private(receipt_path, receipt)
            _append(
                journal,
                {
                    **attempt,
                    "kind": "recognition_attempt_finished",
                    "status": "completed",
                    "prediction_receipt_sha256": file_sha(receipt_path),
                    "at_utc": _now(),
                },
            )
            return result
        except Exception as exc:
            _append(
                journal,
                {
                    **attempt,
                    "kind": "recognition_attempt_finished",
                    "status": "failed",
                    "error_type": type(exc).__name__,
                    "at_utc": _now(),
                },
            )
            raise
