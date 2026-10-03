import json
from pathlib import Path

from test_hud_auto_profile import FakeVideoService, inputs

from valorant_ai_coach.hud.calibrate_profile import create_profile
from valorant_ai_coach.hud.templates import HudTemplateProfile


def test_configured_icon_generation_does_not_require_panel_clustering(
    tmp_path, panel_images, monkeypatch
):
    layout, frames = inputs(tmp_path, panel_images)
    raw = json.loads(layout.read_text())
    raw["rois"]["spectator_icon"] = {
        "px": [10, 270, 35, 298],
        "norm": [10 / 640, 270 / 360, 35 / 640, 298 / 360],
    }
    layout.write_text(json.dumps(raw))

    def forbidden(*args, **kwargs):
        raise AssertionError("icon mode must not invoke legacy panel clustering")

    monkeypatch.setattr(
        "valorant_ai_coach.hud.calibrate_profile.generate_panel_reference", forbidden
    )
    generated = create_profile(
        Path("private.mp4"), layout, tmp_path / "out", video_service=FakeVideoService(frames)
    )
    profile = HudTemplateProfile.load(generated.with_suffix(".templates.json"))
    assert profile.raw["spectator_icon_detector"]["method"] == "fixed_slot_structure_v1"
    assert "spectator_panel_detector" not in profile.raw
    row = profile.raw["automatic_identity_generation"]["references"]["spectator_panel"]
    assert row["reference_required"] is False
    assert row["status"] == "generated"
    assert not profile.reader_diagnostics
