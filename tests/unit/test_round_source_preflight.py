"""Preflight must preserve physical support and never authorize recognition."""
import argparse
import hashlib
import json
from dataclasses import replace
from fractions import Fraction

import cv2
import numpy as np
import pytest

from scripts.e2e.preflight_round_source import run, summarize_pixels, summarize_ticks
from valorant_ai_coach.video import VideoProbeError
from valorant_ai_coach.video.native import NativeSourceFrame


def frames(tmp_path):
    result = []
    for index, value in enumerate((10, 10, 20)):
        image = np.full((16, 16, 3), value, dtype=np.uint8)
        path = tmp_path / f"frame-{index}.png"
        assert cv2.imwrite(str(path), image)
        result.append(NativeSourceFrame(
            path, 553 + index * 256, Fraction(1, 15360), "epoch", "a" * 64,
            hashlib.sha256(path.read_bytes()).hexdigest(),
            hashlib.sha256(image.tobytes()).hexdigest(), 16, 16,
        ))
    return result


def test_nonzero_origin_and_variable_cadence_are_not_rebased_or_normalized():
    summary = summarize_ticks([553, 809, 1321], Fraction(1, 15360))
    assert summary["first_pts_ticks"] == 553
    assert summary["last_pts_sec"] == float(Fraction(1321, 15360))
    assert summary["step_ticks_counts"] == {"256": 1, "512": 1}
    assert summary["uniform_cadence"] is False
    assert summary["capture_loss_excluded"] is False


@pytest.mark.parametrize("ticks", [[], [0], [0, 0], [2, 1], [-1, 1], [0, True]])
def test_invalid_source_order_does_not_produce_a_report(ticks):
    with pytest.raises(ValueError, match="source PTS"):
        summarize_ticks(ticks, Fraction(1, 60))


def test_uniform_cadence_is_not_capture_or_scene_qualification(tmp_path):
    summary = summarize_pixels(frames(tmp_path))
    assert summary["uniform_cadence"] is True
    assert summary["capture_loss_excluded"] is False
    assert summary["scene_continuity_qualified"] is False
    assert summary["adjacent_duplicate_rasters"] == [{
        "previous_pts_ticks": 553, "pts_ticks": 809, "time_sec": float(Fraction(809, 15360)),
    }]
    assert summary["frame_count"] == 3
    assert "event" not in json.dumps(summary)


@pytest.mark.parametrize("field,value", [
    ("source_epoch", "different"), ("source_video_sha256", "b" * 64),
    ("time_base", Fraction(1, 60)), ("width", 32),
])
def test_distinct_epochs_or_sources_cannot_be_spliced(tmp_path, field, value):
    source = frames(tmp_path)
    source[1] = replace(source[1], **{field: value})
    with pytest.raises(ValueError, match="one decoder epoch"):
        summarize_pixels(source)


def test_changed_encoded_pixels_reject_before_publication(tmp_path):
    source = frames(tmp_path)
    source[1].path.write_bytes(source[1].path.read_bytes() + b"changed")
    with pytest.raises(VideoProbeError, match="asset changed"):
        summarize_pixels(source)


def test_wrong_source_sha_rejects_before_probe_or_contract(tmp_path, monkeypatch):
    video = tmp_path / "video.mp4"
    video.write_bytes(b"source")
    monkeypatch.setattr("scripts.e2e.preflight_round_source.subprocess.run",
                        lambda *a, **k: pytest.fail("must not launch decoder"))
    with pytest.raises(ValueError, match="source video SHA256 mismatch"):
        run(argparse.Namespace(video=video, source_sha256="0" * 64))
