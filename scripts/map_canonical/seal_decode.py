"""Bind a finished decode directory to its timeline, source and catalog admission.

Checks that the catalog admits the recording, that the video (or a SHA-256 computed
where the video lives) is the catalog's source, and that every decoded row is a sample
of this canonical timeline. Then writes ``decode_receipt.json``; ``run_pass.py`` refuses
a decode directory without a matching receipt.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from provenance import FRAME_PIXELS, ROI_PIXELS, admit, video_sha256, write_receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--decode", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--video", type=Path)
    source.add_argument("--video-sha256", help="SHA-256 of the video computed where it lives")
    parser.add_argument("--decoder", default="ffmpeg native decode (camera_panel)")
    args = parser.parse_args(argv)
    index = json.loads(args.index.read_text(encoding="utf-8"))
    recording_id = index["source"]["source_id"]
    admission = admit(args.catalog, recording_id, index["source"]["source_sha256"])
    digest = (video_sha256(args.video, args.decode / "source_sha256_cache.json")
              if args.video is not None else args.video_sha256)
    frames = index["native_frames"]
    kinds = set()
    rows = 0
    for path in (args.decode / "done").glob("*.json"):
        for row in json.loads(path.read_text(encoding="utf-8")):
            rows += 1
            frame = frames.get(row["sample_sha256"])
            if frame is None or int(frame["sample"]["native_pts_tick"]) != row["native_pts_tick"]:
                raise SystemExit(f"Decoded row {row['sample_sha256']} is not in this timeline")
            if row.get("pixel_identical"):
                kinds.add(row.get("verification", FRAME_PIXELS))
    if len(kinds) != 1:
        raise SystemExit(f"One pixel verification kind expected, found {sorted(kinds)}")
    verification = kinds.pop()
    if verification not in (FRAME_PIXELS, ROI_PIXELS):
        raise SystemExit("Unknown pixel verification")
    receipt = write_receipt(args.decode, admission=admission,
                            timeline_sha256=index["input_sha256"], video_sha256_value=digest,
                            verification=verification, decoder=args.decoder)
    print(json.dumps({"recording_id": recording_id, "rows": rows,
                      "verification": receipt["verification"], "split": receipt["split"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
