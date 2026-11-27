"""Attach named Zone candidates to a canonical Map report with the existing path builder.

The points and their canonical samples are unchanged; ``build_recorder_paths`` classifies
each point against the Zone polygons of its exact reference image, as the Map library
does. The report keeps ``timeline_sha256`` and stays development-only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from valorant_ai_coach.temporal.map_recorder_path import (
    ReferenceZones,
    build_recorder_paths,
    join_recorder_seconds,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--zones", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    report = json.loads(args.report.read_text(encoding="utf-8"))
    index = json.loads(args.index.read_text(encoding="utf-8"))
    if report["timeline_sha256"] != index["input_sha256"]:
        raise SystemExit("The report and the index name different timelines")
    zones = [ReferenceZones(z["map_id"], z["reference_sha256"], z["polygons"])
             for z in json.loads(args.zones.read_text(encoding="utf-8"))["maps"]]
    rows: list[dict | None] = []
    for segment in report["segments"]:
        for point in segment:
            rows.append({k: v for k, v in point.items()
                         if k not in ("zone_candidate", "callout_candidate")})
        rows.append(None)
    paths = build_recorder_paths(rows, zones=zones)
    timeline = {"seconds": index["seconds"], "native_frames": index["native_frames"]}
    report.update(paths)
    report["second_rows"] = join_recorder_seconds(paths, timeline)
    report["zone_catalog_sha256"] = hashlib.sha256(args.zones.read_bytes()).hexdigest()
    args.output.write_text(json.dumps(report, separators=(",", ":")), encoding="utf-8")
    zoned = sum(1 for s in paths["segments"] for p in s if p.get("zone_candidate"))
    print(json.dumps({"points": sum(len(s) for s in paths["segments"]), "zoned_points": zoned}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
