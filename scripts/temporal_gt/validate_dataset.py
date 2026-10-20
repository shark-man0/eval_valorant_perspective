"""Validate/freeze private temporal data; publish only anonymous counts and hashes.

No file is opened as an evaluation holdout by this CLI's authority. Curation and
prediction opening need separate journal entries. Freeze is not qualification.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.temporal_gt.contract import SCHEMA, ContractError, canonical_hash, require, validate
from valorant_ai_coach.video.native import _sha256

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "docs/temporal_gt/annotation_contract_v1.md"
POLICY = ROOT / "docs/temporal_gt/readiness_policy_v1.json"


def freeze_record(dataset: dict[str, Any]) -> dict[str, Any]:
    return {
        "version": "temporal-data-freeze-v1",
        "dataset_sha256": canonical_hash(dataset),
        "schema_sha256": _sha256(SCHEMA),
        "contract_sha256": _sha256(CONTRACT),
        "policy_sha256": _sha256(POLICY),
        "validator_sha256": _sha256(Path(__file__).with_name("contract.py")),
        "cli_sha256": _sha256(Path(__file__)),
        "recognition_executed": False,
        "formal_End_release": False,
    }


def check_freeze(dataset: dict[str, Any], path: Path, trusted_sha256: str) -> None:
    require(_sha256(path) == trusted_sha256, "external_freeze_anchor")
    require(
        json.loads(path.read_text(encoding="utf-8")) == freeze_record(dataset),
        "frozen_version_or_hash",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=["freeze", "validate"])
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--freeze", type=Path, required=True)
    parser.add_argument("--trusted-freeze-sha256")
    parser.add_argument("--public-report", type=Path)
    args = parser.parse_args()
    try:
        require(args.dataset.resolve() != args.freeze.resolve(), "distinct_freeze_path")
        if args.public_report is not None:
            require(
                args.public_report.resolve() not in {args.dataset.resolve(), args.freeze.resolve()},
                "distinct_report_path",
            )
        dataset = json.loads(args.dataset.read_text(encoding="utf-8"))
        if args.operation == "validate":
            require(args.trusted_freeze_sha256 is not None, "external_anchor_required")
            check_freeze(dataset, args.freeze, args.trusted_freeze_sha256)
        report = validate(dataset)
        if args.operation == "freeze":
            # Exclusive creation avoids silently replacing a prior sealed artifact.
            with args.freeze.open("x", encoding="utf-8") as stream:
                json.dump(freeze_record(dataset), stream, indent=2)
                stream.write("\n")
        report["freeze_sha256"] = _sha256(args.freeze)
        report["schema_sha256"] = _sha256(SCHEMA)
        report["contract_sha256"] = _sha256(CONTRACT)
        if args.public_report is not None:
            args.public_report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report))
    except (OSError, ValueError, KeyError, TypeError, ZeroDivisionError) as exc:
        # Do not echo paths, event IDs, label contents or exception tracebacks.
        rule = str(exc) if isinstance(exc, ContractError) else "input_or_io"
        print(json.dumps({"valid": False, "rule": rule, "formal_End_release": False}))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
