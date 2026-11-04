"""Real tiny native transport with a nonzero PTS origin and no identity seed."""

import csv
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from valorant_ai_coach.temporal import match as module


@pytest.mark.skipif(
    not shutil.which("ffmpeg") or not shutil.which("ffprobe"),
    reason="Optional development FFmpeg transport unavailable",
)
def test_full_file_native_origin_and_recording_second_grid(tmp_path, monkeypatch):
    video = tmp_path / "synthetic.mp4"
    subprocess.run(
        [
            shutil.which("ffmpeg"),
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=c=blue:s=96x64:r=2:d=2",
            "-vf",
            "setpts=PTS+5/TB",
            "-copyts",
            "-c:v",
            "mpeg4",
            "-threads",
            "1",
            str(video),
        ],
        check=True,
        timeout=20,
    )
    source_sha = hashlib.sha256(video.read_bytes()).hexdigest()
    manifest, allocation, policy, config = (
        tmp_path / name
        for name in ("manifest.json", "allocation.json", "policy.json", "config.json")
    )
    manifest.write_text(
        json.dumps(
            {
                "records": [
                    {
                        "video_id": "registered-synthetic",
                        "source_sha256": source_sha,
                        "managed_path": str(video),
                        "physical_match_id": "synthetic",
                        "status": "accepted",
                        "split": "DEVELOPMENT",
                        "exposure": "DEVELOPMENT",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    allocation.write_text("{}", encoding="utf-8")
    policy.write_text(
        json.dumps(
            {
                "manifest": str(manifest),
                "allocation": str(allocation),
                "manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
                "allocation_sha256": hashlib.sha256(allocation.read_bytes()).hexdigest(),
                "allowed_source_sha256s": [source_sha],
            }
        ),
        encoding="utf-8",
    )
    config.write_text("{}", encoding="utf-8")

    class PixelObserver:
        def __init__(self, config_path: Path):
            self.fingerprint, self.bindings = "a" * 64, {}

        def inspect(self, image):
            assert image.shape == (64, 96, 3)
            return {"signals": [], "context": {}, "raw": {}, "map_candidates": []}

    monkeypatch.setattr(module, "ProfileHudObserver", PixelObserver)
    output = tmp_path / "run"
    receipt = module.run_match(
        policy_path=policy,
        source_id="registered-synthetic",
        reader_config=config,
        output=output,
        max_refinement_windows=0,
    )
    assert receipt["whole_file_completed"] is True
    assert receipt["source_bytes_verified_before_and_after"] is True
    assert receipt["native_start_pts_tick"] > 0
    timeline = json.loads((output / "timeline_PRIVATE.json").read_text(encoding="utf-8"))
    assert all(
        f["sample"]["native_pts_tick"] >= receipt["native_start_pts_tick"]
        for f in timeline["frames"]
    )
    with (output / "timeline_1s_PRIVATE.csv").open(encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    assert [r["recording_second"] for r in rows] == ["0", "1"]
    assert all(r["round"] == r["life"] == r["camera"] == "UNKNOWN" for r in rows)
    assert timeline["qualified_events"] == timeline["qualified_facts"] == []
