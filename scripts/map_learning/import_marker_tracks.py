"""Attach a verified development tracker portfolio to the exact original Map results."""

from __future__ import annotations

import argparse
from pathlib import Path

from valorant_ai_coach.application.map_library import attach_map_tracker, list_map_packages
from valorant_ai_coach.temporal.replay import file_sha, read_json


def import_portfolio(library: Path, portfolio: Path) -> tuple[int, int]:
    data = read_json(portfolio)
    if (data.get("schema") != "development_map_multi_marker_portfolio_v1"
            or data.get("formal_outputs") != 0):
        raise ValueError("A development-only multi-marker portfolio is required")
    parents, attached = {}, set()
    for entry in list_map_packages(library, all_versions=True):
        artifacts = read_json(entry.receipt)["artifacts"]
        bundle = artifacts["bundle"]["sha256"]
        if "tracked" in artifacts:
            attached.add((bundle, artifacts["tracked"]["sha256"]))
        else:
            for mode in ("recovered", "standard"):
                parents[bundle, artifacts[mode]["sha256"]] = entry.receipt
    imported, missing = 0, 0
    for entry in data["recordings"]:
        artifact = entry["candidate"]
        report = Path(artifact["path"])
        if not report.is_absolute():
            report = portfolio.parent / report
        if file_sha(report) != artifact["sha256"]:
            raise ValueError("The tracker portfolio contains a changed report")
        source = read_json(report)["multi_marker_replay"]["input_sha256s"]
        if (source["bundle"], artifact["sha256"]) in attached:
            imported += 1
            continue
        receipt = parents.get((source["bundle"], source["incumbent"]))
        if receipt is None:
            missing += 1
            continue
        attach_map_tracker(library, receipt, report)
        imported += 1
    return imported, missing


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--library", required=True, type=Path)
    parser.add_argument("--portfolio", required=True, type=Path)
    args = parser.parse_args()
    imported, missing = import_portfolio(args.library, args.portfolio.resolve())
    print(f"Tracking reports attached: {imported}; exact original results missing: {missing}")
    if missing:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
