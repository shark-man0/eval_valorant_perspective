"""Opt-in metadata for Riot's public VALORANT content catalog.

The catalog is external and versioned; callers provide its extracted directory.
This module neither downloads nor redistributes game assets.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PublicMapReference:
    name: str
    catalog_id: str
    catalog_version: str
    minimap_asset: Path
    x_scalar_to_add: float
    x_multiplier: float
    y_scalar_to_add: float
    y_multiplier: float

    def world_to_minimap_normalized(self, x: float, y: float) -> tuple[float, float] | None:
        """Apply catalog scalars when both axes are defined and finite.

        The returned point is only reference-image geometry, not a marker or
        player observation. A missing transform returns None.
        """
        if not math.isfinite(x) or not math.isfinite(y):
            raise ValueError("Finite world coordinates required")
        if self.x_multiplier == 0 or self.y_multiplier == 0:
            return None
        return (
            x * self.x_multiplier + self.x_scalar_to_add,
            y * self.y_multiplier + self.y_scalar_to_add,
        )


def load_public_map_references(
    catalog_json: Path, asset_root: Path
) -> dict[str, PublicMapReference]:
    """Load map metadata only from a caller supplied official catalog copy.

    Missing minimap images are skipped; labels alone cannot establish a usable
    visual reference. Results are keyed by the catalog's English map name.
    """
    catalog = json.loads(catalog_json.read_text(encoding="utf-8"))
    version = catalog["version"]
    if not isinstance(version, str) or not isinstance(catalog["maps"], list):
        raise ValueError("Invalid public content catalog")
    root = asset_root.resolve()
    result: dict[str, PublicMapReference] = {}
    for entry in catalog["maps"]:
        catalog_id = entry["id"]
        name = entry["name"]["defaultText"]
        if not isinstance(catalog_id, str) or not isinstance(name, str):
            raise ValueError("Invalid public map identity")
        asset = (root / "Maps" / f"{catalog_id}.png").resolve()
        if not asset.is_relative_to(root):
            raise ValueError("Public map asset escapes catalog root")
        if not asset.is_file():
            continue
        values = [
            float(entry[key])
            for key in ("xScalarToAdd", "xMultiplier", "yScalarToAdd", "yMultiplier")
        ]
        if not all(math.isfinite(value) for value in values):
            raise ValueError("Nonfinite public map transform")
        result[name] = PublicMapReference(name, catalog_id, version, asset, *values)
    return result
