"""Export advisory planted-area polygons from pinned Map art and site callouts."""

import argparse
import hashlib
from pathlib import Path

import cv2
import numpy as np

from valorant_ai_coach.knowledge import load_game_knowledge
from valorant_ai_coach.knowledge.assets import ReferenceAssets
from valorant_ai_coach.temporal.replay import read_json, write_private


def plant_footprints(image, anchors):
    if image.ndim != 3 or image.shape[2] != 4 or not anchors:
        return {}
    h, w = image.shape[:2]
    hsv = cv2.cvtColor(image[:, :, :3], cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, (20, 45, 150), (45, 150, 240))
    mask[image[:, :, 3] < 128] = 0
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask)
    retained = {i for i in range(1, count) if stats[i, cv2.CC_STAT_AREA] >= h*w/1200}
    if len(retained) != len(anchors):
        return {}
    polygons = {}
    matched = set()
    for name, (x, y) in sorted(anchors.items()):
        if not (0 <= x < 1 and 0 <= y < 1):
            return {}
        component = labels[int(y*h), int(x*w)]
        if component not in retained or component in matched:
            return {}
        area = np.uint8(labels == component)
        outlines, _ = cv2.findContours(area, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if len(outlines) != 1:
            return {}
        polygon = cv2.approxPolyDP(outlines[0], 1.0, True)
        if cv2.pointPolygonTest(polygon, (x*w, y*h), True) <= 3:
            return {}
        matched.add(component)
        polygons[f"{name} plant footprint"] = polygon.reshape(-1, 2).tolist()
    return polygons


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ("asset-cache", "map-catalog", "output"):
        parser.add_argument(f"--{option}", required=True, type=Path)
    parser.add_argument("--existing", type=Path)
    args = parser.parse_args()
    assets = ReferenceAssets.load(args.asset_cache)
    index = read_json(args.map_catalog)
    root = args.map_catalog.parent.resolve()
    by_map = {row["id"]: row for row in index["maps"]}
    records = read_json(args.existing)["maps"] if args.existing else []
    retained = {row["map_id"] for row in records}
    for game_map in load_game_knowledge().maps:
        if game_map.uuid in retained or game_map.uuid not in by_map:
            continue
        key = f"map:{game_map.uuid}:displayicon"
        if not assets.has(key):
            continue
        asset = assets.records[key]
        path = (root / by_map[game_map.uuid]["reference"]).resolve()
        if (
            not path.is_relative_to(root) or not path.is_file()
            or hashlib.sha256(path.read_bytes()).hexdigest() != asset.sha256
        ):
            continue
        sites = [q for q in game_map.callouts if q.region == "Site"]
        anchors = {q.super_region: q.minimap_xy for q in sites}
        if len(sites) != len(anchors) or set(anchors) != set(game_map.sites):
            continue
        polygons = plant_footprints(assets.image(key), anchors)
        if polygons:
            records.append({"map_id": game_map.uuid, "reference_sha256": asset.sha256,
                            "polygons": polygons, "evidence": "pinned_atlas_site_shading"})
    write_private(args.output, {"maps": records, "formal_outputs": 0})


if __name__ == "__main__":
    main()
