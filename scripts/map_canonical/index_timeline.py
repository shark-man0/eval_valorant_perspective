"""Compact index of a canonical timeline for the Map canonical pass (development only).

Reads ``timeline_PRIVATE.json`` as a stream (plain, zstd ``.zst`` or the ``timeline.tgz``
bundle) and keeps only what the exact Map binding needs: the source, every second's
sample references and Camera/Life/Round states, and every native frame's sample and
states. The SHA-256 of the full JSON is computed while reading and stored as
``input_sha256``; compare it with the bundle's ``summary.json`` before use.

Requires ``ijson`` (and ``zstandard`` for ``.zst``).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import tarfile
import time
from pathlib import Path
from typing import IO, Any

import ijson
from ijson.common import ObjectBuilder

MEMBER = "timeline/timeline_PRIVATE.json"
MINIMAP_BOUNDS = [20, 48, 475, 475]
FRAME_FIELDS = ("sample", "camera", "life", "round", "continuity", "round_token")


def open_stream(path: Path) -> IO[bytes]:
    if path.suffix == ".zst":
        import zstandard

        return zstandard.ZstdDecompressor().stream_reader(path.open("rb"))
    if path.suffix == ".tgz":
        archive = tarfile.open(path, "r|gz")  # noqa: SIM115 - the stream outlives this call
        for member in archive:
            if member.name == MEMBER:
                stream = archive.extractfile(member)
                if stream is not None:
                    return stream
        raise SystemExit(f"{MEMBER} is not in {path}")
    return path.open("rb")


class HashingReader:
    def __init__(self, raw: IO[bytes]) -> None:
        self.raw = raw
        self.hash = hashlib.sha256()
        self.size = 0

    def read(self, size: int = -1) -> bytes:
        block = self.raw.read(size)
        self.hash.update(block)
        self.size += len(block)
        return block


def _state(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    return {"value": value.get("value"), "status": value.get("status")}


def build_index(path: Path) -> dict[str, Any]:
    started = time.monotonic()
    reader = HashingReader(open_stream(path))
    index: dict[str, Any] = {
        "schema": "development_canonical_map_index_v1", "input": path.name,
        "seconds": [], "native_frames": {},
    }
    builder: ObjectBuilder | None = None
    section = None
    frame_key = None
    # Minimap ROI hashes the timeline recorded per sample (public Map pixel observations).
    roi: dict[str, str] = {}
    current: dict[str, Any] = {}
    for prefix, event, value in ijson.parse(reader, use_float=True):
        if prefix == "" and event == "map_key":
            section, builder = value, None
            continue
        if section in ("version", "qualification", "formal_outputs") and prefix == section:
            index[section] = value
        elif section in ("source", "recording"):
            builder = builder or ObjectBuilder()
            builder.event(event, value)
            if prefix == section and event == "end_map":
                index[section] = builder.value
                builder = None
        elif section == "seconds":
            if prefix == "seconds.item" and event == "start_map":
                builder = ObjectBuilder()
            if builder is not None:
                builder.event(event, value)
                if prefix == "seconds.item" and event == "end_map":
                    row = builder.value
                    builder = None
                    index["seconds"].append({
                        "timestamp": row["timestamp"],
                        "sample_refs": row.get("sample_refs", []),
                        "camera_state": _state(row.get("camera_state")),
                        "life_state": _state(row.get("life_state")),
                        "round_state": _state(row.get("round_state")),
                    })
        elif section == "observations":
            parts = prefix.split(".")
            if len(parts) == 2 and event == "start_map":
                current = {}
            elif len(parts) >= 3 and parts[2:] == ["sample", "sample_sha256"]:
                current["sample"] = value
            elif len(parts) >= 3 and parts[2:] == ["raw", "roi_pixel_bounds", "item"]:
                current.setdefault("bounds", []).append(value)
            elif len(parts) >= 3 and parts[2:] == ["raw", "roi_pixel_sha256"]:
                current["roi"] = value
            if len(parts) == 2 and event == "end_map" and current.get("bounds") == MINIMAP_BOUNDS:
                key, digest = current.get("sample"), current.get("roi")
                if key and digest and roi.setdefault(key, digest) != digest:
                    raise SystemExit(f"Two minimap ROI hashes for {key}")
        elif section == "native_frames":
            if prefix == "native_frames" and event == "map_key":
                frame_key, builder = value, ObjectBuilder()
                continue
            if builder is not None:
                builder.event(event, value)
                if prefix == f"native_frames.{frame_key}" and event == "end_map":
                    frame = builder.value
                    builder = None
                    index["native_frames"][frame_key] = {
                        k: frame[k] for k in FRAME_FIELDS if k in frame
                    }
    while reader.read(1 << 20):
        pass
    index["minimap_roi_pixel_sha256"] = roi
    index["input_sha256"] = reader.hash.hexdigest()
    index["input_bytes"] = reader.size
    index["elapsed_seconds"] = round(time.monotonic() - started, 1)
    return index


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("timeline", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args(argv)
    index = build_index(args.timeline)
    args.output.write_text(json.dumps(index), encoding="utf-8")
    print(json.dumps({"input_sha256": index["input_sha256"], "seconds": len(index["seconds"]),
                      "native_frames": len(index["native_frames"]),
                      "elapsed_seconds": index["elapsed_seconds"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
