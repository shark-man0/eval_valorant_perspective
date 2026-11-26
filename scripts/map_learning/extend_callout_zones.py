"""Add conservative development landmark interiors around published callout anchors."""

import argparse
from collections import Counter
from pathlib import Path

import cv2
import numpy as np

from valorant_ai_coach.knowledge import load_game_knowledge
from valorant_ai_coach.knowledge.assets import ReferenceAssets
from valorant_ai_coach.temporal.replay import file_sha, read_json, write_private


def _filled(atlas):
    return (atlas[:, :, 3] >= 252) & (atlas[:, :, :3].max(axis=2) >= 60)


def _aligned_revision(current, published):
    if current.shape != published.shape or current.shape[2] != 4:
        return None
    checks = []
    for alpha in (128, 252):
        a, b = (image[:, :, 3] >= alpha for image in (current, published))
        union = np.count_nonzero(a | b)
        if not union:
            return None
        overlap = np.count_nonzero(a & b) / union
        (dx, dy), confidence = cv2.phaseCorrelate(a.astype(np.float32), b.astype(np.float32))
        if not (overlap >= .90 and confidence >= .55 and np.hypot(dx, dy) <= .5):
            return None
        checks.append({"alpha": alpha, "overlap": overlap, "phase_response": confidence,
                       "offset_px": [dx, dy]})
    return checks


def landmark_interiors(atlas, anchors, existing, *, published=None):
    height, width = atlas.shape[:2]
    filled = _filled(atlas)
    if published is not None:
        filled &= _filled(published)
    interior = cv2.erode(filled.astype(np.uint8), np.ones((13, 13), np.uint8),
                         borderType=cv2.BORDER_CONSTANT, borderValue=0).astype(bool)
    _, components = cv2.connectedComponents(filled.astype(np.uint8))
    clearance = cv2.distanceTransform(filled.astype(np.uint8), cv2.DIST_C, 3)
    occupied = np.zeros((height, width), np.uint8)
    for polygon in existing.values():
        cv2.fillPoly(occupied, [np.asarray(polygon).round().astype(np.int32)], 1)
    names = Counter(label for label, _ in anchors)
    added = {}
    pixels = [(label, (round(x * width), round(y * height))) for label, (x, y) in anchors]
    for idx, (label, (x, y)) in enumerate(pixels):
        if (names[label] != 1 or label in existing or label.endswith(" Site")
                or not 0 <= x < width or not 0 <= y < height):
            continue
        other_distance = min((max(abs(x - xx), abs(y - yy))
                              for i, (_, (xx, yy)) in enumerate(pixels) if i != idx),
                             default=width)
        for radius in range(min(30, (other_distance - 10) // 2), 13, -2):
            left, top, right, bottom = x - radius, y - radius, x + radius, y + radius
            if left < 6 or top < 6 or right >= width - 6 or bottom >= height - 6:
                continue
            if (interior[top:bottom + 1, left:right + 1].all()
                    and not occupied[top - 6:bottom + 7, left - 6:right + 7].any()):
                added[label] = [[left, top], [right, top], [right, bottom], [left, bottom]]
                occupied[top:bottom + 1, left:right + 1] = 1
                break
        if label in added or not components[y, x] or other_distance < 44:
            continue
        # Some atlas revisions have thin transparent texture gaps near valid anchors.
        # Accept a smaller pocket only in the anchor's visible component.
        best = None
        for cy in range(max(y - 12, 13), min(y + 13, height - 13)):
            for cx in range(max(x - 12, 13), min(x + 13, width - 13)):
                distance = (cx - x) ** 2 + (cy - y) ** 2
                if (distance > 12**2 or clearance[cy, cx] < 14
                        or components[cy, cx] != components[y, x]
                        or occupied[cy - 13:cy + 14, cx - 13:cx + 14].any()):
                    continue
                option = (distance, -clearance[cy, cx], cx, cy)
                if best is None or option < best:
                    best = option
        if best is not None:
            _, _, cx, cy = best
            left, top, right, bottom = cx - 9, cy - 9, cx + 9, cy + 9
            added[label] = [[left, top], [right, top], [right, bottom], [left, bottom]]
            occupied[top:bottom + 1, left:right + 1] = 1
    return added


def extend(existing, catalog, asset_cache):
    registry, map_index = read_json(existing), read_json(catalog)
    if registry["formal_outputs"] != 0:
        raise ValueError("A development Zone registry is required")
    assets = ReferenceAssets.load(asset_cache)
    knowledge = load_game_knowledge()
    maps = {game_map.uuid: game_map for game_map in knowledge.maps}
    entries = {row["id"]: row["reference"] for row in map_index["maps"]}
    root = catalog.parent.resolve()
    transfers, skipped = [], []
    for row in registry["maps"]:
        uid = row["map_id"]
        key = f"map:{uid}:displayicon"
        if uid not in maps or uid not in entries or not assets.has(key):
            continue
        reference = (root / entries[uid]).resolve()
        if (not reference.is_relative_to(root)
                or file_sha(reference) != row["reference_sha256"]):
            raise ValueError("Landmark Zones require the exact registered reference image")
        published = assets.image(key)
        alignment = None
        if row["reference_sha256"] != assets.records[key].sha256:
            atlas = cv2.imdecode(np.fromfile(reference, np.uint8), cv2.IMREAD_UNCHANGED)
            alignment = _aligned_revision(atlas, published) if atlas is not None else None
            if not alignment:
                skipped.append(uid)
                continue
        else:
            atlas = published
        anchors = [(callout.label, callout.minimap_xy) for callout in maps[uid].callouts]
        added = landmark_interiors(atlas, anchors, row["polygons"],
                                   published=published if alignment else None)
        row["polygons"].update(added)
        if added:
            transfers.append({
                "map_id": uid, "reference_sha256": row["reference_sha256"],
                "registered_interiors": sorted(added),
                "published_reference_sha256": assets.records[key].sha256,
                "reference_alignment": alignment,
            })
    if not transfers:
        raise ValueError("No landmark area passed the geometry checks")
    registry["named_landmark_interiors"] = {
        "qualification": "development_only",
        "base_registry_sha256": file_sha(existing),
        "knowledge_asset_digest": assets.content_digest,
        "knowledge_game_version": knowledge.game_version,
        "maps": transfers, "unverified_references": skipped,
    }
    return registry


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("existing", "catalog", "asset-cache", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    write_private(args.output, extend(args.existing, args.catalog, args.asset_cache))


if __name__ == "__main__":
    main()
