"""Real container/decode tests use tiny synthetic files only, never private video."""
from __future__ import annotations

import json
import shutil
import subprocess

import pytest

from scripts.diagnostics.intake_recording import inspect_recording
from scripts.diagnostics.register_private_sources import register, verify
from scripts.e2e.run_dataset_case import sha256_file


def test_real_source_acceptance_and_invalid_source_quarantine(tmp_path):
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("FFmpeg tools unavailable")
    source = tmp_path / "source"
    source.mkdir()
    for number in range(8):
        subprocess.run(
            ["ffmpeg", "-nostdin", "-v", "error", "-f", "lavfi", "-i",
             f"color=c=0x{(number + 1) * 0x1c1c1c:06x}:size=96x64:rate=30", "-f", "lavfi", "-i",
             "sine=frequency=440:sample_rate=48000", "-t", "0.2", "-c:v", "libx264",
             "-c:a", "aac", str(source / f"synthetic-{number}.mp4")],
            check=True, capture_output=True,
        )
    (source / "broken.mp4").write_bytes(b"not a recording")
    originals = {p.name: sha256_file(p) for p in source.iterdir()}
    batch, summary = register(source, tmp_path / "private", "synthetic", unused_and_distinct=True)
    assert summary["registered"] == 8
    assert summary["failed"] == 1
    assert originals == {p.name: sha256_file(p) for p in source.iterdir()}
    manifest = json.loads((batch / "manifest.json").read_text(encoding="utf-8"))
    for row in manifest["records"]:
        if row["status"] == "accepted":
            from pathlib import Path

            report = json.loads(Path(row["intake_path"]).read_text(encoding="utf-8"))
            assert report["native_time_base"] == "1/15360"
            assert report["native_first_packet_pts"] == 0
            assert report["audio_tracks"][0]["codec_name"] == "aac"
            assert report["decode_integrity"] == "full_video_and_all_audio_null_sink_passed"
            assert report["timeline"]["visual_continuity"] == "unverified"
    verified = verify(batch, sha256_file(batch / "manifest.json"),
                      sha256_file(batch / "allocation.json"))
    assert verified["registered"] == 8
    broken = source / "broken.mp4"
    with pytest.raises((ValueError, subprocess.CalledProcessError)):
        inspect_recording(broken, "broken")


def _nine(source):
    source.mkdir()
    for number in range(9):
        subprocess.run(
            ["ffmpeg", "-nostdin", "-v", "error", "-f", "lavfi", "-i",
             f"color=c=0x{(number + 1) * 0x1a1a1a:06x}:size=96x64:rate=30", "-f", "lavfi", "-i",
             "sine=frequency=440:sample_rate=48000", "-t", "0.2", "-c:v", "libx264",
             "-c:a", "aac", str(source / f"synthetic-{number}.mp4")],
            check=True, capture_output=True,
        )


def test_catalog_adopts_the_batch_all_or_nothing(tmp_path):
    """Formal registration: adopted into the catalog, or nothing is left at all."""
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("FFmpeg tools unavailable")
    from valorant_ai_coach.recordings import RecordingCatalog

    source = tmp_path / "source"
    _nine(source)
    catalog = RecordingCatalog.create(tmp_path / "catalog", seed="s")
    batch, summary = register(source, tmp_path / "private", "good", unused_and_distinct=True,
                              catalog=catalog)
    assert summary["catalog_import"]["adopted"] == 9
    assert len(RecordingCatalog(catalog.root).state.recordings) == 9

    # Another catalog already holds one of these recordings under a different split.
    other = RecordingCatalog.create(tmp_path / "other", seed="s")
    manifest = json.loads((batch / "manifest.json").read_text(encoding="utf-8"))
    row = next(r for r in manifest["records"] if r["split"] == "DEVELOPMENT")
    clash = tmp_path / "clash.json"
    clash.write_text(json.dumps({"records": [{
        **row, "video_id": "elsewhere", "physical_match_id": "elsewhere",
        "split": "FINAL_HOLDOUT_CANDIDATE",
    }]}), encoding="utf-8")
    other.import_legacy(clash)
    with pytest.raises(ValueError, match="CATALOG_CONFLICT"):
        register(source, tmp_path / "private2", "bad", unused_and_distinct=True,
                 catalog=other)
    assert not (tmp_path / "private2" / "bad").exists()
    assert set(RecordingCatalog(other.root).state.recordings) == {"elsewhere"}
