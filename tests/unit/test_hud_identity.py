from unittest.mock import Mock

import cv2
import numpy as np
import pytest

from valorant_ai_coach.hud.analyzers import RealHudAnalyzer
from valorant_ai_coach.hud.identity import STRUCTURES, live_identity
from valorant_ai_coach.hud.templates import HudTemplateProfile
from valorant_ai_coach.resources import resource_path


def test_geometry_alone_never_proves_identity():
    assert not live_identity(
        {"template_anchor_scores": dict.fromkeys(STRUCTURES, 1.0)}, geometry_valid=True
    ).live


@pytest.mark.parametrize(
    "blocker",
    [
        "remote_control_candidate",
        "cypher_camera_template",
        "sova_drone_template",
        "skye_trailblazer_template",
        "other_remote_view_template",
        "special_reticle_present",
        "spectated_player_panel",
        "self_hud_identity_lost",
        "expanded_map_stable",
        "expanded_map_present",
        "map_transition",
        "combat_report_visible",
    ],
)
def test_current_mode_evidence_blocks_live_without_persistence(live_identity_signals, blocker):
    assert live_identity(live_identity_signals, geometry_valid=True).live
    assert not live_identity({**live_identity_signals, blocker: True}, geometry_valid=True).live
    assert not live_identity({}, geometry_valid=True).live


@pytest.mark.parametrize("value", [0.89, float("nan"), float("inf"), True, None])
def test_structure_thresholds_are_not_lowered(live_identity_signals, value):
    live_identity_signals["hp_hud_structure_confidence"] = value
    assert not live_identity(live_identity_signals, geometry_valid=True).live


def test_geometry_and_exclusion_are_required(live_identity_signals):
    assert not live_identity(live_identity_signals, geometry_valid=False).live
    live_identity_signals.pop("spectator_panel_absent")
    assert not live_identity(live_identity_signals, geometry_valid=True).live


def test_buy_menu_and_astral_overrides(live_identity_signals):
    assert not live_identity(
        {
            **live_identity_signals,
            "buy_menu_grid_present": True,
            "buy_menu_close_anchor_present": True,
        },
        geometry_valid=True,
    ).live
    assert not live_identity(
        {
            **live_identity_signals,
            "astral_geometry": True,
            "purple_palette": True,
            "astra_hand_interface": True,
        },
        geometry_valid=True,
    ).live


def test_real_hud_keeps_independent_identity_when_fresh_anchors_disappear(live_identity_signals):
    analyzer = RealHudAnalyzer(resource_path("config/hud_layout_1080p_v3.json"))
    names = ("round_timer", "top_match_bar", "player_hp_armor", "abilities")
    anchors = {name: analyzer.layout.normalized_roi(name) for name in names}
    profile = Mock()
    profile.raw = {"anchors": {name: {"mask": "unused.png"} for name in names}}
    profile.detect_anchors.side_effect = [(anchors, dict.fromkeys(names, 1.0), ())] + [
        ({}, {}, ())
    ] * 3
    profile.detect_signals.side_effect = [
        live_identity_signals,
        live_identity_signals,
        {
            **live_identity_signals,
            "spectated_player_panel": True,
            "self_hud_identity_trustworthy": False,
        },
        {},
    ]
    analyzer.template_profile = profile
    frame = np.full((1080, 1920, 3), 60, dtype=np.uint8)
    result = analyzer.observe_frames([frame] * 4)
    assert [row["primary_state"] for row in result.observations] == [
        "live_first_person",
        "live_first_person",
        "spectator_first_person",
        "unknown",
    ]
    assert result.calibration.calibrated
    assert result.calibration_diagnostics["counts"]["retained_geometry_frames"] == 3
    assert result.calibration_diagnostics["identity_reasons"]["independent_hud_structures"] == 2


def test_real_pixel_structure_templates_work_without_any_geometry_templates(tmp_path):
    analyzer = RealHudAnalyzer(resource_path("config/hud_layout_1080p_v3.json"))
    frame = np.random.default_rng(41).integers(0, 255, (1080, 1920, 3), dtype=np.uint8)
    roi_names = ("player_hp_armor", "abilities", "ammo_current_weapon", "spectated_player_panel")
    names = (*STRUCTURES, "spectated_player_panel")
    signals = {}
    for index, (name, roi_name) in enumerate(zip(names, roi_names, strict=True)):
        patch = np.random.default_rng(index).integers(0, 255, (20, 24, 3), dtype=np.uint8)
        path = tmp_path / f"{name}.png"
        assert cv2.imwrite(str(path), patch)
        signals[name] = {"roi": roi_name, "template": path.name, "threshold": 0.9}
        if name != "spectated_player_panel":
            x, y, _, _ = analyzer.layout.normalized_roi(roi_name).pixel_bounds(1920, 1080)
            frame[y : y + 20, x : x + 24] = patch
    profile = HudTemplateProfile(
        tmp_path / "profile.json", {"schema_version": "1.0", "signals": signals}
    )
    measured = profile.detect_signals(frame, analyzer.layout)
    assert live_identity(measured, geometry_valid=True).live
    assert not profile.detect_anchors(frame, analyzer.layout)[0]
    # A failed/unreadable exclusion ROI must not manufacture negative evidence.
    blank = profile.detect_signals(np.zeros_like(frame), analyzer.layout)
    assert "spectator_panel_absent" not in blank
    assert not live_identity(blank, geometry_valid=True).live
