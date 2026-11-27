"""Convert YUV minimap crops to BGR and check the timeline's recorded minimap hash.

Run where the timeline was acquired (same FFmpeg build), on the ``decode_yuv.py``
output. A crop is kept only when its minimap ROI has the SHA-256 that the canonical
timeline recorded for the same sample (``index_timeline.py`` collects these). The output
has the ``decode_minimap.py`` layout, so ``run_pass.py`` reads it unchanged.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import subprocess
import zlib
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from valorant_ai_coach.temporal.match import png_frames

CROP_W, CROP_H = 488, 460
LEFT, TOP = 20 - 4, 48 - 32  # ROI offset inside the crop
ROI_W, ROI_H = 455, 427


def convert(blob: bytes, count: int) -> list[np.ndarray]:
    command = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-threads", "1", "-f", "rawvideo",
        "-pix_fmt", "yuv420p", "-s", f"{CROP_W}x{CROP_H}", "-color_range", "tv",
        "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
        "-i", "pipe:0", "-threads", "1", "-c:v", "png", "-compression_level", "1",
        "-pred", "up", "-f", "image2pipe", "pipe:1",
    ]
    result = subprocess.run(command, input=blob, capture_output=True, check=True)
    frames = [cv2.imdecode(np.frombuffer(f, np.uint8), cv2.IMREAD_COLOR)
              for f in png_frames(io.BytesIO(result.stdout))]
    if len(frames) != count:
        raise SystemExit("Converted frame count differs")
    return frames


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("source", type=Path, help="decode_yuv.py yuv/ directory")
    parser.add_argument("index", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args(argv)
    recorded = json.loads(args.index.read_text(encoding="utf-8"))["minimap_roi_pixel_sha256"]
    (args.output / "done").mkdir(parents=True, exist_ok=True)
    (args.output / "crops").mkdir(exist_ok=True)
    same = different = 0
    for meta in sorted(args.source.glob("*.json")):
        if (args.output / "done" / meta.name).exists():
            continue
        rows = json.loads(meta.read_text(encoding="utf-8"))
        blob = zlib.decompress((args.source / f"{meta.stem}.zz").read_bytes())
        present = [r for r in rows if not r.get("missing")]
        frames = convert(blob, len(present)) if present else []
        result: list[dict[str, Any]] = []
        for row, image in zip(present, frames, strict=True):
            roi = np.ascontiguousarray(image[TOP:TOP + ROI_H, LEFT:LEFT + ROI_W])
            digest = hashlib.sha256(roi.tobytes()).hexdigest()
            identical = digest == recorded.get(row["sample_sha256"])
            if identical:
                cv2.imwrite(str(args.output / "crops" / f"{row['sample_sha256']}.png"), roi,
                            [cv2.IMWRITE_PNG_COMPRESSION, 6])
                same += 1
            else:
                different += 1
            result.append({"sample_sha256": row["sample_sha256"],
                           "native_pts_tick": row["native_pts_tick"],
                           "pixel_identical": identical,
                           "verification": "timeline_minimap_roi_sha256",
                           "roi_pixel_bounds": [20, 48, 475, 475],
                           "roi_pixel_sha256": digest})
        result += [{"sample_sha256": r["sample_sha256"], "native_pts_tick": r["native_pts_tick"],
                    "pixel_identical": False} for r in rows if r.get("missing")]
        (args.output / "done" / meta.name).write_text(json.dumps(result), encoding="utf-8")
    print(json.dumps({"roi_identical": same, "roi_different": different}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
