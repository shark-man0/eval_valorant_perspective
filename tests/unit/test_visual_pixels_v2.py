import cv2
import numpy as np
import pytest

from valorant_ai_coach.visual.pixels import PixelMeasurementExtractor
from valorant_ai_coach.visual.remote import classify_remote_view


def hud(time, ammo=25, weapon="Vandal", slots=None):
    return {
        "time_sec": time,
        "primary_state": "live_first_person",
        "state_flags": [],
        "values": {"ammo_current": ammo, "weapon_text": weapon, "ability_slots": slots or []},
        "quality": {"hud_confidence": 0.95, "state_confidence": 0.95},
    }


def test_pixels_redundant_trigger_without_ammo_and_flat_scene_abstention():
    first = np.zeros((180, 320, 3), np.uint8)
    second = np.full_like(first, 255)
    measure = PixelMeasurementExtractor().measure(second, first, hud(0.2, None), hud(0, None))
    assert measure["weapon_action"]["ammo_delta"] is None
    assert measure["weapon_action"]["recoil_score"] >= 0.5
    assert measure["weapon_action"]["confidence"] < 0.65
    assert measure["motion"]["state"] == "unknown"
    assert measure["measurement_meta"]["primary_state"] == "live_first_person"


def test_real_templates_and_color_components_minimap_and_rebind_safe_slot(tmp_path):
    image = np.zeros((180, 320, 3), np.uint8)
    image[40:46, 70:76] = (0, 255, 0)
    rng = np.random.default_rng(43)
    template = rng.integers(0, 255, (10, 10, 3), dtype=np.uint8)
    path = tmp_path / "cue.png"
    cv2.imwrite(str(path), template)
    image[90:100, 160:170] = template
    profile = {
        "validated": True,
        "rois": {"minimap": [0, 0, 0.5, 0.5]},
        "minimap_north_up_calibrated": True,
        "crosshair_template": str(path),
        "cast_template": str(path),
        "minimap_colors_hsv": {
            "self": {"lower": [50, 200, 200], "upper": [70, 255, 255], "min_area_px": 20}
        },
    }
    reader = PixelMeasurementExtractor()
    old = hud(0, slots=[{"slot": 2, "available": True, "charges": 1}])
    new = hud(
        0.05, slots=[{"slot": 2, "available": False, "charges": 0, "displayed_key_text": "MB4"}]
    )
    reader.measure(image, None, old, profile=profile)
    result = reader.measure(image, image, new, old, profile=profile)
    assert result["minimap"]["track_confidence"] >= 0.9
    assert result["minimap"]["self_x_norm"] is not None
    assert result["utility"]["slot"] == "E"
    assert result["measurement_meta"]["cast_animation_score"] >= 0.9
    assert result["measurement_meta"]["primary_state"] == "live_first_person"
    assert result["aiming"]["confidence"] >= 0.9


def test_reload_and_switch_are_measured_as_exclusions():
    image = np.zeros((180, 320, 3), np.uint8)
    reader = PixelMeasurementExtractor()
    result = reader.measure(image, image, hud(0.1, 30), hud(0, 18))
    assert result["measurement_meta"]["reload_detected"]
    result = reader.measure(image, image, hud(0.1, 12, "Classic"), hud(0, 25))
    assert result["measurement_meta"]["weapon_changed"]


@pytest.mark.parametrize(
    "state", ["spectator_first_person", "buy_menu_open", "expanded_tactical_map"]
)
def test_remote_fallback_cannot_override_precedence(state):
    result = classify_remote_view(
        {"primary_state": state},
        {"player_hud_missing": True, "remote_overlay": True, "ability_control_active": True},
    )
    assert result["primary_state"] == state
    assert not result["player_mechanics_eligible"]


def test_hud_remote_subtype_is_preserved_and_normal_ocr_failure_not_remote():
    result = classify_remote_view(
        {"primary_state": "remote_control_view", "view_context": {"remote_view_type": "sova_drone"}}
    )
    assert result["remote_view_type"] == "sova_drone"
    assert classify_remote_view(hud(0, None))["primary_state"] == "live_first_person"


def test_repeated_static_muzzle_template_does_not_create_new_shots(tmp_path):
    rng = np.random.default_rng(34)
    image = rng.integers(0, 255, (90, 160, 3), dtype=np.uint8)
    path = tmp_path / "muzzle.png"
    cv2.imwrite(str(path), image[20:30, 20:30])
    result = PixelMeasurementExtractor().measure(
        image, image, hud(0.05), hud(0), profile={"validated": True, "muzzle_template": str(path)}
    )
    assert result["weapon_action"]["muzzle_flash_score"] == 0
