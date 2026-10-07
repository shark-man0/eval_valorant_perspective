import json

import cv2
import numpy as np
import pytest

from valorant_ai_coach.hud.layout import HudLayout
from valorant_ai_coach.hud.templates import HudTemplateProfile
from valorant_ai_coach.resources import resource_path

ROLES = {
    "buy_menu_grid_present": "buy_menu_grid",
    "buy_menu_close_anchor_present": "buy_menu_close_anchor",
}


def make_profile(tmp_path, roles=tuple(ROLES), *, threshold=0.90, missing=False, wrong_roi=False):
    specs = {}
    images = {}
    for i, role in enumerate(roles):
        image = np.random.default_rng(i + 711).integers(0, 255, (24, 28, 3), dtype=np.uint8)
        images[role] = image
        path = f"{role}.png"
        if not missing:
            assert cv2.imwrite(str(tmp_path / path), image)
        specs[role] = {
            "roi": "round_timer" if wrong_roi else ROLES[role],
            "template": path,
            "threshold": threshold,
        }
    p = tmp_path / "profile.json"
    p.write_text(json.dumps({"schema_version": "1.0", "signals": specs}))
    return HudTemplateProfile.load(p), images


def frame_for(layout, images):
    frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
    for role, image in images.items():
        left, top, _, _ = layout.normalized_roi(ROLES[role]).pixel_bounds(1920, 1080)
        frame[top : top + 24, left : left + 28] = image
    return frame


def merged(profile, layout, frame):
    return {**{role: True for role in ROLES}, **profile.detect_signals(frame, layout)}


def compound(signals):
    return all(bool(signals.get(role)) for role in ROLES)


@pytest.fixture
def layout():
    return HudLayout.load(resource_path("config/hud_layout_1080p_v3.json"))


def test_configured_nonmatch_overrides_texture_without_claiming_absence(tmp_path, layout):
    profile, _ = make_profile(tmp_path)
    result = merged(profile, layout, frame_for(layout, {}))
    assert not compound(result)
    assert all(result[role] is None for role in ROLES)


def test_two_independent_matches_and_missing_one_role(tmp_path, layout):
    profile, images = make_profile(tmp_path)
    assert compound(merged(profile, layout, frame_for(layout, images)))
    for role in ROLES:
        result = merged(profile, layout, frame_for(layout, {role: images[role]}))
        assert result[role] is True
        assert not compound(result)


def test_evidence_does_not_carry_into_next_frame(tmp_path, layout):
    profile, images = make_profile(tmp_path)
    previous = merged(profile, layout, frame_for(layout, images))
    current = {**previous, **profile.detect_signals(frame_for(layout, {}), layout)}
    assert not compound(current)
    assert all(current[role] is None for role in ROLES)


def test_single_configured_role_cannot_borrow_other_heuristic(tmp_path, layout):
    profile, images = make_profile(tmp_path, roles=("buy_menu_grid_present",))
    result = merged(profile, layout, frame_for(layout, images))
    assert result["buy_menu_grid_present"] is True
    assert result["buy_menu_close_anchor_present"] is None
    assert not compound(result)


@pytest.mark.parametrize("options", [{"missing": True}, {"threshold": 0.89}, {"wrong_roi": True}])
def test_unavailable_or_invalid_configured_reference_abstains(tmp_path, layout, options):
    profile, images = make_profile(tmp_path, **options)
    result = merged(profile, layout, frame_for(layout, images))
    assert profile.reader_diagnostics
    assert all(result[role] is None for role in ROLES)
    assert not compound(result)


def test_unconfigured_profile_preserves_legacy_behavior(tmp_path, layout):
    profile, _ = make_profile(tmp_path, roles=())
    assert compound(merged(profile, layout, frame_for(layout, {})))
