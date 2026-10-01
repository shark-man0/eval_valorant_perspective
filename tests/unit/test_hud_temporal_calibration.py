import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from valorant_ai_coach.hud.calibrate_temporal import _candidate, create_temporal_profile
from valorant_ai_coach.video.service import FrameSample, VideoMetadata


class FakeVideoService:
    def __init__(self, frames):
        self.frames = frames

    def probe(self, path):
        return VideoMetadata(path, 10.0, 640, 360, 30.0, "h264", None, False, 0)

    def extract_frames(self, path, timestamps, output_dir, **kwargs):
        output_dir.mkdir(parents=True)
        result = []
        for index, frame in enumerate(self.frames[:len(timestamps)]):
            frame_path = output_dir / f"{index}.png"
            assert cv2.imwrite(str(frame_path), frame)
            result.append(FrameSample(timestamps[index], frame_path))
        return result


def _layout(path: Path):
    names = ("round_timer", "top_match_bar", "player_hp_armor", "abilities")
    rois = {}
    for i, name in enumerate(names):
        x, y = 0.03 + i * 0.24, 0.10
        rois[name] = {"norm": [x, y, x + 0.20, y + 0.35], "px": None}
    path.write_text(json.dumps({
        "schema_version": "3.0", "profile_id": "test",
        "reference_resolution": {"width": 640, "height": 360},
        "coordinate_policy": {}, "rois": rois,
        "calibration_policy": {"required_anchors": list(names)},
    }))


def _frames(changing=False, count=24):
    frames = []
    for index in range(count):
        frame = np.zeros((360, 640, 3), np.uint8)
        for anchor in range(4):
            x = int((0.03 + anchor * 0.24) * 640)
            y = int(0.10 * 360)
            # Stable textured border supplies persistent edges and informative pixels.
            cv2.rectangle(frame, (x + 4, y + 4), (x + 115, y + 115), (220, 220, 220), 2)
            cv2.line(frame, (x + 15, y + 30), (x + 90, y + 90), (150, 150, 150), 3)
            if changing:
                cv2.putText(frame, str(index % 10), (x + 35, y + 75), cv2.FONT_HERSHEY_SIMPLEX,
                            1.4, (255, 255, 255), 3)
        frames.append(frame)
    return frames


def test_static_persistent_edges_survive_temporal_change():
    frames = []
    for index in range(24):
        image = np.zeros((100, 100, 3), np.uint8)
        cv2.rectangle(image, (8, 8), (90, 90), (210, 210, 210), 2)
        cv2.line(image, (15, 20), (80, 75), (140, 140, 140), 3)
        cv2.putText(
            image, str(index % 10), (30, 65), cv2.FONT_HERSHEY_SIMPLEX,
            1.5, (255, 255, 255), 3,
        )
        frames.append(image)
    template, mask, ratio = _candidate(frames)
    assert np.count_nonzero(mask) >= 64
    assert ratio > 0
    assert mask[8, 50] == 0 or mask[9, 50] > 0
    # A digit pixel changes over time and is excluded from the stable mask.
    assert mask[55, 40] == 0
    assert template.shape == (100, 100)


@pytest.mark.parametrize("frames", [[], [np.zeros((20, 20, 3), np.uint8)] * 7])
def test_rejects_too_few_or_uninformative_frames(frames):
    assert _candidate(frames) is None
    constant = [np.full((100, 100, 3), 55, np.uint8) for _ in range(24)]
    assert _candidate(constant) is None


def test_preserves_prior_readers_signals_and_source_assets_and_refuses_overwrite(tmp_path):
    layout = tmp_path / "hud_layout.json"
    _layout(layout)
    local_asset = tmp_path / "signal.png"
    assert cv2.imwrite(str(local_asset), np.full((8, 8, 3), 150, np.uint8))
    profile_path = tmp_path / "hud_layout.templates.json"
    original = {
        "schema_version": "1.0", "anchors": {"round_timer": {"threshold": 0.96}},
        "readers": {"digits": {"kind": "digits", "template": "signal.png"}},
        "signals": {"known_marker": {"roi": "round_timer", "template": "signal.png"}},
    }
    profile_path.write_text(json.dumps(original))
    old_layout = layout.read_bytes()
    old_profile = profile_path.read_bytes()
    out = tmp_path / "generated"
    result = create_temporal_profile(Path("dummy.mp4"), layout, out,
                                     video_service=FakeVideoService(_frames(changing=True)))
    generated = json.loads(result.with_name("hud_layout.templates.json").read_text())
    assert generated["readers"] == {"digits": {"kind": "digits", "template": str(local_asset)}}
    assert generated["signals"]["known_marker"]["template"] == str(local_asset)
    assert generated["anchors"]["round_timer"]["threshold"] == 0.96
    assert set(generated["anchors"]) == {
        "round_timer", "top_match_bar", "player_hp_armor", "abilities",
    }
    assert not any("identity" in key for key in generated["anchors"])
    stats = json.loads((out / "temporal_stats.json").read_text())
    assert generated["temporal_generation"] == stats
    assert "source" not in json.dumps(stats).lower()
    assert "dummy.mp4" not in json.dumps(stats)
    assert layout.read_bytes() == old_layout and profile_path.read_bytes() == old_profile
    with pytest.raises(FileExistsError):
        create_temporal_profile(Path("dummy.mp4"), layout, out,
                                video_service=FakeVideoService(_frames()))


def test_rejects_insufficient_valid_anchors_without_publishing(tmp_path):
    layout = tmp_path / "hud_layout.json"
    _layout(layout)
    # Static but flat frames have no informative edge pixels.
    frames = [np.full((360, 640, 3), 70, np.uint8) for _ in range(24)]
    out = tmp_path / "failed"
    with pytest.raises(ValueError, match="3個未満"):
        create_temporal_profile(Path("dummy.mp4"), layout, out,
                                video_service=FakeVideoService(frames))
    assert not out.exists()


def test_enforces_bounded_sample_count(tmp_path):
    layout = tmp_path / "hud_layout.json"
    _layout(layout)
    with pytest.raises(ValueError, match="8〜64"):
        create_temporal_profile(Path("dummy.mp4"), layout, tmp_path / "out", samples=7,
                                video_service=FakeVideoService(_frames()))
