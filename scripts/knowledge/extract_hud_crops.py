"""Sample fixed HUD regions from full-match recordings into private crop archives.

Development tool for DEVELOPMENT recordings only. Output stays private (never
commit it). Each archive is a zip with ``index.json`` and JPEG crops named
``<region>/<sec>.jpg``. Runs are resumable and time-boxed so they can be driven
in short steps: ``--budget-sec`` stops cleanly and the next run continues.

    python3 scripts/knowledge/extract_hud_crops.py --video ID=/path/match.mp4 \
        --out /private/crops --step 5 --budget-sec 150

Python 3.10+ standard library, NumPy, OpenCV and ffmpeg on PATH.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import time
import zipfile
from pathlib import Path

import cv2
import numpy as np

WIDTH, HEIGHT = 1920, 1080
# x0, y0, x1, y1 in 1920x1080 pixels; scale applied before PNG encoding.
REGIONS = {
    "abilities": ((745, 975, 1175, 1062), 1.0),
    "top_bar": ((385, 0, 1540, 100), 0.5),
    "ammo": ((1255, 990, 1420, 1062), 1.0),
    "weapon_inventory": ((1670, 600, 1918, 1015), 0.5),
    "kill_feed": ((1440, 45, 1918, 188), 0.75),
}


def probe(path: Path) -> dict[str, object]:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=width,height,avg_frame_rate:format=duration", "-of", "json", str(path)],
        check=True, capture_output=True, text=True, encoding="utf-8",
    ).stdout
    data = json.loads(out)
    stream = data["streams"][0]
    return {
        "width": int(stream["width"]),
        "height": int(stream["height"]),
        "fps": stream["avg_frame_rate"],
        "duration_sec": float(data["format"]["duration"]),
    }


def frame_at(path: Path, sec: float) -> np.ndarray | None:
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-ss", f"{sec:.3f}", "-i", str(path), "-frames:v", "1",
         "-f", "rawvideo", "-pix_fmt", "bgr24", "-"],
        capture_output=True,
    ).stdout
    if len(raw) != WIDTH * HEIGHT * 3:
        return None
    return np.frombuffer(raw, np.uint8).reshape(HEIGHT, WIDTH, 3)


def crops(frame: np.ndarray) -> dict[str, bytes]:
    result = {}
    for name, ((x0, y0, x1, y1), scale) in REGIONS.items():
        crop = frame[y0:y1, x0:x1]
        if scale != 1.0:
            crop = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        ok, encoded = cv2.imencode(".jpg", crop, [cv2.IMWRITE_JPEG_QUALITY, 92])
        if ok:
            result[name] = encoded.tobytes()
    return result


def run(video_id: str, path: Path, out: Path, step: float, deadline: float) -> str:
    final = out / f"{video_id}.zip"
    if final.exists():
        return "done"
    partial = out / f"{video_id}.partial"
    partial.mkdir(parents=True, exist_ok=True)
    meta_path = partial / "meta.json"
    if meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    else:
        stat = path.stat()
        meta = {
            "video_id": video_id,
            "file_name": path.name,
            "size_bytes": stat.st_size,
            "mtime": int(stat.st_mtime),
            **probe(path),
            "step_sec": step,
            "regions": {k: {"box": v[0], "scale": v[1]} for k, v in REGIONS.items()},
            "samples": [],
        }
    if (meta["width"], meta["height"]) != (WIDTH, HEIGHT):
        raise SystemExit(f"{video_id}: only 1920x1080 is supported")
    done = {s["sec"] for s in meta["samples"]}
    sec = 0.0
    while sec < float(meta["duration_sec"]) - 1:
        if time.time() > deadline:
            meta_path.write_text(json.dumps(meta), encoding="utf-8")
            return "partial"
        key = round(sec, 3)
        if key not in done:
            frame = frame_at(path, sec)
            sample = {"sec": key, "ok": frame is not None}
            if frame is not None:
                for name, data in crops(frame).items():
                    (partial / name).mkdir(exist_ok=True)
                    (partial / name / f"{key:.1f}.jpg").write_bytes(data)
            meta["samples"].append(sample)
        sec += step
    meta_path.write_text(json.dumps(meta), encoding="utf-8")
    with zipfile.ZipFile(final.with_suffix(".tmp"), "w", zipfile.ZIP_STORED) as archive:
        archive.writestr("index.json", json.dumps(meta))
        for file in sorted(p for p in partial.rglob("*") if p.suffix in {".png", ".jpg"}):
            archive.write(file, file.relative_to(partial).as_posix())
    final.with_suffix(".tmp").rename(final)
    return "done"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", action="append", required=True, help="ID=/path/video.mp4")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--step", type=float, default=5.0)
    parser.add_argument("--budget-sec", type=float, default=150.0)
    args = parser.parse_args()
    deadline = time.time() + args.budget_sec
    args.out.mkdir(parents=True, exist_ok=True)
    for item in args.video:
        video_id, path = item.split("=", 1)
        status = run(video_id, Path(path), args.out, args.step, deadline)
        print(video_id, status, flush=True)
        if status == "partial":
            break
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
