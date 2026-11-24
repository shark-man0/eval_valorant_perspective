"""Export advisory planted-area polygons from pinned Map art and site callouts."""

import argparse
import hashlib
import math
from collections import Counter
from pathlib import Path

import cv2
import numpy as np

from valorant_ai_coach.knowledge import load_game_knowledge
from valorant_ai_coach.knowledge.assets import ReferenceAssets
from valorant_ai_coach.temporal.evidence import is_sha
from valorant_ai_coach.temporal.replay import read_json, write_private


def _paint_components(image):
    h, w = image.shape[:2]
    hsv = cv2.cvtColor(image[:, :, :3], cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, (20, 45, 150), (45, 150, 240))
    mask[image[:, :, 3] < 128] = 0
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask)
    retained = {
        i: int(stats[i, cv2.CC_STAT_AREA])
        for i in range(1, count) if stats[i, cv2.CC_STAT_AREA] >= h*w/1200
    }
    return labels, retained


def plant_footprints(image, anchors):
    if image.ndim != 3 or image.shape[2] != 4 or not anchors:
        return {}
    h, w = image.shape[:2]
    labels, retained = _paint_components(image)
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


def nearby_plant_footprints(image, anchors):
    """Recover shaded footprints whose published anchor is just outside the paint."""
    if image.ndim != 3 or image.shape[2] != 4 or not anchors:
        return {}
    h, w = image.shape[:2]
    labels, retained = _paint_components(image)
    sketches = {}
    for i, area in retained.items():
        contours, layout = cv2.findContours(
            np.uint8(labels == i), cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE,
        )
        if layout is None:
            continue
        exterior = [j for j, item in enumerate(layout[0]) if item[3] == -1]
        if len(exterior) != 1:
            continue
        outer = exterior[0]
        if sum(cv2.contourArea(c) for j, c in enumerate(contours) if j != outer) > area * .01:
            continue
        boundary = cv2.approxPolyDP(contours[outer], 1.0, True)
        if len(boundary) >= 3:
            sketches[i] = (area, boundary)
    if not sketches:
        return {}
    votes = {}
    for name, (x, y) in sorted(anchors.items()):
        if not (0 <= x < 1 and 0 <= y < 1):
            return {}
        ranked = sorted(
            (-cv2.pointPolygonTest(boundary, (x*w, y*h), True), i, area)
            for i, (area, boundary) in sketches.items()
        )
        distance, chosen, area = ranked[0]
        tolerance = min(.045*min(w, h), .45*math.sqrt(area))
        if distance <= tolerance and (
            len(ranked) == 1 or ranked[1][0] - distance > .5*math.sqrt(area)
        ):
            votes[name] = chosen
    counts = Counter(votes.values())
    return {
        f"{name} plant footprint": sketches[chosen][1].reshape(-1, 2).tolist()
        for name, chosen in votes.items()
        if counts[chosen] == 1
    }


def seeded_plant_cores(image, seeds):
    """Recover a contiguous interior patch around each reviewed atlas seed.

    A core lies entirely in the connected plant-colored pixels, so walls and
    disconnected pieces cannot be included by filling the outer contour.
    """
    if image.ndim != 3 or image.shape[2] != 4 or not seeds:
        return {}
    height, width = image.shape[:2]
    labels, retained = _paint_components(image)
    result = {}
    used = set()
    for site, (x, y) in sorted(seeds.items()):
        if not (0 <= x < 1 and 0 <= y < 1):
            return {}
        px, py = int(x * width), int(y * height)
        identity = int(labels[py, px])
        if identity not in retained or identity in used:
            return {}
        used.add(identity)
        mask = labels == identity
        row_limits = {}
        for direction in (-1, 1):
            for row in range(py, -1 if direction < 0 else height, direction):
                if not mask[row, px]:
                    break
                west = np.flatnonzero(~mask[row, :px])
                east = np.flatnonzero(~mask[row, px+1:])
                row_limits[row] = (
                    int(west[-1]) + 1 if len(west) else 0,
                    px + int(east[0]) if len(east) else width - 1,
                )
        best = (0, px, py, px, py)
        top_left, top_right = 0, width - 1
        for top in range(py, min(row_limits) - 1, -1):
            lo, hi = row_limits[top]
            top_left, top_right = max(top_left, lo), min(top_right, hi)
            left, right = top_left, top_right
            for bottom in range(py, max(row_limits) + 1):
                lo, hi = row_limits[bottom]
                left, right = max(left, lo), min(right, hi)
                candidate = ((right - left) * (bottom - top), left, top, right, bottom)
                best = max(best, candidate)
        area, left, top, right, bottom = best
        if area < .15 * retained[identity] or min(right-left, bottom-top) < 12:
            return {}
        result[f"{site} plant core"] = [[left, top], [right, top], [right, bottom], [left, bottom]]
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ("asset-cache", "map-catalog", "output"):
        parser.add_argument(f"--{option}", required=True, type=Path)
    parser.add_argument("--existing", type=Path)
    parser.add_argument("--plant-core-seeds", type=Path)
    args = parser.parse_args()
    assets = ReferenceAssets.load(args.asset_cache)
    index = read_json(args.map_catalog)
    root = args.map_catalog.parent.resolve()
    by_map = {row["id"]: row for row in index["maps"]}
    records = read_json(args.existing)["maps"] if args.existing else []
    seeds = {}
    if args.plant_core_seeds is not None:
        source = read_json(args.plant_core_seeds)
        if source["schema"] != "development_atlas_plant_core_seeds_v1":
            raise ValueError("Known development plant-core seed schema required")
        for record in source["maps"]:
            if record["map_id"] in seeds or not is_sha(record["reference_sha256"]):
                raise ValueError("Unique exact references required for plant cores")
            seeds[record["map_id"]] = record
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
        image = assets.image(key)
        polygons = plant_footprints(image, anchors)
        method = "pinned_atlas_site_shading"
        if not polygons:
            polygons = nearby_plant_footprints(image, anchors)
            method = "pinned_atlas_site_shading_unique_nearby_anchor"
        seed = seeds.get(game_map.uuid)
        if not polygons and seed is not None:
            if (
                seed["reference_sha256"] != asset.sha256
                or set(seed["site_seeds_norm"]) != set(game_map.sites)
            ):
                raise ValueError("Plant-core seed must use the exact atlas and named sites")
            polygons = seeded_plant_cores(image, seed["site_seeds_norm"])
            method = "pinned_atlas_site_paint_interior"
        if polygons:
            records.append({"map_id": game_map.uuid, "reference_sha256": asset.sha256,
                            "polygons": polygons, "evidence": method})
    write_private(args.output, {"maps": records, "formal_outputs": 0})


if __name__ == "__main__":
    main()
