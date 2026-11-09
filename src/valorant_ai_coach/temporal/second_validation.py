"""Activate and preserve the second reserved DEVELOPMENT recording only.

The original six-source allocation and first-use protocol remain immutable.
A new protocol and prior-development assessment are required before content use.
"""

from __future__ import annotations

import argparse
import importlib
import json
from datetime import UTC, datetime
from fractions import Fraction
from pathlib import Path
from typing import Any

from .replay import SourcePolicy, file_sha, read_json, write_private
from .staged_validation import (
    RUN_FLAGS,
    _settings,
    _verify_active_runtime,
)
from .validation import _append, _exclusive, _private, verify_protocol

EXTRA_FLAGS = {"current_hp_return_candidate", "current_menu_return_candidate"}


def _now() -> str:
    return datetime.now(UTC).isoformat()


def settings(protocol: dict[str, Any]) -> dict[str, Any]:
    frozen = protocol["settings"]
    old_flags = RUN_FLAGS - {"retain_frames", "audit_sample_plan"}
    if set(frozen) != old_flags | EXTRA_FLAGS or any(
        type(frozen[k]) is not bool for k in EXTRA_FLAGS
    ):
        raise ValueError("Every sampling and recognition flag must be frozen")
    old = {k: v for k, v in frozen.items() if k in old_flags}
    normalized = _settings(
        {**old, "retain_frames": False, "audit_sample_plan": None}, {"settings": old}
    )
    if any(frozen[k] for k in EXTRA_FLAGS) and not frozen["return_display_tail"]:
        raise ValueError("Return candidates require the existing offline return projection")
    return {**normalized, **{k: frozen[k] for k in EXTRA_FLAGS}}


def activate(*, batch: Path, protocol: Path, assessment: Path, allocation_sha256: str) -> Path:
    """Metadata-only admission; does not open any recording content."""
    batch, protocol, assessment = map(_private, (batch, protocol, assessment))
    with _exclusive(batch / ".second_activation.lock"):
        original = batch / "allocation.json"
        if file_sha(original) != allocation_sha256:
            raise ValueError("Original allocation changed")
        allocation = read_json(original)
        report = read_json(assessment)
        if (
            report.get("phase_1_to_4_complete") is not True
            or report.get("second_content_accesses") != 0
            or report.get("protected_content_accesses") != 0
            or report.get("protocol_sha256") != file_sha(protocol)
            or not report.get("evidence_sha256s")
        ):
            raise ValueError(
                "Completed prior-development assessment before second content required"
            )
        for name, sha in report["evidence_sha256s"].items():
            if file_sha(Path(name)) != sha:
                raise ValueError("Prior-development assessment evidence changed")
        frozen = verify_protocol(protocol)
        _verify_active_runtime(frozen)
        settings(frozen)
        first = batch / "first_full_prediction_receipt_PRIVATE.json"
        value = read_json(first)
        for path_key, sha_key in (
            ("timeline_path", "timeline_sha256"),
            ("completion_path", "completion_sha256"),
        ):
            if file_sha(Path(value[path_key])) != value[sha_key]:
                raise ValueError("First DEVELOPMENT prediction changed")
        selected = allocation["future_five_order"][0]
        records = allocation["records"]
        admitted = [r for r in records if r["video_id"] == selected]
        if (
            len(records) != 6
            or len(admitted) != 1
            or admitted[0]["split"] != "DEVELOPMENT"
            or admitted[0]["exposure"] != "UNEXPOSED_AT_REGISTRATION"
            or selected == allocation["first_development_source_id"]
            or sum(r["split"] == "DEVELOPMENT" for r in records) != 2
            or sum(r["split"] == "QUALIFICATION" for r in records) != 2
            or sum(r["split"] == "FINAL_HOLDOUT" for r in records) != 2
            or any(v is not True for v in allocation["declarations"].values())
        ):
            raise ValueError("Exactly the reserved second DEVELOPMENT Source required")
        stage = batch / "second_development"
        if stage.exists():
            raise ValueError("Second activation already exists; preserve first attempt")
        stage.mkdir(mode=0o700)
        manifest = {
            "records": [
                {
                    **r,
                    "managed_path": r["original_path"],
                    "status": "accepted" if r["video_id"] == selected else "protected",
                    "exposure": "DEVELOPMENT" if r["video_id"] == selected else r["exposure"],
                }
                for r in records
            ],
            "formal_outputs": 0,
        }
        write_private(stage / "manifest.json", manifest)
        policy = {
            "manifest": str(stage / "manifest.json"),
            "allocation": str(original),
            "manifest_sha256": file_sha(stage / "manifest.json"),
            "allocation_sha256": allocation_sha256,
            "allowed_source_sha256s": [admitted[0]["source_sha256"]],
            "protected_source_sha256s": [
                r["source_sha256"] for r in records if r["video_id"] != selected
            ],
        }
        write_private(stage / "policy_PRIVATE.json", policy)
        SourcePolicy(policy)
        write_private(
            stage / "stage_PRIVATE.json",
            {
                "source_id": selected,
                "source_sha256": admitted[0]["source_sha256"],
                "protocol": str(protocol),
                "protocol_sha256": file_sha(protocol),
                "assessment": str(assessment),
                "assessment_sha256": file_sha(assessment),
                "first_full_receipt": str(first),
                "first_full_receipt_sha256": file_sha(first),
                "original_first_policy_sha256": file_sha(
                    batch / "first_development/policy_PRIVATE.json"
                ),
                "policy_sha256": file_sha(stage / "policy_PRIVATE.json"),
                "at_utc": _now(),
                "protected_qualification_final_count": 4,
                "formal_outputs": 0,
            },
        )
        return stage


def _load(stage: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    value = read_json(stage / "stage_PRIVATE.json")
    for key in ("protocol", "assessment", "first_full_receipt"):
        if file_sha(Path(value[key])) != value[key + "_sha256"]:
            raise ValueError("Frozen second-stage dependency changed")
    if (
        file_sha(stage / "policy_PRIVATE.json") != value["policy_sha256"]
        or file_sha(stage.parent / "first_development/policy_PRIVATE.json")
        != value["original_first_policy_sha256"]
    ):
        raise ValueError("Source policy changed")
    policy = SourcePolicy(read_json(stage / "policy_PRIVATE.json"))
    if set(policy.allowed) != {value["source_sha256"]}:
        raise ValueError("Only the second DEVELOPMENT Source may be admitted")
    frozen = verify_protocol(Path(value["protocol"]))
    _verify_active_runtime(frozen)
    return value, frozen


def confirm(*, stage: Path, check: Path) -> Path:
    """Operator structural review, not a human semantic label or qualification."""
    stage, check = _private(stage), _private(check)
    with _exclusive(stage / ".run.lock"):
        value, _ = _load(stage)
        receipt = stage / "first_pilot_prediction_PRIVATE.json"
        pilot = read_json(receipt)
        checked = read_json(check)
        _prediction_intact(pilot)
        if (
            checked.get("first_pilot_receipt_sha256") != file_sha(receipt)
            or checked.get("source_id") != value["source_id"]
            or checked.get("source_sha256") != value["source_sha256"]
            or checked.get("acquisition_receipt_sha256") != pilot["completion_sha256"]
            or checked.get("processing") != "COMPLETE_WITH_INFORMATION"
            or checked.get("structural_pass") is not True
            or checked.get("JSON_CSV_content_equal") is not True
            or checked.get("evaluation_handoff") is not True
            or checked.get("formal_outputs") != 0
        ):
            raise ValueError(
                "Informative same-Source pilot with JSON/CSV/evaluation check required"
            )
        output = stage / "pilot_review_PRIVATE.json"
        write_private(
            output,
            {
                "pilot_receipt_sha256": file_sha(receipt),
                "check": str(check),
                "check_sha256": file_sha(check),
                "proceed_to_full": True,
                "scope": "operator structural inspection only; accuracy unmeasured",
                "at_utc": _now(),
            },
        )
        return output


def _prediction_intact(value: dict[str, Any]) -> None:
    for path_key, sha_key in (
        ("timeline_path", "timeline_sha256"),
        ("completion_path", "completion_sha256"),
    ):
        if file_sha(Path(value[path_key])) != value[sha_key]:
            raise ValueError("Preserved prediction changed")


def run(*, stage: Path, output: Path, phase: str, pilot_seconds: int = 120) -> dict[str, Any]:
    from .match import run_match

    stage, output = _private(stage), _private(output)
    if (
        phase not in {"pilot", "full"}
        or type(pilot_seconds) is not int
        or not 0 < pilot_seconds <= 180
    ):
        raise ValueError("Bounded pilot or gated full phase required")
    with _exclusive(stage / ".run.lock"):
        value, frozen = _load(stage)
        receipt = stage / f"first_{phase}_prediction_PRIVATE.json"
        started = stage / f"first_{phase}_started_PRIVATE.json"
        if output.exists() or receipt.exists() or started.exists():
            raise ValueError("First attempt already exists; never overwrite")
        if phase == "full":
            pilot = stage / "first_pilot_prediction_PRIVATE.json"
            review = read_json(stage / "pilot_review_PRIVATE.json")
            if (
                review["pilot_receipt_sha256"] != file_sha(pilot)
                or review["proceed_to_full"] is not True
                or file_sha(Path(review["check"])) != review["check_sha256"]
            ):
                raise ValueError("Preserved positive pilot review required")
            _prediction_intact(read_json(pilot))
        event = {
            "source_id": value["source_id"],
            "phase": phase,
            "output": str(output),
            "protocol_sha256": value["protocol_sha256"],
            "at_utc": _now(),
            "content_exposure_started": True,
        }
        write_private(started, event)
        _append(stage / "exposure_PRIVATE.jsonl", event)
        module, name = frozen["observer"].split(":", 1)
        args = settings(frozen)
        for key in ("coarse_seconds", "dense_seconds", "refinement_padding_seconds"):
            args[key] = Fraction(args[key])
        try:
            result = run_match(
                policy_path=stage / "policy_PRIVATE.json",
                source_id=value["source_id"],
                reader_config=Path(frozen["reader_config"]),
                output=output,
                observer_factory=getattr(importlib.import_module(module), name),
                stop_after=pilot_seconds if phase == "pilot" else None,
                **args,
            )
            _load(stage)
            write_private(
                receipt,
                {
                    **event,
                    "timeline_path": str(output / "timeline_PRIVATE.json"),
                    "timeline_sha256": file_sha(output / "timeline_PRIVATE.json"),
                    "completion_path": str(output / "completion_PRIVATE.json"),
                    "completion_sha256": file_sha(output / "completion_PRIVATE.json"),
                    "formal_outputs": 0,
                    "accuracy": None,
                },
            )
            return result
        except Exception as exc:
            _append(
                stage / "exposure_PRIVATE.jsonl",
                {
                    **event,
                    "status": "FAILED_INITIAL_ATTEMPT_PRESERVED",
                    "error_type": type(exc).__name__,
                    "detail": str(exc),
                },
            )
            raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    activation = commands.add_parser("activate")
    activation.add_argument("--batch", type=Path, required=True)
    activation.add_argument("--protocol", type=Path, required=True)
    activation.add_argument("--assessment", type=Path, required=True)
    activation.add_argument("--allocation-sha256", required=True)
    inspect = commands.add_parser("confirm")
    inspect.add_argument("--stage", type=Path, required=True)
    inspect.add_argument("--check", type=Path, required=True)
    execution = commands.add_parser("run")
    execution.add_argument("--stage", type=Path, required=True)
    execution.add_argument("--output", type=Path, required=True)
    execution.add_argument("--phase", choices=["pilot", "full"], required=True)
    execution.add_argument("--pilot-seconds", type=int, default=120)
    args = vars(parser.parse_args())
    command = args.pop("command")
    if command == "activate":
        result: Any = activate(**args)
    elif command == "confirm":
        result = confirm(**args)
    else:
        result = run(**args)
    print(json.dumps(result, default=str), flush=True)


if __name__ == "__main__":
    main()
