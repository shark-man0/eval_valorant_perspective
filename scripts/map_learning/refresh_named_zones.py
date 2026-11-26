"""Re-evaluate verified library packages with new named Zones without opening video."""

import argparse
import os
from pathlib import Path
from tempfile import TemporaryDirectory

from valorant_ai_coach.application.map_library import (
    list_map_packages,
    publish_map_package,
    verified_map_package,
)
from valorant_ai_coach.application.timeline_evaluation import run as evaluate
from valorant_ai_coach.temporal.evidence import digest
from valorant_ai_coach.temporal.map_display import prepare_map_display
from valorant_ai_coach.temporal.map_recorder_path import (
    ReferenceZones,
    join_recorder_seconds,
    measured_native_edges,
)
from valorant_ai_coach.temporal.replay import file_sha, read_json, write_private


def with_new_zones(report, bundle, resolver):
    count = 0
    segments = []
    for segment in report["segments"]:
        amended = []
        for point in segment:
            if point["kind"] == "selected" and point.get("zone_candidate") is None:
                margin = max(4, point.get("fit_residual_p95_reference_px") or 0)
                zone = resolver.classify(point, margin_reference_px=margin)
                if zone is not None:
                    point = {**point, "zone_candidate": zone}
                    count += 1
            amended.append(point)
        segments.append(amended)
    result = {**report, "segments": segments}
    result["second_rows"] = join_recorder_seconds(result, bundle)
    if measured_native_edges(result) != measured_native_edges(report):
        raise ValueError("The added Zones changed measured trajectory edges")
    return result, count


def refresh(library, catalog, zones, output):
    output = output.resolve()
    if any((p / ".git").exists() for p in (output, *output.parents)):
        raise ValueError("Updated Map packages must stay outside Git checkouts")
    doc = read_json(zones)
    proof = doc["named_zone_transfer"]
    uid, names = proof["map_id"], proof["registered_interiors"]
    record, = [row for row in doc["maps"] if row["map_id"] == uid]
    if doc["formal_outputs"] != 0 or record["reference_sha256"] != proof["reference_sha256"]:
        raise ValueError("New named Zones must use their exact development atlas")
    resolver = ReferenceZones(uid, record["reference_sha256"],
                              {name: record["polygons"][name] for name in names})
    checksum = file_sha(zones)
    count, found = 0, 0
    for entry in list_map_packages(library):
        paths = verified_map_package(entry.receipt)
        display = read_json(paths["display"])
        if not any(row["map_id"] == uid and row["reference_sha256"] == proof["reference_sha256"]
                   for row in display["atlases"]):
            continue
        recovered = read_json(paths["recovered"])
        if recovered["zone_catalog_sha256"] == checksum:
            continue
        bundle = read_json(paths["bundle"])
        after, additions = with_new_zones(recovered, bundle, resolver)
        before, _ = with_new_zones(read_json(paths["standard"]), bundle, resolver)
        key = digest([file_sha(paths["recovered"]), file_sha(paths["standard"]), checksum])
        output.mkdir(mode=0o700, parents=True, exist_ok=True)
        root = output / key
        if not root.is_dir():
            with TemporaryDirectory(dir=output) as temporary:
                stage = Path(temporary) / key
                for mode, report in (("standard", before), ("recovered", after)):
                    report["zone_catalog_sha256"] = checksum
                    report["zone_overlay"] = {
                        "base_report_sha256": file_sha(paths[mode]),
                        "named_zone_transfer_sha256": checksum,
                    }
                    if mode == "recovered":
                        report["primary_report_sha256"] = file_sha(stage / "standard_PRIVATE.json")
                    write_private(stage / f"{mode}_PRIVATE.json", report)
                prepare_map_display(stage / "recovered_PRIVATE.json", catalog, zones)
                evaluate(timeline_path=paths["bundle"], output=stage / "evaluation",
                         match_id="map-development", promote=False,
                         development_map_path=stage / "recovered_PRIVATE.json")
                stage.rename(root)
        publish_map_package(
            library, label=entry.label, bundle=paths["bundle"], policy=paths["policy"],
            standard=root / "standard_PRIVATE.json", recovered=root / "recovered_PRIVATE.json",
            evaluation=root / "evaluation/match_evaluation_PRIVATE.json",
        )
        count += 1
        found += additions
    return count, found


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("library", "catalog", "zones", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    count, found = refresh(args.library, args.catalog, args.zones, args.output)
    print("Re-evaluated Map packages:", count, "/ New zone observations:", found)


if __name__ == "__main__":
    main()
