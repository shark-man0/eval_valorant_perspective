"""Transfer conservative Summit non-site interiors from the existing v3 registry."""

import argparse
from pathlib import Path

import cv2
import numpy as np
from export_sites import _seeded_rectangle

from valorant_ai_coach.temporal.replay import file_sha, read_json, write_private

_KINDS = {"spawn", "connector", "transit", "site_approach"}


def _registration(old, atlas):
    detector = cv2.SIFT_create(nfeatures=1500, contrastThreshold=.006)
    enhancer = cv2.createCLAHE(2, (8, 8))
    inputs = [cv2.cvtColor(image[:, :, :3], cv2.COLOR_BGR2GRAY) for image in (old, atlas)]
    methods = (lambda image: image, enhancer.apply, lambda image: cv2.Canny(image, 40, 100))
    transforms, measurements = [], []
    for prepare in methods:
        (a, da), (b, db) = [detector.detectAndCompute(prepare(image), None) for image in inputs]
        if da is None or db is None:
            continue
        matches = [p for pair in cv2.BFMatcher().knnMatch(da, db, k=2)
                   if len(pair) == 2 for p, q in (pair,) if p.distance < .72*q.distance]
        if len(matches) < 12:
            continue
        x = np.float32([a[m.queryIdx].pt for m in matches])
        y = np.float32([b[m.trainIdx].pt for m in matches])
        matrix, mask = cv2.estimateAffinePartial2D(x, y, ransacReprojThreshold=4)
        if matrix is None or mask is None:
            continue
        inliers = mask.ravel().astype(bool)
        residuals = np.linalg.norm(x @ matrix[:, :2].T + matrix[:, 2] - y, axis=1)[inliers]
        span = cv2.contourArea(cv2.convexHull(x[inliers]))
        if len(residuals) < 12 or span < old.shape[0] * old.shape[1] * .10:
            continue
        p95 = float(np.quantile(residuals, .95))
        if p95 <= 4 and np.isfinite(matrix).all():
            transforms.append(matrix)
            measurements.append({"inliers": len(residuals), "residual_p95_reference_px": p95})
    if len(transforms) != len(methods):
        raise ValueError("The two Summit assets did not agree across all registration methods")
    matrix = np.median(transforms, axis=0)
    agreement = np.array([[38, 18, 1], [38, 422, 1], [430, 18, 1], [430, 422, 1]])
    worst = float(max(np.linalg.norm(agreement @ (v - matrix).T, axis=1).max()
                      for v in transforms))
    if worst > 6 or np.linalg.det(matrix[:, :2]) <= 0:
        raise ValueError("The Summit coordinate transfers disagree")
    return matrix, measurements, worst


def _interiors(atlas, definition, existing, matrix):
    height, width = atlas.shape[:2]
    occupied = np.zeros((height, width), np.uint8)
    for vertices in existing.values():
        cv2.fillPoly(occupied, [np.round(vertices).astype(np.int32)], 1)
    kernel = np.ones((13, 13), np.uint8)
    drawable = (atlas[:, :, 3] >= 252) & (atlas[:, :, :3].max(axis=2) >= 60)
    bounds = definition["coordinate_system"]["reference_map_mask_bbox_within_roi_px"]
    minx, miny, maxx, maxy = bounds
    new = {}
    for zone in definition["zones"]:
        if zone["kind"] not in _KINDS:
            continue
        points = np.asarray(zone["polygon_norm"]) * [maxx-minx, maxy-miny] + [minx, miny]
        path = points @ matrix[:, :2].T + matrix[:, 2]
        local = np.zeros_like(occupied)
        cv2.fillPoly(local, [path.round().astype(np.int32)], 1)
        mask = cv2.erode(np.uint8(drawable & (local != 0)), kernel).astype(bool)
        mask &= cv2.dilate(occupied, kernel) == 0
        _, depth, _, (px, py) = cv2.minMaxLoc(
            cv2.distanceTransform(mask.astype(np.uint8), cv2.DIST_L2, 5)
        )
        if depth < 14:
            continue
        size, left, top, right, bottom = _seeded_rectangle(mask, px, py)
        if size < 900 or min(right-left, bottom-top) < 24:
            continue
        if not mask[top:bottom + 1, left:right + 1].all():
            raise ValueError("A transferred Zone left its verified interior")
        name = zone["zone_name"]
        if name in existing or name in new:
            raise ValueError("A transferred Zone would replace an existing name")
        new[name] = [[left, top], [right, top], [right, bottom], [left, bottom]]
        occupied[top:bottom + 1, left:right + 1] = 1
    return new


def extend(existing, catalog, legacy):
    data, atlas_index = read_json(existing), read_json(catalog)
    zone_file = legacy / "config/maps/summit_map_v3.json"
    mask = read_json(legacy / "config/maps/summit_operational_mask_v1.json")
    old_path = legacy / mask["reference_asset"]
    atlas_entry, = [row for row in atlas_index["maps"] if row["name"] == "Summit"]
    row, = [row for row in data["maps"] if row["map_id"] == atlas_entry["id"]]
    atlas_path = (catalog.parent / atlas_entry["reference"]).resolve()
    if (data["formal_outputs"] != 0 or file_sha(old_path) != mask["reference_sha256"]
            or not atlas_path.is_relative_to(catalog.parent.resolve())
            or file_sha(atlas_path) != row["reference_sha256"]):
        raise ValueError("Both named Zone reference assets must match their pinned hashes")
    old, atlas = [cv2.imread(str(path), cv2.IMREAD_UNCHANGED) for path in (old_path, atlas_path)]
    if old is None or atlas is None or old.shape[2] != 4 or atlas.shape[2] != 4:
        raise ValueError("RGBA reference assets required")
    matrix, measurements, disagreement = _registration(old, atlas)
    added = _interiors(atlas, read_json(zone_file), row["polygons"], matrix)
    if not added:
        raise ValueError("No substantial Summit interior passed the transfer checks")
    row["polygons"].update(added)
    data["named_zone_transfer"] = {
        "qualification": "development_only", "base_registry_sha256": file_sha(existing),
        "source_reference_sha256": mask["reference_sha256"],
        "source_definition_sha256": file_sha(zone_file),
        "map_id": row["map_id"], "reference_sha256": row["reference_sha256"],
        "registered_interiors": sorted(added), "fit_checks": measurements,
        "maximum_fit_disagreement_reference_px": disagreement,
    }
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("existing", "catalog", "legacy", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    write_private(args.output, extend(args.existing, args.catalog, args.legacy))


if __name__ == "__main__":
    main()
