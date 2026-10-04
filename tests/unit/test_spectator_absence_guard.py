"""Current-frame safeguards for sparse-edge Spectator exclusion."""

from pathlib import Path

import cv2
import numpy as np
import pytest
from test_spectator_icon import _abstract_icon, _icon_layout, _icon_profile, _ordinary_slot

from valorant_ai_coach.hud.identity import live_identity
from valorant_ai_coach.hud.spectator_icon import detect_icon


def faded_icon(side="none", scale=0.125):
    icon = _abstract_icon().copy()
    fill = int(icon.mean())
    if side == "left":
        icon[:, : round(icon.shape[1] * 0.25)] = fill
    elif side == "bottom":
        icon[-round(icon.shape[0] * 0.25) :] = fill
    return np.clip(icon.mean() + scale * (icon.astype(float) - icon.mean()), 0, 255).astype(
        np.uint8
    )


@pytest.mark.parametrize("side", ["none", "left", "bottom"])
@pytest.mark.parametrize("scale", [0.125, 0.2])
def test_brightness_preserving_damaged_icon_cannot_prove_absence(side, scale):
    result = detect_icon(faded_icon(side, scale))
    assert result["panel_present"] is None
    assert result["checked"] is False
    assert result["reason"] == "icon_structure_ambiguous"


def test_low_contrast_icon_cannot_release_live_identity_gate():
    result = detect_icon(faded_icon())
    signals = {
        "hp_hud_structure": True,
        "hp_hud_structure_confidence": 0.99,
        "ability_bar_structure": True,
        "ability_bar_structure_confidence": 0.99,
        "weapon_ammo_structure": True,
        "weapon_ammo_structure_confidence": 0.99,
        "spectator_detector_checked": result["checked"],
        "spectator_panel_present": result["panel_present"],
        "spectator_panel_absent": result["panel_present"] is False and result["checked"],
    }
    assert live_identity(signals, geometry_valid=True).live is False


@pytest.mark.parametrize(
    "crop,expected", [(_ordinary_slot(), False), (_abstract_icon(), True), (faded_icon(), None)]
)
def test_global_scene_detail_cannot_override_current_local_icon_evidence(crop, expected):
    layout = _icon_layout()
    profile = _icon_profile(
        Path("unused.json"),
        {"version": 1, "roi": "spectator_icon", "method": "fixed_slot_structure_v1"},
    )
    frame = np.full((1080, 1920, 3), 70, np.uint8)
    x1, y1, x2, y2 = layout.normalized_roi("spectator_icon").pixel_bounds(1920, 1080)
    frame[y1:y2, x1:x2] = cv2.cvtColor(crop, cv2.COLOR_GRAY2BGR)
    evidence = profile.detect_signals(frame, layout, context={"scene_detail_collapse": True})
    assert evidence["spectator_panel_present"] is expected
    assert evidence["spectator_panel_absent"] is (expected is False)
    for key in (
        "buy_menu_grid_present",
        "expanded_map_present",
        "flash_candidate",
        "abrupt_luminance_spike",
        "visual_transition",
    ):
        blocked = profile.detect_signals(frame, layout, context={key: True})
        assert blocked["spectator_panel_present"] is None
        assert blocked["spectator_detector_checked"] is False
        assert blocked["spectator_panel_absent"] is False


def test_outside_damaged_icon_cannot_modify_checked_ordinary_slot():
    layout = _icon_layout()
    profile = _icon_profile(
        Path("unused.json"),
        {"version": 1, "roi": "spectator_icon", "method": "fixed_slot_structure_v1"},
    )
    frame = np.full((1080, 1920, 3), 70, np.uint8)
    x1, y1, x2, y2 = layout.normalized_roi("spectator_icon").pixel_bounds(1920, 1080)
    frame[y1:y2, x1:x2] = cv2.cvtColor(_ordinary_slot(), cv2.COLOR_GRAY2BGR)
    before = profile.detect_signals(frame, layout)
    frame[200:283, 1200:1275] = cv2.cvtColor(faded_icon(), cv2.COLOR_GRAY2BGR)
    after = profile.detect_signals(frame, layout)
    assert before["spectator_panel_absent"] is after["spectator_panel_absent"] is True
