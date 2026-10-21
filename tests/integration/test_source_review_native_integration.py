"""Exercise the existing native decoder with a tiny synthetic private registry."""

from __future__ import annotations

import json
import shutil
import subprocess

import pytest

from scripts.diagnostics.register_private_sources import register, verify
from scripts.e2e.run_dataset_case import read_json, sha256_file
from scripts.temporal_gt import review_session as review


def test_real_native_acquisition_export_and_integrity(tmp_path, monkeypatch):
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("FFmpeg tools unavailable")
    source = tmp_path / "source"
    source.mkdir()
    for number in range(9):
        subprocess.run(
            [
                "ffmpeg",
                "-nostdin",
                "-v",
                "error",
                "-f",
                "lavfi",
                "-i",
                f"color=c=0x{(number + 1) * 0x181818:06x}:size=96x64:rate=30",
                "-t",
                "0.6",
                "-c:v",
                "libx264",
                str(source / f"synthetic-{number}.mp4"),
            ],
            check=True,
            capture_output=True,
        )
    batch, _ = register(
        source, tmp_path / "private", "synthetic", unused_and_distinct=True, unedited=True
    )
    anchors = [sha256_file(batch / p) for p in ("manifest.json", "allocation.json")]
    session = batch / "review"
    review.create_session(batch, session, *anchors)
    decoded = []
    native = review.decode_native_window

    def watched(video, **kwargs):
        decoded.append(str(video))
        return native(video, **kwargs)

    monkeypatch.setattr(review, "decode_native_window", watched)
    review.acquire(session, "pilot", "0", "0.2")
    acq = review.read_acquisition(session, "pilot")
    response = review.response_defaults(acq)
    response["human_source_review_confirmed"] = True
    response["round"].update(
        reviewed=True, verdict="unknown", uncertainty="Synthetic trial only, not real human GT"
    )
    response_path = tmp_path / "synthetic_response.json"
    response_path.write_text(json.dumps(response), encoding="utf-8")
    snapshot = review.record_response(session, "pilot", response_path)
    report = review.validate_snapshot(
        snapshot,
        sha256_file(snapshot / "round.freeze.json"),
        sha256_file(snapshot / "self_death_annotations.json"),
    )
    assert report["readiness"] == "BLOCKED" and report["recognition_executed"] is False
    assert len(acq["frames"]) == 7
    assert len({f["epoch"] for f in acq["frames"]}) == 1
    assert decoded == [acq["video_path"]]
    assert read_json(snapshot / "public_counts.json")["reviewed_unknown_annotations"] == 1
    assert verify(batch, *anchors)["registered"] == 9
