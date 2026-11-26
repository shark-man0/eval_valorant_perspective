"""Use the exact public Map atlas and registered polygons behind development points."""

from __future__ import annotations

import argparse
import hashlib
import math
import os
import struct
from pathlib import Path
from typing import Any

from .evidence import is_sha
from .replay import file_sha, read_json, write_private

_SCHEMA = "development_map_display_v1"
_PNG_HEADER = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
_MAX_ATLAS_BYTES = 12 * 1024 * 1024


def _png_dimensions(image: bytes) -> tuple[int, int]:
    if len(image) < 24 or not image.startswith(_PNG_HEADER):
        raise ValueError("A public PNG atlas is required")
    width, height = struct.unpack(">II", image[16:24])
    if not (1 <= width <= 8192 and 1 <= height <= 8192):
        raise ValueError("Invalid public atlas dimensions")
    return width, height


def _atlas(path: Path, sha: str) -> tuple[bytes, tuple[int, int]]:
    with path.open("rb") as stream:
        image = stream.read(_MAX_ATLAS_BYTES + 1)
    if len(image) > _MAX_ATLAS_BYTES or hashlib.sha256(image).hexdigest() != sha:
        raise ValueError("Public Map atlas hash mismatch")
    return image, _png_dimensions(image)


def _validate_polygons(polygons: Any, size: tuple[int, int]) -> None:
    width, height = size
    if not isinstance(polygons, dict):
        raise ValueError("Named Zone polygons must be supplied by the development registry")
    for name, ring in polygons.items():
        if not isinstance(name, str) or not name or not isinstance(ring, list) or len(ring) < 3:
            raise ValueError("Invalid Named Zone polygon")
        for point in ring:
            if (
                not isinstance(point, list) or len(point) != 2
                or any(type(v) not in (int, float) or not math.isfinite(v)
                       or not 0 <= v < lim for v, lim in zip(point, (width, height), strict=True))
            ):
                raise ValueError("Named Zone must use the public atlas coordinate space")


def _validate_zone_aliases(aliases: Any, polygons: dict[str, Any]) -> None:
    if not isinstance(aliases, dict) or any(
        alias not in polygons or not isinstance(parent, str) or parent not in polygons
        or parent in aliases for alias, parent in aliases.items()
    ):
        raise ValueError("Each additional Zone polygon must name its registered parent")


def prepare_map_display(report_path: Path, catalog_path: Path, zones_path: Path) -> Path:
    """Copy only content-matching public atlases, and bind their metadata to the Map report."""
    report = read_json(report_path)
    if report["qualified"] is not False or report["formal_outputs"] != 0:
        raise ValueError("A development Map report is required")
    if report.get("zone_catalog_sha256") != file_sha(zones_path):
        raise ValueError("Named Zone registry differs from the Map report")
    references = {(p["map_id"], p["reference_sha256"])
                  for segment in report["segments"] for p in segment}
    maps = {m["id"]: m for m in read_json(catalog_path)["maps"]}
    zones = {(z["map_id"], z["reference_sha256"]): z
             for z in read_json(zones_path)["maps"]}
    root = catalog_path.resolve().parent
    output = report_path.parent / "map_atlases"
    if any((p / ".git").exists() for p in (output.resolve(), *output.resolve().parents)):
        raise ValueError("Display artifacts must remain outside Git checkouts")
    output.mkdir(exist_ok=True, mode=0o700)
    records = []
    for map_id, sha in sorted(references):
        entry = maps.get(map_id)
        if entry is None:
            continue
        atlas = (root / entry["reference"]).resolve()
        if not atlas.is_relative_to(root) or not is_sha(sha):
            raise ValueError("Public atlas must be in the reference catalog")
        image, size = _atlas(atlas, sha)
        row = zones.get((map_id, sha), {})
        polygons, aliases = row.get("polygons", {}), row.get("plant_interior_aliases", {})
        _validate_polygons(polygons, size)
        _validate_zone_aliases(aliases, polygons)
        cached = output / f"{sha}.png"
        if cached.is_file():
            _atlas(cached, sha)
        else:
            fd = os.open(cached, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as file:
                file.write(image)
        records.append({"map_id": map_id, "map_name": entry["name"], "reference_sha256": sha,
                        "size": list(size), "zones": polygons,
                        **({"zone_aliases": aliases} if aliases else {})})
    path = report_path.with_suffix(".display.json")
    write_private(path, {"schema": _SCHEMA, "report_sha256": file_sha(report_path),
                         "atlases": records, "formal_outputs": 0})
    return path


def load_map_display(
    path: Path, report_path: Path, rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, bytes]]:
    """Serve only immutable atlas bytes referenced by observed positions."""
    manifest = read_json(path)
    if (manifest.get("schema") != _SCHEMA or manifest.get("formal_outputs") != 0
            or manifest.get("report_sha256") != file_sha(report_path)):
        raise ValueError("Map display manifest does not match the exact report")
    references = {(p["map_id"], p["reference_sha256"])
                  for row in rows for p in row["recorder_map_observations"]}
    assets: dict[str, bytes] = {}
    records = []
    seen = set()
    root = (path.parent / "map_atlases").resolve()
    for record in manifest["atlases"]:
        key = record["map_id"], record["reference_sha256"]
        if key in seen or key not in references or not is_sha(key[1]):
            raise ValueError("Unobserved or duplicate Map atlas")
        seen.add(key)
        sha = key[1]
        candidate = (root / f"{sha}.png").resolve()
        if not candidate.is_relative_to(root):
            raise ValueError("Atlas must be stored in the bound display bundle")
        image, size = _atlas(candidate, sha)
        if record["size"] != list(size):
            raise ValueError("Map display dimensions do not match the PNG")
        _validate_polygons(record["zones"], size)
        _validate_zone_aliases(record.get("zone_aliases", {}), record["zones"])
        assets[sha] = image
        records.append(record)
    return records, assets


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--zones", type=Path, required=True)
    args = parser.parse_args()
    prepare_map_display(args.report, args.catalog, args.zones)


if __name__ == "__main__":
    main()
