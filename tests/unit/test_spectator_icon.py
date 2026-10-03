from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import cv2
import numpy as np
import pytest

from valorant_ai_coach.hud.identity import live_identity
from valorant_ai_coach.hud.layout import HudLayout, NormalizedRoi
from valorant_ai_coach.hud.spectator_icon import detect_icon
from valorant_ai_coach.hud.templates import HudTemplateProfile

HEIGHT, WIDTH = 83, 75


def _abstract_icon() -> np.ndarray:
    """High-detail abstract emblem with no face, text, or agent identity."""
    image = np.full((HEIGHT, WIDTH), 18, dtype=np.uint8)
    rng = np.random.default_rng(8731)
    # Local irregular polygons and crossing strokes distribute edge directions
    # throughout the fixed slot while keeping the background mostly dark.
    for row in range(4):
        for column in range(4):
            cx = 9 + column * 19
            cy = 10 + row * 20
            points = []
            for angle in (0, 45, 90, 135, 180, 225, 270, 315):
                radius = int(rng.integers(3, 7))
                theta = np.deg2rad(angle + int(rng.integers(-12, 13)))
                points.append((cx + int(radius * np.cos(theta)), cy + int(radius * np.sin(theta))))
            cv2.fillPoly(image, [np.asarray(points, dtype=np.int32)], int(rng.integers(150, 241)))
            for angle in (0, 45, 90, 135):
                theta = np.deg2rad(angle + int(rng.integers(-8, 9)))
                dx, dy = int(5 * np.cos(theta)), int(5 * np.sin(theta))
                cv2.line(image, (cx - dx, cy - dy), (cx + dx, cy + dy), 250, 1)
    # Fine, spatially distributed etched detail raises edge density while
    # leaving a clear abstract emblem rather than any recognizable subject.
    flecks = rng.random(image.shape) < 0.06
    image[flecks] = rng.choice((20, 250), int(flecks.sum()))
    return image


def _ordinary_slot() -> np.ndarray:
    """Sharp but sparse border-like HUD decoration without icon detail."""
    image = np.full((HEIGHT, WIDTH), 70, dtype=np.uint8)
    cv2.rectangle(image, (8, 12), (66, 70), 160, 1)
    return image


def _shift(image: np.ndarray, dx: int, dy: int) -> np.ndarray:
    return cv2.warpAffine(
        image,
        np.float32([[1, 0, dx], [0, 1, dy]]),
        (WIDTH, HEIGHT),
        borderValue=18,
    )


def _result(crop: np.ndarray, **kwargs):
    return detect_icon(crop, **kwargs)


def test_abstract_icon_is_detected_across_small_rendering_shifts() -> None:
    icon = _abstract_icon()
    renderings = [_shift(icon, dx, dy) for dx, dy in ((0, 0), (1, 0), (-1, 1), (2, -2), (-2, 2))]
    renderings.extend(
        cv2.resize(icon, dimensions, interpolation=cv2.INTER_LINEAR)
        for dimensions in ((68, 75), (82, 91))
    )
    renderings.append(cv2.cvtColor(icon, cv2.COLOR_GRAY2BGR))
    for rendering in renderings:
        result = _result(rendering)
        assert result["checked"] is True
        assert result["panel_present"] is True


@pytest.mark.parametrize(
    "crop,expected_checked,expected_present",
    [(_ordinary_slot(), True, False), (np.full((HEIGHT, WIDTH), 24, np.uint8), False, None)],
)
def test_ordinary_or_blank_slot_is_not_a_positive_icon(
    crop: np.ndarray, expected_checked: bool, expected_present: bool | None
) -> None:
    result = _result(crop)
    assert result["checked"] is expected_checked
    assert result["panel_present"] is expected_present


def test_texture_outside_configured_slot_cannot_prove_icon_presence() -> None:
    # The runtime contract consumes only this configured crop; content outside
    # it is intentionally absent from the detector call.
    frame = np.full((220, 240), 24, dtype=np.uint8)
    frame[20:103, 10:85] = _abstract_icon()
    configured_slot = frame[120:203, 150:225]
    result = _result(configured_slot)
    assert result["panel_present"] is not True


@pytest.mark.parametrize(
    "kwargs,crop",
    [
        ({"configured": False}, _abstract_icon()),
        ({"obscured": True}, _abstract_icon()),
        ({}, _abstract_icon()[:, :55]),
        ({}, np.full((HEIGHT, WIDTH), 242, np.uint8)),
        ({}, np.full((HEIGHT, WIDTH), 24, np.uint8)),
    ],
    ids=("missing-configuration", "menu-obscured", "partial-slot", "fade", "blank"),
)
def test_unavailable_ambiguous_or_obscured_evidence_stays_unknown(kwargs, crop) -> None:
    result = _result(crop, **kwargs)
    assert result["panel_present"] is None
    assert result["checked"] is False


def test_wrong_aspect_ratio_is_unknown() -> None:
    result = _result(np.zeros((HEIGHT, WIDTH + 24), np.uint8))
    assert result["panel_present"] is None
    assert result["checked"] is False


def _icon_layout() -> HudLayout:
    layout = HudLayout.load(Path("config/hud_layout_1080p_v3.json"))
    regions = dict(layout.regions)
    regions["spectator_icon"] = NormalizedRoi(0.5, 0.3, WIDTH / 1920, HEIGHT / 1080)
    return replace(layout, regions=regions)


def _icon_profile(path: Path, detector: dict) -> HudTemplateProfile:
    return HudTemplateProfile(
        path,
        {"schema_version": "1.0", "spectator_icon_detector": detector},
    )


def test_profile_uses_only_configured_icon_roi_and_obscuring_context() -> None:
    layout = _icon_layout()
    profile = _icon_profile(
        Path("unused-profile.json"),
        {"version": 1, "roi": "spectator_icon", "method": "fixed_slot_structure_v1"},
    )
    frame = np.full((1080, 1920, 3), 24, dtype=np.uint8)
    x1, y1, x2, y2 = layout.normalized_roi("spectator_icon").pixel_bounds(1920, 1080)
    icon = _abstract_icon()
    frame[y1:y2, x1:x2] = cv2.cvtColor(icon, cv2.COLOR_GRAY2BGR)

    present = profile.detect_signals(frame, layout)
    assert present["spectator_panel_present"] is True
    assert present["spectated_player_panel"] is True

    for context in (
        {"buy_menu_grid_present": True},
        {"expanded_map_present": True},
        {"flash_candidate": True},
    ):
        obscured = profile.detect_signals(frame, layout, context=context)
        assert obscured["spectator_panel_present"] is None
        assert obscured["spectator_panel_absent"] is False

    frame[y1:y2, x1:x2] = 24
    # The exact same high-detail pattern outside the configured slot must not
    # be found by a global or sliding search.
    frame[200 : 200 + HEIGHT, 1200 : 1200 + WIDTH] = cv2.cvtColor(icon, cv2.COLOR_GRAY2BGR)
    unrelated = profile.detect_signals(frame, layout)
    assert unrelated["spectator_panel_present"] is not True
    assert "spectated_player_panel" not in unrelated


def test_malformed_dedicated_configuration_does_not_fall_back_to_legacy_signal(tmp_path) -> None:
    layout = _icon_layout()
    icon = _abstract_icon()
    assert cv2.imwrite(str(tmp_path / "legacy.png"), icon)
    profile = HudTemplateProfile(
        tmp_path / "profile.json",
        {
            "schema_version": "1.0",
            "signals": {
                "spectated_player_panel": {
                    "roi": "spectated_player_panel",
                    "template": "legacy.png",
                }
            },
            "spectator_icon_detector": {
                "version": 1,
                "roi": "unknown_roi",
                "method": "fixed_slot_structure_v1",
            },
        },
    )
    frame = np.full((1080, 1920, 3), 24, dtype=np.uint8)
    px1, py1, _, _ = layout.normalized_roi("spectated_player_panel").pixel_bounds(1920, 1080)
    frame[py1 : py1 + HEIGHT, px1 : px1 + WIDTH] = cv2.cvtColor(icon, cv2.COLOR_GRAY2BGR)

    result = profile.detect_signals(frame, layout)
    assert result["spectator_panel_present"] is None
    assert result["spectator_detector_checked"] is False
    assert "spectated_player_panel" not in result


@pytest.mark.parametrize("kernel", [5, 9, 15])
def test_blurred_icon_is_unknown(kernel: int) -> None:
    blurred = cv2.GaussianBlur(_abstract_icon(), (kernel, kernel), 0)
    result = _result(blurred)
    assert result["panel_present"] is None
    assert result["checked"] is False


@pytest.mark.parametrize("factor", [0.2, 0.5])
def test_dark_low_contrast_fade_is_unknown(factor: float) -> None:
    faded = np.clip(_abstract_icon().astype(np.float32) * factor, 0, 255).astype(np.uint8)
    result = _result(faded)
    assert result["panel_present"] is None
    assert result["checked"] is False


def test_transition_context_keeps_dimmed_icon_unknown() -> None:
    faded = np.clip(_abstract_icon().astype(np.float32) * 0.5, 0, 255).astype(np.uint8)
    result = _result(faded, obscured=True)
    assert result["panel_present"] is None
    assert result["checked"] is False


def test_partially_black_occluded_icon_is_unknown() -> None:
    partial = _abstract_icon()
    partial[:18, :20] = 0
    result = _result(partial)
    assert result["panel_present"] is None
    assert result["checked"] is False


def test_identity_requires_checked_absence_even_with_all_three_live_structures() -> None:
    live_signals = {
        key: True for key in ("hp_hud_structure", "ability_bar_structure", "weapon_ammo_structure")
    }
    live_signals.update(
        hp_hud_structure_confidence=0.97,
        ability_bar_structure_confidence=0.97,
        weapon_ammo_structure_confidence=0.97,
    )
    unknown = _result(_abstract_icon(), configured=False)
    unverified = {
        **live_signals,
        "spectator_detector_checked": unknown["checked"],
        "spectator_panel_present": unknown["panel_present"],
        "spectator_panel_absent": False,
    }
    assert live_identity(unverified, geometry_valid=True).live is False

    absence = _result(_ordinary_slot())
    verified = {
        **live_signals,
        "spectator_detector_checked": absence["checked"],
        "spectator_panel_present": absence["panel_present"],
        "spectator_panel_absent": absence["checked"] and absence["panel_present"] is False,
    }
    assert live_identity(verified, geometry_valid=True).live is True


@pytest.mark.parametrize("seed", range(8))
def test_dense_random_texture_never_proves_icon(seed: int) -> None:
    texture = np.random.default_rng(seed).integers(20, 240, (HEIGHT, WIDTH), dtype=np.uint8)
    result = detect_icon(texture)
    assert result["panel_present"] is not True


def test_short_menu_close_x_vetoes_icon_without_menu_grid_candidate() -> None:
    from valorant_ai_coach.hud.spectator_icon import menu_overlay_candidate

    crop = np.full((95, 93, 3), 55, np.uint8)
    cv2.line(crop, (34, 32), (54, 52), (210, 210, 210), 4)
    cv2.line(crop, (34, 52), (54, 32), (210, 210, 210), 4)
    assert menu_overlay_candidate(crop)
    assert detect_icon(_abstract_icon(), obscured=menu_overlay_candidate(crop))["checked"] is False
    empty = np.full_like(crop, 55)
    cv2.line(empty, (8, 32), (84, 32), (210, 210, 210), 2)
    assert not menu_overlay_candidate(empty)
    assert not menu_overlay_candidate(np.empty((0, 0, 3), np.uint8))

    layout = _icon_layout()
    profile = _icon_profile(
        Path("unused-profile.json"),
        {"version": 1, "roi": "spectator_icon", "method": "fixed_slot_structure_v1"},
    )
    frame = np.full((1080, 1920, 3), 24, np.uint8)
    x1, y1, x2, y2 = layout.normalized_roi("spectator_icon").pixel_bounds(1920, 1080)
    frame[y1:y2, x1:x2] = cv2.cvtColor(_abstract_icon(), cv2.COLOR_GRAY2BGR)
    cx1, cy1, cx2, cy2 = layout.normalized_roi("buy_menu_close_anchor").pixel_bounds(1920, 1080)
    frame[cy1:cy2, cx1:cx2] = cv2.resize(crop, (cx2 - cx1, cy2 - cy1))
    result = profile.detect_signals(frame, layout, context={"buy_menu_grid_present": False})
    assert result["spectator_detector_checked"] is False
    assert result["spectator_panel_present"] is None
    assert result["spectator_panel_absent"] is False
    frame[cy1:cy2, cx1:cx2] = cv2.resize(empty, (cx2 - cx1, cy2 - cy1))
    assert profile.detect_signals(frame, layout)["spectator_panel_present"] is True

