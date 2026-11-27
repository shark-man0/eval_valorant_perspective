"""Build development Map position candidates for one recording (no formal Facts).

Inputs are the zoned canonical Map report (``apply_zones.py``), the timeline index
(``index_timeline.py``) whose ``input_sha256`` must equal the report's
``timeline_sha256``, the confirmed Rounds of the same recording (a match evaluation with
``formal_promotion.rounds``, built from the application bundle whose timeline SHA-256 the
caller has checked against the canonical timeline), the calibration file
(``calibrate_positions.py``), the Zone registry used for the report (for its
plant-interior aliases) and the game knowledge file (for the Map scale).
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from valorant_ai_coach.facts.map_position_promotion import MapGeometry, position_candidates


def _load(path: Path) -> Any:
    return json.loads(path.read_bytes().decode("utf-8"))


def confirmed_rounds(evaluation: dict[str, Any]) -> list[tuple[int, int, int]]:
    """Rounds whose start and end are both confirmed; a one-sided Round is left out."""
    rows = evaluation["formal_promotion"]["rounds"]
    return [(int(r["round_no"]), int(r["start"]["time_sec"]), int(r["end"]["time_sec"]))
            for r in rows if r.get("start") and r.get("end")]


def plant_aliases(registry: dict[str, Any]) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for entry in registry.get("maps", []):
        value = entry.get("plant_interior_aliases") or {}
        if isinstance(value, str):
            value = json.loads(value.replace("'", '"'))
        aliases.update(value)
    return aliases


def zone_polygons(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Zone polygons keyed by the exact reference image they are drawn on."""
    return {entry["reference_sha256"]: entry["polygons"] for entry in registry["maps"]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--evaluation", type=Path, required=True)
    parser.add_argument("--calibration", type=Path, required=True)
    parser.add_argument("--zones", type=Path, required=True)
    parser.add_argument("--knowledge", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    report = _load(args.report)
    index = _load(args.index)
    if report.get("timeline_sha256") != index.get("input_sha256"):
        raise SystemExit("report and timeline index do not belong to the same timeline")
    evaluation = _load(args.evaluation)
    if evaluation.get("source", {}).get("source_id") != index["source"]["source_id"]:
        raise SystemExit("confirmed Rounds come from another recording")
    registry = _load(args.zones)
    calibration_bytes = args.calibration.read_bytes()
    calibration = json.loads(calibration_bytes.decode("utf-8"))
    maps = {row[0]: row for row in _load(args.knowledge)["maps"]}
    map_id = report["segments"][0][0]["map_id"]
    row = maps[map_id]
    geometry = MapGeometry.from_knowledge(map_id, row[1], row[4])
    result = position_candidates(
        report, {"seconds": index["seconds"]}, confirmed_rounds(evaluation), geometry,
        calibration=calibration["confidence"], aliases=plant_aliases(registry),
        zones=zone_polygons(registry))
    result["provenance"] = {
        "report_sha256": hashlib.sha256(args.report.read_bytes()).hexdigest(),
        "evaluation_sha256": hashlib.sha256(args.evaluation.read_bytes()).hexdigest(),
        "calibration_sha256": hashlib.sha256(calibration_bytes).hexdigest(),
        "zones_sha256": hashlib.sha256(args.zones.read_bytes()).hexdigest(),
    }
    args.output.write_text(json.dumps(result, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
