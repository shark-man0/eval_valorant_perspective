"""Optional acceptance against the user's source video, never synthetic claims."""

import json
import os
from pathlib import Path

import pytest

from valorant_ai_coach.hud import RealHudAnalyzer
from valorant_ai_coach.resources import resource_path
from valorant_ai_coach.video import VideoService
from valorant_ai_coach.video.sampling import HudFrameSampler


def test_provided_recording_matches_authoritative_state_samples(tmp_path: Path) -> None:
    source = os.environ.get("VALORANT_HUD_TEST_VIDEO")
    if not source:
        pytest.skip("source VALORANT recording not supplied; real HUD accuracy unverified")
    layout = Path(
        os.environ.get("VALORANT_HUD_TEST_LAYOUT")
        or resource_path("config/hud_layout_1080p_v3.json")
    )
    video = VideoService(os.environ.get("VALORANT_FFPROBE", "ffprobe"))
    metadata = video.probe(Path(source))
    sampler = HudFrameSampler()
    frames = sampler.extract_in_batches(
        video.extract_frames,
        path=metadata.path,
        requests=sampler.pass_a(metadata.duration_sec),
        output_dir=tmp_path,
        metadata=metadata,
    )
    analysis = RealHudAnalyzer(layout).observe_frames(frames, video_metadata=metadata)
    assert analysis.calibration.calibrated, analysis.calibration.reasons
    contract = json.loads((Path(__file__).parents[1] / "hud_state_samples_v2.json").read_text())
    for case in contract["samples"]:
        nearby = [
            item
            for item in analysis.observations
            if abs(item["time_sec"] - case["time_sec"]) <= contract["tolerance_sec"]
        ]
        assert any(
            item["primary_state"] == case["expect_primary"]
            and set(case["expect_flags"]) <= set(item["state_flags"])
            and item["view_context"]["remote_view_type"] == case["expect_remote_view_type"]
            for item in nearby
        ), f"unmatched real-video anchor: {case}"
