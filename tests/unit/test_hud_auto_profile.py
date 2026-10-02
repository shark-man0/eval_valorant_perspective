import json
from pathlib import Path

import cv2
import numpy as np
import pytest
from test_hud_temporal_calibration import FakeVideoService, _frames, _layout

from valorant_ai_coach.hud.calibrate_profile import (
    clear_reference,
    create_profile,
    structure_reference,
)
from valorant_ai_coach.hud.identity import STRUCTURES, live_identity
from valorant_ai_coach.hud.layout import HudLayout
from valorant_ai_coach.hud.templates import HudTemplateProfile


def inputs(tmp_path, panel_images):
    layout = tmp_path / "base.json"
    _layout(layout)
    raw = json.loads(layout.read_text())
    raw["rois"]["ammo_current_weapon"] = {"norm": [0.03, 0.60, 0.23, 0.95], "px": None}
    raw["rois"]["spectated_player_panel"] = {"norm": [0.30, 0.60, 0.55, 0.95], "px": None}
    layout.write_text(json.dumps(raw))
    frames = _frames(changing=True, count=32)
    hud = HudLayout.load(layout)
    for index, frame in enumerate(frames):
        x1, y1, x2, y2 = hud.normalized_roi("ammo_current_weapon").pixel_bounds(640, 360)
        frame[y1:y2, x1:x2] = frame[36 : 36 + y2 - y1, 19 : 19 + x2 - x1]
        x1, y1, x2, y2 = hud.normalized_roi("spectated_player_panel").pixel_bounds(640, 360)
        panel, scene = panel_images(x2 - x1, y2 - y1, index % 8)
        frame[y1:y2, x1:x2] = panel if index % 4 >= 2 else scene
    return layout, frames


def test_generated_layout_consumed_without_json_edits(tmp_path, panel_images):
    layout, frames = inputs(tmp_path, panel_images)
    original = layout.read_bytes()
    out = tmp_path / "local"
    generated = create_profile(
        Path("private.mp4"), layout, out, video_service=FakeVideoService(frames)
    )
    assert generated.name == "hud_layout.json"
    profile = HudTemplateProfile.load(generated.with_suffix(".templates.json"))
    assert not profile.reader_diagnostics
    signals = profile.detect_signals(frames[1], HudLayout.load(generated))
    assert live_identity(signals, geometry_valid=True).live
    assert not live_identity(signals, geometry_valid=False).live
    assert all("mask" not in profile.raw["signals"][name] for name in STRUCTURES)
    assert all(
        profile.raw["signals"][name]["template"].startswith("identity/") for name in STRUCTURES
    )
    stats = (out / "profile_diagnostics.json").read_text()
    assert "private.mp4" not in stats and str(tmp_path) not in stats
    assert layout.read_bytes() == original
    # A newly visible panel must not retain live identity.
    blocked = frames[1].copy()
    x1, y1, x2, y2 = (
        HudLayout.load(generated).normalized_roi("spectated_player_panel").pixel_bounds(640, 360)
    )
    cv2.putText(
        blocked, "PLAYER", (x1 + 5, y1 + 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2
    )
    assert not live_identity(
        profile.detect_signals(blocked, HudLayout.load(generated)), geometry_valid=True
    ).live
    with pytest.raises(FileExistsError):
        create_profile(Path("private.mp4"), layout, out, video_service=FakeVideoService(frames))


def test_structure_requires_disjoint_holdout_support():
    crops = []
    for index in range(32):
        image = np.zeros((120, 130, 3), np.uint8)
        if index % 2 == 0:
            cv2.rectangle(image, (4, 4), (115, 115), (220, 220, 220), 2)
        crops.append(image)
    assert structure_reference(crops) is None


@pytest.mark.parametrize("value", [0, 255])
def test_black_white_frames_are_not_spectator_absence(value):
    assert clear_reference([np.full((40, 60), value, np.uint8)] * 32) is None


def test_textured_panel_is_not_automatically_labelled_clear():
    frame = np.full((40, 120), 65, np.uint8)
    cv2.putText(frame, "PLAYER", (2, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.5, 255, 2)
    assert clear_reference([frame] * 32) is None


def test_missing_identity_publishes_runnable_but_unknown_profile(tmp_path, panel_images):
    layout, frames = inputs(tmp_path, panel_images)
    hud = HudLayout.load(layout)
    x1, y1, x2, y2 = hud.normalized_roi("ammo_current_weapon").pixel_bounds(640, 360)
    for frame in frames:
        frame[y1:y2, x1:x2] = 0
    generated = create_profile(
        Path("private.mp4"), layout, tmp_path / "out", video_service=FakeVideoService(frames)
    )
    profile = HudTemplateProfile.load(generated.with_suffix(".templates.json"))
    assert (
        profile.raw["automatic_identity_generation"]["references"]["weapon_ammo_structure"][
            "status"
        ]
        == "insufficient_evidence"
    )
    assert not live_identity(profile.detect_signals(frames[0], hud), geometry_valid=True).live


def test_invalid_inherited_identity_is_regenerated_and_readers_preserved(tmp_path, panel_images):
    layout, frames = inputs(tmp_path, panel_images)
    base = {
        "schema_version": "1.0",
        "readers": {"hp": {"kind": "digits"}},
        "signals": {"hp_hud_structure": {"roi": "player_hp_armor", "template": "missing.png"}},
    }
    sidecar = layout.with_suffix(".templates.json")
    sidecar.write_text(json.dumps(base))
    original = sidecar.read_bytes()
    generated = create_profile(
        Path("private.mp4"),
        layout,
        tmp_path / "日本語profile",
        video_service=FakeVideoService(frames),
    )
    profile = HudTemplateProfile.load(generated.with_suffix(".templates.json"))
    assert profile.raw["readers"] == base["readers"]
    assert (
        profile.raw["automatic_identity_generation"]["references"]["hp_hud_structure"]["status"]
        == "generated"
    )
    assert not profile.reader_diagnostics
    assert sidecar.read_bytes() == original


def test_legacy_clear_reference_cannot_override_unverified_panel(
    tmp_path, monkeypatch, panel_images
):
    from valorant_ai_coach.hud.readers import ReaderResult

    layout, frames = inputs(tmp_path, panel_images)
    generated = create_profile(
        Path("private.mp4"), layout, tmp_path / "out", video_service=FakeVideoService(frames)
    )
    profile = HudTemplateProfile.load(generated.with_suffix(".templates.json"))
    profile._panel_components = None
    # Existing configured presence detector returns ambiguous .5, not absence.
    template = profile._signal_templates["hp_hud_structure"][1]
    profile._signal_templates["spectated_player_panel"] = ("spectated_player_panel", template)
    frame = frames[0].copy()
    roi = HudLayout.load(generated).normalized_roi("spectated_player_panel")
    x1, y1, x2, y2 = roi.pixel_bounds(640, 360)
    frame[y1:y2:2, x1:x2] += 4  # Still within clear-reference tolerance, but non-flat.
    monkeypatch.setattr(
        "valorant_ai_coach.hud.templates._best_template_match",
        lambda *args: ReaderResult(None, 0.5, ("template_below_threshold",)),
    )
    signals = profile.detect_signals(frame, HudLayout.load(generated))
    assert signals["spectator_panel_absent"] is False
