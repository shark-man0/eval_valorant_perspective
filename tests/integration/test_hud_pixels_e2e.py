"""Encoded synthetic pixels through the real HUD and application services."""

import json
import shutil
import subprocess
from pathlib import Path

import cv2
import numpy as np
import pytest

from valorant_ai_coach.bootstrap import build_services
from valorant_ai_coach.hud.calibrate import create_anchor_profile
from valorant_ai_coach.hud.calibrate_profile import create_profile
from valorant_ai_coach.hud.layout import HudLayout
from valorant_ai_coach.hud.spectator import panel_components
from valorant_ai_coach.resources import resource_path
from valorant_ai_coach.settings import AppSettings, SettingsStore


@pytest.mark.parametrize("automatic", [False, True])
def test_calibrated_pixels_reach_round_package_and_sqlite_without_fabrication(
    tmp_path: Path,
    automatic: bool,
    panel_images,
) -> None:
    ffmpeg, ffprobe = shutil.which("ffmpeg"), shutil.which("ffprobe")
    if ffmpeg is None or ffprobe is None:
        pytest.skip("ffmpeg/ffprobe are not installed on this host")
    layout_path = resource_path("config/hud_layout_1080p_v3.json")
    layout = HudLayout.load(layout_path)
    image = np.full((1080, 1920, 3), 60, dtype=np.uint8)
    rng = np.random.default_rng(54)
    for name in [
        *(layout.calibration_policy or {})["required_anchors"],
        "ammo_current_weapon",
        "spectated_player_panel",
    ]:
        x1, y1, x2, y2 = layout.normalized_roi(name).pixel_bounds(1920, 1080)
        gray = rng.integers(30, 230, (y2 - y1, x2 - x1), dtype=np.uint8)
        image[y1:y2, x1:x2] = gray[:, :, np.newaxis]
    sx1, sy1, sx2, sy2 = layout.normalized_roi("spectated_player_panel").pixel_bounds(1920, 1080)
    panel, scene = panel_images(sx2 - sx1, sy2 - sy1)
    image[sy1:sy2, sx1:sx2] = scene
    reference = tmp_path / "reference.png"
    assert cv2.imwrite(str(reference), image)
    selected_layout = create_anchor_profile(layout_path, reference, tmp_path / "profile")
    # Explicit independent pixel detectors replace the former assumption that
    # geometry reference matching itself establishes player identity.
    sidecar = selected_layout.with_suffix(".templates.json")
    profile = json.loads(sidecar.read_text(encoding="utf-8"))
    profile["signals"] = {}
    for signal, roi in (
        ("hp_hud_structure", "player_hp_armor"),
        ("ability_bar_structure", "abilities"),
        ("weapon_ammo_structure", "ammo_current_weapon"),
        ("spectated_player_panel", "spectated_player_panel"),
    ):
        x, y, _, _ = layout.normalized_roi(roi).pixel_bounds(1920, 1080)
        patch = (
            image[y : y + 32, x : x + 32]
            if signal != "spectated_player_panel"
            else (rng.integers(30, 230, (32, 32, 3), dtype=np.uint8))
        )
        asset = sidecar.parent / f"{signal}.png"
        assert cv2.imwrite(str(asset), patch)
        profile["signals"][signal] = {"roi": roi, "template": asset.name, "threshold": 0.9}
    labels = panel_components(cv2.cvtColor(panel, cv2.COLOR_BGR2GRAY))
    assert labels is not None
    assert cv2.imwrite(str(sidecar.parent / "panel.components.png"), labels)
    profile["spectator_panel_detector"] = {"version": 1, "template": "panel.components.png"}
    sidecar.write_text(json.dumps(profile), encoding="utf-8")
    if automatic:
        # Unlabelled synthetic recording. The automatic path below receives only
        # this video and the base layout, NOT the manually constructed profile.
        image[:] = 60
        for roi in (
            "round_timer",
            "top_match_bar",
            "player_hp_armor",
            "abilities",
            "ammo_current_weapon",
        ):
            x1, y1, x2, y2 = layout.normalized_roi(roi).pixel_bounds(1920, 1080)
            for y in range(y1 + 4, y2 - 3, 12):
                cv2.line(image, (x1 + 4, y), (x2 - 4, y), (220, 220, 220), 2)
            cv2.rectangle(image, (x1 + 4, y1 + 4), (x2 - 5, y2 - 5), (150, 150, 150), 2)
        x1, y1, x2, y2 = layout.normalized_roi("spectated_player_panel").pixel_bounds(1920, 1080)
        image[y1:y2, x1:x2] = scene
        assert cv2.imwrite(str(reference), image)
    source = tmp_path / "synthetic hud.mp4"
    subprocess.run(
        [
            ffmpeg,
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "error",
            "-loop",
            "1",
            "-framerate",
            "10",
            "-i",
            str(reference),
            "-t",
            "2",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-crf",
            "0",
            "-pix_fmt",
            "yuv420p",
            "-y",
            str(source),
        ],
        check=True,
        capture_output=True,
        timeout=30,
    )
    if automatic:
        # Base profile has a positive panel UI detector only, no identity references.
        base = tmp_path / "base.json"
        shutil.copy2(layout_path, base)
        assert cv2.imwrite(str(tmp_path / "positive_panel.png"), panel)
        base.with_suffix(".templates.json").write_text(
            json.dumps(
                {
                    "schema_version": "1.0",
                    "signals": {
                        "spectated_player_panel": {
                            "roi": "spectated_player_panel",
                            "template": "positive_panel.png",
                        }
                    },
                }
            )
        )
        selected_layout = create_profile(source, base, tmp_path / "automatic", samples=16)
    services = build_services(
        SettingsStore(tmp_path / "settings.json"),
        settings=AppSettings(
            data_dir=tmp_path / "data",
            hud_mode="real",
            hud_layout_path=str(selected_layout),
            ffmpeg_path=ffmpeg,
            ffprobe_path=ffprobe,
        ),
    )
    result = services.pipeline.analyze_video(source, match_id="M-PIXELS")
    assert result.status == "completed"
    report = json.loads((result.analysis_json.parent / "hud-analysis.json").read_text())
    assert report["sampled_frame_count"] >= 8
    assert any(item["primary_state"] == "live_first_person" for item in report["observations"])
    packages = services.repository.list_round_packages(result.match_id)
    assert len(packages) == 1
    # No numeric templates, known round boundaries, or visual model were supplied.
    # Pixel textures cannot turn into health values, complete round context or shots.
    assert all(item["hp"] is None for item in packages[0]["state_snapshots"])
    assert packages[0]["observation_quality"]["timeline_completeness"] == 0
    assert not {item["type"] for item in packages[0]["events"]} & {"shot", "peek", "kill"}
    assert not (tmp_path / "data" / "temp" / result.match_id).exists()
