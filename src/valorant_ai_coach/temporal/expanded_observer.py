"""Development composition of existing HUD, menu geometry and generic Map pixels.

Only suppliers are combined. The common game engine remains the state owner.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from .evidence import digest
from .generic_map_provider import GenericMapObserver
from .menu_geometry import MenuGeometrySupplementObserver
from .replay import file_sha, read_json


class ExpandedDevelopmentObserver:
    def __init__(self, config_path: Path) -> None:
        config = read_json(config_path)
        if set(config) != {"menu_config", "map_config"}:
            raise ValueError("Explicit menu and generic Map supplier configurations required")
        self.parent = MenuGeometrySupplementObserver(Path(config["menu_config"]))
        self.map = GenericMapObserver(Path(config["map_config"]))
        suppliers = self.parent.bindings["supplier_producer_fingerprints"]
        self.bindings = {
            "schema": "development_expanded_suppliers_v1",
            "parent": self.parent.bindings,
            "map": self.map.bindings,
            "config_sha256": file_sha(config_path),
            "code_sha256": file_sha(Path(__file__)),
            "parent_fingerprint": self.parent.fingerprint,
            "map_fingerprint": self.map.fingerprint,
            "baseline_producer_fingerprints": self.parent.bindings[
                "baseline_producer_fingerprints"
            ],
            "supplier_producer_fingerprints": [*suppliers, self.map.fingerprint],
            "map_reader_status": "CONFIGURED_DEVELOPMENT_CANDIDATES",
            "formal_authority": False,
        }
        self.fingerprint = digest(self.bindings)

    def inspect(self, image: NDArray[np.uint8]) -> dict[str, Any]:
        result = deepcopy(self.parent.inspect(image))
        supplied = self.map.inspect(image)
        result["supplier_observations"].append(
            {**supplied, "producer_fingerprint": self.map.fingerprint}
        )
        # Sampling hints only. Original suppliers retain sole observation evidence.
        result["map_candidates"] = [*result.get("map_candidates", []), *supplied["map_candidates"]]
        menu = next(
            row
            for row in result["supplier_observations"]
            if row.get("context", {}).get("stream_kind") == "hud_menu_geometry"
        )
        result.setdefault("context", {})["menu_grid_candidate"] = menu["raw"][
            "menu_grid_measurement"
        ]["supported"]
        return result
