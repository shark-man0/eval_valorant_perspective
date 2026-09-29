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
from valorant_ai_coach.hud.layout import HudLayout
from valorant_ai_coach.resources import resource_path
from valorant_ai_coach.settings import AppSettings, SettingsStore


def test_calibrated_pixels_reach_round_package_and_sqlite_without_fabrication(
    tmp_path: Path,
) -> None:
    ffmpeg, ffprobe = shutil.which("ffmpeg"), shutil.which("ffprobe")
    if ffmpeg is None or ffprobe is None:
        pytest.skip("ffmpeg/ffprobe are not installed on this host")
    layout_path = resource_path("config/hud_layout_1080p_v3.json")
    layout = HudLayout.load(layout_path)
    image = np.full((1080, 1920, 3), 60, dtype=np.uint8)
    rng = np.random.default_rng(54)
    for name in (layout.calibration_policy or {})["required_anchors"]:
        x1, y1, x2, y2 = layout.normalized_roi(name).pixel_bounds(1920, 1080)
        gray = rng.integers(30, 230, (y2 - y1, x2 - x1), dtype=np.uint8)
        image[y1:y2, x1:x2] = gray[:, :, np.newaxis]
    reference = tmp_path / "reference.png"
    assert cv2.imwrite(str(reference), image)
    selected_layout = create_anchor_profile(layout_path, reference, tmp_path / "profile")
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
