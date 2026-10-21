from __future__ import annotations

import json
import subprocess

import pytest

from scripts.diagnostics.intake_recording import inspect_recording, timeline_summary


def test_decode_order_reordering_is_not_a_timestamp_gap():
    report = timeline_summary([{"pts_time": time} for time in (0, 0.1, 0.05)], 20, 0.001)
    assert report["gaps_above_nominal_count"] == 0
    assert report["visual_continuity"] == "unverified"
    assert report["unedited_source"] == "unverified"


def test_missing_duplicate_and_large_gaps_are_descriptive():
    report = timeline_summary(
        [{"pts_time": time} for time in (0, 0, 0.05, 1, "N/A", "nan")] + [{}], 20, 0.001,
    )
    assert report["duplicate_pts_count"] == 1
    assert report["missing_pts_count"] == 3
    assert report["gaps_above_nominal_count"] == 1
    assert report["gap_examples"] == [
        {"previous_pts_sec": .05, "current_pts_sec": 1, "gap_sec": .95}
    ]


@pytest.mark.parametrize("fps,tick", [(0, .001), (float("nan"), .001), (60, 0)])
def test_invalid_timing_rejects(fps, tick):
    with pytest.raises(ValueError):
        timeline_summary([{"pts_time": 0}], fps, tick)


def test_intake_is_sanitized_and_never_calls_analyzer_or_evaluator(tmp_path, monkeypatch):
    video = tmp_path / "private-recording.mp4"
    video.write_bytes(b"source")
    calls = []

    def probe(command, **kwargs):
        calls.append(command)
        if "-show_packets" in command:
            data = {"packets": [{"pts_time": 0}, {"pts_time": .05}]}
        else:
            data = {
                "format": {"duration": "1", "size": "6", "filename": str(video)},
                "streams": [
                    {"index": 0, "codec_type": "video", "codec_name": "h264",
                     "width": 1920, "height": 1080, "avg_frame_rate": "20/1",
                     "time_base": "1/1000", "tags": {"private": "OCR text"}},
                    *[{"index": i, "codec_type": "audio", "codec_name": "aac",
                       "sample_rate": "48000", "channels": 2} for i in range(1, 4)],
                ],
            }
        return subprocess.CompletedProcess(command, 0, json.dumps(data), "")

    monkeypatch.setattr(subprocess, "run", probe)
    report = inspect_recording(video, "match_002", "probe-tool", user_confirmed_unedited=True)
    assert len(calls) == 2
    assert all(command[0] == "probe-tool" for command in calls)
    assert len(report["audio_tracks"]) == 3
    assert report["lifecycle_evaluation"] == "not_run"
    assert report["dataset_manifest"] == "pending_matching_validation_pack"
    assert report["user_declaration"]["unedited_full_match"] is True
    assert report["timeline"]["unedited_source"] == "unverified"
    text = json.dumps(report)
    assert str(video) not in text
    assert "private-recording" not in text and "OCR text" not in text


def test_source_mutation_rejects(tmp_path, monkeypatch):
    video = tmp_path / "video.mp4"
    video.write_bytes(b"first")
    hashes = iter(["a" * 64, "b" * 64])
    monkeypatch.setattr("scripts.diagnostics.intake_recording.sha256_file", lambda _: next(hashes))

    def probe(command, **kwargs):
        data = {"packets": [{"pts_time": 0}]} if "-show_packets" in command else {
            "format": {"duration": "1", "size": "5"},
            "streams": [{"codec_type": "video", "codec_name": "h264", "width": 1,
                         "height": 1, "avg_frame_rate": "60/1", "time_base": "1/1000"}],
        }
        return subprocess.CompletedProcess(command, 0, json.dumps(data), "")

    monkeypatch.setattr(subprocess, "run", probe)
    with pytest.raises(ValueError, match="source changed"):
        inspect_recording(video, "match_002")


@pytest.mark.parametrize("metadata", [
    {"duration": "nan", "width": 1920, "size": "6"},
    {"duration": "0", "width": 1920, "size": "6"},
    {"duration": "1", "width": 0, "size": "6"},
    {"duration": "1", "width": 1920, "size": "7"},
])
def test_invalid_source_metadata_rejects(tmp_path, monkeypatch, metadata):
    video = tmp_path / "synthetic.mp4"
    video.write_bytes(b"source")
    data = {
        "format": {"duration": metadata["duration"], "size": metadata["size"]},
        "streams": [{"codec_type": "video", "codec_name": "h264",
                     "width": metadata["width"], "height": 1080,
                     "avg_frame_rate": "60/1", "time_base": "1/15360"}],
    }
    monkeypatch.setattr(subprocess, "run", lambda command, **kwargs:
                        subprocess.CompletedProcess(command, 0, json.dumps(data), ""))
    with pytest.raises(ValueError, match="invalid source metadata"):
        inspect_recording(video, "synthetic")


def test_probe_error_stderr_rejects_even_on_zero_exit(tmp_path, monkeypatch):
    video = tmp_path / "synthetic.mp4"
    video.write_bytes(b"source")
    monkeypatch.setattr(subprocess, "run", lambda command, **kwargs:
                        subprocess.CompletedProcess(command, 0, "{}", "damaged packet"))
    with pytest.raises(ValueError, match="source probe reported errors"):
        inspect_recording(video, "synthetic")
