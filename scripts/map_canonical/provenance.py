"""Catalog admission, source identity and decode receipts for the canonical Map pass.

Every step refuses work unless:

* the recording catalog admits the recording for development analysis
  (``RecordingCatalog.guard``; protected evaluation recordings are refused);
* the catalog, the canonical timeline and the video file name the same source SHA-256;
* a decode directory carries a receipt bound to that timeline file, so crops from an
  older timeline or another recording can never be read as this one's.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from valorant_ai_coach.recordings.catalog import RecordingCatalog

RECEIPT = "decode_receipt.json"
RECEIPT_SCHEMA = "development_canonical_decode_receipt_v1"
FRAME_PIXELS = "native_frame_pixels"
ROI_PIXELS = "timeline_minimap_roi_sha256"


def admit(catalog_root: Path, recording_id: str, source_sha256: str) -> dict[str, Any]:
    """Return the catalog facts used, or raise if the recording may not be analysed."""
    catalog = RecordingCatalog(catalog_root)
    recording = catalog.state.recordings.get(recording_id)
    if recording is None:
        raise SystemExit(f"{recording_id} is not in the recording catalog")
    catalog.guard([recording_id], "development_analysis")
    if recording.source_sha256 != source_sha256:
        raise SystemExit(f"{recording_id}: the catalog and the timeline name different sources")
    return {"recording_id": recording_id, "split": recording.split,
            "catalog_head": catalog.head_anchor(), "source_sha256": source_sha256}


def video_sha256(video: Path, cache: Path) -> str:
    """SHA-256 of the video, cached against its size and modification time."""
    stat = video.stat()
    key = {"path": str(video.resolve()), "size": stat.st_size, "mtime_ns": stat.st_mtime_ns}
    if cache.exists():
        saved = json.loads(cache.read_text(encoding="utf-8"))
        if {k: saved.get(k) for k in key} == key:
            return str(saved["sha256"])
    digest = hashlib.sha256()
    with video.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 22), b""):
            digest.update(block)
    cache.write_text(json.dumps({**key, "sha256": digest.hexdigest()}), encoding="utf-8")
    return digest.hexdigest()


def write_receipt(decode: Path, *, admission: dict[str, Any], timeline_sha256: str,
                  video_sha256_value: str, verification: str, decoder: str) -> dict[str, Any]:
    if video_sha256_value != admission["source_sha256"]:
        raise SystemExit("The video file is not the catalog's source")
    if verification not in (FRAME_PIXELS, ROI_PIXELS):
        raise SystemExit("Unknown pixel verification")
    receipt = {"schema": RECEIPT_SCHEMA, **admission, "timeline_sha256": timeline_sha256,
               "video_sha256": video_sha256_value, "verification": verification,
               "decoder": decoder, "formal_outputs": 0}
    path = decode / RECEIPT
    if path.exists():
        old = json.loads(path.read_text(encoding="utf-8"))
        if any(old.get(k) != receipt[k] for k in
               ("recording_id", "source_sha256", "timeline_sha256", "verification")):
            raise SystemExit(f"{decode} holds a decode of another timeline or source")
    path.write_text(json.dumps(receipt, indent=1), encoding="utf-8")
    os.chmod(path, 0o600)
    return receipt


def read_receipt(decode: Path, *, recording_id: str, source_sha256: str,
                 timeline_sha256: str) -> tuple[dict[str, Any], str]:
    path = decode / RECEIPT
    if not path.exists():
        raise SystemExit(f"{decode} has no decode receipt")
    data = path.read_bytes()
    receipt = json.loads(data)
    if (receipt.get("schema") != RECEIPT_SCHEMA or receipt.get("recording_id") != recording_id
            or receipt.get("source_sha256") != source_sha256
            or receipt.get("video_sha256") != source_sha256
            or receipt.get("timeline_sha256") != timeline_sha256
            or receipt.get("verification") not in (FRAME_PIXELS, ROI_PIXELS)):
        raise SystemExit(f"{decode}: the decode receipt does not match this timeline")
    return receipt, hashlib.sha256(data).hexdigest()
