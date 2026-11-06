"""Attach opt-in configured values to an existing image observer, not a new FSM."""

from __future__ import annotations

import importlib
from copy import deepcopy
from pathlib import Path
from typing import Any

import numpy as np

from valorant_ai_coach.hud.templates import TesseractTextReader

from .evidence import digest
from .inventory_labels import InventoryLabelReader
from .match_observer import ProfileHudObserver
from .replay import file_sha, read_json


class ValueSupplementObserver:
    """Keep parent claims intact, append separately fingerprinted value evidence."""

    def __init__(self, path: Path) -> None:
        cfg = read_json(path)
        if set(cfg) != {"parent_observer", "parent_config", "value_reader_config",
                        "inventory_labels", "tessdata"}:
            raise ValueError("Explicit separate parent and value configuration required")
        module, name = cfg["parent_observer"].split(":")
        self.parent = getattr(importlib.import_module(module), name)(Path(cfg["parent_config"]))
        self.values = ProfileHudObserver(Path(cfg["value_reader_config"]))
        self.inventory = InventoryLabelReader(TesseractTextReader(
            language="jpn+eng", tessdata_dir=cfg["tessdata"], psm=7), cfg["inventory_labels"])
        if self.inventory.reader.diagnostics or self.inventory.reader.executable is None:
            raise ValueError("Configured inventory OCR languages required")
        self.values.analyzer.readers["weapon_inventory"] = self.inventory
        self.bindings = {"schema": "development_value_supplement_v2",
            "parent": self.parent.bindings, "parent_fingerprint": self.parent.fingerprint,
            "values": self.values.bindings, "configuration_sha256": file_sha(path),
            "aliases_sha256": digest(cfg["inventory_labels"]),
            "OCR_binary_sha256": file_sha(Path(self.inventory.reader.executable)),
            "language_assets_sha256": {n: file_sha(Path(cfg["tessdata"])/(n+".traineddata"))
                                        for n in ("jpn", "eng")},
            "code_sha256": file_sha(Path(__file__)),
            "inventory_code_sha256": file_sha(Path(__file__).with_name("inventory_labels.py")),
            "fields": ["armor", "weapon", "ammo_current", "ammo_reserve", "credits"],
            "state_authority": False}
        self.value_fingerprint = digest({k: v for k, v in self.bindings.items()
                                         if k not in {"parent", "parent_fingerprint"}})
        parent_suppliers = self.parent.bindings.get(
            "supplier_producer_fingerprints", [self.parent.fingerprint])
        self.bindings.update(
            baseline_producer_fingerprints=list(parent_suppliers),
            supplier_producer_fingerprints=[*parent_suppliers, self.value_fingerprint])
        self.fingerprint = digest(self.bindings)

    def inspect_values(self, image: np.ndarray) -> dict[str, Any]:
        self.inventory.last_attempts = []
        result = self.values.inspect_values(image)
        result["raw"]["hud_value_measurements"] = [
            m for m in result["raw"]["hud_value_measurements"]
            if m["name"] in {"armor", "weapon", "ammo_current", "ammo_reserve", "credits"}]
        for measured in result["raw"]["hud_value_measurements"]:
            if measured["name"] == "weapon":
                measured.update(value_scope="visible_inventory_label",
                                current_weapon_selection="UNKNOWN")
        result["raw"]["inventory_label_attempts"] = deepcopy(self.inventory.last_attempts)
        return result

    def inspect(self, image: np.ndarray) -> dict[str, Any]:
        parent: dict[str, Any] = self.parent.inspect(image)
        result = deepcopy(parent)
        values = self.inspect_values(image)
        suppliers = result.get("supplier_observations")
        if suppliers is None:
            suppliers = [{k: deepcopy(v) for k, v in parent.items()
                          if k in {"signals", "raw", "context", "map_candidates"}}]
            suppliers[0]["producer_fingerprint"] = self.parent.fingerprint
        result["supplier_observations"] = suppliers + [
            {**values, "producer_fingerprint": self.value_fingerprint}]
        return result
