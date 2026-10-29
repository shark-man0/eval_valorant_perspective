import os
import shutil
import subprocess
from pathlib import Path

import pytest
from test_shared_timeline_replay import policy_fixture, write

from valorant_ai_coach.temporal.acquire import acquire
from valorant_ai_coach.video.native import _sha256


@pytest.mark.skipif(
    not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="FFmpeg required"
)
def test_sparse_pngs_retain_exact_native_pts_after_complete_decoder_check(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    video = tmp_path / "synthetic.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=160x90:rate=12",
            "-t",
            "2.2",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(video),
        ],
        check=True,
        capture_output=True,
    )
    policy = policy_fixture(tmp_path)
    import json

    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    source_hash = _sha256(video)
    manifest["records"][0].update(source_sha256=source_hash, managed_path=str(video))
    write(tmp_path / "manifest.json", manifest)
    policy.update(
        manifest_sha256=_sha256(tmp_path / "manifest.json"), allowed_source_sha256s=[source_hash]
    )
    policy_path = write(tmp_path / "policy.json", policy)
    result = acquire(
        policy_path=policy_path, source_id="a", start=0, end=2, output=tmp_path / "acquired"
    )
    assert len(result["all_native_pts_ticks"]) == 25
    assert len(result["frames"]) == 3
    ticks = [r["sample"]["native_pts_tick"] for r in result["frames"]]
    assert ticks == [result["all_native_pts_ticks"][n] for n in [0, 12, 24]]
    assert all(Path(r["path"]).is_absolute() for r in result["frames"])
    assert result["source_bytes_verified_before_and_after"] is True
    assert result["semantic_continuity"] == "UNKNOWN"
    if os.name != "nt":  # Windows stat mode bits do not describe its ACL.
        assert all(Path(r["path"]).stat().st_mode & 0o777 == 0o600 for r in result["frames"])
    with pytest.raises(ValueError, match="outside Git"):
        acquire(
            policy_path=policy_path, source_id="a", start=0, end=2, output=tmp_path / "acquired"
        )


def test_invalid_interval_or_protected_source_is_rejected_before_decode(tmp_path):
    path = write(tmp_path / "policy.json", policy_fixture(tmp_path, split="FINAL_HOLDOUT"))
    with pytest.raises(ValueError, match="180"):
        acquire(policy_path=path, source_id="a", start=0, end=181, output=tmp_path / "output")
    with pytest.raises(ValueError, match="Protected"):
        acquire(policy_path=path, source_id="a", start=0, end=2, output=tmp_path / "output")
