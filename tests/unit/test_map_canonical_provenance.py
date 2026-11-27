"""Catalog admission, source identity and stale-decode protection of the canonical Map pass."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pytest

from valorant_ai_coach.recordings.catalog import LeakageError, RecordingCatalog

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "map_canonical"))
from provenance import (  # noqa: E402
    FRAME_PIXELS,
    ROI_PIXELS,
    admit,
    read_receipt,
    video_sha256,
    write_receipt,
)


def _catalog(tmp_path: Path) -> tuple[Path, dict[str, tuple[str, str]]]:
    catalog = RecordingCatalog.create(tmp_path / "private" / "catalog", seed="fixed-seed")
    found = {}
    for name, split in (("dev", "DEVELOPMENT"), ("held", "FINAL_HOLDOUT")):
        video = tmp_path / f"{name}.mp4"
        video.write_bytes(name.encode() * 64)
        result = catalog.register(video, physical_match_id=f"match_{name}", split=split)
        found[name] = (result.recording_id, hashlib.sha256(video.read_bytes()).hexdigest())
    return catalog.root, found


def test_only_development_recordings_are_admitted(tmp_path: Path) -> None:
    root, found = _catalog(tmp_path)
    rid, sha = found["dev"]
    assert admit(root, rid, sha)["source_sha256"] == sha
    with pytest.raises(SystemExit, match="different sources"):
        admit(root, rid, "0" * 64)
    held, held_sha = found["held"]
    with pytest.raises(LeakageError):
        admit(root, held, held_sha)


def test_receipt_binds_the_decode_to_one_timeline_and_source(tmp_path: Path) -> None:
    root, found = _catalog(tmp_path)
    rid, sha = found["dev"]
    decode = tmp_path / "decode"
    decode.mkdir()
    digest = video_sha256(tmp_path / "dev.mp4", decode / "cache.json")
    assert digest == sha
    admission = admit(root, rid, sha)
    write_receipt(decode, admission=admission, timeline_sha256="a" * 64,
                  video_sha256_value=digest, verification=FRAME_PIXELS, decoder="test")
    receipt, _ = read_receipt(decode, recording_id=rid, source_sha256=sha,
                              timeline_sha256="a" * 64)
    assert receipt["verification"] == FRAME_PIXELS
    # A decode of an older timeline is never read as the current one.
    with pytest.raises(SystemExit, match="does not match"):
        read_receipt(decode, recording_id=rid, source_sha256=sha, timeline_sha256="b" * 64)
    with pytest.raises(SystemExit, match="another timeline"):
        write_receipt(decode, admission=admission, timeline_sha256="b" * 64,
                      video_sha256_value=digest, verification=FRAME_PIXELS, decoder="test")
    with pytest.raises(SystemExit, match="another timeline"):
        write_receipt(decode, admission=admission, timeline_sha256="a" * 64,
                      video_sha256_value=digest, verification=ROI_PIXELS, decoder="test")
    with pytest.raises(SystemExit, match="not the catalog's source"):
        write_receipt(tmp_path, admission=admission, timeline_sha256="a" * 64,
                      video_sha256_value="1" * 64, verification=FRAME_PIXELS, decoder="test")
