import json

import cv2
import numpy as np
import pytest

from scripts.diagnostics.probe_numeric_reader_connection import write_native_profile
from valorant_ai_coach.hud.numeric_regions import LOCATOR, LocalizedNumericReader
from valorant_ai_coach.hud.templates import HudTemplateProfile


def source_profile(tmp_path):
    root = tmp_path / "original"
    root.mkdir()
    layout = root / "hud_layout.json"
    layout.write_text("{}", encoding="utf-8")
    assert cv2.imwrite(str(root / "identity.png"), np.zeros((20, 20, 3), np.uint8))
    raw = {"schema_version": "1.0", "readers": {
        region: {"kind": "digits", "format": "timer_mmss" if region == "round_timer"
                 else "integer", "templates": {}, "minimum_confidence": .95}
        for region in ("round_timer", "ally_score", "enemy_score")},
        "signals": {"hp_hud_structure": {"roi": "player_hp_armor",
                                          "template": "identity.png"}}}
    path = layout.with_suffix(".templates.json")
    path.write_text(json.dumps(raw), encoding="utf-8")
    return layout, HudTemplateProfile.load(path)


def test_private_clone_preserves_original_and_identity_assets_without_qualification(tmp_path):
    layout, profile = source_profile(tmp_path)
    originals = {p: p.read_bytes() for p in (layout, profile.path, layout.parent / "identity.png")}
    target = write_native_profile(layout, profile, tmp_path / "new_candidate")
    clone = HudTemplateProfile.load(target.with_suffix(".templates.json"))
    assert target.read_bytes() == originals[layout]
    assert all(p.read_bytes() == content for p, content in originals.items())
    for region, reader in clone.build_readers().items():
        assert isinstance(reader, LocalizedNumericReader)
        assert reader.minimum == .95
        assert clone.raw["readers"][region]["numeric_region_locator"] == LOCATOR
    asset = clone.raw["signals"]["hp_hud_structure"]["template"]
    assert clone.resolve_asset(asset).read_bytes() == originals[layout.parent / "identity.png"]
    assert not target.with_name("hud_layout.global_qualification.json").exists()
    with pytest.raises(FileExistsError):
        write_native_profile(layout, profile, target.parent)


def test_invalid_source_contract_is_rejected_before_writing_a_candidate(tmp_path):
    layout, profile = source_profile(tmp_path)
    profile.raw["readers"]["round_timer"]["minimum_confidence"] = .89
    target = tmp_path / "rejected"
    with pytest.raises(ValueError):
        write_native_profile(layout, profile, target)
    assert not target.exists()
