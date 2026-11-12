from copy import deepcopy
from types import SimpleNamespace

import numpy as np
import pytest

from valorant_ai_coach.hud.readers import ReaderResult
from valorant_ai_coach.temporal.application import _hud
from valorant_ai_coach.temporal.inventory_labels import InventoryLabelReader
from valorant_ai_coach.temporal.match import frame_observations
from valorant_ai_coach.temporal.value_provider import ValueSupplementObserver


def test_factory_declares_every_native_supplier_for_transport(tmp_path, monkeypatch):
    import json
    from types import ModuleType

    import valorant_ai_coach.temporal.value_provider as module

    binary = tmp_path / "OCR"
    binary.write_bytes(b"synthetic")
    for name in ("jpn", "eng"):
        (tmp_path / (name + ".traineddata")).write_bytes(b"synthetic")
    parent = SimpleNamespace(bindings={"supplier_producer_fingerprints": ["a"*64, "b"*64]},
                             fingerprint="c"*64)
    imported = ModuleType("synthetic_parent")
    imported.Observer = lambda _: parent
    monkeypatch.setattr(module.importlib, "import_module", lambda _: imported)
    monkeypatch.setattr(module, "ProfileHudObserver", lambda _: SimpleNamespace(
        bindings={}, analyzer=SimpleNamespace(readers={})))
    monkeypatch.setattr(module, "TesseractTextReader", lambda **_: SimpleNamespace(
        executable=str(binary), diagnostics=[]))
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({"parent_observer": "synthetic_parent:Observer",
        "parent_config": "synthetic", "value_reader_config": "synthetic",
        "inventory_labels": {"A": "A"}, "tessdata": str(tmp_path)}), encoding="utf-8")
    observer = ValueSupplementObserver(cfg)
    assert observer.bindings["baseline_producer_fingerprints"] == ["a"*64, "b"*64]
    assert observer.bindings["supplier_producer_fingerprints"] == [
        "a"*64, "b"*64, observer.value_fingerprint]
    assert observer.bindings["fields"] == [
        "armor", "weapon", "ammo_current", "ammo_reserve", "credits"]


def image():
    value = np.zeros((200, 100, 3), np.uint8)
    value[30:40, 30:70] = 255
    value[90:100, 30:70] = 255
    return value


class Text:
    def __init__(self, results):
        self.results = iter(results)

    def read(self, _image, _roi):
        text, confidence = next(self.results)
        return ReaderResult(text, confidence, ("synthetic_OCR",))


@pytest.mark.parametrize("other", ["skin name", "prefix 武器A suffix", "unread"])
def test_exact_alias_only_and_rejected_lines_are_retained(other):
    reader = InventoryLabelReader(Text([(" 武器 A ", .96), (other, .98)]), {"武器A": "A"})
    value = reader.read(image(), image())
    assert value.value == "A" and value.confidence == .96
    assert "selected_weapon_unresolved" in value.sources
    assert len(reader.last_attempts) == 2 and not reader.last_attempts[1]["accepted"]


def test_competing_accepted_labels_abstain_and_low_confidence_is_not_evidence():
    reader = InventoryLabelReader(Text([("A", .96), ("B", .97)]), {"A": "A", "B": "B"})
    assert reader.read(image(), image()).value is None
    reader = InventoryLabelReader(Text([("A", .8), ("B", .89)]), {"A": "A", "B": "B"})
    assert reader.read(image(), image()).value is None
    with pytest.raises(ValueError, match="Duplicate"):
        InventoryLabelReader(Text([]), {"A": "A", " a ": "B"})


def test_composite_does_not_mutate_parent_or_add_state_claims():
    parent = {"signals": ["active"], "raw": {"current": True}, "context": {},
              "map_candidates": [], "supplier_observations": [{
                  "producer_fingerprint": "a"*64, "signals": ["active"], "raw": {},
                  "context": {}, "map_candidates": []}]}
    saved = deepcopy(parent)
    observer = object.__new__(ValueSupplementObserver)
    observer.parent = SimpleNamespace(inspect=lambda _: parent)
    observer.value_fingerprint = "b"*64
    observer.inspect_values = lambda _: {"signals": [], "map_candidates": [], "context": {},
        "raw": {"hud_value_measurements": [{"name": "weapon", "value": "A",
                    "confidence": .97, "status": "CANDIDATE",
                    "current_weapon_selection": "UNKNOWN",
                    "value_scope": "visible_inventory_label"}]}}
    result = observer.inspect(image())
    assert parent == saved
    assert result["supplier_observations"][:-1] == parent["supplier_observations"]
    assert result["signals"] == parent["signals"]
    from test_shared_game_timeline import obs
    rows = frame_observations(result, obs(0)["sample"], "c"*64)
    assert rows[-1]["signals"] == [] and rows[-1]["map_candidates"] == []
    candidate = _hud(rows)["weapon"]["candidates"][0]
    assert candidate["current_weapon_selection"] == "UNKNOWN"
    assert candidate["subject"] == "viewed_HUD; recorder_ownership_unresolved"


def test_supplement_retains_missing_ammo_and_credits_without_inventing_values():
    observer = object.__new__(ValueSupplementObserver)
    observer.inventory = SimpleNamespace(last_attempts=[])
    measured = [
        {"name": name, "status": "UNKNOWN", "value": None,
         "reason": "unconfigured_reader_or_roi"}
        for name in ("hp", "armor", "weapon", "ammo_current", "ammo_reserve", "credits")
    ]
    observer.values = SimpleNamespace(inspect_values=lambda _: {
        "raw": {"hud_value_measurements": measured}})
    result = observer.inspect_values(image())
    assert [m["name"] for m in result["raw"]["hud_value_measurements"]] == [
        "armor", "weapon", "ammo_current", "ammo_reserve", "credits"]
    assert all(m["status"] == "UNKNOWN" and m["value"] is None
               for m in result["raw"]["hud_value_measurements"])
    assert observer.inventory.last_attempts == []
