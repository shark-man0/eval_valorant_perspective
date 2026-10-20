"""Read-only, hash-bound transport replay; never new reader qualification.

Targets are diagnostic selectors only. No expected value enters production code.
The output contains observations, so keep it private under outputs/.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from tests.e2e.trace_adapter import to_e2e_trace
from valorant_ai_coach.events import EventSourceContract
from valorant_ai_coach.facts import FactBuilder
from valorant_ai_coach.hud.calibrate_temporal import _check_output_privacy
from valorant_ai_coach.hud.global_lifecycle import global_recognizer_fingerprint
from valorant_ai_coach.resources import resource_path
from valorant_ai_coach.rounds import RoundPackageBuilder
from valorant_ai_coach.schema_validation import SchemaValidator


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def recognition_context(raw_path: Path) -> tuple[dict[str, Any], list[Path]]:
    """Retain original run bindings without claiming to renew qualification."""
    metadata_path = raw_path.parent / "run_metadata.json"
    runtime_path = raw_path.parent / "runtime_summary.json"
    if not metadata_path.exists():
        return {"status": "unavailable; source qualification must be checked separately"}, []
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if metadata.get("input_hashes", {}).get(raw_path.name) != digest(raw_path):
        raise ValueError("original run metadata does not bind this raw artifact")
    files = [metadata_path]
    context = {"status": "original run bindings, not renewed qualification",
               "run_metadata": metadata}
    if runtime_path.exists():
        runtime = json.loads(runtime_path.read_text(encoding="utf-8"))
        context["original_input_fingerprint"] = runtime.get("input_fingerprint", {})
        files.append(runtime_path)
    return context, files


def replay(raw: dict[str, Any], targets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Project only real observations in their existing native package windows.

    Baseline means the unchanged aggregate admission predicate, not an old
    recognizer run. No lifecycle, round number, map, or visual fact is inferred.
    """
    builder = RoundPackageBuilder(
        contract=EventSourceContract.load(resource_path("config/event_source_contract_v1.json")),
        validator=SchemaValidator(),
    )
    result = []
    for target in targets:
        timestamp, radius = float(target["target_sec"]), float(target["tolerance_sec"])
        local = [o for o in raw["observations"] if abs(o["time_sec"] - timestamp) <= radius]
        stages: dict[str, Any] = {}
        for label in ("aggregate_admission", "field_admission"):
            packages = []
            for package in raw["round_packages"]:
                window = package["round_window"]
                rows = [o for o in local if window["start_sec"] <= o["time_sec"]
                        <= window["end_sec"]]
                if label == "aggregate_admission":
                    rows = [o for o in rows if o["quality"]["hud_confidence"] >= .65]
                projected = deepcopy(package)
                projected["state_snapshots"] = builder._state_snapshots(rows)
                # Report only newly snapshot-derived facts; raw facts are not
                # reclassified as evidence created by this projection.
                projected["deterministic_facts"] = []
                projected["events"] = []
                projected = FactBuilder().enrich(projected)
                SchemaValidator().validate_round_package(projected)
                packages.append(projected)
            trace = to_e2e_trace(SimpleNamespace(round_packages=packages, observations=local))
            stages[label] = {
                "snapshots": [s for p in packages for s in p["state_snapshots"]],
                "facts": [f for p in packages for f in p["deterministic_facts"]
                          if f.get("time_sec") is not None],
                "trace_snapshots": trace["snapshots"],
            }
        result.append({
            "assertion_id": target["assertion_id"],
            "source_observations": local,
            "package_windows": [p["round_window"] for p in raw["round_packages"]],
            "stages": stages,
            "missing_source": not local,
            "qualification_scope": "Producer acceptance only; not independent image correctness",
            "canonical_status": "not evaluated by this transport diagnostic",
        })
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", required=True, type=Path)
    parser.add_argument("--raw-sha256", required=True)
    parser.add_argument("--targets", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output already exists; preserve earlier evidence")
    _check_output_privacy(args.output.resolve())
    if digest(args.raw) != args.raw_sha256:
        parser.error("raw integrity mismatch")
    context, context_paths = recognition_context(args.raw)
    code_paths = (
        Path(__file__), Path("src/valorant_ai_coach/rounds/builder.py"),
        Path("src/valorant_ai_coach/facts/builder.py"), Path("tests/e2e/trace_adapter.py"),
    )
    inputs = {str(p): digest(p) for p in (args.raw, args.targets, *code_paths, *context_paths)}
    fingerprint = global_recognizer_fingerprint()
    started = time.perf_counter()
    raw = json.loads(args.raw.read_text(encoding="utf-8"))
    selectors = json.loads(args.targets.read_text(encoding="utf-8"))["targets"]
    # Deliberately discard expected values and assertion definitions.
    targets = [{k: r[k] for k in ("assertion_id", "target_sec", "tolerance_sec")}
               for r in selectors]
    rows = replay(raw, targets)
    if fingerprint != global_recognizer_fingerprint() or any(
        digest(Path(p)) != value for p, value in inputs.items()
    ):
        raise ValueError("terminal input/code mismatch")
    report = {
        "scope": "Saved-raw transport diagnostic; no new recognition or canonical run",
        "source_recognition_metadata": context,
        "input_sha256": inputs,
        "transport_recognizer_fingerprint": fingerprint,
        "historical_qualification_resigned": False,
        "targets": rows,
        "wall_sec": time.perf_counter() - started,
    }
    if sys.platform != "win32":
        import resource
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        report["peak_process_rss_mib"] = peak / (1024 ** 2 if sys.platform == "darwin" else 1024)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
    print(json.dumps({"targets": len(rows), "wall_sec": report["wall_sec"]}))


if __name__ == "__main__":
    main()
